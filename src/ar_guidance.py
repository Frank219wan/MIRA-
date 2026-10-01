"""Normalized spatial guidance geometry for live or static camera landmarks."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "0.1"
SIDES = frozenset(("left", "right"))
MIN_DISTANCE = 1e-12
LOWER_LID_BASE_RANGE_FRACTION = 0.6
LOWER_LID_BAND_WIDTH_NORM = 0.004


class ARGuidanceError(ValueError):
    """Raised when normalized landmarks or action parameters are invalid."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ARGuidanceError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ARGuidanceError(f"{label} must be finite.")
    return number


def _point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, Mapping):
        raise ARGuidanceError(f"{label} must be a point object.")
    x_key = "x_norm" if "x_norm" in value else "x"
    y_key = "y_norm" if "y_norm" in value else "y"
    x = _finite_number(value.get(x_key), f"{label}.{x_key}")
    y = _finite_number(value.get(y_key), f"{label}.{y_key}")
    if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
        raise ARGuidanceError(f"{label} must be within normalized range 0..1.")
    return x, y


def _point_output(point: tuple[float, float]) -> dict[str, float]:
    return {"x_norm": round(point[0], 12), "y_norm": round(point[1], 12)}


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _first_mapping(value: Mapping[str, Any], *keys: str) -> Mapping[str, Any] | None:
    for key in keys:
        nested = value.get(key)
        if isinstance(nested, Mapping):
            return nested
    return None


def _first_number(value: Mapping[str, Any], label: str, *keys: str) -> float:
    for key in keys:
        if key in value:
            return _finite_number(value[key], f"{label}.{key}")
    raise ARGuidanceError(f"{label} is missing one of: {', '.join(keys)}.")


def a04_action_parameters(action: Mapping[str, Any]) -> dict[str, float]:
    """Normalize Reference Geometry, case output, or fixture A04 fields."""

    if not isinstance(action, Mapping):
        raise ARGuidanceError("A04 action must be an object.")
    geometry = action.get("geometry")
    if isinstance(geometry, Mapping):
        source = geometry
        direction = _first_number(
            source,
            "A04 geometry direction",
            "direction_relative_to_eye_axis_deg",
        )
        extension = _first_number(
            source,
            "A04 geometry extension",
            "eyeliner_extension_ratio",
        )
        start = _first_number(
            source,
            "A04 geometry start",
            "start_position_ratio",
        )
    else:
        direction_group = _first_mapping(action, "direction")
        extension_group = _first_mapping(action, "extension")
        direction = _first_number(
            direction_group or action,
            "A04 direction",
            "personalized_direction",
            "personalized_direction_deg",
            "direction_relative_to_eye_axis_deg",
            "reference_direction",
            "reference_direction_deg",
        )
        extension = _first_number(
            extension_group or action,
            "A04 extension",
            "personalized_extension_ratio",
            "reference_extension_ratio",
            "eyeliner_extension_ratio",
        )
        start = _first_number(
            action,
            "A04 start",
            "start_position_ratio",
        )
    if extension <= 0.0:
        raise ARGuidanceError("A04 extension ratio must be greater than zero.")
    return {
        "direction_relative_to_eye_axis_deg": direction,
        "extension_ratio": extension,
        "start_position_ratio": start,
    }


