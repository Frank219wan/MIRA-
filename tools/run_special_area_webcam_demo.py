"""Track a user-selected Special Area polygon in the local webcam preview."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import cv2
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.face_landmarker import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    FaceLandmarkerDetector,
    FaceLandmarkerError,
    read_image,
)
from src.special_area_profile import (  # noqa: E402
    SpecialAreaProfileError,
    validate_special_area_profile,
)
from src.special_area_tracking import (  # noqa: E402
    TRACKING_ACTIVE,
    SpecialAreaLiveSession,
    SpecialAreaLiveSessionError,
    SpecialAreaTrackingError,
    assert_current_live_session,
    build_live_session,
    build_tracking_binding,
    mark_face_lost,
    normalized_to_display_pixel,
    save_live_session_json,
    update_live_session,
)


WINDOW_TITLE = "MIRA — Special Area Live"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "special_area_live"
LIVE_GUIDANCE = {
    "KEEP": (
        "Keep visible",
        "Avoid heavy coverage",
        "Blend edges only",
    ),
    "BLEND": (
        "Light blending",
        "Reduce contrast",
        "Do not fully cover",
    ),
    "COVER": (
        "Apply locally",
        "Build coverage gradually",
        "Blend edges",
    ),
    "HIGHLIGHT": (
        "Keep visible",
        "Avoid high coverage",
        "Integrate with the overall look",
    ),
}
PREFERENCE_COLORS = {
    "KEEP": (90, 220, 120),
    "BLEND": (80, 220, 255),
    "COVER": (255, 130, 80),
    "HIGHLIGHT": (220, 120, 240),
}


class SpecialAreaWebcamRuntimeError(RuntimeError):
    """Raised for local image, profile, or camera runtime failures."""


def _load_profile(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise SpecialAreaWebcamRuntimeError(f"Profile does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SpecialAreaWebcamRuntimeError(
            f"Could not read strict JSON profile: {path.name}"
        ) from exc
    return validate_special_area_profile(payload)


def _draw_text_lines(canvas: Any, lines: Sequence[str]) -> None:
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


def _landmark_xy(landmark: Any) -> tuple[float, float]:
    if isinstance(landmark, Mapping):
        return float(landmark["x"]), float(landmark["y"])
    return float(landmark.x), float(landmark.y)


def _debug_anchor_indices(session: SpecialAreaLiveSession) -> set[int]:
    return {
        index
        for area in session.tracking_binding["areas"]
        for point in area["points"]
        for index in point["landmark_indices"]
    }


def render_special_area_live(
    raw_frame: Any,
    session: SpecialAreaLiveSession,
    *,
    live_landmarks: Sequence[Any] | None,
    mirrored_preview: bool = True,
    debug_enabled: bool = False,
    guidance_visible: bool = True,
    controls_text: str = "Q quit | S save JSON | D debug | P guidance",
    notice_text: str = "",
) -> Any:
    """Render raw-coordinate tracking after applying the display mirror only."""

    assert_current_live_session(session)
    if raw_frame is None or not hasattr(raw_frame, "size") or raw_frame.size == 0:
        raise SpecialAreaWebcamRuntimeError("Camera frame is empty.")
    canvas = cv2.flip(raw_frame, 1) if mirrored_preview else raw_frame.copy()
    height, width = canvas.shape[:2]

    if session.tracking_status == TRACKING_ACTIVE:
        overlay = canvas.copy()
        prepared = []
        for area in session.current_live_areas:
            pixels = np.asarray(
                [
                    normalized_to_display_pixel(
                        point,
                        width=width,
                        height=height,
                        mirrored_preview=mirrored_preview,
                    )
                    for point in area["polygon"]
                ],
                dtype=np.int32,
            )
            color = PREFERENCE_COLORS[area["preference"]]
            cv2.fillPoly(overlay, [pixels], color)
            prepared.append((area, pixels, color))
        canvas = cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0.0)
        for area, pixels, color in prepared:
            cv2.polylines(canvas, [pixels], True, color, 3, cv2.LINE_AA)
            label = f"{area['user_label'] or area['area_id']} | {area['preference']}"
            x = max(0, int(pixels[:, 0].min()))
            y = max(24, int(pixels[:, 1].min()) - 8)
            cv2.putText(
                canvas,
                label,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

    if debug_enabled and live_landmarks is not None:
        for landmark_index in _debug_anchor_indices(session):
            x_norm, y_norm = _landmark_xy(live_landmarks[landmark_index])
            pixel = normalized_to_display_pixel(
                {"x_norm": x_norm, "y_norm": y_norm},
                width=width,
                height=height,
                mirrored_preview=mirrored_preview,
            )
            cv2.circle(canvas, pixel, 3, (0, 255, 255), -1, cv2.LINE_AA)

    first_area = session.tracking_binding["areas"][0]
    lines = [
        "SPECIAL AREA LIVE",
        f"Session: {session.session_id[:8]}",
        f"Label: {first_area['user_label'] or '(none)'}",
        f"Location: {first_area['location']}",
        f"Preference: {first_area['preference']}",
        f"Tracking: {session.tracking_status.replace('_', ' ')}",
    ]
    if guidance_visible:
        lines.extend(LIVE_GUIDANCE[first_area["preference"]])
    if notice_text:
        lines.append(notice_text)
    lines.append(controls_text)
    _draw_text_lines(canvas, lines)
    return canvas


def run_live_tracking(
    capture: Any,
    detector: FaceLandmarkerDetector,
    *,
    session: SpecialAreaLiveSession,
    output_dir: Path,
) -> None:
    """Run face tracking in raw frames and mirror only the user preview."""

    debug_enabled = False
    guidance_visible = True
    consecutive_read_failures = 0
    while True:
        ok, raw_frame = capture.read()
        if not ok or raw_frame is None or raw_frame.size == 0:
            consecutive_read_failures += 1
            if consecutive_read_failures >= 10:
                raise SpecialAreaWebcamRuntimeError(
                    "Camera stopped returning frames during live tracking."
                )
            continue
        consecutive_read_failures = 0
        live_landmarks = None
        try:
            # Geometry always uses the raw, unmirrored frame.
            live_landmarks = detector.detect(raw_frame)
            update_live_session(session, live_landmarks)
        except (FaceLandmarkerError, SpecialAreaTrackingError):
            mark_face_lost(session)
            live_landmarks = None

        display = render_special_area_live(
            raw_frame,
            session,
            live_landmarks=live_landmarks,
            mirrored_preview=True,
            debug_enabled=debug_enabled,
            guidance_visible=guidance_visible,
        )
        cv2.imshow(WINDOW_TITLE, display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("d"), ord("D")):
            debug_enabled = not debug_enabled
        elif key in (ord("p"), ord("P")):
            guidance_visible = not guidance_visible
        elif key in (ord("s"), ord("S")):
            path = save_live_session_json(
                output_dir / "special_area_live_session.json", session
            )
            print(f"Saved JSON session metadata: {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capture = None
    try:
        source_image = read_image(args.image)
        profile = _load_profile(args.profile)
        if profile["image_sample_id"] != args.image.stem:
            raise SpecialAreaWebcamRuntimeError(
                "Profile image_sample_id does not match the static image."
            )
        with FaceLandmarkerDetector(model_path=args.model, max_faces=1) as detector:
            source_landmarks = detector.detect(source_image)
            binding = build_tracking_binding(profile, source_landmarks)
            session = build_live_session(
                profile,
                binding,
                source_image_identifier=args.image.stem,
            )
            capture = cv2.VideoCapture(args.camera)
            if not capture.isOpened():
                raise SpecialAreaWebcamRuntimeError(
                    "Could not open the camera. Check macOS Camera permission for "
                    "Terminal/Python."
                )
            first_area = profile["areas"][0]
            print("Special Area tracking binding ready.")
            print(f"Session ID: {session.session_id}")
            print(f"Label: {first_area['user_label'] or '(none)'}")
            print(f"Location: {first_area['location']}")
            print(f"Preference: {first_area['preference']}")
            print("LIVE — Q quit | S save JSON | D debug | P guidance")
            run_live_tracking(
                capture,
                detector,
                session=session,
                output_dir=args.output,
            )
    except KeyboardInterrupt:
        print("Special Area Live Tracking canceled.")
        return 0
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        FaceLandmarkerError,
        SpecialAreaProfileError,
        SpecialAreaTrackingError,
        SpecialAreaLiveSessionError,
        SpecialAreaWebcamRuntimeError,
    ) as exc:
        print(f"Special Area Live Tracking failed: {exc}", file=sys.stderr)
        return 1
    finally:
        if capture is not None:
            capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
