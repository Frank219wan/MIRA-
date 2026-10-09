"""State and coordination for selecting one Special Area from a live camera.

Frozen camera frames remain owned by the UI and are never stored here.  This
module keeps only normalized polygon geometry, landmark geometry, and strict
JSON metadata needed to build the existing tracking pipeline.
"""

from __future__ import annotations

import math
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .special_area_profile import (
    VALID_LOCATIONS,
    VALID_PREFERENCES,
    build_special_area,
    build_special_area_profile,
    save_strict_json,
)
from .special_area_tracking import (
    TRACKING_ACTIVE,
    SpecialAreaLiveSession,
    assert_current_live_session,
    build_live_session,
    build_tracking_binding,
    landmark_signature,
    live_session_payload,
    mark_face_lost,
    project_tracking_binding,
    special_area_profile_hash,
    update_live_session,
)


LIVE_SELECTION_SCHEMA_VERSION = "0.1"
IDENTITY_REPROJECTION_TOLERANCE = 1e-6
POLYGON_DUPLICATE_DISTANCE = 1e-4
POLYGON_AREA_EPSILON = 1e-6
SEGMENT_EPSILON = 1e-12


class LiveAreaSelectionState(str, Enum):
    LIVE_UNCONFIGURED = "LIVE_UNCONFIGURED"
    FREEZE_SELECTING = "FREEZE_SELECTING"
    METADATA_INPUT = "METADATA_INPUT"
    BINDING = "BINDING"
    LIVE_TRACKING = "LIVE_TRACKING"
    FACE_LOST = "FACE_LOST"
    QUIT = "QUIT"


class LiveAreaSelectionError(RuntimeError):
    """Raised when a live selection transition cannot be completed safely."""


@dataclass
class LiveAreaSelectionSession:
    """One camera session with at most one active user-selected area."""

    session_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    state: LiveAreaSelectionState = LiveAreaSelectionState.LIVE_UNCONFIGURED
    selection_revision: int = 0
    active_tracking_session: SpecialAreaLiveSession | None = None
    source_frame_id: str | None = None
    source_landmark_signature: str | None = None
    identity_reprojection_max_error: float | None = None
    pending_source_frame_id: str | None = None
    pending_source_landmarks: list[Any] | None = None
    pending_polygon: list[dict[str, float]] | None = None
    resume_state: LiveAreaSelectionState | None = None


