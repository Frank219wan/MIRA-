"""Landmark-local tracking for user-selected Special Area polygons.

The source profile remains the authority for what the user selected.  This
module only records how each polygon point is attached to face geometry and
reprojects that attachment onto a new set of landmarks.
"""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .special_area_profile import (
    VALID_LOCATIONS,
    VALID_PREFERENCES,
    save_strict_json,
    validate_special_area_profile,
)


TRACKING_SCHEMA_VERSION = "0.1"
DEFAULT_NEIGHBOR_COUNT = 10
DEFAULT_TRIANGLE_AREA_EPSILON = 1e-8
WEIGHT_TOLERANCE = 1e-6
TRACKING_ACTIVE = "ACTIVE"
TRACKING_FACE_LOST = "FACE_LOST"


class SpecialAreaTrackingError(ValueError):
    """Raised when a safe landmark binding or reprojection cannot be built."""


class SpecialAreaLiveSessionError(RuntimeError):
    """Raised when a profile, binding, or live session is stale or mismatched."""


@dataclass
class SpecialAreaLiveSession:
    """One static-profile-to-live lifecycle with no image persistence."""

    session_id: str
    source_image_identifier: str
    source_profile_hash: str
    source_profile: dict[str, Any]
    tracking_binding: dict[str, Any]
    tracking_status: str = TRACKING_FACE_LOST
    current_live_areas: list[dict[str, Any]] = field(default_factory=list)
    frame_index: int = 0
    smoothing_enabled: bool = False
    smoothing_alpha: float | None = None


