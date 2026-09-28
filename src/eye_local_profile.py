"""Shared single-eye geometry for tutorial references and user faces.

EyeLocalProfile is deliberately parallel to Face Profile.  It measures one
eye in image coordinates and never changes or aliases the full-face schema.
The same :class:`EyeLocalKeypoints` contract is used for visual tutorial
annotations and MediaPipe-derived user points.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from .eye_landmarks import (
        SUBJECT_LEFT_BROW_INDICES,
        SUBJECT_LEFT_EYE_INDICES,
        SUBJECT_LEFT_EYE_RULE_INDICES,
        SUBJECT_RIGHT_BROW_INDICES,
        SUBJECT_RIGHT_EYE_INDICES,
        SUBJECT_RIGHT_EYE_RULE_INDICES,
        extract_brow_landmarks,
        extract_eye_landmarks,
        extract_rule_landmarks,
    )
    from .face_geometry import (
        GeometryError,
        Point2D,
        angle_at_vertex_deg,
        calculate_brow_eye_geometry,
        calculate_eye_geometry,
        calculate_lower_lid_space,
    )
except ImportError:  # Support: python src/eye_local_profile.py
    from eye_landmarks import (  # type: ignore
        SUBJECT_LEFT_BROW_INDICES,
        SUBJECT_LEFT_EYE_INDICES,
        SUBJECT_LEFT_EYE_RULE_INDICES,
        SUBJECT_RIGHT_BROW_INDICES,
        SUBJECT_RIGHT_EYE_INDICES,
        SUBJECT_RIGHT_EYE_RULE_INDICES,
        extract_brow_landmarks,
        extract_eye_landmarks,
        extract_rule_landmarks,
    )
    from face_geometry import (  # type: ignore
        GeometryError,
        Point2D,
        angle_at_vertex_deg,
        calculate_brow_eye_geometry,
        calculate_eye_geometry,
        calculate_lower_lid_space,
    )


VERSION = "0.1"
SOURCE_TYPES = frozenset(("tutorial_reference", "user_face"))
SIDES = frozenset(("left", "right"))


class EyeLocalProfileError(ValueError):
    """Raised when a single-eye profile cannot be measured safely."""


@dataclass(frozen=True)
class EyeLocalKeypoints:
    """One eye's shared semantic points in the same pixel coordinate space."""

    eye_inner: Point2D
    eye_outer: Point2D
    eye_upper: Point2D
    eye_lower: Point2D
    inner_upper: Point2D
    inner_lower: Point2D
    brow_references: tuple[Point2D, ...] | None = None
    lower_lid_points: tuple[Point2D, ...] | None = None
    lower_lid_references: tuple[Point2D, ...] | None = None


def _axis_angle_deg(inner: Point2D, outer: Point2D) -> float:
    """Return oriented inner-to-outer angle against image horizontal.

    Image y grows downward, so y is negated for conventional positive-up
    angles.  The oriented value is intentionally side-sensitive and primarily
    diagnostic; it does not replace Face Profile's anatomical eye-tail angle.
    """

    dx = outer.x - inner.x
    dy_up = inner.y - outer.y
    if dx == 0.0 and dy_up == 0.0:
        raise EyeLocalProfileError("eye width must be greater than zero.")
    return math.degrees(math.atan2(dy_up, dx))


def _validate_optional_groups(points: EyeLocalKeypoints) -> None:
    lower_groups = (points.lower_lid_points, points.lower_lid_references)
    if (lower_groups[0] is None) != (lower_groups[1] is None):
        raise EyeLocalProfileError(
            "lower_lid_points and lower_lid_references must both be present or null."
        )
    if points.brow_references is not None and not points.brow_references:
        raise EyeLocalProfileError("brow_references cannot be empty.")


def _strict_finite(value: Any) -> bool:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return True
    if isinstance(value, (int, float)):
        return math.isfinite(float(value))
    if isinstance(value, Mapping):
        return all(_strict_finite(item) for item in value.values())
    if isinstance(value, Sequence):
        return all(_strict_finite(item) for item in value)
    return True


