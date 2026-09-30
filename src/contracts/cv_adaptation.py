"""Backend handoff for the authoritative CV Face Profile v0.3 payload."""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

from pydantic import Field, field_validator

from src.face_profile import FACE_PROFILE_VERSION

from .common import ContractModel


def _finite_number(value: Any, path: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"Face Profile field must be numeric: {path}")
    if not math.isfinite(float(value)):
        raise ValueError(f"Face Profile field must be finite: {path}")


def _validate_cv_face_profile_v03(value: dict[str, Any]) -> dict[str, Any]:
    """Validate every required v0.3 field without creating a parallel model."""
    required_numbers = (
        ("eye_geometry.eye_tail_angle.left", ("eye_geometry", "eye_tail_angle", "left")),
        ("eye_geometry.eye_tail_angle.right", ("eye_geometry", "eye_tail_angle", "right")),
        ("eye_geometry.eye_tail_angle.mean", ("eye_geometry", "eye_tail_angle", "mean")),
        ("eye_geometry.eye_spacing_ratio", ("eye_geometry", "eye_spacing_ratio")),
        ("eye_geometry.relative_eye_length.left", ("eye_geometry", "relative_eye_length", "left")),
        ("eye_geometry.relative_eye_length.right", ("eye_geometry", "relative_eye_length", "right")),
        ("eye_geometry.relative_eye_length.mean", ("eye_geometry", "relative_eye_length", "mean")),
        ("eye_geometry.eye_width_height_ratio.left", ("eye_geometry", "eye_width_height_ratio", "left")),
        ("eye_geometry.eye_width_height_ratio.right", ("eye_geometry", "eye_width_height_ratio", "right")),
        ("eye_geometry.eye_width_height_ratio.mean", ("eye_geometry", "eye_width_height_ratio", "mean")),
        ("eye_geometry.brow_eye_ratio.left", ("eye_geometry", "brow_eye_ratio", "left")),
        ("eye_geometry.brow_eye_ratio.right", ("eye_geometry", "brow_eye_ratio", "right")),
        ("eye_geometry.brow_eye_ratio.mean", ("eye_geometry", "brow_eye_ratio", "mean")),
        ("eye_geometry.lower_lid_space_ratio.left", ("eye_geometry", "lower_lid_space_ratio", "left")),
        ("eye_geometry.lower_lid_space_ratio.right", ("eye_geometry", "lower_lid_space_ratio", "right")),
        ("eye_geometry.lower_lid_space_ratio.mean", ("eye_geometry", "lower_lid_space_ratio", "mean")),
        ("eye_geometry.inner_corner_angle.left_deg", ("eye_geometry", "inner_corner_angle", "left_deg")),
        ("eye_geometry.inner_corner_angle.right_deg", ("eye_geometry", "inner_corner_angle", "right_deg")),
        ("eye_geometry.inner_corner_angle.mean_deg", ("eye_geometry", "inner_corner_angle", "mean_deg")),
        ("symmetry.eye_width", ("symmetry", "eye_width")),
        ("symmetry.eye_height", ("symmetry", "eye_height")),
        ("symmetry.eye_aspect_ratio", ("symmetry", "eye_aspect_ratio")),
        ("symmetry.eye_tail_angle_difference", ("symmetry", "eye_tail_angle_difference")),
    )
    for label, path in required_numbers:
        current: Any = value
        for key in path:
            if not isinstance(current, dict) or key not in current:
                raise ValueError(f"Face Profile missing required field: {label}")
            current = current[key]
        _finite_number(current, label)
    if not isinstance(value.get("raw_geometry_reference"), dict):
        raise ValueError("Face Profile missing raw_geometry_reference")
    if not isinstance(value.get("confidence"), dict):
        raise ValueError("Face Profile missing confidence")
    confidence = value["confidence"]
    for field in ("pose_normalized", "expression_controlled"):
        if not isinstance(confidence.get(field), bool):
            raise ValueError(f"Face Profile confidence.{field} must be boolean")
    return value


SUPPORTED_CV_FACE_PROFILE_VALIDATORS: dict[
    str, Callable[[dict[str, Any]], dict[str, Any]]
] = {FACE_PROFILE_VERSION: _validate_cv_face_profile_v03}


def validate_cv_face_profile(value: Any) -> dict[str, Any]:
    """Version-dispatching adapter for CV-owned Face Profile payloads.

    The returned dictionary is the original payload. Add future CV versions to
    ``SUPPORTED_CV_FACE_PROFILE_VALIDATORS`` rather than reshaping this contract.
    """
    if not isinstance(value, dict):
        raise ValueError("Face Profile must be a JSON object")
    version = value.get("version")
    if not isinstance(version, str):
        raise ValueError("Face Profile version must be a string")
    validator = SUPPORTED_CV_FACE_PROFILE_VALIDATORS.get(version)
    if validator is None:
        supported = ", ".join(sorted(SUPPORTED_CV_FACE_PROFILE_VALIDATORS))
        raise ValueError(
            f"Unsupported Face Profile version: {version!r}; supported: {supported}"
        )
    return validator(value)


class CVAdaptation(ContractModel):
    """Input for a future adaptation service; no adaptation occurs yet."""

    schema_version: str = "1.0"
    recipe_id: str = Field(min_length=1)
    face_profile: dict[str, Any]

    @field_validator("face_profile")
    @classmethod
    def validate_face_profile(cls, value: Any) -> dict[str, Any]:
        return validate_cv_face_profile(value)
