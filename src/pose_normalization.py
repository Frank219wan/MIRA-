"""Lightweight two-dimensional face-roll normalization.

The module is independent of MediaPipe and OpenCV.  Callers supply pixel-space
landmarks and the corner indices used to define the two eye centers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

try:
    from .face_geometry import Point2D, mean_point
except ImportError:  # Support direct module execution/import from src.
    from face_geometry import Point2D, mean_point  # type: ignore


class PoseNormalizationError(ValueError):
    """Raised when a stable roll axis cannot be calculated."""


@dataclass(frozen=True)
class RollNormalizationResult:
    """Successful roll estimate and rotated pixel-space landmarks."""

    roll_angle_deg: float
    rotation_applied_deg: float
    face_center: Point2D
    left_eye_center: Point2D
    right_eye_center: Point2D
    normalized_points: Mapping[int, Point2D]


def rotate_point(
    point: Point2D,
    center: Point2D,
    angle_deg: float,
) -> Point2D:
    """Rotate one image-coordinate point around ``center`` by ``angle_deg``."""

    if not math.isfinite(angle_deg):
        raise PoseNormalizationError("Rotation angle must be finite.")
    angle_rad = math.radians(angle_deg)
    cosine = math.cos(angle_rad)
    sine = math.sin(angle_rad)
    offset_x = point.x - center.x
    offset_y = point.y - center.y
    return Point2D(
        x=center.x + cosine * offset_x - sine * offset_y,
        y=center.y + sine * offset_x + cosine * offset_y,
    )


def _indexed_center(
    points: Mapping[int, Point2D],
    indices: Sequence[int],
    side: str,
) -> Point2D:
    if len(indices) < 2:
        raise PoseNormalizationError(
            f"{side} eye center requires at least two landmark indices."
        )
    missing = [index for index in indices if index not in points]
    if missing:
        raise PoseNormalizationError(
            f"Missing {side} eye-center landmark indices: {missing}"
        )
    return mean_point(tuple(points[index] for index in indices))


def normalize_face_roll(
    points: Mapping[int, Point2D],
    *,
    left_eye_center_indices: Sequence[int],
    right_eye_center_indices: Sequence[int],
    minimum_eye_center_distance_px: float = 1e-6,
) -> RollNormalizationResult:
    """Rotate landmarks so the screen-left-to-right eye-center axis is level.

    ``left`` and ``right`` in the arguments retain anatomical semantics.  The
    two calculated centers are sorted by image x only for estimating a
    direction with positive dx; this makes the roll sign consistent for both
    mirrored and unmirrored inputs.
    """

    if not points:
        raise PoseNormalizationError("At least one landmark is required.")
    if (
        not math.isfinite(minimum_eye_center_distance_px)
        or minimum_eye_center_distance_px <= 0.0
    ):
        raise PoseNormalizationError(
            "Minimum eye-center distance must be positive and finite."
        )

    left_center = _indexed_center(
        points, left_eye_center_indices, "left"
    )
    right_center = _indexed_center(
        points, right_eye_center_indices, "right"
    )
    face_center = mean_point((left_center, right_center))
    screen_left, screen_right = sorted(
        (left_center, right_center), key=lambda point: point.x
    )
    delta_x = screen_right.x - screen_left.x
    delta_y = screen_right.y - screen_left.y
    eye_center_distance = math.hypot(delta_x, delta_y)
    if eye_center_distance <= minimum_eye_center_distance_px:
        raise PoseNormalizationError(
            "Eye centers are too close to define a stable roll axis."
        )

    roll_angle_deg = math.degrees(math.atan2(delta_y, delta_x))
    if not math.isfinite(roll_angle_deg):
        raise PoseNormalizationError("Calculated roll angle is not finite.")
    rotation_deg = -roll_angle_deg
    normalized_points = {
        index: rotate_point(point, face_center, rotation_deg)
        for index, point in points.items()
    }
    return RollNormalizationResult(
        roll_angle_deg=roll_angle_deg,
        rotation_applied_deg=rotation_deg,
        face_center=face_center,
        left_eye_center=left_center,
        right_eye_center=right_center,
        normalized_points=normalized_points,
    )