def build_eye_local_profile(
    keypoints: EyeLocalKeypoints,
    *,
    source_type: str,
    side: str,
    quality: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the shared v0.1 profile from already identified semantic points."""

    if source_type not in SOURCE_TYPES:
        raise EyeLocalProfileError(
            f"source_type must be one of {sorted(SOURCE_TYPES)}."
        )
    if side not in SIDES:
        raise EyeLocalProfileError(f"side must be one of {sorted(SIDES)}.")
    _validate_optional_groups(keypoints)

    try:
        eye = calculate_eye_geometry(
            keypoints.eye_inner,
            keypoints.eye_outer,
            keypoints.eye_upper,
            keypoints.eye_lower,
        )
        inner_angle = angle_at_vertex_deg(
            keypoints.eye_inner,
            keypoints.inner_upper,
            keypoints.inner_lower,
        )
        lower_ratio = None
        if keypoints.lower_lid_points is not None:
            lower_ratio = calculate_lower_lid_space(
                keypoints.lower_lid_points,
                keypoints.lower_lid_references or (),
                eye.width_px,
            ).ratio
        brow_ratio = None
        if keypoints.brow_references is not None:
            brow_ratio = calculate_brow_eye_geometry(
                keypoints.brow_references,
                keypoints.eye_inner,
                keypoints.eye_outer,
                eye.width_px,
            ).ratio
    except GeometryError as exc:
        raise EyeLocalProfileError(str(exc)) from exc

    profile: dict[str, Any] = {
        "version": VERSION,
        "source_type": source_type,
        "side": side,
        "geometry": {
            "eye_width_px": round(eye.width_px, 6),
            "eye_height_px": round(eye.height_px, 6),
            "eye_width_height_ratio": round(eye.width_px / eye.height_px, 6),
            "eye_axis_angle_deg": round(
                _axis_angle_deg(keypoints.eye_inner, keypoints.eye_outer), 6
            ),
            "inner_corner_angle_deg": round(inner_angle, 6),
            "lower_lid_space_ratio_local": (
                round(lower_ratio, 6) if lower_ratio is not None else None
            ),
            "brow_eye_ratio_local": (
                round(brow_ratio, 6) if brow_ratio is not None else None
            ),
        },
        "quality": dict(quality or {}),
    }
    if not _strict_finite(profile):
        raise EyeLocalProfileError("EyeLocalProfile contains NaN or infinity.")
    return profile


def _pixel(point: Any, image_width: int, image_height: int) -> Point2D:
    return point.to_pixel(image_width, image_height)


def mediapipe_keypoints(
    face_landmarks: Sequence[Any],
    *,
    image_width: int,
    image_height: int,
    subject_side: str = "right",
    input_is_mirrored: bool = False,
) -> EyeLocalKeypoints:
    """Adapt MediaPipe 478 landmarks to the shared single-eye contract."""

    if subject_side not in SIDES:
        raise EyeLocalProfileError(f"subject_side must be one of {sorted(SIDES)}.")
    if image_width <= 1 or image_height <= 1:
        raise EyeLocalProfileError("image dimensions must be greater than one pixel.")

    eyes = extract_eye_landmarks(face_landmarks, input_is_mirrored)
    brows = extract_brow_landmarks(face_landmarks, input_is_mirrored)
    rules = extract_rule_landmarks(face_landmarks, input_is_mirrored)
    eye = getattr(eyes, subject_side)
    brow = getattr(brows, subject_side)
    rule = getattr(rules, subject_side)
    return EyeLocalKeypoints(
        eye_inner=_pixel(eye.inner_corner, image_width, image_height),
        eye_outer=_pixel(eye.outer_corner, image_width, image_height),
        eye_upper=_pixel(eye.upper_lid, image_width, image_height),
        eye_lower=_pixel(eye.lower_lid, image_width, image_height),
        inner_upper=_pixel(rule.upper_inner, image_width, image_height),
        inner_lower=_pixel(rule.lower_inner, image_width, image_height),
        brow_references=tuple(
            _pixel(point, image_width, image_height) for point in brow.points
        ),
        lower_lid_points=tuple(
            _pixel(point, image_width, image_height) for point in rule.lower_lid
        ),
        lower_lid_references=tuple(
            _pixel(point, image_width, image_height) for point in rule.infraorbital
        ),
    )


def build_eye_local_profile_from_mediapipe(
    face_landmarks: Sequence[Any],
    *,
    image_width: int,
    image_height: int,
    subject_side: str = "right",
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    """Build a user EyeLocalProfile without duplicating face inference."""

    keypoints = mediapipe_keypoints(
        face_landmarks,
        image_width=image_width,
        image_height=image_height,
        subject_side=subject_side,
        input_is_mirrored=input_is_mirrored,
    )
    image_side = subject_side if input_is_mirrored else (
        "right" if subject_side == "left" else "left"
    )
    use_left_group = (subject_side == "left") != input_is_mirrored
    eye_indices = (
        SUBJECT_LEFT_EYE_INDICES if use_left_group else SUBJECT_RIGHT_EYE_INDICES
    )
    rule_indices = (
        SUBJECT_LEFT_EYE_RULE_INDICES
        if use_left_group
        else SUBJECT_RIGHT_EYE_RULE_INDICES
    )
    brow_indices = (
        SUBJECT_LEFT_BROW_INDICES if use_left_group else SUBJECT_RIGHT_BROW_INDICES
    )
    indices = {
        "eye": eye_indices.__dict__,
        "inner_corner_neighbors": {
            "upper": rule_indices.upper_inner,
            "lower": rule_indices.lower_inner,
        },
        "lower_lid": list(rule_indices.lower_lid),
        "infraorbital": list(rule_indices.infraorbital),
        "brow": list(brow_indices),
    }
    return build_eye_local_profile(
        keypoints,
        source_type="user_face",
        side=subject_side,
        quality={
            "landmark_source": "mediapipe_face_landmarker_478",
            "visual_estimation": False,
            "human_confirmed": False,
            "input_is_mirrored": input_is_mirrored,
            "image_side": image_side,
            "subject_side": subject_side,
            "is_directly_comparable": True,
            "landmark_indices": indices,
        },
    )


def save_eye_local_profile(path: Path | str, value: Mapping[str, Any]) -> None:
    """Write strict RFC-compatible JSON (NaN and infinity are rejected)."""

    if not _strict_finite(value):
        raise EyeLocalProfileError("EyeLocalProfile contains NaN or infinity.")
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
