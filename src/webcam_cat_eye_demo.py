"""Testable integration helpers for the local MIRA Cat Eye webcam demo."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np

from .ar_guidance import build_a02_guidance, build_a04_guidance
from .eye_landmarks import (
    build_face_geometry_payload,
    extract_brow_landmarks,
    extract_eye_landmarks,
    extract_rule_landmarks,
)
from .eye_local_profile import mediapipe_keypoints
from .face_profile import build_face_profile
from .face_scan_aggregator import FaceScanAggregator
from .personalization_engine import save_json_output
from .reference_package import (
    package_existing_reference,
    personalize_reference_package,
    reference_a04_parameters,
)


OVERLAY_MODES = frozenset(("personalized", "reference", "both"))
SUBJECT_SIDES = frozenset(("left", "right"))
REFERENCE_COLOR = (0, 210, 255)
PERSONALIZED_COLOR = (255, 80, 220)


class WebcamCatEyeDemoError(ValueError):
    """Raised when scan, personalization, or overlay inputs are invalid."""


class WebcamSessionStateError(RuntimeError):
    """Raised when live UI, guidance, and save state come from different sessions."""


@dataclass(frozen=True)
class WebcamDemoSession:
    """One scan-to-live lifecycle; output files are never a state source."""

    session_id: str
    stable_profile_hash: str
    stable_face_profile: Mapping[str, Any]
    reference_package: Mapping[str, Any]
    personalization: Mapping[str, Any]
    session_summary: Mapping[str, Any]
    overlay_summary: Mapping[str, Any]
    subject_side: str


def face_profile_from_landmarks(
    face_landmarks: Sequence[Any],
    *,
    image_width: int,
    image_height: int,
    frame_id: str,
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    """Reuse the existing v0.3 geometry/Profile pipeline without disk I/O."""

    eyes = extract_eye_landmarks(face_landmarks, input_is_mirrored)
    brows = extract_brow_landmarks(face_landmarks, input_is_mirrored)
    rules = extract_rule_landmarks(face_landmarks, input_is_mirrored)
    geometry = build_face_geometry_payload(
        eyes,
        image_width=image_width,
        image_height=image_height,
        input_is_mirrored=input_is_mirrored,
        brows=brows,
        rule_landmarks=rules,
    )
    return build_face_profile(
        geometry,
        raw_geometry_source=f"webcam_{frame_id}",
    )


def stable_scan_from_profiles(
    profiles: Sequence[Mapping[str, Any]],
    *,
    min_valid_frames: int = 3,
) -> dict[str, Any]:
    """Feed saved/in-memory profiles through the existing median aggregator."""

    aggregator = FaceScanAggregator(min_valid_frames=min_valid_frames)
    for index, profile in enumerate(profiles, start=1):
        aggregator.add_profile(profile, frame_id=f"webcam_{index:04d}")
    return aggregator.finalize()


def ar_landmarks_from_face_landmarks(
    face_landmarks: Sequence[Any],
    *,
    image_width: int,
    image_height: int,
    subject_side: str = "right",
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    """Adapt MediaPipe landmarks to normalized, subject-relative AR points."""

    if subject_side not in SUBJECT_SIDES:
        raise WebcamCatEyeDemoError(
            f"subject_side must be one of {sorted(SUBJECT_SIDES)}."
        )
    if image_width <= 1 or image_height <= 1:
        raise WebcamCatEyeDemoError("Image dimensions must exceed one pixel.")
    keypoints = mediapipe_keypoints(
        face_landmarks,
        image_width=image_width,
        image_height=image_height,
        subject_side=subject_side,
        input_is_mirrored=input_is_mirrored,
    )

    def normalized(point: Any) -> dict[str, float]:
        x = float(point.x) / (image_width - 1)
        y = float(point.y) / (image_height - 1)
        if not all(math.isfinite(value) for value in (x, y)):
            raise WebcamCatEyeDemoError("AR landmark contains NaN or infinity.")
        return {"x_norm": x, "y_norm": y}

    lower_lid = keypoints.lower_lid_points
    if lower_lid is None or len(lower_lid) < 2:
        raise WebcamCatEyeDemoError("Lower-lid landmarks are unavailable.")
    return {
        "side": subject_side,
        "side_semantics": f"subject_{subject_side}",
        "input_is_mirrored": input_is_mirrored,
        "eye_inner": normalized(keypoints.eye_inner),
        "eye_outer": normalized(keypoints.eye_outer),
        "lower_lid_path": [normalized(point) for point in lower_lid],
    }


def personalize_stable_profile(
    stable_face_profile: Mapping[str, Any],
    reference_fixture: Mapping[str, Any],
    *,
    sample_id: str = "webcam_user",
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use the existing Main Demo reference and validated personalization."""

    package = package_existing_reference(reference_fixture)
    personalization = personalize_reference_package(
        package,
        stable_face_profile,
        sample_id=sample_id,
    )
    return package, personalization