def build_a04_guidance(
    landmarks: Mapping[str, Any],
    personalized_action: Mapping[str, Any],
    side: str,
    *,
    source: str = "personalized_action",
) -> dict[str, Any]:
    """Build an A04 direction line in normalized camera coordinates.

    ``landmarks`` must already use subject-relative eye semantics. No left/right
    swapping is performed here. Image x grows right and y grows downward.
    Positive reference-relative direction remains visually upward for either
    eye-axis orientation, matching ``build_reference_action_geometry``.
    """

    if side not in SIDES:
        raise ARGuidanceError(f"side must be one of {sorted(SIDES)}.")
    if not isinstance(landmarks, Mapping):
        raise ARGuidanceError("landmarks must be an object.")
    inner = _point(landmarks.get("eye_inner"), "eye_inner")
    outer = _point(landmarks.get("eye_outer"), "eye_outer")
    axis_x, axis_y = outer[0] - inner[0], outer[1] - inner[1]
    eye_width = math.hypot(axis_x, axis_y)
    if eye_width <= MIN_DISTANCE:
        raise ARGuidanceError("eye_inner and eye_outer must be distinct.")
    if abs(axis_x) <= MIN_DISTANCE:
        raise ARGuidanceError(
            "A vertical eye axis cannot define visually upward direction."
        )
    action = a04_action_parameters(personalized_action)
    start_ratio = action["start_position_ratio"]
    anchor = (
        inner[0] + start_ratio * axis_x,
        inner[1] + start_ratio * axis_y,
    )
    unit_x, unit_y = axis_x / eye_width, axis_y / eye_width
    angle = math.radians(action["direction_relative_to_eye_axis_deg"])
    outward_sign = math.copysign(1.0, axis_x)
    # p=(unit_y,-unit_x) is clockwise in screen coordinates. Multiplying it
    # by sign(axis_x) preserves visually-upward-positive for both eye sides.
    direction_x = (
        math.cos(angle) * unit_x
        + outward_sign * math.sin(angle) * unit_y
    )
    direction_y = (
        math.cos(angle) * unit_y
        - outward_sign * math.sin(angle) * unit_x
    )
    extension_length = eye_width * action["extension_ratio"]
    endpoint = (
        anchor[0] + direction_x * extension_length,
        anchor[1] + direction_y * extension_length,
    )
    for label, point in (("anchor", anchor), ("endpoint", endpoint)):
        if not 0.0 <= point[0] <= 1.0 or not 0.0 <= point[1] <= 1.0:
            raise ARGuidanceError(
                f"{label} falls outside normalized camera coordinates."
            )
    result = {
        "schema_version": SCHEMA_VERSION,
        "action_id": "A04",
        "guidance_type": "direction_line",
        "side": side,
        "anchor": _point_output(anchor),
        "endpoint": _point_output(endpoint),
        "eye_axis": {
            "inner": _point_output(inner),
            "outer": _point_output(outer),
        },
        "eye_width_norm": round(eye_width, 12),
        "direction_relative_to_eye_axis_deg": action[
            "direction_relative_to_eye_axis_deg"
        ],
        "extension_ratio": action["extension_ratio"],
        "extension_length_norm": round(extension_length, 12),
        "start_position_ratio": start_ratio,
        "source": source,
    }
    assert_strict_finite(result)
    return result


def _a02_parameters(action: Mapping[str, Any]) -> tuple[float, float]:
    if not isinstance(action, Mapping):
        raise ARGuidanceError("A02 action must be an object.")
    parameters = action.get("personalized_parameters")
    source = parameters if isinstance(parameters, Mapping) else action
    range_factor = _first_number(
        source,
        "A02 range",
        "personalized_range_factor",
        "range_factor",
        "reference_range_factor",
    )
    intensity_factor = _first_number(
        source,
        "A02 intensity",
        "personalized_intensity_factor",
        "intensity_factor",
        "reference_intensity_factor",
    )
    if range_factor <= 0.0 or intensity_factor < 0.0:
        raise ARGuidanceError(
            "A02 range must be positive and intensity must be non-negative."
        )
    return range_factor, intensity_factor


def _path_prefix(
    path: Sequence[tuple[float, float]], target_length: float
) -> list[tuple[float, float]]:
    result = [path[0]]
    remaining = target_length
    for start, end in zip(path, path[1:]):
        segment = _distance(start, end)
        if segment <= MIN_DISTANCE:
            continue
        if remaining >= segment:
            result.append(end)
            remaining -= segment
            continue
        fraction = remaining / segment
        result.append(
            (
                start[0] + fraction * (end[0] - start[0]),
                start[1] + fraction * (end[1] - start[1]),
            )
        )
        break
    if len(result) < 2:
        raise ARGuidanceError("A02 target path is too short.")
    return result


def _band_polygon(
    centerline: Sequence[tuple[float, float]], width: float
) -> list[tuple[float, float]]:
    upper: list[tuple[float, float]] = []
    lower: list[tuple[float, float]] = []
    for index, point in enumerate(centerline):
        previous = centerline[max(0, index - 1)]
        following = centerline[min(len(centerline) - 1, index + 1)]
        tangent_x = following[0] - previous[0]
        tangent_y = following[1] - previous[1]
        length = math.hypot(tangent_x, tangent_y)
        if length <= MIN_DISTANCE:
            raise ARGuidanceError("A02 path contains degenerate segments.")
        normal_x, normal_y = -tangent_y / length, tangent_x / length
        upper.append(
            (
                min(1.0, max(0.0, point[0] + width * normal_x)),
                min(1.0, max(0.0, point[1] + width * normal_y)),
            )
        )
        lower.append(
            (
                min(1.0, max(0.0, point[0] - width * normal_x)),
                min(1.0, max(0.0, point[1] - width * normal_y)),
            )
        )
    return upper + list(reversed(lower))


