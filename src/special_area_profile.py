"""Special Area Preference v0.1 data contract.

This module records only regions that a user selected and the treatment the
user requested.  It deliberately performs no detection, diagnosis, severity
assessment, or preference inference.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"
VALID_PREFERENCES = ("KEEP", "BLEND", "COVER", "HIGHLIGHT")
# ``subject_left`` and ``subject_right`` always describe the user's own side,
# never the left or right side of the displayed image.
VALID_LOCATIONS = (
    "subject_left_cheek",
    "subject_right_cheek",
    "forehead",
    "nose",
    "chin",
    "upper_lip",
    "other",
)


class SpecialAreaProfileError(ValueError):
    """Raised when a SpecialAreaProfile cannot satisfy the v0.1 contract."""


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SpecialAreaProfileError(f"{field} must be a non-empty string.")
    return value.strip()


def _normalized_coordinate(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SpecialAreaProfileError(f"{field} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise SpecialAreaProfileError(f"{field} must be finite.")
    if not 0.0 <= number <= 1.0:
        raise SpecialAreaProfileError(f"{field} must be between 0 and 1.")
    return number


def normalize_pixel_polygon(
    pixel_points: Sequence[Sequence[int | float]],
    image_width: int,
    image_height: int,
) -> list[dict[str, float]]:
    """Convert pixel points to normalized points using x/width and y/height."""

    if image_width <= 0 or image_height <= 0:
        raise SpecialAreaProfileError("Image width and height must be positive.")
    if len(pixel_points) < 3:
        raise SpecialAreaProfileError("polygon must contain at least 3 points.")

    normalized: list[dict[str, float]] = []
    for index, point in enumerate(pixel_points):
        if not isinstance(point, Sequence) or len(point) != 2:
            raise SpecialAreaProfileError(
                f"polygon[{index}] must contain an x and y coordinate."
            )
        x, y = point
        if isinstance(x, bool) or isinstance(y, bool):
            raise SpecialAreaProfileError("Pixel coordinates must be numeric.")
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise SpecialAreaProfileError("Pixel coordinates must be numeric.")
        x_number, y_number = float(x), float(y)
        if not math.isfinite(x_number) or not math.isfinite(y_number):
            raise SpecialAreaProfileError("Pixel coordinates must be finite.")
        if not 0 <= x_number < image_width or not 0 <= y_number < image_height:
            raise SpecialAreaProfileError("Pixel coordinates must be inside the image.")
        normalized.append(
            {
                "x_norm": x_number / image_width,
                "y_norm": y_number / image_height,
            }
        )
    return normalized


def build_special_area(
    *,
    area_id: str,
    user_label: str,
    location: str,
    preference: str,
    polygon: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build and validate one user-selected area."""

    area = {
        "area_id": area_id,
        "source": "user_selected",
        "user_label": user_label,
        "label_source": "user_provided",
        "location": location,
        "preference": preference,
        "polygon": list(polygon),
    }
    return _validate_area(area, 0)


