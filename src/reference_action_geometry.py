"""Pure geometry for manually annotated local-eye tutorial actions."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping


VERSION = "0.1"
REQUIRED_POINTS = ("eye_inner", "eye_outer", "eyeliner_tip")
OPTIONAL_POINTS = (
    "eyeliner_start",
    "upper_lash_outer_reference",
    "before_eye_inner",
    "before_eye_outer",
)
MIN_EYE_WIDTH_PX = 1e-6  # Numerical degeneracy guard, not a product threshold.


class ReferenceActionGeometryError(ValueError):
    """Raised for missing, degenerate, or non-finite annotations."""


def _point(annotation: Mapping[str, Any], name: str) -> tuple[float, float]:
    value = annotation.get(name)
    if not isinstance(value, Mapping):
        raise ReferenceActionGeometryError(f"Missing required point: {name}")
    coordinates = []
    for axis in ("x", "y"):
        number = value.get(axis)
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise ReferenceActionGeometryError(f"{name}.{axis} must be numeric.")
        number = float(number)
        if not math.isfinite(number):
            raise ReferenceActionGeometryError(f"{name}.{axis} must be finite.")
        coordinates.append(number)
    return coordinates[0], coordinates[1]


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(second[0] - first[0], second[1] - first[1])


def build_reference_action_geometry(
    annotation: Mapping[str, Any],
    *,
    reference_id: str = "cat_eye_main_demo",
    source_image: str | None = None,
    crop_roi: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Measure A04 from a single eye; image y increases downward.

    Signed angle is atan2(-sign(axis_x)*screen_cross, dot). The sign(axis_x)
    term makes a tip visually above the eye axis positive for either eye side.
    This assumes the tutorial image is approximately upright, and remains
    stable under small joint image rotations that do not reverse axis_x.
    """

    if not isinstance(annotation, Mapping):
        raise ReferenceActionGeometryError("annotation must be an object.")
    if not isinstance(reference_id, str) or not reference_id.strip():
        raise ReferenceActionGeometryError("reference_id must be non-empty.")

    points = {name: _point(annotation, name) for name in REQUIRED_POINTS}
    for name in OPTIONAL_POINTS:
        if name in annotation and annotation[name] is not None:
            points[name] = _point(annotation, name)

    inner = points["eye_inner"]
    outer = points["eye_outer"]
    tip = points["eyeliner_tip"]
    eye_width = _distance(inner, outer)
    if eye_width <= MIN_EYE_WIDTH_PX:
        raise ReferenceActionGeometryError("eye width is zero or too close to zero.")
    extension_px = _distance(outer, tip)
    if extension_px <= MIN_EYE_WIDTH_PX:
        raise ReferenceActionGeometryError(
            "eyeliner_tip must be distinct from eye_outer."
        )

    axis_x, axis_y = outer[0] - inner[0], outer[1] - inner[1]
    if abs(axis_x) <= MIN_EYE_WIDTH_PX:
        raise ReferenceActionGeometryError(
            "A vertical eye axis cannot define visually upward direction."
        )
    liner_x, liner_y = tip[0] - outer[0], tip[1] - outer[1]
    dot = axis_x * liner_x + axis_y * liner_y
    screen_cross = axis_x * liner_y - axis_y * liner_x
    direction = math.degrees(
        math.atan2(-math.copysign(1.0, axis_x) * screen_cross, dot)
    )
    start_ratio = None
    if "eyeliner_start" in points:
        start = points["eyeliner_start"]
        start_x, start_y = start[0] - inner[0], start[1] - inner[1]
        start_ratio = (start_x * axis_x + start_y * axis_y) / (
            axis_x * axis_x + axis_y * axis_y
        )
    numbers = (eye_width, extension_px, extension_px / eye_width, direction)
    if not all(math.isfinite(value) for value in numbers) or (
        start_ratio is not None and not math.isfinite(start_ratio)
    ):
        raise ReferenceActionGeometryError("Geometry contains NaN or infinity.")

    result: dict[str, Any] = {
        "version": VERSION,
        "reference_id": reference_id,
        "action_id": "A04",
        "source_type": "local_eye_tutorial",
        "annotation": {
            name: {"x": round(point[0], 6), "y": round(point[1], 6)}
            for name, point in points.items()
        },
        "geometry": {
            "eye_width_px": round(eye_width, 6),
            "eyeliner_extension_px": round(extension_px, 6),
            "eyeliner_extension_ratio": round(extension_px / eye_width, 6),
            "direction_relative_to_eye_axis_deg": round(direction, 6),
            "start_position_ratio": (
                round(start_ratio, 6) if start_ratio is not None else None
            ),
        },
        "quality": {
            "annotation_complete": True,
            "source_is_full_face": False,
            "manual_annotation": True,
        },
    }
    if source_image is not None or crop_roi is not None:
        result["source"] = {
            "image": source_image,
            "crop_roi_original_image_px": dict(crop_roi) if crop_roi else None,
            "annotation_coordinate_space": "cropped_image_pixels",
        }
    return result


def save_reference_action_geometry(path: Path | str, value: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