def _finite_normalized(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LiveAreaSelectionError(f"{field_name} must be numeric.")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise LiveAreaSelectionError(
            f"{field_name} must be finite and normalized to 0..1."
        )
    return number


def display_normalized_to_raw(
    point: Mapping[str, Any], *, mirrored_preview: bool = True
) -> dict[str, float]:
    """Convert one displayed normalized click into raw camera coordinates."""

    if not isinstance(point, Mapping) or set(point) != {"x_norm", "y_norm"}:
        raise LiveAreaSelectionError(
            "Display point must contain only x_norm and y_norm."
        )
    display_x = _finite_normalized(point["x_norm"], "display.x_norm")
    display_y = _finite_normalized(point["y_norm"], "display.y_norm")
    return {
        "x_norm": 1.0 - display_x if mirrored_preview else display_x,
        "y_norm": display_y,
    }


def display_pixels_to_raw_polygon(
    display_points: Sequence[Sequence[int | float]],
    *,
    width: int,
    height: int,
    mirrored_preview: bool = True,
) -> list[dict[str, float]]:
    """Convert display pixels from the mirrored selector to raw normalized points."""

    if width <= 1 or height <= 1:
        raise LiveAreaSelectionError("Display width and height must exceed one pixel.")
    if not isinstance(display_points, Sequence) or len(display_points) < 3:
        raise LiveAreaSelectionError("At least 3 polygon points are required.")
    polygon = []
    for index, point in enumerate(display_points):
        if not isinstance(point, Sequence) or len(point) != 2:
            raise LiveAreaSelectionError(
                f"display_points[{index}] must contain x and y."
            )
        x, y = point
        if (
            isinstance(x, bool)
            or isinstance(y, bool)
            or not isinstance(x, (int, float))
            or not isinstance(y, (int, float))
        ):
            raise LiveAreaSelectionError("Display pixel coordinates must be numeric.")
        x_value, y_value = float(x), float(y)
        if (
            not math.isfinite(x_value)
            or not math.isfinite(y_value)
            or not 0.0 <= x_value <= width - 1
            or not 0.0 <= y_value <= height - 1
        ):
            raise LiveAreaSelectionError(
                "Display pixel coordinates must be finite and inside the frame."
            )
        polygon.append(
            display_normalized_to_raw(
                {
                    "x_norm": x_value / (width - 1),
                    "y_norm": y_value / (height - 1),
                },
                mirrored_preview=mirrored_preview,
            )
        )
    return polygon


def normalize_display_polygon(
    display_points: Sequence[Sequence[int | float]],
    *,
    width: int,
    height: int,
    mirrored_preview: bool = True,
) -> list[dict[str, float]]:
    """Run the authoritative display-to-raw polygon normalization pipeline."""

    raw_polygon = display_pixels_to_raw_polygon(
        display_points,
        width=width,
        height=height,
        mirrored_preview=mirrored_preview,
    )
    return normalize_polygon(raw_polygon)


def _polygon_point_xy(point: Any, field_name: str) -> tuple[float, float]:
    if isinstance(point, Mapping):
        if set(point) != {"x_norm", "y_norm"}:
            raise LiveAreaSelectionError(
                f"{field_name} must contain only x_norm and y_norm."
            )
        x, y = point["x_norm"], point["y_norm"]
    elif (
        isinstance(point, Sequence)
        and not isinstance(point, (str, bytes))
        and len(point) == 2
    ):
        x, y = point
    else:
        raise LiveAreaSelectionError(
            f"{field_name} must contain exactly two normalized coordinates."
        )
    return (
        _finite_normalized(x, f"{field_name}.x"),
        _finite_normalized(y, f"{field_name}.y"),
    )


def polygon_signed_area(points: Sequence[Any]) -> float:
    """Return signed shoelace area for normalized polygon coordinates."""

    coordinates = [
        _polygon_point_xy(point, f"points[{index}]")
        for index, point in enumerate(points)
    ]
    if len(coordinates) < 3:
        return 0.0
    return 0.5 * sum(
        x_a * y_b - x_b * y_a
        for (x_a, y_a), (x_b, y_b) in zip(
            coordinates,
            coordinates[1:] + coordinates[:1],
        )
    )


def _cross(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (
        c[0] - a[0]
    )


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    return (
        min(start[0], end[0]) - SEGMENT_EPSILON
        <= point[0]
        <= max(start[0], end[0]) + SEGMENT_EPSILON
        and min(start[1], end[1]) - SEGMENT_EPSILON
        <= point[1]
        <= max(start[1], end[1]) + SEGMENT_EPSILON
    )


def _segments_intersect(
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    d: tuple[float, float],
) -> bool:
    cross_abc = _cross(a, b, c)
    cross_abd = _cross(a, b, d)
    cross_cda = _cross(c, d, a)
    cross_cdb = _cross(c, d, b)
    if (
        (cross_abc > SEGMENT_EPSILON and cross_abd < -SEGMENT_EPSILON)
        or (cross_abc < -SEGMENT_EPSILON and cross_abd > SEGMENT_EPSILON)
    ) and (
        (cross_cda > SEGMENT_EPSILON and cross_cdb < -SEGMENT_EPSILON)
        or (cross_cda < -SEGMENT_EPSILON and cross_cdb > SEGMENT_EPSILON)
    ):
        return True
    collinear_checks = (
        (cross_abc, c, a, b),
        (cross_abd, d, a, b),
        (cross_cda, a, c, d),
        (cross_cdb, b, c, d),
    )
    return any(
        abs(cross_value) <= SEGMENT_EPSILON
        and _point_on_segment(point, start, end)
        for cross_value, point, start, end in collinear_checks
    )


def is_simple_polygon(points: Sequence[Any]) -> bool:
    """Return false when any non-adjacent closed polygon edges intersect."""

    try:
        coordinates = [
            _polygon_point_xy(point, f"points[{index}]")
            for index, point in enumerate(points)
        ]
    except LiveAreaSelectionError:
        return False
    point_count = len(coordinates)
    if point_count < 3:
        return False
    for first_edge in range(point_count):
        a = coordinates[first_edge]
        b = coordinates[(first_edge + 1) % point_count]
        for second_edge in range(first_edge + 1, point_count):
            if (
                second_edge == first_edge
                or second_edge == (first_edge + 1) % point_count
                or first_edge == (second_edge + 1) % point_count
            ):
                continue
            c = coordinates[second_edge]
            d = coordinates[(second_edge + 1) % point_count]
            if _segments_intersect(a, b, c, d):
                return False
    return True


def normalize_polygon(
    points: Sequence[Any],
    *,
    duplicate_distance: float = POLYGON_DUPLICATE_DISTANCE,
    area_epsilon: float = POLYGON_AREA_EPSILON,
) -> list[dict[str, float]]:
    """Deduplicate and angle-sort raw points without changing their coordinates."""

    if not isinstance(points, Sequence):
        raise LiveAreaSelectionError("Polygon points must be a sequence.")
    distance_threshold = float(duplicate_distance)
    minimum_area = float(area_epsilon)
    if (
        not math.isfinite(distance_threshold)
        or distance_threshold < 0.0
        or not math.isfinite(minimum_area)
        or minimum_area <= 0.0
    ):
        raise LiveAreaSelectionError("Polygon validation tolerances are invalid.")

    unique: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        coordinate = _polygon_point_xy(point, f"points[{index}]")
        if any(
            math.hypot(
                coordinate[0] - existing[0],
                coordinate[1] - existing[1],
            )
            < distance_threshold
            for existing in unique
        ):
            continue
        unique.append(coordinate)
    if len(unique) < 3:
        raise LiveAreaSelectionError(
            "At least 3 unique polygon points are required.\n"
            "Please redraw the area."
        )

    centroid_x = sum(point[0] for point in unique) / len(unique)
    centroid_y = sum(point[1] for point in unique) / len(unique)
    ordered = sorted(
        unique,
        key=lambda point: (
            math.atan2(point[1] - centroid_y, point[0] - centroid_x),
            (point[0] - centroid_x) ** 2 + (point[1] - centroid_y) ** 2,
        ),
    )
    normalized = [
        {"x_norm": point[0], "y_norm": point[1]} for point in ordered
    ]
    if abs(polygon_signed_area(normalized)) <= minimum_area:
        raise LiveAreaSelectionError(
            "Area is too small or degenerate.\nPlease redraw the area."
        )
    if not is_simple_polygon(normalized):
        raise LiveAreaSelectionError(
            "Invalid polygon: edges intersect.\nPlease redraw the area."
        )
    return normalized


def raw_polygon_to_display_pixels(
    raw_polygon: Sequence[Any],
    *,
    width: int,
    height: int,
    mirrored_preview: bool = True,
) -> list[tuple[int, int]]:
    """Map validated raw geometry back to display pixels for preview only."""

    if width <= 1 or height <= 1:
        raise LiveAreaSelectionError("Display width and height must exceed one pixel.")
    pixels = []
    for index, point in enumerate(raw_polygon):
        x_norm, y_norm = _polygon_point_xy(point, f"raw_polygon[{index}]")
        display_x = 1.0 - x_norm if mirrored_preview else x_norm
        pixels.append(
            (
                round(display_x * (width - 1)),
                round(y_norm * (height - 1)),
            )
        )
    return pixels


def require_single_freeze_face(detected_faces: Sequence[Sequence[Any]]) -> list[Any]:
    """Return exactly one usable face or a precise freeze-selection error."""

    if not isinstance(detected_faces, Sequence) or len(detected_faces) == 0:
        raise LiveAreaSelectionError("Cannot select area: no face detected.")
    if len(detected_faces) > 1:
        raise LiveAreaSelectionError("Cannot select area: multiple faces detected.")
    face = detected_faces[0]
    if not isinstance(face, Sequence) or len(face) < 3:
        raise LiveAreaSelectionError("Cannot select area: no usable face detected.")
    return list(face)


def _resume_state(session: LiveAreaSelectionSession) -> LiveAreaSelectionState:
    if session.active_tracking_session is None:
        return LiveAreaSelectionState.LIVE_UNCONFIGURED
    if session.active_tracking_session.tracking_status == TRACKING_ACTIVE:
        return LiveAreaSelectionState.LIVE_TRACKING
    return LiveAreaSelectionState.FACE_LOST


def begin_freeze_selection(
    session: LiveAreaSelectionSession,
    detected_faces: Sequence[Sequence[Any]],
) -> str:
    """Begin an in-memory freeze selection without changing the active binding."""

    assert_live_area_selection_session(session)
    if session.state == LiveAreaSelectionState.QUIT:
        raise LiveAreaSelectionError("Cannot select an area after quit.")
    source_landmarks = require_single_freeze_face(detected_faces)
    next_revision = session.selection_revision + 1
    source_frame_id = (
        f"live_session_{session.session_id}_freeze_{next_revision:03d}"
    )
    session.resume_state = _resume_state(session)
    session.pending_source_frame_id = source_frame_id
    session.pending_source_landmarks = source_landmarks
    session.pending_polygon = None
    session.state = LiveAreaSelectionState.FREEZE_SELECTING
    return source_frame_id


def set_pending_polygon(
    session: LiveAreaSelectionSession,
    raw_polygon: Sequence[Mapping[str, Any]],
) -> None:
    """Accept one raw-coordinate polygon and advance to metadata input."""

    if session.state != LiveAreaSelectionState.FREEZE_SELECTING:
        raise LiveAreaSelectionError("Polygon can only be set while selecting.")
    if not isinstance(raw_polygon, Sequence) or len(raw_polygon) < 3:
        raise LiveAreaSelectionError("At least 3 polygon points are required.")
    session.pending_polygon = normalize_polygon(raw_polygon)
    session.state = LiveAreaSelectionState.METADATA_INPUT


def cancel_pending_selection(session: LiveAreaSelectionSession) -> None:
    """Discard only pending work and restore the previous active selection."""

    if session.state not in {
        LiveAreaSelectionState.FREEZE_SELECTING,
        LiveAreaSelectionState.METADATA_INPUT,
        LiveAreaSelectionState.BINDING,
    }:
        raise LiveAreaSelectionError("There is no pending selection to cancel.")
    restored = session.resume_state or _resume_state(session)
    session.pending_source_frame_id = None
    session.pending_source_landmarks = None
    session.pending_polygon = None
    session.resume_state = None
    session.state = restored
    assert_live_area_selection_session(session)


def retry_pending_polygon(session: LiveAreaSelectionSession) -> None:
    """Keep the frozen landmarks but discard an invalid polygon attempt."""

    if (
        session.pending_source_frame_id is None
        or session.pending_source_landmarks is None
    ):
        raise LiveAreaSelectionError("Frozen source geometry is unavailable.")
    session.pending_polygon = None
    session.state = LiveAreaSelectionState.FREEZE_SELECTING


def _identity_reprojection_error(
    profile: Mapping[str, Any],
    binding: Mapping[str, Any],
    source_landmarks: Sequence[Any],
) -> float:
    projected = project_tracking_binding(
        binding,
        source_landmarks,
        source_profile=profile,
    )
    source_polygon = profile["areas"][0]["polygon"]
    projected_polygon = projected[0]["polygon"]
    if len(source_polygon) != len(projected_polygon):
        raise LiveAreaSelectionError("Identity reprojection changed point count.")
    return max(
        math.hypot(
            float(actual["x_norm"]) - float(expected["x_norm"]),
            float(actual["y_norm"]) - float(expected["y_norm"]),
        )
        for actual, expected in zip(projected_polygon, source_polygon)
    )


def commit_pending_selection(
    session: LiveAreaSelectionSession,
    *,
    user_label: str,
    location: str,
    preference: str,
    identity_tolerance: float = IDENTITY_REPROJECTION_TOLERANCE,
) -> SpecialAreaLiveSession:
    """Build Profile and Binding in memory, validate identity, then swap atomically."""

    if session.state != LiveAreaSelectionState.METADATA_INPUT:
        raise LiveAreaSelectionError("Selection metadata is not ready.")
    if not isinstance(user_label, str):
        raise LiveAreaSelectionError("user_label must be a string.")
    if location not in VALID_LOCATIONS:
        raise LiveAreaSelectionError("A current subject-relative location is required.")
    if preference not in VALID_PREFERENCES:
        raise LiveAreaSelectionError("An explicit preference is required.")
    tolerance = float(identity_tolerance)
    if not math.isfinite(tolerance) or tolerance < 0.0:
        raise LiveAreaSelectionError("identity_tolerance must be finite and non-negative.")
    if (
        session.pending_source_frame_id is None
        or session.pending_source_landmarks is None
        or session.pending_polygon is None
    ):
        raise LiveAreaSelectionError("Pending freeze geometry is incomplete.")

    source_frame_id = session.pending_source_frame_id
    source_landmarks = session.pending_source_landmarks
    polygon = session.pending_polygon
    session.state = LiveAreaSelectionState.BINDING
    try:
        area = build_special_area(
            area_id="area_01",
            user_label=user_label,
            location=location,
            preference=preference,
            polygon=polygon,
        )
        profile = build_special_area_profile(source_frame_id, [area])
        binding = build_tracking_binding(profile, source_landmarks)
        identity_error = _identity_reprojection_error(
            profile,
            binding,
            source_landmarks,
        )
        if identity_error > tolerance:
            raise LiveAreaSelectionError(
                "Failed to bind selected area safely: identity reprojection "
                f"error {identity_error:.9g} exceeds {tolerance:.9g}."
            )
        tracking_session = build_live_session(
            profile,
            binding,
            source_image_identifier=source_frame_id,
            session_id=session.session_id,
        )
        source_signature = landmark_signature(source_landmarks)
    except Exception:
        session.state = LiveAreaSelectionState.FREEZE_SELECTING
        session.pending_polygon = None
        raise

    # Commit only after every candidate object has passed validation.  The old
    # profile and binding remain untouched until this point.
    session.selection_revision += 1
    session.active_tracking_session = tracking_session
    session.source_frame_id = source_frame_id
    session.source_landmark_signature = source_signature
    session.identity_reprojection_max_error = identity_error
    session.pending_source_frame_id = None
    session.pending_source_landmarks = None
    session.pending_polygon = None
    session.resume_state = None
    session.state = LiveAreaSelectionState.LIVE_TRACKING
    assert_live_area_selection_session(session)
    return tracking_session


def update_live_tracking(
    session: LiveAreaSelectionSession,
    live_landmarks: Sequence[Any],
) -> list[dict[str, Any]]:
    """Project one live frame and mark the workflow active."""

    if session.active_tracking_session is None:
        raise LiveAreaSelectionError("No active area has been configured.")
    projected = update_live_session(session.active_tracking_session, live_landmarks)
    session.state = LiveAreaSelectionState.LIVE_TRACKING
    assert_live_area_selection_session(session)
    return projected


def mark_live_face_lost(session: LiveAreaSelectionSession) -> None:
    """Clear the live polygon and expose FACE_LOST at workflow level."""

    if session.active_tracking_session is None:
        raise LiveAreaSelectionError("No active area has been configured.")
    mark_face_lost(session.active_tracking_session)
    session.state = LiveAreaSelectionState.FACE_LOST
    assert_live_area_selection_session(session)


def quit_live_area_selection(session: LiveAreaSelectionSession) -> None:
    """End the state machine without persisting camera imagery."""

    session.pending_source_frame_id = None
    session.pending_source_landmarks = None
    session.pending_polygon = None
    session.resume_state = None
    session.state = LiveAreaSelectionState.QUIT


def assert_live_area_selection_session(session: LiveAreaSelectionSession) -> None:
    """Reject stale profile/binding/session combinations."""

    if not isinstance(session.session_id, str) or not session.session_id.strip():
        raise LiveAreaSelectionError("session_id must be non-empty.")
    if session.selection_revision < 0:
        raise LiveAreaSelectionError("selection_revision cannot be negative.")
    active = session.active_tracking_session
    if active is None:
        if session.selection_revision != 0:
            raise LiveAreaSelectionError("A revision requires an active selection.")
        if session.state in {
            LiveAreaSelectionState.LIVE_TRACKING,
            LiveAreaSelectionState.FACE_LOST,
        }:
            raise LiveAreaSelectionError("Tracking state requires an active selection.")
        return

    assert_current_live_session(active)
    if active.session_id != session.session_id:
        raise LiveAreaSelectionError("Active tracking uses another session_id.")
    if session.selection_revision < 1:
        raise LiveAreaSelectionError("Active selection requires revision >= 1.")
    if session.source_frame_id != active.source_image_identifier:
        raise LiveAreaSelectionError("Active source frame is stale.")
    if (
        session.source_landmark_signature is None
        or len(session.source_landmark_signature) != 64
    ):
        raise LiveAreaSelectionError("Source landmark signature is missing.")
    profile_hash = special_area_profile_hash(active.source_profile)
    if profile_hash != active.source_profile_hash:
        raise LiveAreaSelectionError("Active SpecialAreaProfile hash is stale.")
    if active.tracking_binding["source_profile_hash"] != profile_hash:
        raise LiveAreaSelectionError("Active tracking binding profile hash is stale.")
    if session.state == LiveAreaSelectionState.FACE_LOST and active.current_live_areas:
        raise LiveAreaSelectionError("FACE_LOST must not retain a polygon.")


def live_area_selection_payload(
    session: LiveAreaSelectionSession,
) -> dict[str, Any]:
    """Build path-free strict JSON session metadata without camera pixels."""

    assert_live_area_selection_session(session)
    if session.active_tracking_session is None:
        raise LiveAreaSelectionError("Nothing can be saved before an area is active.")
    active = session.active_tracking_session
    area = active.source_profile["areas"][0]
    return {
        "schema_version": LIVE_SELECTION_SCHEMA_VERSION,
        "workflow": "live_area_selection",
        "session_id": session.session_id,
        "state": session.state.value,
        "selection_revision": session.selection_revision,
        "source_frame_id": session.source_frame_id,
        "source_landmark_signature": session.source_landmark_signature,
        "special_area_profile_hash": active.source_profile_hash,
        "tracking_binding_profile_hash": active.tracking_binding[
            "source_profile_hash"
        ],
        "identity_reprojection_max_error": session.identity_reprojection_max_error,
        "active_area": {
            "area_id": area["area_id"],
            "user_label": area["user_label"],
            "location": area["location"],
            "preference": area["preference"],
        },
        "live_tracking": live_session_payload(active),
    }


def save_live_area_selection(
    output_dir: Path | str,
    session: LiveAreaSelectionSession,
) -> tuple[Path, Path, Path]:
    """Save only Profile, Binding, and session JSON after an explicit S action."""

    assert_live_area_selection_session(session)
    if session.active_tracking_session is None:
        raise LiveAreaSelectionError("Nothing can be saved before an area is active.")
    directory = Path(output_dir)
    profile_path = directory / "special_area_profile.json"
    binding_path = directory / "special_area_tracking_binding.json"
    session_path = directory / "special_area_live_session.json"
    active = session.active_tracking_session
    save_strict_json(profile_path, active.source_profile)
    save_strict_json(binding_path, active.tracking_binding)
    save_strict_json(session_path, live_area_selection_payload(session))
    return profile_path, binding_path, session_path


__all__ = [
    "IDENTITY_REPROJECTION_TOLERANCE",
    "LIVE_SELECTION_SCHEMA_VERSION",
    "POLYGON_AREA_EPSILON",
    "POLYGON_DUPLICATE_DISTANCE",
    "LiveAreaSelectionError",
    "LiveAreaSelectionSession",
    "LiveAreaSelectionState",
    "assert_live_area_selection_session",
    "begin_freeze_selection",
    "cancel_pending_selection",
    "commit_pending_selection",
    "display_normalized_to_raw",
    "display_pixels_to_raw_polygon",
    "is_simple_polygon",
    "live_area_selection_payload",
    "mark_live_face_lost",
    "normalize_polygon",
    "normalize_display_polygon",
    "polygon_signed_area",
    "quit_live_area_selection",
    "require_single_freeze_face",
    "raw_polygon_to_display_pixels",
    "retry_pending_polygon",
    "save_live_area_selection",
    "set_pending_polygon",
    "update_live_tracking",
]