def build_a02_guidance(
    landmarks: Mapping[str, Any],
    personalized_action: Mapping[str, Any],
    side: str,
    *,
    source: str = "personalized_action",
) -> dict[str, Any]:
    """Build a narrow-band lower-lid target region, not a rendered makeup."""

    if side not in SIDES:
        raise ARGuidanceError(f"side must be one of {sorted(SIDES)}.")
    if not isinstance(landmarks, Mapping):
        raise ARGuidanceError("landmarks must be an object.")
    outer = _point(landmarks.get("eye_outer"), "eye_outer")
    raw_path = landmarks.get("lower_lid_path")
    if not isinstance(raw_path, Sequence) or isinstance(raw_path, (str, bytes)):
        raise ARGuidanceError("lower_lid_path must be an array of points.")
    path = [
        _point(value, f"lower_lid_path[{index}]")
        for index, value in enumerate(raw_path)
    ]
    if len(path) < 2:
        raise ARGuidanceError("lower_lid_path requires at least two points.")
    if _distance(outer, path[-1]) < _distance(outer, path[0]):
        path.reverse()
    segment_lengths = [
        _distance(start, end) for start, end in zip(path, path[1:])
    ]
    total_length = sum(segment_lengths)
    if total_length <= MIN_DISTANCE:
        raise ARGuidanceError("lower_lid_path must have non-zero length.")
    range_factor, intensity_factor = _a02_parameters(personalized_action)
    target_fraction = min(1.0, LOWER_LID_BASE_RANGE_FRACTION * range_factor)
    centerline = _path_prefix(path, total_length * target_fraction)
    polygon = _band_polygon(centerline, LOWER_LID_BAND_WIDTH_NORM)
    result = {
        "schema_version": SCHEMA_VERSION,
        "action_id": "A02",
        "guidance_type": "target_region",
        "side": side,
        "polygon": [_point_output(point) for point in polygon],
        "centerline": [_point_output(point) for point in centerline],
        "range_factor": range_factor,
        "intensity_factor": intensity_factor,
        "intensity_semantics": "metadata_only_not_ui_opacity",
        "range_semantics": {
            "baseline_lower_lid_fraction": LOWER_LID_BASE_RANGE_FRACTION,
            "applied_fraction": round(target_fraction, 12),
        },
        "source": source,
    }
    assert_strict_finite(result)
    return result


def _angular_difference(first: float, second: float) -> float:
    return abs((second - first + 180.0) % 360.0 - 180.0)


def evaluate_a04_stability(
    frames: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Measure consecutive A04 overlay jitter without applying smoothing."""

    if len(frames) < 2:
        raise ARGuidanceError("At least two A04 guidance frames are required.")
    anchors = [_point(frame.get("anchor"), "anchor") for frame in frames]
    endpoints = [_point(frame.get("endpoint"), "endpoint") for frame in frames]
    directions = [
        _finite_number(
            frame.get("direction_relative_to_eye_axis_deg"), "direction"
        )
        for frame in frames
    ]
    anchor_displacements = [
        _distance(first, second) for first, second in zip(anchors, anchors[1:])
    ]
    endpoint_displacements = [
        _distance(first, second)
        for first, second in zip(endpoints, endpoints[1:])
    ]
    direction_jitter = [
        _angular_difference(first, second)
        for first, second in zip(directions, directions[1:])
    ]

    def summary(values: Sequence[float]) -> dict[str, float]:
        return {
            "mean": round(mean(values), 12),
            "max": round(max(values), 12),
        }

    result = {
        "schema_version": SCHEMA_VERSION,
        "measurement": "a04_temporal_stability",
        "frame_count": len(frames),
        "smoothing_applied": False,
        "anchor_displacement_norm": summary(anchor_displacements),
        "endpoint_displacement_norm": summary(endpoint_displacements),
        "direction_jitter_deg": summary(direction_jitter),
    }
    assert_strict_finite(result)
    return result


def assert_strict_finite(value: Any, path: str = "guidance") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            assert_strict_finite(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            assert_strict_finite(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ARGuidanceError(f"{path} contains NaN or infinity.")
