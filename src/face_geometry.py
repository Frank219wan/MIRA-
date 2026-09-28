"""Pure 2D geometry for facial measurements.

This module intentionally has no MediaPipe or OpenCV dependency. Coordinates
are supplied by callers, so the formulas can be tested independently from face
inference and reused by later profile-building stages.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


class GeometryError(ValueError):
    """Raised when a geometric measurement cannot be computed safely."""


@dataclass(frozen=True)
class Point2D:
    x: float
    y: float

    def __post_init__(self) -> None:
        if not math.isfinite(self.x) or not math.isfinite(self.y):
            raise GeometryError("Point coordinates must be finite numbers.")


@dataclass(frozen=True)
class EyeGeometry:
    width_px: float
    height_px: float
    aspect_ratio: float


@dataclass(frozen=True)
class EyeSpacingGeometry:
    inner_eye_distance_px: float
    mean_eye_width_px: float
    eye_spacing_ratio: float


@dataclass(frozen=True)
class BrowEyeGeometry:
    """Distance from a multi-point brow reference to the eye axis."""

    reference_point: Point2D
    eye_axis_projection: Point2D
    distance_px: float
    ratio: float


@dataclass(frozen=True)
class EyeAsymmetryGeometry:
    """Continuous left/right differences; no categorical judgement."""

    eye_width_asymmetry: float
    eye_height_asymmetry: float
    eye_aspect_ratio_asymmetry: float
    eye_tail_angle_difference_deg: float


@dataclass(frozen=True)
class RelativeEyeLengthGeometry:
    """Eye dimensions normalized by face width and eye height."""

    face_width_px: float
    relative_eye_length_left: float
    relative_eye_length_right: float
    relative_eye_length_mean: float
    eye_width_height_ratio_left: float
    eye_width_height_ratio_right: float
    eye_width_height_ratio_mean: float


@dataclass(frozen=True)
class LowerLidSpaceGeometry:
    """Mean lower-lid-to-infraorbital distance and eye-width ratio."""

    segment_distances_px: tuple[float, ...]
    space_px: float
    ratio: float


def euclidean_distance(point_a: Point2D, point_b: Point2D) -> float:
    """Return the two-dimensional Euclidean distance between two points."""
    return math.hypot(point_b.x - point_a.x, point_b.y - point_a.y)


def eye_tail_angle_deg(
    inner_corner: Point2D,
    outer_corner: Point2D,
) -> float:
    """Return the anatomical inner-to-outer eye-axis angle in degrees.

    Image y grows downward, so ``inner.y - outer.y`` converts the vertical
    component to a conventional upward-positive axis. ``abs(dx)`` makes the
    definition anatomical and mirror-invariant: positive always means the
    person's outer corner is higher than their inner corner.
    """
    dx_outward = abs(outer_corner.x - inner_corner.x)
    dy_upward = inner_corner.y - outer_corner.y
    if dx_outward == 0.0 and dy_upward == 0.0:
        raise GeometryError("Eye inner and outer corners must be distinct.")
    return math.degrees(math.atan2(dy_upward, dx_outward))


def mean_point(points: Sequence[Point2D]) -> Point2D:
    """Return the centroid of one or more finite two-dimensional points."""
    if not points:
        raise GeometryError("At least one point is required.")
    return Point2D(
        x=sum(point.x for point in points) / len(points),
        y=sum(point.y for point in points) / len(points),
    )


def project_point_onto_line(
    point: Point2D,
    line_start: Point2D,
    line_end: Point2D,
) -> Point2D:
    """Project a point onto the infinite line through two distinct points."""
    axis_x = line_end.x - line_start.x
    axis_y = line_end.y - line_start.y
    squared_length = axis_x * axis_x + axis_y * axis_y
    if squared_length <= 0.0:
        raise GeometryError("Projection line endpoints must be distinct.")
    scale = (
        (point.x - line_start.x) * axis_x
        + (point.y - line_start.y) * axis_y
    ) / squared_length
    return Point2D(
        x=line_start.x + scale * axis_x,
        y=line_start.y + scale * axis_y,
    )


def calculate_brow_eye_geometry(
    brow_points: Sequence[Point2D],
    inner_corner: Point2D,
    outer_corner: Point2D,
    eye_width_px: float,
) -> BrowEyeGeometry:
    """Measure brow-centroid distance perpendicular to the eye axis.

    A centroid over several eye-facing brow landmarks is less sensitive to a
    single landmark's jitter. Measuring to the eye axis, rather than by raw y
    difference, also makes the result less sensitive to in-plane head roll.
    """
    if not math.isfinite(eye_width_px) or eye_width_px <= 0.0:
        raise GeometryError("Eye width must be a positive finite number.")
    reference_point = mean_point(brow_points)
    projection = project_point_onto_line(
        reference_point, inner_corner, outer_corner
    )
    distance_px = euclidean_distance(reference_point, projection)
    ratio = distance_px / eye_width_px
    if distance_px <= 0.0 or not math.isfinite(ratio):
        raise GeometryError("Brow-eye measurements must be positive and finite.")
    return BrowEyeGeometry(reference_point, projection, distance_px, ratio)


def normalized_difference(left_value: float, right_value: float) -> float:
    """Return abs(left-right) divided by their mean for positive measures."""
    if not all(math.isfinite(value) for value in (left_value, right_value)):
        raise GeometryError("Asymmetry inputs must be finite numbers.")
    mean_value = (left_value + right_value) / 2.0
    if left_value <= 0.0 or right_value <= 0.0 or mean_value <= 0.0:
        raise GeometryError("Size inputs must be greater than zero.")
    return abs(left_value - right_value) / mean_value


def calculate_eye_asymmetry(
    left_geometry: EyeGeometry,
    right_geometry: EyeGeometry,
    left_tail_angle_deg: float,
    right_tail_angle_deg: float,
) -> EyeAsymmetryGeometry:
    """Calculate continuous size and angle differences between both eyes."""
    if not all(
        math.isfinite(angle)
        for angle in (left_tail_angle_deg, right_tail_angle_deg)
    ):
        raise GeometryError("Eye tail angles must be finite numbers.")
    return EyeAsymmetryGeometry(
        eye_width_asymmetry=normalized_difference(
            left_geometry.width_px, right_geometry.width_px
        ),
        eye_height_asymmetry=normalized_difference(
            left_geometry.height_px, right_geometry.height_px
        ),
        eye_aspect_ratio_asymmetry=normalized_difference(
            left_geometry.aspect_ratio, right_geometry.aspect_ratio
        ),
        eye_tail_angle_difference_deg=abs(
            left_tail_angle_deg - right_tail_angle_deg
        ),
    )


def calculate_eye_geometry(
    inner_corner: Point2D,
    outer_corner: Point2D,
    upper_lid: Point2D,
    lower_lid: Point2D,
) -> EyeGeometry:
    """Calculate eye width, eye height, and height/width ratio in pixels."""
    width_px = euclidean_distance(inner_corner, outer_corner)
    height_px = euclidean_distance(upper_lid, lower_lid)

    if width_px <= 0:
        raise GeometryError("Eye width must be greater than zero.")
    if height_px <= 0:
        raise GeometryError("Eye height must be greater than zero.")

    aspect_ratio = height_px / width_px
    return EyeGeometry(width_px, height_px, aspect_ratio)


def calculate_eye_spacing(
    left_inner_corner: Point2D,
    right_inner_corner: Point2D,
    left_eye_width_px: float,
    right_eye_width_px: float,
) -> EyeSpacingGeometry:
    """Calculate inner-eye spacing and its scale-normalized ratio."""
    if not all(
        math.isfinite(value)
        for value in (left_eye_width_px, right_eye_width_px)
    ):
        raise GeometryError("Eye widths must be finite numbers.")
    if left_eye_width_px <= 0 or right_eye_width_px <= 0:
        raise GeometryError("Eye widths must be greater than zero.")

    inner_eye_distance_px = euclidean_distance(
        left_inner_corner, right_inner_corner
    )
    mean_eye_width_px = (left_eye_width_px + right_eye_width_px) / 2.0
    eye_spacing_ratio = inner_eye_distance_px / mean_eye_width_px

    if inner_eye_distance_px <= 0 or not all(
        math.isfinite(value)
        for value in (
            inner_eye_distance_px,
            mean_eye_width_px,
            eye_spacing_ratio,
        )
    ):
        raise GeometryError("Eye spacing measurements must be positive and finite.")

    return EyeSpacingGeometry(
        inner_eye_distance_px,
        mean_eye_width_px,
        eye_spacing_ratio,
    )


def calculate_relative_eye_length(
    left_geometry: EyeGeometry,
    right_geometry: EyeGeometry,
    face_width_start: Point2D,
    face_width_end: Point2D,
) -> RelativeEyeLengthGeometry:
    """Normalize eye width by same-image face width.

    The existing eye width and height measurements are consumed unchanged.
    This function only adds scale-independent ratios around them.
    """
    face_width_px = euclidean_distance(face_width_start, face_width_end)
    measures = (
        face_width_px,
        left_geometry.width_px,
        right_geometry.width_px,
        left_geometry.height_px,
        right_geometry.height_px,
    )
    if not all(math.isfinite(value) and value > 0.0 for value in measures):
        raise GeometryError(
            "Face width and eye dimensions must be positive finite numbers."
        )

    relative_left = left_geometry.width_px / face_width_px
    relative_right = right_geometry.width_px / face_width_px
    width_height_left = left_geometry.width_px / left_geometry.height_px
    width_height_right = right_geometry.width_px / right_geometry.height_px
    return RelativeEyeLengthGeometry(
        face_width_px=face_width_px,
        relative_eye_length_left=relative_left,
        relative_eye_length_right=relative_right,
        relative_eye_length_mean=(relative_left + relative_right) / 2.0,
        eye_width_height_ratio_left=width_height_left,
        eye_width_height_ratio_right=width_height_right,
        eye_width_height_ratio_mean=(
            width_height_left + width_height_right
        )
        / 2.0,
    )


def calculate_lower_lid_space(
    lower_lid_points: Sequence[Point2D],
    infraorbital_points: Sequence[Point2D],
    eye_width_px: float,
) -> LowerLidSpaceGeometry:
    """Average paired lower-lid-to-infraorbital mesh-edge distances.

    Each lower-lid point must have one corresponding infraorbital reference.
    The mean pixel distance is normalized by the existing same-eye width.
    """
    if not lower_lid_points:
        raise GeometryError("At least one lower-lid point pair is required.")
    if len(lower_lid_points) != len(infraorbital_points):
        raise GeometryError(
            "Lower-lid and infraorbital point counts must match."
        )
    if not math.isfinite(eye_width_px) or eye_width_px <= 0.0:
        raise GeometryError("Eye width must be a positive finite number.")

    distances = tuple(
        euclidean_distance(lower_lid, infraorbital)
        for lower_lid, infraorbital in zip(
            lower_lid_points, infraorbital_points
        )
    )
    if not all(math.isfinite(value) and value > 0.0 for value in distances):
        raise GeometryError(
            "Lower-lid space distances must be positive and finite."
        )
    space_px = sum(distances) / len(distances)
    return LowerLidSpaceGeometry(
        segment_distances_px=distances,
        space_px=space_px,
        ratio=space_px / eye_width_px,
    )


def angle_at_vertex_deg(
    vertex: Point2D,
    point_a: Point2D,
    point_b: Point2D,
) -> float:
    """Return the smaller angle A-vertex-B in degrees."""
    vector_a = (point_a.x - vertex.x, point_a.y - vertex.y)
    vector_b = (point_b.x - vertex.x, point_b.y - vertex.y)
    length_a = math.hypot(*vector_a)
    length_b = math.hypot(*vector_b)
    if length_a <= 0.0 or length_b <= 0.0:
        raise GeometryError("Angle rays must have positive length.")
    cosine = (
        vector_a[0] * vector_b[0] + vector_a[1] * vector_b[1]
    ) / (length_a * length_b)
    angle = math.degrees(math.acos(min(1.0, max(-1.0, cosine))))
    if not math.isfinite(angle) or angle <= 0.0 or angle > 180.0:
        raise GeometryError("Angle must be finite and within (0, 180].")
    return angle