def _validate_area(area: Mapping[str, Any], index: int) -> dict[str, Any]:
    required = {
        "area_id",
        "source",
        "user_label",
        "label_source",
        "location",
        "preference",
        "polygon",
    }
    if not isinstance(area, Mapping):
        raise SpecialAreaProfileError(f"areas[{index}] must be an object.")
    unexpected = set(area) - required
    missing = required - set(area)
    if missing:
        raise SpecialAreaProfileError(
            f"areas[{index}] is missing fields: {', '.join(sorted(missing))}."
        )
    if unexpected:
        raise SpecialAreaProfileError(
            f"areas[{index}] has unsupported fields: {', '.join(sorted(unexpected))}."
        )

    area_id = _non_empty_string(area["area_id"], f"areas[{index}].area_id")
    if area["source"] != "user_selected":
        raise SpecialAreaProfileError("source must be user_selected.")
    user_label = area["user_label"]
    if not isinstance(user_label, str):
        raise SpecialAreaProfileError("user_label must be a string (empty is allowed).")
    if area["label_source"] != "user_provided":
        raise SpecialAreaProfileError("label_source must be user_provided.")
    location = area["location"]
    if location not in VALID_LOCATIONS:
        raise SpecialAreaProfileError(
            "location must be one of: " + ", ".join(VALID_LOCATIONS) + "."
        )
    preference = area["preference"]
    if preference not in VALID_PREFERENCES:
        raise SpecialAreaProfileError(
            "preference must be one of: " + ", ".join(VALID_PREFERENCES) + "."
        )

    polygon = area["polygon"]
    if not isinstance(polygon, list) or len(polygon) < 3:
        raise SpecialAreaProfileError("polygon must contain at least 3 points.")
    validated_polygon: list[dict[str, float]] = []
    for point_index, point in enumerate(polygon):
        if not isinstance(point, Mapping) or set(point) != {"x_norm", "y_norm"}:
            raise SpecialAreaProfileError(
                f"areas[{index}].polygon[{point_index}] must contain only "
                "x_norm and y_norm."
            )
        validated_polygon.append(
            {
                "x_norm": _normalized_coordinate(
                    point["x_norm"],
                    f"areas[{index}].polygon[{point_index}].x_norm",
                ),
                "y_norm": _normalized_coordinate(
                    point["y_norm"],
                    f"areas[{index}].polygon[{point_index}].y_norm",
                ),
            }
        )

    return {
        "area_id": area_id,
        "source": "user_selected",
        "user_label": user_label.strip(),
        "label_source": "user_provided",
        "location": location,
        "preference": preference,
        "polygon": validated_polygon,
    }


def validate_special_area_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and return a clean SpecialAreaProfile v0.1 dictionary."""

    if not isinstance(profile, Mapping):
        raise SpecialAreaProfileError("SpecialAreaProfile must be an object.")
    required = {"schema_version", "image_sample_id", "areas"}
    if set(profile) != required:
        missing = required - set(profile)
        unexpected = set(profile) - required
        details = []
        if missing:
            details.append("missing " + ", ".join(sorted(missing)))
        if unexpected:
            details.append("unsupported " + ", ".join(sorted(unexpected)))
        raise SpecialAreaProfileError("Invalid profile fields: " + "; ".join(details) + ".")
    if profile["schema_version"] != SCHEMA_VERSION:
        raise SpecialAreaProfileError(f"schema_version must be {SCHEMA_VERSION}.")
    image_sample_id = _non_empty_string(profile["image_sample_id"], "image_sample_id")
    if "/" in image_sample_id or "\\" in image_sample_id:
        raise SpecialAreaProfileError("image_sample_id must not contain a path.")
    areas = profile["areas"]
    if not isinstance(areas, list) or not areas:
        raise SpecialAreaProfileError("areas must be a non-empty array.")
    validated_areas = [_validate_area(area, index) for index, area in enumerate(areas)]
    area_ids = [area["area_id"] for area in validated_areas]
    if len(set(area_ids)) != len(area_ids):
        raise SpecialAreaProfileError("area_id values must be unique.")
    return {
        "schema_version": SCHEMA_VERSION,
        "image_sample_id": image_sample_id,
        "areas": validated_areas,
    }


def build_special_area_profile(
    image_sample_id: str,
    areas: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build a profile supporting one or more user-selected areas."""

    return validate_special_area_profile(
        {
            "schema_version": SCHEMA_VERSION,
            "image_sample_id": image_sample_id,
            "areas": list(areas),
        }
    )


def save_strict_json(output_path: Path, payload: Mapping[str, Any]) -> None:
    """Write UTF-8 JSON while rejecting NaN and Infinity."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                payload,
                output_file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            output_file.write("\n")
    except (OSError, ValueError) as exc:
        raise SpecialAreaProfileError(
            f"Could not write strict JSON {output_path.name}: {exc}"
        ) from exc
