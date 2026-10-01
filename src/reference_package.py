"""Portable tutorial reference packages for Main Demo personalization."""

from __future__ import annotations

import copy
import json
import math
import re
from pathlib import Path
from typing import Any, Mapping

from .face_scan_aggregator import validate_face_profile
from .main_demo_personalization_cases import calculate_case
from .reference_action_adapter import adapt_a04_action


SCHEMA_VERSION = "0.1"
SOURCE_MODES = frozenset(("existing_reference", "video_reference"))
FORBIDDEN_PORTABLE_TEXT = (
    "/users/",
    "data:image",
    ";base64,",
)
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


class ReferencePackageError(ValueError):
    """Raised when a reference package is invalid or non-portable."""


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferencePackageError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ReferencePackageError(f"{label} must be finite.")
    return number


def _assert_finite(value: Any, path: str = "reference_package") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _assert_finite(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_finite(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ReferencePackageError(f"{path} contains NaN or infinity.")


def _assert_portable(value: Mapping[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False).lower()
    matches = [token for token in FORBIDDEN_PORTABLE_TEXT if token in serialized]
    if matches:
        raise ReferencePackageError(
            "Reference Package contains non-portable content: "
            + ", ".join(matches)
        )

    def inspect(nested: Any, path: str) -> None:
        if isinstance(nested, Mapping):
            for key, item in nested.items():
                if "exif" in str(key).lower():
                    raise ReferencePackageError(
                        f"Reference Package cannot contain EXIF: {path}.{key}"
                    )
                inspect(item, f"{path}.{key}")
        elif isinstance(nested, (list, tuple)):
            for index, item in enumerate(nested):
                inspect(item, f"{path}[{index}]")
        elif isinstance(nested, str):
            lower = nested.lower()
            if (
                nested.startswith("/")
                or re.match(r"^[a-zA-Z]:[\\/]", nested)
                or lower.endswith(IMAGE_SUFFIXES)
            ):
                raise ReferencePackageError(
                    f"Reference Package contains a local/image path: {path}"
                )

    inspect(value, "reference_package")


def _timestamps(value: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ReferencePackageError("timestamps must be an object.")
    result = {
        key: _finite_number(value.get(key), f"timestamps.{key}")
        for key in ("before_sec", "A04_sec", "after_sec")
    }
    if any(timestamp < 0.0 for timestamp in result.values()):
        raise ReferencePackageError("timestamps cannot be negative.")
    if not result["before_sec"] <= result["A04_sec"] <= result["after_sec"]:
        raise ReferencePackageError(
            "timestamps must satisfy before_sec <= A04_sec <= after_sec."
        )
    return result


def _safe_reference_action(
    reference_action_geometry: Mapping[str, Any],
) -> dict[str, Any]:
    # The existing adapter is the canonical structural validator for A04 v0.1.
    adapt_a04_action(
        reference_action_geometry,
        {"action_id": "A04", "parameters": {}},
    )
    safe_keys = (
        "version",
        "reference_id",
        "action_id",
        "source_type",
        "annotation",
        "geometry",
        "quality",
    )
    return {
        key: copy.deepcopy(reference_action_geometry[key])
        for key in safe_keys
        if key in reference_action_geometry
    }


def build_reference_package(
    *,
    tutorial_id: str,
    video_filename: str,
    timestamps: Mapping[str, Any],
    blogger_face_profile: Mapping[str, Any],
    reference_action_geometry: Mapping[str, Any],
    after_frame_available: bool,
) -> dict[str, Any]:
    """Build a portable v0.1 package from video-derived CV results."""

    if not isinstance(tutorial_id, str) or not tutorial_id.strip():
        raise ReferencePackageError("tutorial_id must be a non-empty string.")
    if not isinstance(video_filename, str) or not video_filename.strip():
        raise ReferencePackageError("video_filename must be a non-empty string.")
    filename = Path(video_filename).name
    if filename in ("", ".", ".."):
        raise ReferencePackageError("video_filename must identify a file.")
    if not isinstance(after_frame_available, bool):
        raise ReferencePackageError("after_frame_available must be boolean.")
    try:
        validate_face_profile(blogger_face_profile)
    except ValueError as exc:
        raise ReferencePackageError(str(exc)) from exc
    profile = copy.deepcopy(dict(blogger_face_profile))
    profile["raw_geometry_reference"] = {
        "source": "tutorial_video_before_frame"
    }
    safe_action = _safe_reference_action(reference_action_geometry)
    geometry = safe_action.get("geometry")
    if not isinstance(geometry, Mapping):
        raise ReferencePackageError("Reference A04 geometry is missing.")
    _finite_number(
        geometry.get("start_position_ratio"),
        "reference_actions.A04.geometry.start_position_ratio",
    )
    package = {
        "schema_version": SCHEMA_VERSION,
        "mode": "video_reference",
        "tutorial_id": tutorial_id,
        "source": {
            "type": "video",
            "video_filename": filename,
        },
        "timestamps": _timestamps(timestamps),
        "blogger_face_profile": profile,
        "reference_actions": {
            "A04": safe_action
        },
        "target": {
            "after_frame_available": after_frame_available,
        },
    }
    _assert_finite(package)
    _assert_portable(package)
    return package


def package_existing_reference(
    fixture: Mapping[str, Any],
    *,
    fixture_filename: str = "main_demo_reference.json",
) -> dict[str, Any]:
    """Normalize the stable Main Demo fixture into the package interface."""

    reference_id = fixture.get("reference_id")
    p0 = fixture.get("blogger_face_profile_p0")
    actions = fixture.get("reference_action")
    if not isinstance(reference_id, str) or not reference_id:
        raise ReferencePackageError("Reference fixture is missing reference_id.")
    if not isinstance(p0, Mapping) or not isinstance(actions, Mapping):
        raise ReferencePackageError(
            "Reference fixture is missing blogger P0 or reference_action."
        )
    a04 = actions.get("A04")
    if not isinstance(a04, Mapping):
        raise ReferencePackageError("Reference fixture is missing A04.")
    profile = {
        "version": "0.3",
        "source_type": "safe_fixture",
        "eye_geometry": {
            "eye_tail_angle": {
                "mean": _finite_number(
                    p0.get("eye_tail_angle_mean"), "eye_tail_angle_mean"
                )
            },
            "relative_eye_length": {
                "mean": _finite_number(
                    p0.get("relative_eye_length_mean"),
                    "relative_eye_length_mean",
                )
            },
            "lower_lid_space_ratio": {
                "mean": _finite_number(
                    p0.get("lower_lid_space_ratio_mean"),
                    "lower_lid_space_ratio_mean",
                )
            },
        },
    }
    package = {
        "schema_version": SCHEMA_VERSION,
        "mode": "existing_reference",
        "tutorial_id": reference_id,
        "source": {
            "type": "safe_fixture",
            "fixture_filename": Path(fixture_filename).name,
        },
        "timestamps": None,
        "blogger_face_profile": profile,
        "reference_actions": {"A04": copy.deepcopy(dict(a04))},
        "target": {"after_frame_available": False},
    }
    _assert_finite(package)
    _assert_portable(package)
    return package


def reference_a04_parameters(package: Mapping[str, Any]) -> dict[str, float]:
    """Return a single parameter shape for either reference source mode."""

    mode = package.get("mode")
    if mode not in SOURCE_MODES:
        raise ReferencePackageError(
            f"mode must be one of {sorted(SOURCE_MODES)}."
        )
    actions = package.get("reference_actions")
    if not isinstance(actions, Mapping) or not isinstance(
        actions.get("A04"), Mapping
    ):
        raise ReferencePackageError("Reference Package is missing A04.")
    a04 = actions["A04"]
    if mode == "video_reference":
        geometry = a04.get("geometry")
        if not isinstance(geometry, Mapping):
            raise ReferencePackageError("Video reference A04 geometry is missing.")
        source = geometry
        keys = {
            "direction_relative_to_eye_axis_deg": (
                "direction_relative_to_eye_axis_deg"
            ),
            "reference_extension_ratio": "eyeliner_extension_ratio",
            "start_position_ratio": "start_position_ratio",
        }
    else:
        source = a04
        keys = {
            "direction_relative_to_eye_axis_deg": (
                "direction_relative_to_eye_axis_deg"
            ),
            "reference_extension_ratio": "reference_extension_ratio",
            "start_position_ratio": "start_position_ratio",
        }
    return {
        output_key: _finite_number(source.get(source_key), output_key)
        for output_key, source_key in keys.items()
    }


def personalize_reference_package(
    package: Mapping[str, Any],
    user_face_profile: Mapping[str, Any],
    *,
    sample_id: str,
) -> dict[str, Any]:
    """Run the frozen Main Demo relative mapping and validation dead zone."""

    blogger_profile = package.get("blogger_face_profile")
    if not isinstance(blogger_profile, Mapping):
        raise ReferencePackageError(
            "Reference Package is missing blogger_face_profile."
        )
    if not isinstance(sample_id, str) or not sample_id.strip():
        raise ReferencePackageError("sample_id must be a non-empty string.")
    result = calculate_case(
        blogger_profile,
        user_face_profile,
        reference_a04_parameters(package),
        case=sample_id.replace("_", ""),
        dead_zone_enabled=True,
    )
    _assert_finite(result)
    return result


def save_reference_package(path: Path | str, value: Mapping[str, Any]) -> None:
    """Write strict JSON after rechecking privacy and finite values."""

    _assert_finite(value)
    _assert_portable(value)
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