def _stable_profile_hash(profile: Mapping[str, Any]) -> str:
    try:
        encoded = json.dumps(
            profile,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise WebcamCatEyeDemoError(
            "Stable Face Profile must be strict JSON."
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def build_live_overlay_summary(
    personalization: Mapping[str, Any],
    reference_package: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the single numeric/text source shared by terminal and live UI."""

    reference_a04 = reference_a04_parameters(reference_package)
    a04 = personalization["A04"]
    a02 = personalization["A02"]
    rules = list(personalization["triggered_rules"])
    return {
        "direction_ref_deg": reference_a04[
            "direction_relative_to_eye_axis_deg"
        ],
        "direction_mine_deg": a04["direction"][
            "personalized_direction_deg"
        ],
        "extension_ref_ratio": reference_a04["reference_extension_ratio"],
        "extension_mine_ratio": a04["extension"][
            "personalized_extension_ratio"
        ],
        "a02_range_factor": a02["personalized_range_factor"],
        "a02_intensity_factor": a02["personalized_intensity_factor"],
        "rules": rules,
        "decision": "ADAPT" if rules else "KEEP_REFERENCE",
    }


def _session_mismatch(detail: str) -> WebcamSessionStateError:
    return WebcamSessionStateError(
        "live overlay state does not match current personalization session: "
        + detail
    )


def assert_current_session(
    session: WebcamDemoSession,
    guidance: Mapping[str, Any] | None = None,
) -> None:
    """Fail closed if profile, personalization, UI, AR, or save state diverges."""

    if not session.session_id:
        raise _session_mismatch("session_id is empty")
    if _stable_profile_hash(session.stable_face_profile) != session.stable_profile_hash:
        raise _session_mismatch("Stable Face Profile hash changed")

    expected_overlay = build_live_overlay_summary(
        session.personalization, session.reference_package
    )
    if dict(session.overlay_summary) != expected_overlay:
        raise _session_mismatch("overlay summary is stale")

    identity = session.session_summary.get("session")
    if not isinstance(identity, Mapping):
        raise _session_mismatch("session summary identity is missing")
    if identity.get("session_id") != session.session_id:
        raise _session_mismatch("session summary uses another session_id")
    if identity.get("stable_profile_hash") != session.stable_profile_hash:
        raise _session_mismatch("session summary uses another profile hash")
    if session.session_summary.get("triggered_rules") != expected_overlay["rules"]:
        raise _session_mismatch("session summary rules are stale")
    if session.session_summary.get("decision") != expected_overlay["decision"]:
        raise _session_mismatch("session summary decision is stale")
    try:
        tutorial = session.session_summary["tutorial"]
        summary_checks = (
            (
                tutorial["A04"]["direction_deg"],
                expected_overlay["direction_mine_deg"],
                "session summary A04 direction",
            ),
            (
                tutorial["A04"]["extension_percent_of_eye_width"],
                round(expected_overlay["extension_mine_ratio"] * 100, 3),
                "session summary A04 extension",
            ),
            (
                tutorial["A02"]["range_factor"],
                expected_overlay["a02_range_factor"],
                "session summary A02 range",
            ),
            (
                tutorial["A02"]["intensity_factor"],
                expected_overlay["a02_intensity_factor"],
                "session summary A02 intensity",
            ),
        )
    except (KeyError, TypeError) as exc:
        raise _session_mismatch("session summary structure is invalid") from exc
    for actual, expected, label in summary_checks:
        if not math.isclose(
            float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12
        ):
            raise _session_mismatch(f"{label} is stale")

    if guidance is None:
        return
    if guidance.get("session_id") != session.session_id:
        raise _session_mismatch("AR guidance uses another session_id")
    try:
        checks = (
            (
                guidance["reference"]["A04"][
                    "direction_relative_to_eye_axis_deg"
                ],
                expected_overlay["direction_ref_deg"],
                "reference A04 direction",
            ),
            (
                guidance["personalized"]["A04"][
                    "direction_relative_to_eye_axis_deg"
                ],
                expected_overlay["direction_mine_deg"],
                "personalized A04 direction",
            ),
            (
                guidance["reference"]["A04"]["extension_ratio"],
                expected_overlay["extension_ref_ratio"],
                "reference A04 extension",
            ),
            (
                guidance["personalized"]["A04"]["extension_ratio"],
                expected_overlay["extension_mine_ratio"],
                "personalized A04 extension",
            ),
            (
                guidance["personalized"]["A02"]["range_factor"],
                expected_overlay["a02_range_factor"],
                "personalized A02 range",
            ),
            (
                guidance["personalized"]["A02"]["intensity_factor"],
                expected_overlay["a02_intensity_factor"],
                "personalized A02 intensity",
            ),
        )
    except (KeyError, TypeError) as exc:
        raise _session_mismatch("AR guidance structure is invalid") from exc
    for actual, expected, label in checks:
        if not math.isclose(
            float(actual), float(expected), rel_tol=0.0, abs_tol=1e-12
        ):
            raise _session_mismatch(f"{label} is stale")


def build_live_guidance(
    ar_landmarks: Mapping[str, Any],
    reference_package: Mapping[str, Any],
    personalization: Mapping[str, Any],
) -> dict[str, Any]:
    """Build reference and personalized A04/A02 geometry for one live frame."""

    side = ar_landmarks.get("side")
    if side not in SUBJECT_SIDES:
        raise WebcamCatEyeDemoError("AR landmarks require subject side semantics.")
    reference_a04 = reference_a04_parameters(reference_package)
    reference_a02 = {
        "range_factor": personalization["A02"]["reference_range_factor"],
        "intensity_factor": personalization["A02"][
            "reference_intensity_factor"
        ],
    }
    return {
        "schema_version": "0.1",
        "side": f"subject_{side}",
        "reference": {
            "A04": build_a04_guidance(
                ar_landmarks,
                reference_a04,
                side,
                source="blogger_reference_action",
            ),
            "A02": build_a02_guidance(
                ar_landmarks,
                reference_a02,
                side,
                source="blogger_reference_action",
            ),
        },
        "personalized": {
            "A04": build_a04_guidance(
                ar_landmarks,
                personalization["A04"],
                side,
                source="personalized_action",
            ),
            "A02": build_a02_guidance(
                ar_landmarks,
                personalization["A02"],
                side,
                source="personalized_action",
            ),
        },
    }


def build_session_live_guidance(
    ar_landmarks: Mapping[str, Any],
    session: WebcamDemoSession,
) -> dict[str, Any]:
    """Build live geometry only from the current session and verify it."""

    assert_current_session(session)
    guidance = build_live_guidance(
        ar_landmarks,
        session.reference_package,
        session.personalization,
    )
    guidance["session_id"] = session.session_id
    assert_current_session(session, guidance)
    return guidance


def guidance_layers(
    guidance: Mapping[str, Any], mode: str
) -> list[tuple[str, Mapping[str, Any]]]:
    """Select overlay layers without changing their geometry."""

    if mode not in OVERLAY_MODES:
        raise WebcamCatEyeDemoError(
            f"mode must be one of {sorted(OVERLAY_MODES)}."
        )
    if mode == "both":
        names = ("reference", "personalized")
    else:
        names = (mode,)
    return [(name, guidance[name]) for name in names]


def preview_pixel(
    point: Mapping[str, Any],
    *,
    width: int,
    height: int,
    mirrored_preview: bool,
) -> tuple[int, int]:
    """Map raw normalized geometry to display pixels without swapping eyes."""

    x = float(point["x_norm"])
    y = float(point["y_norm"])
    if mirrored_preview:
        x = 1.0 - x
    return round(x * (width - 1)), round(y * (height - 1))


def build_live_overlay_lines(
    session: WebcamDemoSession,
    guidance: Mapping[str, Any],
    *,
    mode: str,
) -> tuple[str, ...]:
    """Format live text from the verified current-session summary."""

    guidance_layers(guidance, mode)
    assert_current_session(session, guidance)
    values = session.overlay_summary
    rules = values["rules"]
    return (
        "MIRA - My Cat Eye",
        mode.upper(),
        f"Session: {session.session_id[:8]}",
        f"Side: {guidance['side']}",
        "Direction: "
        f"Ref {values['direction_ref_deg']:.2f} deg  "
        f"Mine {values['direction_mine_deg']:.2f} deg",
        "Extension: "
        f"Ref {values['extension_ref_ratio'] * 100:.1f}%  "
        f"Mine {values['extension_mine_ratio'] * 100:.1f}%",
        "Rules: " + (" / ".join(rules) if rules else "KEEP_REFERENCE"),
        "P personalized | R reference | B both | S save JSON | Q quit",
    )


def render_live_guidance(
    raw_frame: Any,
    guidance: Mapping[str, Any],
    session: WebcamDemoSession,
    *,
    mode: str,
    mirrored_preview: bool = True,
) -> Any:
    """Render selected guidance layers; all geometry stays in raw-frame space."""

    if raw_frame is None or raw_frame.size == 0:
        raise WebcamCatEyeDemoError("Camera frame is empty.")
    lines = build_live_overlay_lines(session, guidance, mode=mode)
    canvas = cv2.flip(raw_frame, 1) if mirrored_preview else raw_frame.copy()
    height, width = canvas.shape[:2]
    layers = guidance_layers(guidance, mode)

    for name, actions in layers:
        color = REFERENCE_COLOR if name == "reference" else PERSONALIZED_COLOR
        polygon = np.array(
            [
                preview_pixel(
                    point,
                    width=width,
                    height=height,
                    mirrored_preview=mirrored_preview,
                )
                for point in actions["A02"]["polygon"]
            ],
            dtype=np.int32,
        )
        overlay = canvas.copy()
        cv2.fillPoly(overlay, [polygon], color)
        canvas = cv2.addWeighted(overlay, 0.22, canvas, 0.78, 0.0)

    for name, actions in layers:
        color = REFERENCE_COLOR if name == "reference" else PERSONALIZED_COLOR
        a04 = actions["A04"]
        anchor = preview_pixel(
            a04["anchor"],
            width=width,
            height=height,
            mirrored_preview=mirrored_preview,
        )
        endpoint = preview_pixel(
            a04["endpoint"],
            width=width,
            height=height,
            mirrored_preview=mirrored_preview,
        )
        cv2.arrowedLine(canvas, anchor, endpoint, color, 3, tipLength=0.2)
        cv2.circle(canvas, anchor, 4, color, -1)

    for index, line in enumerate(lines):
        y = 28 + index * 24
        cv2.putText(
            canvas,
            line,
            (14, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (0, 0, 0),
            3,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            line,
            (14, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    return canvas


def build_session_summary(
    personalization: Mapping[str, Any],
    *,
    reference_id: str,
    subject_side: str,
    valid_frame_count: int,
    target_frame_count: int,
    session_id: str | None = None,
    stable_profile_hash: str | None = None,
) -> dict[str, Any]:
    """Create neutral geometric explanations and a readable tutorial."""

    decisions = personalization["feature_decisions"]
    direction_decision = decisions["eye_tail_angle.mean"]
    extension_decision = decisions["relative_eye_length.mean"]
    lower_decision = decisions["lower_lid_space_ratio.mean"]
    a04 = personalization["A04"]
    a02 = personalization["A02"]
    overall = "ADAPT" if personalization["triggered_rules"] else "KEEP_REFERENCE"

    def operation_change(
        label: str,
        reference: float,
        personalized: float,
        *,
        unit: str = "",
    ) -> str:
        delta = personalized - reference
        if delta > 0:
            verb = "increases"
        elif delta < 0:
            verb = "decreases"
        else:
            return f"{label} remains at the reference value"
        return f"{label} {verb} by {abs(delta):.6f}{unit}"

    def why(decision: Mapping[str, Any], change: str) -> str:
        difference = float(decision["difference"])
        if decision["decision"] == "KEEP_REFERENCE":
            return (
                "Keep Reference — signed geometric difference "
                f"{difference:+.6f} is inside the validation dead zone."
            )
        return (
            f"Signed geometric difference {difference:+.6f} is outside the "
            f"validation dead zone, so {change}."
        )

    tutorial = {
        "title": "MY CAT EYE TUTORIAL",
        "A04": {
            "title": "STEP A04 — CAT EYE LINER",
            "where": "Start at the on-screen anchor on your current eye axis.",
            "how": "Follow the guidance line outward to its arrow endpoint.",
            "direction_deg": a04["direction"]["personalized_direction_deg"],
            "extension_percent_of_eye_width": round(
                a04["extension"]["personalized_extension_ratio"] * 100, 3
            ),
            "direction_why": why(
                direction_decision,
                operation_change(
                    "the liner direction",
                    a04["direction"]["reference_direction_deg"],
                    a04["direction"]["personalized_direction_deg"],
                    unit=" deg",
                ),
            ),
            "extension_why": why(
                extension_decision,
                operation_change(
                    "the liner extension",
                    a04["extension"]["reference_extension_ratio"] * 100,
                    a04["extension"]["personalized_extension_ratio"] * 100,
                    unit=" percentage points of eye width",
                ),
            ),
        },
        "A02": {
            "title": "STEP A02 — LOWER LID",
            "range_factor": a02["personalized_range_factor"],
            "intensity_factor": a02["personalized_intensity_factor"],
            "how": "Apply only within the on-screen lower-lid target region.",
            "why": why(
                lower_decision,
                operation_change(
                    "the lower-lid range factor",
                    a02["reference_range_factor"],
                    a02["personalized_range_factor"],
                )
                + ", and "
                + operation_change(
                    "the intensity factor",
                    a02["reference_intensity_factor"],
                    a02["personalized_intensity_factor"],
                ),
            ),
        },
    }
    return {
        "schema_version": "0.1",
        "session": {
            "session_id": session_id,
            "stable_profile_hash": stable_profile_hash,
        },
        "reference_id": reference_id,
        "subject_side": f"subject_{subject_side}",
        "scan": {
            "valid_frame_count": valid_frame_count,
            "target_frame_count": target_frame_count,
        },
        "decision": overall,
        "triggered_rules": list(personalization["triggered_rules"]),
        "comparison": {
            feature: {
                "reference": value["blogger"],
                "user": value["user"],
                "signed_difference": value["difference"],
                "inside_dead_zone": value["inside_dead_zone"],
                "triggered_rule": value["triggered_rule"],
            }
            for feature, value in decisions.items()
        },
        "tutorial": tutorial,
    }


def build_webcam_session(
    stable_face_profile: Mapping[str, Any],
    reference_fixture: Mapping[str, Any],
    *,
    subject_side: str,
    valid_frame_count: int,
    target_frame_count: int,
    session_id: str | None = None,
    sample_id: str = "webcam_user",
) -> WebcamDemoSession:
    """Create a fresh isolated scan-to-live session with no output-file reads."""

    if subject_side not in SUBJECT_SIDES:
        raise WebcamCatEyeDemoError(
            f"subject_side must be one of {sorted(SUBJECT_SIDES)}."
        )
    current_id = session_id or uuid.uuid4().hex
    if not isinstance(current_id, str) or not current_id.strip():
        raise WebcamCatEyeDemoError("session_id must be a non-empty string.")

    profile = copy.deepcopy(dict(stable_face_profile))
    profile_hash = _stable_profile_hash(profile)
    package, personalization = personalize_stable_profile(
        profile,
        reference_fixture,
        sample_id=sample_id,
    )
    package = copy.deepcopy(package)
    personalization = copy.deepcopy(personalization)
    overlay = build_live_overlay_summary(personalization, package)
    summary = build_session_summary(
        personalization,
        reference_id=str(reference_fixture["reference_id"]),
        subject_side=subject_side,
        valid_frame_count=valid_frame_count,
        target_frame_count=target_frame_count,
        session_id=current_id,
        stable_profile_hash=profile_hash,
    )
    session = WebcamDemoSession(
        session_id=current_id,
        stable_profile_hash=profile_hash,
        stable_face_profile=profile,
        reference_package=package,
        personalization=personalization,
        session_summary=summary,
        overlay_summary=overlay,
        subject_side=subject_side,
    )
    assert_current_session(session)
    return session


def format_terminal_summary(
    session: WebcamDemoSession,
) -> str:
    """Format the concise terminal report shown after the one-time scan."""

    assert_current_session(session)
    session_summary = session.session_summary
    overlay = session.overlay_summary
    comparisons = session_summary["comparison"]
    tutorial_a04 = session_summary["tutorial"]["A04"]
    tutorial_a02 = session_summary["tutorial"]["A02"]
    lines = [
        "================================",
        "MIRA MY CAT EYE",
        "================================",
        f"Session ID: {session.session_id}",
        f"Stable Profile SHA-256: {session.stable_profile_hash}",
        "Your Face vs Reference",
    ]
    for feature in (
        "eye_tail_angle.mean",
        "relative_eye_length.mean",
        "lower_lid_space_ratio.mean",
    ):
        value = comparisons[feature]
        lines.extend(
            (
                "",
                f"{feature}:",
                f"Reference: {value['reference']}",
                f"You: {value['user']}",
                f"Difference: {value['signed_difference']:+.6f}",
            )
        )
    lines.extend(
        (
            "",
            "Triggered Rules:",
            str(session_summary["triggered_rules"]),
            "",
            "A04 EYELINER",
            "Reference direction: "
            f"{overlay['direction_ref_deg']:.6f} deg",
            "Your direction: "
            f"{overlay['direction_mine_deg']:.6f} deg",
            "Reference extension: "
            f"{overlay['extension_ref_ratio']:.12f}",
            "Your extension: "
            f"{overlay['extension_mine_ratio']:.12f}",
            "",
            "A02 LOWER LID",
            f"Range: {overlay['a02_range_factor']:.12f}",
            f"Intensity: {overlay['a02_intensity_factor']:.12f}",
            "",
            f"Decision: {session_summary['decision']}",
            "================================",
            "",
            session_summary["tutorial"]["title"],
            tutorial_a04["title"],
            "Where: " + tutorial_a04["where"],
            tutorial_a04["how"],
            "Direction: "
            f"{tutorial_a04['direction_deg']:.6f} deg ",
            "Extension: "
            f"{tutorial_a04['extension_percent_of_eye_width']:.3f}% "
            "of current eye width",
            tutorial_a04["direction_why"],
            tutorial_a04["extension_why"],
            "",
            tutorial_a02["title"],
            tutorial_a02["how"],
            f"Range factor: {tutorial_a02['range_factor']:.12f}",
            f"Intensity factor: {tutorial_a02['intensity_factor']:.12f}",
            tutorial_a02["why"],
        )
    )
    return "\n".join(lines)


def save_session_results(
    output_dir: Path | str,
    *,
    session: WebcamDemoSession,
    guidance_snapshot: Mapping[str, Any],
) -> tuple[Path, ...]:
    """Save JSON only; no raw frame or webcam video is persisted."""

    assert_current_session(session, guidance_snapshot)
    output = Path(output_dir)
    files = (
        ("stable_face_profile.json", session.stable_face_profile),
        ("personalization.json", session.personalization),
        ("ar_guidance_snapshot.json", guidance_snapshot),
        ("session_summary.json", session.session_summary),
    )
    paths = []
    for filename, value in files:
        path = output / filename
        save_json_output(path, value)
        paths.append(path)
    return tuple(paths)