def special_area_profile_hash(profile: Mapping[str, Any]) -> str:
    """Return a stable SHA-256 over the validated SpecialAreaProfile."""

    validated = validate_special_area_profile(profile)
    try:
        encoded = json.dumps(
            validated,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise SpecialAreaTrackingError(
            "SpecialAreaProfile must be strict JSON."
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _number(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecialAreaTrackingError(f"{field_name} must be numeric.")
    result = float(value)
    if not math.isfinite(result):
        raise SpecialAreaTrackingError(f"{field_name} must be finite.")
    return result


def _landmark_xy(landmark: Any, index: int) -> tuple[float, float]:
    if isinstance(landmark, Mapping):
        if "x_norm" in landmark and "y_norm" in landmark:
            x, y = landmark["x_norm"], landmark["y_norm"]
        elif "x" in landmark and "y" in landmark:
            x, y = landmark["x"], landmark["y"]
        else:
            raise SpecialAreaTrackingError(
                f"landmarks[{index}] must contain x/y or x_norm/y_norm."
            )
    elif hasattr(landmark, "x") and hasattr(landmark, "y"):
        x, y = landmark.x, landmark.y
    elif (
        isinstance(landmark, Sequence)
        and not isinstance(landmark, (str, bytes))
        and len(landmark) >= 2
    ):
        x, y = landmark[0], landmark[1]
    else:
        raise SpecialAreaTrackingError(
            f"landmarks[{index}] must provide normalized x and y coordinates."
        )

    x_value = _number(x, f"landmarks[{index}].x")
    y_value = _number(y, f"landmarks[{index}].y")
    if not 0.0 <= x_value <= 1.0 or not 0.0 <= y_value <= 1.0:
        raise SpecialAreaTrackingError(
            f"landmarks[{index}] must be inside normalized image coordinates."
        )
    return x_value, y_value


def _normalized_landmarks(landmarks: Sequence[Any]) -> list[tuple[float, float]]:
    if not isinstance(landmarks, Sequence) or len(landmarks) < 3:
        raise SpecialAreaTrackingError("At least 3 face landmarks are required.")
    return [_landmark_xy(landmark, index) for index, landmark in enumerate(landmarks)]


def landmark_signature(landmarks: Sequence[Any]) -> str:
    """Return a path-free SHA-256 signature of normalized source geometry."""

    coordinates = _normalized_landmarks(landmarks)
    encoded = json.dumps(
        coordinates,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _triangle_area_twice(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))


def _barycentric_weights(
    point: tuple[float, float],
    triangle: tuple[
        tuple[float, float], tuple[float, float], tuple[float, float]
    ],
    *,
    area_epsilon: float,
) -> tuple[float, float, float]:
    a, b, c = triangle
    denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (
        a[1] - c[1]
    )
    if not math.isfinite(denominator) or abs(denominator) <= area_epsilon:
        raise SpecialAreaTrackingError("Landmark triangle is degenerate.")
    weight_a = (
        (b[1] - c[1]) * (point[0] - c[0])
        + (c[0] - b[0]) * (point[1] - c[1])
    ) / denominator
    weight_b = (
        (c[1] - a[1]) * (point[0] - c[0])
        + (a[0] - c[0]) * (point[1] - c[1])
    ) / denominator
    weight_c = 1.0 - weight_a - weight_b
    weights = (weight_a, weight_b, weight_c)
    if not all(math.isfinite(weight) for weight in weights):
        raise SpecialAreaTrackingError("Barycentric weights must be finite.")
    return weights


def _inside_triangle(weights: Sequence[float]) -> bool:
    return all(
        -WEIGHT_TOLERANCE <= weight <= 1.0 + WEIGHT_TOLERANCE
        for weight in weights
    )


def _clean_weights(weights: Sequence[float]) -> list[float]:
    cleaned = [min(1.0, max(0.0, float(weight))) for weight in weights]
    total = sum(cleaned)
    if not math.isfinite(total) or total <= 0.0:
        raise SpecialAreaTrackingError("Barycentric weights cannot be normalized.")
    normalized = [weight / total for weight in cleaned]
    if not math.isclose(sum(normalized), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise SpecialAreaTrackingError("Barycentric weights must sum to one.")
    return normalized


def bind_point_to_landmarks(
    point: Mapping[str, Any],
    landmarks: Sequence[Any],
    *,
    neighbor_count: int = DEFAULT_NEIGHBOR_COUNT,
    triangle_area_epsilon: float = DEFAULT_TRIANGLE_AREA_EPSILON,
) -> dict[str, Any]:
    """Bind one normalized point to a nearby, non-degenerate landmark triangle."""

    if set(point) != {"x_norm", "y_norm"}:
        raise SpecialAreaTrackingError(
            "A polygon point must contain only x_norm and y_norm."
        )
    point_xy = (
        _number(point["x_norm"], "point.x_norm"),
        _number(point["y_norm"], "point.y_norm"),
    )
    if not 0.0 <= point_xy[0] <= 1.0 or not 0.0 <= point_xy[1] <= 1.0:
        raise SpecialAreaTrackingError("Polygon point must be normalized to 0..1.")
    if isinstance(neighbor_count, bool) or not isinstance(neighbor_count, int):
        raise SpecialAreaTrackingError("neighbor_count must be an integer.")
    if neighbor_count < 3:
        raise SpecialAreaTrackingError("neighbor_count must be at least 3.")
    epsilon = _number(triangle_area_epsilon, "triangle_area_epsilon")
    if epsilon <= 0.0:
        raise SpecialAreaTrackingError("triangle_area_epsilon must be positive.")

    coordinates = _normalized_landmarks(landmarks)
    nearest = sorted(
        range(len(coordinates)),
        key=lambda index: (
            (coordinates[index][0] - point_xy[0]) ** 2
            + (coordinates[index][1] - point_xy[1]) ** 2,
            index,
        ),
    )[: min(neighbor_count, len(coordinates))]

    best: tuple[tuple[float, float, float], tuple[int, int, int], list[float]] | None = None
    for indices in itertools.combinations(nearest, 3):
        triangle = tuple(coordinates[index] for index in indices)
        area_twice = _triangle_area_twice(*triangle)
        if not math.isfinite(area_twice) or area_twice <= epsilon:
            continue
        try:
            weights = _barycentric_weights(
                point_xy,
                triangle,  # type: ignore[arg-type]
                area_epsilon=epsilon,
            )
        except SpecialAreaTrackingError:
            continue
        if not _inside_triangle(weights):
            continue
        distances = [
            (coordinates[index][0] - point_xy[0]) ** 2
            + (coordinates[index][1] - point_xy[1]) ** 2
            for index in indices
        ]
        # Prefer a compact local triangle; for equal proximity prefer more area.
        score = (max(distances), sum(distances), -area_twice)
        candidate = (score, indices, _clean_weights(weights))
        if best is None or candidate[0] < best[0]:
            best = candidate

    if best is None:
        raise SpecialAreaTrackingError(
            "Could not find a nearby non-degenerate landmark triangle containing "
            "the polygon point."
        )
    return {
        "landmark_indices": list(best[1]),
        "weights": best[2],
    }


def build_tracking_binding(
    profile: Mapping[str, Any],
    source_landmarks: Sequence[Any],
    *,
    neighbor_count: int = DEFAULT_NEIGHBOR_COUNT,
    triangle_area_epsilon: float = DEFAULT_TRIANGLE_AREA_EPSILON,
) -> dict[str, Any]:
    """Build a separate SpecialAreaTrackingBinding v0.1."""

    validated = validate_special_area_profile(profile)
    coordinates = _normalized_landmarks(source_landmarks)
    areas = []
    for area in validated["areas"]:
        points = [
            bind_point_to_landmarks(
                point,
                coordinates,
                neighbor_count=neighbor_count,
                triangle_area_epsilon=triangle_area_epsilon,
            )
            for point in area["polygon"]
        ]
        areas.append(
            {
                "area_id": area["area_id"],
                "user_label": area["user_label"],
                "location": area["location"],
                "preference": area["preference"],
                "points": points,
            }
        )
    return validate_tracking_binding(
        {
            "schema_version": TRACKING_SCHEMA_VERSION,
            "source_profile_id": validated["image_sample_id"],
            "source_profile_hash": special_area_profile_hash(validated),
            "landmark_count": len(coordinates),
            "triangle_selection": {
                "neighbor_count": min(neighbor_count, len(coordinates)),
                "area_epsilon": float(triangle_area_epsilon),
            },
            "areas": areas,
        }
    )


def validate_tracking_binding(binding: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a strict SpecialAreaTrackingBinding v0.1."""

    required = {
        "schema_version",
        "source_profile_id",
        "source_profile_hash",
        "landmark_count",
        "triangle_selection",
        "areas",
    }
    if not isinstance(binding, Mapping) or set(binding) != required:
        raise SpecialAreaTrackingError("Invalid tracking binding fields.")
    if binding["schema_version"] != TRACKING_SCHEMA_VERSION:
        raise SpecialAreaTrackingError(
            f"tracking schema_version must be {TRACKING_SCHEMA_VERSION}."
        )
    source_id = binding["source_profile_id"]
    if not isinstance(source_id, str) or not source_id.strip():
        raise SpecialAreaTrackingError("source_profile_id must be a non-empty string.")
    source_hash = binding["source_profile_hash"]
    if (
        not isinstance(source_hash, str)
        or len(source_hash) != 64
        or any(character not in "0123456789abcdef" for character in source_hash)
    ):
        raise SpecialAreaTrackingError("source_profile_hash must be SHA-256 hex.")
    landmark_count = binding["landmark_count"]
    if (
        isinstance(landmark_count, bool)
        or not isinstance(landmark_count, int)
        or landmark_count < 3
    ):
        raise SpecialAreaTrackingError("landmark_count must be at least 3.")

    selection = binding["triangle_selection"]
    if not isinstance(selection, Mapping) or set(selection) != {
        "neighbor_count",
        "area_epsilon",
    }:
        raise SpecialAreaTrackingError("Invalid triangle_selection fields.")
    neighbor_count = selection["neighbor_count"]
    if (
        isinstance(neighbor_count, bool)
        or not isinstance(neighbor_count, int)
        or not 3 <= neighbor_count <= landmark_count
    ):
        raise SpecialAreaTrackingError("Invalid triangle neighbor_count.")
    area_epsilon = _number(selection["area_epsilon"], "area_epsilon")
    if area_epsilon <= 0.0:
        raise SpecialAreaTrackingError("area_epsilon must be positive.")

    raw_areas = binding["areas"]
    if not isinstance(raw_areas, list) or not raw_areas:
        raise SpecialAreaTrackingError("Tracking binding areas must be non-empty.")
    areas: list[dict[str, Any]] = []
    seen_area_ids: set[str] = set()
    for area_index, area in enumerate(raw_areas):
        if not isinstance(area, Mapping) or set(area) != {
            "area_id",
            "user_label",
            "location",
            "preference",
            "points",
        }:
            raise SpecialAreaTrackingError(
                f"Invalid tracking binding area at index {area_index}."
            )
        area_id = area["area_id"]
        if not isinstance(area_id, str) or not area_id.strip():
            raise SpecialAreaTrackingError("Tracking area_id must be non-empty.")
        if area_id in seen_area_ids:
            raise SpecialAreaTrackingError("Tracking area_id values must be unique.")
        seen_area_ids.add(area_id)
        user_label = area["user_label"]
        if not isinstance(user_label, str):
            raise SpecialAreaTrackingError("Tracking user_label must be a string.")
        location = area["location"]
        preference = area["preference"]
        if location not in VALID_LOCATIONS:
            raise SpecialAreaTrackingError("Tracking location is invalid.")
        if preference not in VALID_PREFERENCES:
            raise SpecialAreaTrackingError("Tracking preference is invalid.")
        raw_points = area["points"]
        if not isinstance(raw_points, list) or len(raw_points) < 3:
            raise SpecialAreaTrackingError(
                "Tracking polygon must contain at least 3 point bindings."
            )
        points = []
        for point_index, point in enumerate(raw_points):
            if not isinstance(point, Mapping) or set(point) != {
                "landmark_indices",
                "weights",
            }:
                raise SpecialAreaTrackingError(
                    f"Invalid point binding at {area_index}:{point_index}."
                )
            indices = point["landmark_indices"]
            weights = point["weights"]
            if (
                not isinstance(indices, list)
                or len(indices) != 3
                or any(
                    isinstance(index, bool)
                    or not isinstance(index, int)
                    or not 0 <= index < landmark_count
                    for index in indices
                )
                or len(set(indices)) != 3
            ):
                raise SpecialAreaTrackingError(
                    "Each point binding needs 3 distinct valid landmark indices."
                )
            if not isinstance(weights, list) or len(weights) != 3:
                raise SpecialAreaTrackingError(
                    "Each point binding needs exactly 3 weights."
                )
            checked_weights = [
                _number(weight, f"weights[{weight_index}]")
                for weight_index, weight in enumerate(weights)
            ]
            if not _inside_triangle(checked_weights) or not math.isclose(
                sum(checked_weights), 1.0, rel_tol=0.0, abs_tol=1e-6
            ):
                raise SpecialAreaTrackingError(
                    "Barycentric weights must be finite, inside the triangle, and sum to one."
                )
            points.append(
                {
                    "landmark_indices": list(indices),
                    "weights": checked_weights,
                }
            )
        areas.append(
            {
                "area_id": area_id.strip(),
                "user_label": user_label.strip(),
                "location": location,
                "preference": preference,
                "points": points,
            }
        )
    return {
        "schema_version": TRACKING_SCHEMA_VERSION,
        "source_profile_id": source_id.strip(),
        "source_profile_hash": source_hash,
        "landmark_count": landmark_count,
        "triangle_selection": {
            "neighbor_count": neighbor_count,
            "area_epsilon": area_epsilon,
        },
        "areas": areas,
    }


def assert_binding_matches_profile(
    binding: Mapping[str, Any], profile: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Fail closed when a binding belongs to another or stale profile."""

    validated_profile = validate_special_area_profile(profile)
    validated_binding = validate_tracking_binding(binding)
    if validated_binding["source_profile_id"] != validated_profile["image_sample_id"]:
        raise SpecialAreaLiveSessionError(
            "Tracking binding source_profile_id does not match the profile."
        )
    if validated_binding["source_profile_hash"] != special_area_profile_hash(
        validated_profile
    ):
        raise SpecialAreaLiveSessionError(
            "Tracking binding source profile hash mismatch."
        )
    profile_areas = {area["area_id"]: area for area in validated_profile["areas"]}
    if set(profile_areas) != {
        area["area_id"] for area in validated_binding["areas"]
    }:
        raise SpecialAreaLiveSessionError(
            "Tracking binding area IDs do not match the profile."
        )
    for area in validated_binding["areas"]:
        source_area = profile_areas[area["area_id"]]
        for field_name in ("user_label", "location", "preference"):
            if area[field_name] != source_area[field_name]:
                raise SpecialAreaLiveSessionError(
                    f"Tracking binding {field_name} is stale."
                )
        if len(area["points"]) != len(source_area["polygon"]):
            raise SpecialAreaLiveSessionError(
                "Tracking point count does not match the source polygon."
            )
    return validated_binding, validated_profile


def project_tracking_binding(
    binding: Mapping[str, Any],
    live_landmarks: Sequence[Any],
    *,
    source_profile: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Reproject all bound polygon points in raw, unmirrored frame coordinates."""

    if source_profile is None:
        validated_binding = validate_tracking_binding(binding)
    else:
        validated_binding, _ = assert_binding_matches_profile(binding, source_profile)
    coordinates = _normalized_landmarks(live_landmarks)
    if len(coordinates) != validated_binding["landmark_count"]:
        raise SpecialAreaTrackingError(
            "Live landmark topology does not match the source binding."
        )

    projected_areas = []
    for area in validated_binding["areas"]:
        polygon = []
        for point in area["points"]:
            anchors = [coordinates[index] for index in point["landmark_indices"]]
            x_norm = sum(
                weight * anchor[0]
                for weight, anchor in zip(point["weights"], anchors)
            )
            y_norm = sum(
                weight * anchor[1]
                for weight, anchor in zip(point["weights"], anchors)
            )
            if not all(math.isfinite(value) for value in (x_norm, y_norm)):
                raise SpecialAreaTrackingError(
                    "Projected polygon contains NaN or infinity."
                )
            if not 0.0 <= x_norm <= 1.0 or not 0.0 <= y_norm <= 1.0:
                raise SpecialAreaTrackingError(
                    "Projected polygon left normalized image coordinates."
                )
            polygon.append({"x_norm": x_norm, "y_norm": y_norm})
        if len(polygon) < 3:
            raise SpecialAreaTrackingError(
                "Projected polygon must contain at least 3 points."
            )
        projected_areas.append(
            {
                "area_id": area["area_id"],
                "user_label": area["user_label"],
                "location": area["location"],
                "preference": area["preference"],
                "polygon": polygon,
            }
        )
    return projected_areas


def build_live_session(
    profile: Mapping[str, Any],
    tracking_binding: Mapping[str, Any],
    *,
    source_image_identifier: str,
    session_id: str | None = None,
) -> SpecialAreaLiveSession:
    """Create an isolated profile-to-live session with raw tracking enabled."""

    binding, validated_profile = assert_binding_matches_profile(
        tracking_binding, profile
    )
    if (
        not isinstance(source_image_identifier, str)
        or not source_image_identifier.strip()
        or Path(source_image_identifier).name != source_image_identifier
    ):
        raise SpecialAreaLiveSessionError(
            "source_image_identifier must be a path-free non-empty string."
        )
    if source_image_identifier != validated_profile["image_sample_id"]:
        raise SpecialAreaLiveSessionError(
            "Source image identifier does not match image_sample_id."
        )
    resolved_session_id = session_id or uuid.uuid4().hex
    if not isinstance(resolved_session_id, str) or not resolved_session_id.strip():
        raise SpecialAreaLiveSessionError("session_id must be non-empty.")
    session = SpecialAreaLiveSession(
        session_id=resolved_session_id.strip(),
        source_image_identifier=source_image_identifier,
        source_profile_hash=special_area_profile_hash(validated_profile),
        source_profile=copy.deepcopy(validated_profile),
        tracking_binding=copy.deepcopy(binding),
    )
    assert_current_live_session(session)
    return session


def assert_current_live_session(session: SpecialAreaLiveSession) -> None:
    """Ensure UI, binding, and source profile all belong to this session."""

    if not isinstance(session.session_id, str) or not session.session_id:
        raise SpecialAreaLiveSessionError("Live session_id is missing.")
    current_hash = special_area_profile_hash(session.source_profile)
    if current_hash != session.source_profile_hash:
        raise SpecialAreaLiveSessionError("Live session source profile hash changed.")
    assert_binding_matches_profile(session.tracking_binding, session.source_profile)
    if session.source_image_identifier != session.source_profile["image_sample_id"]:
        raise SpecialAreaLiveSessionError(
            "Live session source image identifier is stale."
        )
    if session.smoothing_enabled or session.smoothing_alpha is not None:
        raise SpecialAreaLiveSessionError(
            "Special Area Live Tracking v0.1 does not enable smoothing."
        )
    if session.tracking_status not in {TRACKING_ACTIVE, TRACKING_FACE_LOST}:
        raise SpecialAreaLiveSessionError("Live tracking status is invalid.")
    if session.tracking_status == TRACKING_FACE_LOST and session.current_live_areas:
        raise SpecialAreaLiveSessionError(
            "FACE_LOST sessions must not retain an old live polygon."
        )


def update_live_session(
    session: SpecialAreaLiveSession, live_landmarks: Sequence[Any]
) -> list[dict[str, Any]]:
    """Project one valid frame and replace the session's current live polygon."""

    assert_current_live_session(session)
    projected = project_tracking_binding(
        session.tracking_binding,
        live_landmarks,
        source_profile=session.source_profile,
    )
    session.current_live_areas = projected
    session.tracking_status = TRACKING_ACTIVE
    session.frame_index += 1
    return projected


def mark_face_lost(session: SpecialAreaLiveSession) -> None:
    """Clear old geometry so a missing face is never presented as active tracking."""

    assert_current_live_session(session)
    session.current_live_areas = []
    session.tracking_status = TRACKING_FACE_LOST
    session.frame_index += 1


def normalized_to_display_pixel(
    point: Mapping[str, Any],
    *,
    width: int,
    height: int,
    mirrored_preview: bool,
) -> tuple[int, int]:
    """Apply the display transform after raw-frame tracking geometry is complete."""

    if width <= 1 or height <= 1:
        raise SpecialAreaTrackingError("Display dimensions must exceed one pixel.")
    x_norm = _number(point.get("x_norm"), "display_point.x_norm")
    y_norm = _number(point.get("y_norm"), "display_point.y_norm")
    if not 0.0 <= x_norm <= 1.0 or not 0.0 <= y_norm <= 1.0:
        raise SpecialAreaTrackingError("Display point must be normalized to 0..1.")
    display_x = 1.0 - x_norm if mirrored_preview else x_norm
    return round(display_x * (width - 1)), round(y_norm * (height - 1))


def live_session_payload(session: SpecialAreaLiveSession) -> dict[str, Any]:
    """Build strict JSON metadata; no webcam image or frame is included."""

    assert_current_live_session(session)
    return {
        "schema_version": TRACKING_SCHEMA_VERSION,
        "session_id": session.session_id,
        "source_image_identifier": session.source_image_identifier,
        "source_profile_hash": session.source_profile_hash,
        "tracking_status": session.tracking_status,
        "frame_index": session.frame_index,
        "smoothing": {"enabled": False, "alpha": None},
        "tracking_binding": copy.deepcopy(session.tracking_binding),
        "current_live_areas": copy.deepcopy(session.current_live_areas),
    }


def save_live_session_json(
    output_path: Path | str, session: SpecialAreaLiveSession
) -> Path:
    """Save session metadata only when explicitly requested by the UI."""

    path = Path(output_path)
    save_strict_json(path, live_session_payload(session))
    return path


__all__ = [
    "DEFAULT_NEIGHBOR_COUNT",
    "DEFAULT_TRIANGLE_AREA_EPSILON",
    "SpecialAreaLiveSession",
    "SpecialAreaLiveSessionError",
    "SpecialAreaTrackingError",
    "TRACKING_ACTIVE",
    "TRACKING_FACE_LOST",
    "TRACKING_SCHEMA_VERSION",
    "assert_binding_matches_profile",
    "assert_current_live_session",
    "bind_point_to_landmarks",
    "build_live_session",
    "build_tracking_binding",
    "live_session_payload",
    "landmark_signature",
    "mark_face_lost",
    "normalized_to_display_pixel",
    "project_tracking_binding",
    "save_live_session_json",
    "special_area_profile_hash",
    "update_live_session",
    "validate_tracking_binding",
]
