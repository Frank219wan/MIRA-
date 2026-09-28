"""Extract, visualize, and measure the first set of eye landmarks.

Left/right always means the detected person's anatomical left/right, not the
left/right side of the displayed image. For an unmirrored frontal image, the
person's left eye normally appears on the image's right side.

MediaPipe cannot tell whether pixels were horizontally mirrored before they
were passed to the model. Use ``--mirrored-input`` for an already mirrored
selfie; this swaps the MediaPipe eye groups back to person-relative semantics.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple

import cv2
import numpy as np

try:
    from .face_geometry import (
        BrowEyeGeometry,
        EyeGeometry,
        LowerLidSpaceGeometry,
        Point2D,
        angle_at_vertex_deg,
        calculate_brow_eye_geometry,
        calculate_eye_asymmetry,
        calculate_eye_geometry,
        calculate_eye_spacing,
        calculate_lower_lid_space,
        calculate_relative_eye_length,
        euclidean_distance,
        eye_tail_angle_deg,
    )
    from .face_landmarker import (
        DEFAULT_IMAGE_PATH,
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerDetector,
        FaceLandmarkerError,
        read_image,
        save_image,
    )
    from .face_profile import (
        DEFAULT_PROFILE_PATH,
        build_face_profile,
        save_face_profile,
    )
    from .pose_normalization import (
        PoseNormalizationError,
        RollNormalizationResult,
        normalize_face_roll,
    )
except ImportError:  # Support: python src/eye_landmarks.py
    from face_geometry import (  # type: ignore
        BrowEyeGeometry,
        EyeGeometry,
        LowerLidSpaceGeometry,
        Point2D,
        angle_at_vertex_deg,
        calculate_brow_eye_geometry,
        calculate_eye_asymmetry,
        calculate_eye_geometry,
        calculate_eye_spacing,
        calculate_lower_lid_space,
        calculate_relative_eye_length,
        euclidean_distance,
        eye_tail_angle_deg,
    )
    from face_landmarker import (  # type: ignore
        DEFAULT_IMAGE_PATH,
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerDetector,
        FaceLandmarkerError,
        read_image,
        save_image,
    )
    from face_profile import (  # type: ignore
        DEFAULT_PROFILE_PATH,
        build_face_profile,
        save_face_profile,
    )
    from pose_normalization import (  # type: ignore
        PoseNormalizationError,
        RollNormalizationResult,
        normalize_face_roll,
    )


DEFAULT_EYE_DEBUG_PATH = (
    PROJECT_ROOT / "data" / "output" / "eye_landmarks_result.jpg"
)
DEFAULT_GEOMETRY_JSON_PATH = (
    PROJECT_ROOT / "data" / "output" / "face_geometry.json"
)
EXPECTED_LANDMARK_COUNT = 478


@dataclass(frozen=True)
class EyeLandmarkIndices:
    inner_corner: int
    outer_corner: int
    upper_lid: int
    lower_lid: int


@dataclass(frozen=True)
class EyeRuleLandmarkIndices:
    upper_inner: int
    lower_inner: int
    lower_lid: Tuple[int, ...]
    infraorbital: Tuple[int, ...]


# Confirmed against MediaPipe Tasks FaceLandmarksConnections and the official
# canonical face model. These are person-relative groups for an UNMIRRORED
# input image, not labels based on which half of the image contains the eye.
SUBJECT_LEFT_EYE_INDICES = EyeLandmarkIndices(
    inner_corner=362,
    outer_corner=263,
    upper_lid=386,
    lower_lid=374,
)
SUBJECT_RIGHT_EYE_INDICES = EyeLandmarkIndices(
    inner_corner=133,
    outer_corner=33,
    upper_lid=159,
    lower_lid=145,
)

# MediaPipe Tasks official eye contours connect the inner-corner vertex to
# these immediate upper/lower neighbors. The lower-lid/infraorbital pairs are
# direct edges in the official face tessellation. Groups are person-relative
# for unmirrored input, matching SUBJECT_*_EYE_INDICES above.
SUBJECT_LEFT_EYE_RULE_INDICES = EyeRuleLandmarkIndices(
    upper_inner=398,
    lower_inner=382,
    lower_lid=(373, 374, 380),
    infraorbital=(254, 253, 252),
)
SUBJECT_RIGHT_EYE_RULE_INDICES = EyeRuleLandmarkIndices(
    upper_inner=173,
    lower_inner=155,
    lower_lid=(144, 145, 153),
    infraorbital=(24, 23, 22),
)

# Both indices are lateral points in MediaPipe Tasks' official
# FACE_LANDMARKS_FACE_OVAL connection list. Their same-image 2D distance is
# the v0.2 face-width denominator; it is not assigned a cosmetic label.
FACE_WIDTH_LANDMARK_INDICES = (234, 454)

# These five-point chains are the eye-facing (lower) eyebrow contours from
# MediaPipe Tasks FaceLandmarksConnections:
#   left  276-283-282-295-285
#   right 46-53-52-65-55
# The centroid of each chain is used as a stable brow reference. As with the
# eye groups, these constants are person-relative for an unmirrored input.
SUBJECT_LEFT_BROW_INDICES = (276, 283, 282, 295, 285)
SUBJECT_RIGHT_BROW_INDICES = (46, 53, 52, 65, 55)


@dataclass(frozen=True)
class LandmarkPoint:
    index: int
    x: float
    y: float
    z: float

    def to_pixel(self, image_width: int, image_height: int) -> Point2D:
        """Convert normalized coordinates without mutating or clipping them."""
        return Point2D(
            x=self.x * (image_width - 1),
            y=self.y * (image_height - 1),
        )


@dataclass(frozen=True)
class EyeLandmarks:
    inner_corner: LandmarkPoint
    outer_corner: LandmarkPoint
    upper_lid: LandmarkPoint
    lower_lid: LandmarkPoint

    def items(self) -> Iterable[tuple[str, LandmarkPoint]]:
        return (
            ("inner_corner", self.inner_corner),
            ("outer_corner", self.outer_corner),
            ("upper_lid", self.upper_lid),
            ("lower_lid", self.lower_lid),
        )


@dataclass(frozen=True)
class ExtractedEyes:
    left: EyeLandmarks
    right: EyeLandmarks


@dataclass(frozen=True)
class BrowLandmarks:
    points: Tuple[LandmarkPoint, ...]


@dataclass(frozen=True)
class ExtractedBrows:
    left: BrowLandmarks
    right: BrowLandmarks


@dataclass(frozen=True)
class EyeRuleLandmarks:
    upper_inner: LandmarkPoint
    lower_inner: LandmarkPoint
    lower_lid: Tuple[LandmarkPoint, ...]
    infraorbital: Tuple[LandmarkPoint, ...]


@dataclass(frozen=True)
class ExtractedRuleLandmarks:
    left: EyeRuleLandmarks
    right: EyeRuleLandmarks
    face_width_start: LandmarkPoint
    face_width_end: LandmarkPoint


def _copy_landmark(face_landmarks, index: int) -> LandmarkPoint:
    landmark = face_landmarks[index]
    return LandmarkPoint(
        index=index,
        x=float(landmark.x),
        y=float(landmark.y),
        z=float(landmark.z),
    )


def _extract_eye(face_landmarks, indices: EyeLandmarkIndices) -> EyeLandmarks:
    return EyeLandmarks(
        inner_corner=_copy_landmark(face_landmarks, indices.inner_corner),
        outer_corner=_copy_landmark(face_landmarks, indices.outer_corner),
        upper_lid=_copy_landmark(face_landmarks, indices.upper_lid),
        lower_lid=_copy_landmark(face_landmarks, indices.lower_lid),
    )


def _extract_eye_rule_landmarks(
    face_landmarks,
    indices: EyeRuleLandmarkIndices,
) -> EyeRuleLandmarks:
    return EyeRuleLandmarks(
        upper_inner=_copy_landmark(face_landmarks, indices.upper_inner),
        lower_inner=_copy_landmark(face_landmarks, indices.lower_inner),
        lower_lid=tuple(
            _copy_landmark(face_landmarks, index)
            for index in indices.lower_lid
        ),
        infraorbital=tuple(
            _copy_landmark(face_landmarks, index)
            for index in indices.infraorbital
        ),
    )


def extract_eye_landmarks(
    face_landmarks,
    input_is_mirrored: bool = False,
) -> ExtractedEyes:
    """Copy the eight required eye points from a 478-landmark face result.

    MediaPipe's left/right groups map to the person's sides for unmirrored
    input. If the saved pixels were horizontally mirrored, the two full eye
    groups are swapped so the returned fields still mean the person's sides.
    """
    if len(face_landmarks) < EXPECTED_LANDMARK_COUNT:
        raise FaceLandmarkerError(
            "Face Landmarker 返回的关键点数量不足："
            f"期望至少 {EXPECTED_LANDMARK_COUNT}，实际 {len(face_landmarks)}。"
        )

    left_indices = (
        SUBJECT_RIGHT_EYE_INDICES
        if input_is_mirrored
        else SUBJECT_LEFT_EYE_INDICES
    )
    right_indices = (
        SUBJECT_LEFT_EYE_INDICES
        if input_is_mirrored
        else SUBJECT_RIGHT_EYE_INDICES
    )
    return ExtractedEyes(
        left=_extract_eye(face_landmarks, left_indices),
        right=_extract_eye(face_landmarks, right_indices),
    )


def extract_brow_landmarks(
    face_landmarks,
    input_is_mirrored: bool = False,
) -> ExtractedBrows:
    """Copy the two five-point, eye-facing eyebrow contours.

    Left/right follows the detected person's anatomy. A mirrored input swaps
    complete brow groups for the same reason as ``extract_eye_landmarks``.
    """
    if len(face_landmarks) < EXPECTED_LANDMARK_COUNT:
        raise FaceLandmarkerError(
            "Face Landmarker 返回的关键点数量不足："
            f"期望至少 {EXPECTED_LANDMARK_COUNT}，实际 {len(face_landmarks)}。"
        )
    left_indices = (
        SUBJECT_RIGHT_BROW_INDICES
        if input_is_mirrored
        else SUBJECT_LEFT_BROW_INDICES
    )
    right_indices = (
        SUBJECT_LEFT_BROW_INDICES
        if input_is_mirrored
        else SUBJECT_RIGHT_BROW_INDICES
    )
    return ExtractedBrows(
        left=BrowLandmarks(
            tuple(_copy_landmark(face_landmarks, index) for index in left_indices)
        ),
        right=BrowLandmarks(
            tuple(_copy_landmark(face_landmarks, index) for index in right_indices)
        ),
    )


def extract_rule_landmarks(
    face_landmarks,
    input_is_mirrored: bool = False,
) -> ExtractedRuleLandmarks:
    """Copy v0.2 rule landmarks with person-relative left/right semantics."""
    if len(face_landmarks) < EXPECTED_LANDMARK_COUNT:
        raise FaceLandmarkerError(
            "Face Landmarker 返回的关键点数量不足："
            f"期望至少 {EXPECTED_LANDMARK_COUNT}，实际 {len(face_landmarks)}。"
        )
    left_indices = (
        SUBJECT_RIGHT_EYE_RULE_INDICES
        if input_is_mirrored
        else SUBJECT_LEFT_EYE_RULE_INDICES
    )
    right_indices = (
        SUBJECT_LEFT_EYE_RULE_INDICES
        if input_is_mirrored
        else SUBJECT_RIGHT_EYE_RULE_INDICES
    )
    return ExtractedRuleLandmarks(
        left=_extract_eye_rule_landmarks(face_landmarks, left_indices),
        right=_extract_eye_rule_landmarks(face_landmarks, right_indices),
        face_width_start=_copy_landmark(
            face_landmarks, FACE_WIDTH_LANDMARK_INDICES[0]
        ),
        face_width_end=_copy_landmark(
            face_landmarks, FACE_WIDTH_LANDMARK_INDICES[1]
        ),
    )


def _eye_pixel_points(
    eye: EyeLandmarks,
    image_width: int,
    image_height: int,
) -> Dict[str, Point2D]:
    return {
        name: landmark.to_pixel(image_width, image_height)
        for name, landmark in eye.items()
    }


def _brow_pixel_points(
    brow: BrowLandmarks,
    image_width: int,
    image_height: int,
) -> Tuple[Point2D, ...]:
    return tuple(
        landmark.to_pixel(image_width, image_height)
        for landmark in brow.points
    )


def _rule_pixel_points(
    rule_landmarks: EyeRuleLandmarks,
    image_width: int,
    image_height: int,
) -> dict:
    return {
        "upper_inner": rule_landmarks.upper_inner.to_pixel(
            image_width, image_height
        ),
        "lower_inner": rule_landmarks.lower_inner.to_pixel(
            image_width, image_height
        ),
        "lower_lid": tuple(
            point.to_pixel(image_width, image_height)
            for point in rule_landmarks.lower_lid
        ),
        "infraorbital": tuple(
            point.to_pixel(image_width, image_height)
            for point in rule_landmarks.infraorbital
        ),
    }


def _selected_landmarks_by_index(
    eyes: ExtractedEyes,
    brows: Optional[ExtractedBrows],
    rule_landmarks: Optional[ExtractedRuleLandmarks],
) -> Dict[int, LandmarkPoint]:
    """Collect every landmark used by the geometry layer without duplication."""

    selected: Dict[int, LandmarkPoint] = {}
    for eye in (eyes.left, eyes.right):
        for _, landmark in eye.items():
            selected[landmark.index] = landmark
    if brows is not None:
        for brow in (brows.left, brows.right):
            for landmark in brow.points:
                selected[landmark.index] = landmark
    if rule_landmarks is not None:
        for rule in (rule_landmarks.left, rule_landmarks.right):
            for landmark in (
                rule.upper_inner,
                rule.lower_inner,
                *rule.lower_lid,
                *rule.infraorbital,
            ):
                selected[landmark.index] = landmark
        selected[rule_landmarks.face_width_start.index] = (
            rule_landmarks.face_width_start
        )
        selected[rule_landmarks.face_width_end.index] = (
            rule_landmarks.face_width_end
        )
    return selected


def _normalize_selected_landmarks(
    eyes: ExtractedEyes,
    brows: Optional[ExtractedBrows],
    rule_landmarks: Optional[ExtractedRuleLandmarks],
    image_width: int,
    image_height: int,
) -> tuple[Dict[int, Point2D], Optional[RollNormalizationResult], Optional[str]]:
    selected = _selected_landmarks_by_index(eyes, brows, rule_landmarks)
    original_points = {
        index: landmark.to_pixel(image_width, image_height)
        for index, landmark in selected.items()
    }
    try:
        result = normalize_face_roll(
            original_points,
            left_eye_center_indices=(
                eyes.left.inner_corner.index,
                eyes.left.outer_corner.index,
            ),
            right_eye_center_indices=(
                eyes.right.inner_corner.index,
                eyes.right.outer_corner.index,
            ),
        )
    except PoseNormalizationError as exc:
        return original_points, None, str(exc)
    return dict(result.normalized_points), result, None


def _points_for_eye(
    eye: EyeLandmarks,
    normalized_by_index: Mapping[int, Point2D],
) -> Dict[str, Point2D]:
    return {
        name: normalized_by_index[landmark.index]
        for name, landmark in eye.items()
    }


def _points_for_brow(
    brow: BrowLandmarks,
    normalized_by_index: Mapping[int, Point2D],
) -> Tuple[Point2D, ...]:
    return tuple(normalized_by_index[point.index] for point in brow.points)


def _points_for_rule(
    rule_landmarks: EyeRuleLandmarks,
    normalized_by_index: Mapping[int, Point2D],
) -> dict:
    return {
        "upper_inner": normalized_by_index[rule_landmarks.upper_inner.index],
        "lower_inner": normalized_by_index[rule_landmarks.lower_inner.index],
        "lower_lid": tuple(
            normalized_by_index[point.index]
            for point in rule_landmarks.lower_lid
        ),
        "infraorbital": tuple(
            normalized_by_index[point.index]
            for point in rule_landmarks.infraorbital
        ),
    }


def _landmark_payload(
    landmark: LandmarkPoint,
    image_width: int,
    image_height: int,
    pose_normalized_point: Optional[Point2D] = None,
) -> dict:
    pixel = landmark.to_pixel(image_width, image_height)
    payload = {
        "index": landmark.index,
        "normalized": {
            "x": round(landmark.x, 6),
            "y": round(landmark.y, 6),
            "z": round(landmark.z, 6),
        },
        "pixel": {
            "x": round(pixel.x, 2),
            "y": round(pixel.y, 2),
        },
    }
    if pose_normalized_point is not None:
        payload["pose_normalized"] = {
            "x": round(pose_normalized_point.x / (image_width - 1), 6),
            "y": round(pose_normalized_point.y / (image_height - 1), 6),
            "z": round(landmark.z, 6),
        }
        payload["pose_normalized_pixel"] = _point_payload(
            pose_normalized_point
        )
    return payload


def _eye_payload(
    eye: EyeLandmarks,
    geometry: EyeGeometry,
    image_width: int,
    image_height: int,
    normalized_by_index: Mapping[int, Point2D],
) -> dict:
    payload = {
        name: _landmark_payload(
            landmark,
            image_width,
            image_height,
            normalized_by_index.get(landmark.index),
        )
        for name, landmark in eye.items()
    }
    payload.update(
        {
            "width_px": round(geometry.width_px, 3),
            "height_px": round(geometry.height_px, 3),
            "aspect_ratio": round(geometry.aspect_ratio, 4),
        }
    )
    return payload


def _point_payload(point: Point2D) -> dict:
    return {"x": round(point.x, 2), "y": round(point.y, 2)}


def _brow_payload(
    brow: BrowLandmarks,
    geometry: BrowEyeGeometry,
    image_width: int,
    image_height: int,
    normalized_by_index: Mapping[int, Point2D],
) -> dict:
    return {
        "reference_landmark_indices": [point.index for point in brow.points],
        "reference_landmarks": [
            _landmark_payload(
                point,
                image_width,
                image_height,
                normalized_by_index.get(point.index),
            )
            for point in brow.points
        ],
        "reference_point_px": _point_payload(geometry.reference_point),
        "eye_axis_projection_px": _point_payload(
            geometry.eye_axis_projection
        ),
        "distance_px": round(geometry.distance_px, 3),
        "ratio": round(geometry.ratio, 4),
    }


def _lower_lid_space_payload(
    rule_landmarks: EyeRuleLandmarks,
    geometry: LowerLidSpaceGeometry,
    image_width: int,
    image_height: int,
    normalized_by_index: Mapping[int, Point2D],
) -> dict:
    return {
        "lower_lid_landmark_indices": [
            point.index for point in rule_landmarks.lower_lid
        ],
        "infraorbital_landmark_indices": [
            point.index for point in rule_landmarks.infraorbital
        ],
        "lower_lid_landmarks": [
            _landmark_payload(
                point,
                image_width,
                image_height,
                normalized_by_index.get(point.index),
            )
            for point in rule_landmarks.lower_lid
        ],
        "infraorbital_landmarks": [
            _landmark_payload(
                point,
                image_width,
                image_height,
                normalized_by_index.get(point.index),
            )
            for point in rule_landmarks.infraorbital
        ],
        "segment_distances_px": [
            round(distance, 3)
            for distance in geometry.segment_distances_px
        ],
        "space_px": round(geometry.space_px, 3),
        "ratio": round(geometry.ratio, 4),
    }


def _inner_corner_payload(
    eye: EyeLandmarks,
    rule_landmarks: EyeRuleLandmarks,
    angle_deg: float,
    image_width: int,
    image_height: int,
    normalized_by_index: Mapping[int, Point2D],
) -> dict:
    return {
        "vertex": _landmark_payload(
            eye.inner_corner,
            image_width,
            image_height,
            normalized_by_index.get(eye.inner_corner.index),
        ),
        "upper_inner": _landmark_payload(
            rule_landmarks.upper_inner,
            image_width,
            image_height,
            normalized_by_index.get(rule_landmarks.upper_inner.index),
        ),
        "lower_inner": _landmark_payload(
            rule_landmarks.lower_inner,
            image_width,
            image_height,
            normalized_by_index.get(rule_landmarks.lower_inner.index),
        ),
        "angle_deg": round(angle_deg, 3),
    }


def _pose_normalization_payload(
    eyes: ExtractedEyes,
    result: Optional[RollNormalizationResult],
    failure_reason: Optional[str],
) -> dict:
    payload = {
        "method": "2d_interocular_roll",
        "eye_center_landmark_indices": {
            "left": [
                eyes.left.inner_corner.index,
                eyes.left.outer_corner.index,
            ],
            "right": [
                eyes.right.inner_corner.index,
                eyes.right.outer_corner.index,
            ],
        },
        "roll_angle_deg": None,
        "rotation_applied_deg": None,
        "face_center_px": None,
        "left_eye_center_px": None,
        "right_eye_center_px": None,
        "applied": result is not None,
    }
    if result is None:
        payload["failure_reason"] = failure_reason or "unknown"
        return payload
    payload.update(
        {
            "roll_angle_deg": round(result.roll_angle_deg, 6),
            "rotation_applied_deg": round(
                result.rotation_applied_deg, 6
            ),
            "face_center_px": _point_payload(result.face_center),
            "left_eye_center_px": _point_payload(result.left_eye_center),
            "right_eye_center_px": _point_payload(
                result.right_eye_center
            ),
        }
    )
    return payload


def build_face_geometry_payload(
    eyes: ExtractedEyes,
    image_width: int,
    image_height: int,
    input_is_mirrored: bool = False,
    brows: Optional[ExtractedBrows] = None,
    rule_landmarks: Optional[ExtractedRuleLandmarks] = None,
) -> dict:
    """Build the JSON-ready eye geometry payload from extracted eye points."""
    if image_width <= 1 or image_height <= 1:
        raise FaceLandmarkerError("图片宽高必须大于 1 pixel。")

    normalized_by_index, pose_result, pose_failure = (
        _normalize_selected_landmarks(
            eyes,
            brows,
            rule_landmarks,
            image_width,
            image_height,
        )
    )
    left_points = _points_for_eye(eyes.left, normalized_by_index)
    right_points = _points_for_eye(eyes.right, normalized_by_index)

    left_geometry = calculate_eye_geometry(**left_points)
    right_geometry = calculate_eye_geometry(**right_points)
    spacing = calculate_eye_spacing(
        left_inner_corner=left_points["inner_corner"],
        right_inner_corner=right_points["inner_corner"],
        left_eye_width_px=left_geometry.width_px,
        right_eye_width_px=right_geometry.width_px,
    )
    left_tail_angle = eye_tail_angle_deg(
        left_points["inner_corner"], left_points["outer_corner"]
    )
    right_tail_angle = eye_tail_angle_deg(
        right_points["inner_corner"], right_points["outer_corner"]
    )
    asymmetry = calculate_eye_asymmetry(
        left_geometry,
        right_geometry,
        left_tail_angle,
        right_tail_angle,
    )

    payload = {
        "face_detected": True,
        "coordinate_system": {
            "normalized": "MediaPipe x/y/z coordinates",
            "pixel": "origin top-left; x rightward; y downward",
            "pose_normalized": (
                "roll-corrected x/y; z unchanged; rotation in pixel space"
            ),
            "eye_side_semantics": "detected person's anatomical left/right",
            "input_is_mirrored": input_is_mirrored,
        },
        "pose_normalization": _pose_normalization_payload(
            eyes, pose_result, pose_failure
        ),
        "confidence": {
            "pose_normalized": pose_result is not None,
        },
        "eyes": {
            "left": _eye_payload(
                eyes.left,
                left_geometry,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "right": _eye_payload(
                eyes.right,
                right_geometry,
                image_width,
                image_height,
                normalized_by_index,
            ),
        },
        "geometry": {
            "inner_eye_distance_px": round(
                spacing.inner_eye_distance_px, 3
            ),
            "mean_eye_width_px": round(spacing.mean_eye_width_px, 3),
            "eye_spacing_ratio": round(spacing.eye_spacing_ratio, 4),
        },
        "eye_tail_angle": {
            "left_eye_tail_angle_deg": round(left_tail_angle, 3),
            "right_eye_tail_angle_deg": round(right_tail_angle, 3),
            "mean_eye_tail_angle_deg": round(
                (left_tail_angle + right_tail_angle) / 2.0, 3
            ),
        },
        "asymmetry": {
            "eye_width_asymmetry": round(
                asymmetry.eye_width_asymmetry, 4
            ),
            "eye_height_asymmetry": round(
                asymmetry.eye_height_asymmetry, 4
            ),
            "eye_aspect_ratio_asymmetry": round(
                asymmetry.eye_aspect_ratio_asymmetry, 4
            ),
            "eye_tail_angle_difference_deg": round(
                asymmetry.eye_tail_angle_difference_deg, 3
            ),
        },
    }

    if rule_landmarks is not None:
        left_rule_points = _points_for_rule(
            rule_landmarks.left, normalized_by_index
        )
        right_rule_points = _points_for_rule(
            rule_landmarks.right, normalized_by_index
        )
        face_width_start = normalized_by_index[
            rule_landmarks.face_width_start.index
        ]
        face_width_end = normalized_by_index[
            rule_landmarks.face_width_end.index
        ]
        relative_length = calculate_relative_eye_length(
            left_geometry,
            right_geometry,
            face_width_start,
            face_width_end,
        )
        left_lower_lid = calculate_lower_lid_space(
            left_rule_points["lower_lid"],
            left_rule_points["infraorbital"],
            left_geometry.width_px,
        )
        right_lower_lid = calculate_lower_lid_space(
            right_rule_points["lower_lid"],
            right_rule_points["infraorbital"],
            right_geometry.width_px,
        )
        left_inner_angle = angle_at_vertex_deg(
            left_points["inner_corner"],
            left_rule_points["upper_inner"],
            left_rule_points["lower_inner"],
        )
        right_inner_angle = angle_at_vertex_deg(
            right_points["inner_corner"],
            right_rule_points["upper_inner"],
            right_rule_points["lower_inner"],
        )

        payload["relative_eye_length"] = {
            "face_width_landmark_indices": list(
                FACE_WIDTH_LANDMARK_INDICES
            ),
            "face_width_reference_landmarks": [
                _landmark_payload(
                    rule_landmarks.face_width_start,
                    image_width,
                    image_height,
                    normalized_by_index.get(
                        rule_landmarks.face_width_start.index
                    ),
                ),
                _landmark_payload(
                    rule_landmarks.face_width_end,
                    image_width,
                    image_height,
                    normalized_by_index.get(
                        rule_landmarks.face_width_end.index
                    ),
                ),
            ],
            "face_width_px": round(relative_length.face_width_px, 3),
            "relative_eye_length_left": round(
                relative_length.relative_eye_length_left, 4
            ),
            "relative_eye_length_right": round(
                relative_length.relative_eye_length_right, 4
            ),
            "relative_eye_length_mean": round(
                relative_length.relative_eye_length_mean, 4
            ),
        }
        payload["eye_width_height_ratio"] = {
            "eye_width_height_ratio_left": round(
                relative_length.eye_width_height_ratio_left, 4
            ),
            "eye_width_height_ratio_right": round(
                relative_length.eye_width_height_ratio_right, 4
            ),
            "eye_width_height_ratio_mean": round(
                relative_length.eye_width_height_ratio_mean, 4
            ),
        }
        payload["lower_lid_space"] = {
            "left": _lower_lid_space_payload(
                rule_landmarks.left,
                left_lower_lid,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "right": _lower_lid_space_payload(
                rule_landmarks.right,
                right_lower_lid,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "lower_lid_space_px_left": round(
                left_lower_lid.space_px, 3
            ),
            "lower_lid_space_px_right": round(
                right_lower_lid.space_px, 3
            ),
            "lower_lid_space_px_mean": round(
                (left_lower_lid.space_px + right_lower_lid.space_px)
                / 2.0,
                3,
            ),
            "lower_lid_space_ratio_left": round(
                left_lower_lid.ratio, 4
            ),
            "lower_lid_space_ratio_right": round(
                right_lower_lid.ratio, 4
            ),
            "lower_lid_space_ratio_mean": round(
                (left_lower_lid.ratio + right_lower_lid.ratio) / 2.0,
                4,
            ),
        }
        payload["inner_corner_angle"] = {
            "left": _inner_corner_payload(
                eyes.left,
                rule_landmarks.left,
                left_inner_angle,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "right": _inner_corner_payload(
                eyes.right,
                rule_landmarks.right,
                right_inner_angle,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "inner_corner_angle_left_deg": round(left_inner_angle, 3),
            "inner_corner_angle_right_deg": round(right_inner_angle, 3),
            "inner_corner_angle_mean_deg": round(
                (left_inner_angle + right_inner_angle) / 2.0, 3
            ),
        }

    if brows is not None:
        left_brow_points = _points_for_brow(
            brows.left, normalized_by_index
        )
        right_brow_points = _points_for_brow(
            brows.right, normalized_by_index
        )
        left_brow_geometry = calculate_brow_eye_geometry(
            left_brow_points,
            left_points["inner_corner"],
            left_points["outer_corner"],
            left_geometry.width_px,
        )
        right_brow_geometry = calculate_brow_eye_geometry(
            right_brow_points,
            right_points["inner_corner"],
            right_points["outer_corner"],
            right_geometry.width_px,
        )
        payload["brow_eye"] = {
            "left": _brow_payload(
                brows.left,
                left_brow_geometry,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "right": _brow_payload(
                brows.right,
                right_brow_geometry,
                image_width,
                image_height,
                normalized_by_index,
            ),
            "left_brow_eye_distance_px": round(
                left_brow_geometry.distance_px, 3
            ),
            "right_brow_eye_distance_px": round(
                right_brow_geometry.distance_px, 3
            ),
            "left_brow_eye_ratio": round(left_brow_geometry.ratio, 4),
            "right_brow_eye_ratio": round(right_brow_geometry.ratio, 4),
            "mean_brow_eye_ratio": round(
                (left_brow_geometry.ratio + right_brow_geometry.ratio)
                / 2.0,
                4,
            ),
        }

    _assert_finite_numbers(payload)
    return payload


def _assert_finite_numbers(value) -> None:
    if isinstance(value, Mapping):
        for nested in value.values():
            _assert_finite_numbers(nested)
    elif isinstance(value, (list, tuple)):
        for nested in value:
            _assert_finite_numbers(nested)
    elif isinstance(value, float) and not math.isfinite(value):
        raise FaceLandmarkerError("Geometry output contains NaN or infinity.")


def draw_eye_landmarks(
    bgr_image,
    eyes: ExtractedEyes,
    brows: Optional[ExtractedBrows] = None,
    rule_landmarks: Optional[ExtractedRuleLandmarks] = None,
    geometry_payload: Optional[Mapping] = None,
):
    """Draw selected landmarks and the measurements used by the profile."""
    image_height, image_width = bgr_image.shape[:2]
    side_margin = max(210, min(360, round(image_width * 0.45)))
    annotated = cv2.copyMakeBorder(
        bgr_image,
        0,
        0,
        side_margin,
        side_margin,
        cv2.BORDER_CONSTANT,
        value=(28, 28, 28),
    )
    canvas_width = annotated.shape[1]
    radius = max(3, round(min(image_width, image_height) / 180))
    font_scale = max(0.42, min(0.7, min(image_width, image_height) / 1100))
    thickness = max(1, round(font_scale * 2))
    colors = {"left": (255, 0, 255), "right": (0, 255, 255)}
    short_names = {
        "inner_corner": "INNER",
        "outer_corner": "OUTER",
        "upper_lid": "UPPER",
        "lower_lid": "LOWER",
    }
    display_order = ("inner_corner", "outer_corner", "upper_lid", "lower_lid")

    if geometry_payload is not None:
        pose = geometry_payload.get("pose_normalization", {})
        if pose.get("applied") is True:
            pose_label = f"ROLL {pose['roll_angle_deg']:+.2f} deg / NORMALIZED"
        else:
            pose_label = "ROLL NORMALIZATION NOT APPLIED"
        cv2.putText(
            annotated,
            pose_label,
            (side_margin + 14, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )

    eye_entries = (("left", eyes.left), ("right", eyes.right))
    brows_by_side = (
        {"left": brows.left, "right": brows.right}
        if brows is not None
        else {}
    )
    rules_by_side = (
        {"left": rule_landmarks.left, "right": rule_landmarks.right}
        if rule_landmarks is not None
        else {}
    )
    mean_x_by_side = {
        side: sum(
            landmark.x * (image_width - 1) for _, landmark in eye.items()
        )
        / 4.0
        for side, eye in eye_entries
    }
    image_left_side = min(mean_x_by_side, key=mean_x_by_side.get)

    face_width_px = None
    if rule_landmarks is not None:
        face_start = rule_landmarks.face_width_start.to_pixel(
            image_width, image_height
        )
        face_end = rule_landmarks.face_width_end.to_pixel(
            image_width, image_height
        )
        face_width_px = euclidean_distance(face_start, face_end)
        face_start_canvas = (
            round(face_start.x + side_margin),
            round(face_start.y),
        )
        face_end_canvas = (
            round(face_end.x + side_margin),
            round(face_end.y),
        )
        cv2.line(
            annotated,
            face_start_canvas,
            face_end_canvas,
            (255, 180, 0),
            2,
            cv2.LINE_AA,
        )
        face_midpoint = (
            round((face_start_canvas[0] + face_end_canvas[0]) / 2),
            round((face_start_canvas[1] + face_end_canvas[1]) / 2),
        )
        cv2.putText(
            annotated,
            "FACE WIDTH 234-454",
            (face_midpoint[0] - 95, face_midpoint[1] + 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale * 0.75,
            (255, 180, 0),
            thickness,
            cv2.LINE_AA,
        )

    for side, eye in eye_entries:
        color = colors[side]
        points = _eye_pixel_points(eye, image_width, image_height)
        canvas_points = {
            name: (pixel.x + side_margin, pixel.y)
            for name, pixel in points.items()
        }
        # This arrow is anatomical inner -> outer. Its visual slope plus the
        # displayed signed angle makes the tail direction explicit.
        cv2.arrowedLine(
            annotated,
            (
                round(canvas_points["inner_corner"][0]),
                round(canvas_points["inner_corner"][1]),
            ),
            (
                round(canvas_points["outer_corner"][0]),
                round(canvas_points["outer_corner"][1]),
            ),
            color,
            2,
            cv2.LINE_AA,
            tipLength=0.10,
        )
        cv2.line(
            annotated,
            (
                round(canvas_points["upper_lid"][0]),
                round(canvas_points["upper_lid"][1]),
            ),
            (
                round(canvas_points["lower_lid"][0]),
                round(canvas_points["lower_lid"][1]),
            ),
            color,
            1,
            cv2.LINE_AA,
        )

        mean_y = sum(point.y for point in points.values()) / len(points)
        panel_is_left = side == image_left_side
        line_gap = max(27, round(34 * font_scale / 0.45))
        block_height = line_gap * len(display_order)
        first_label_y = min(
            max(round(mean_y - block_height / 2), 58),
            image_height - block_height - 8,
        )
        label_x = 12 if panel_is_left else side_margin + image_width + 12
        line_end_x = (
            side_margin - 10
            if panel_is_left
            else side_margin + image_width + 10
        )
        header = f"SUBJECT {side.upper()} EYE"
        cv2.putText(
            annotated,
            header,
            (label_x, first_label_y - 25),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            color,
            thickness,
            cv2.LINE_AA,
        )

        landmarks_by_name = dict(eye.items())
        for row, semantic_name in enumerate(display_order):
            landmark = landmarks_by_name[semantic_name]
            raw_point = canvas_points[semantic_name]
            point = (
                min(max(round(raw_point[0]), 0), canvas_width - 1),
                min(max(round(raw_point[1]), 0), image_height - 1),
            )
            label_y = first_label_y + row * line_gap
            cv2.circle(annotated, point, radius + 2, (0, 0, 0), -1)
            cv2.circle(annotated, point, radius, color, -1)
            label = (
                f"{side.upper()}_{short_names[semantic_name]} "
                f"{landmark.index}"
            )
            cv2.line(
                annotated,
                point,
                (line_end_x, label_y - 5),
                color,
                1,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (0, 0, 0),
                thickness + 2,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated,
                label,
                (label_x, label_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                color,
                thickness,
                cv2.LINE_AA,
            )

        tail_angle = (
            geometry_payload["eye_tail_angle"][
                f"{side}_eye_tail_angle_deg"
            ]
            if geometry_payload is not None
            else eye_tail_angle_deg(
                points["inner_corner"], points["outer_corner"]
            )
        )
        summary_y = first_label_y + len(display_order) * line_gap + 8
        summary_lines = [f"TAIL ANGLE {tail_angle:+.2f} deg"]

        brow = brows_by_side.get(side)
        if brow is not None:
            brow_points = _brow_pixel_points(
                brow, image_width, image_height
            )
            brow_geometry = calculate_brow_eye_geometry(
                brow_points,
                points["inner_corner"],
                points["outer_corner"],
                euclidean_distance(
                    points["inner_corner"], points["outer_corner"]
                ),
            )
            canvas_brow_points = [
                (round(point.x + side_margin), round(point.y))
                for point in brow_points
            ]
            cv2.polylines(
                annotated,
                [np.array(canvas_brow_points, dtype=np.int32)],
                False,
                color,
                2,
                cv2.LINE_AA,
            )
            brow_radius = max(2, radius - 1)
            for point in canvas_brow_points:
                cv2.circle(annotated, point, brow_radius + 1, (0, 0, 0), -1)
                cv2.circle(annotated, point, brow_radius, color, -1)

            reference_point = (
                round(brow_geometry.reference_point.x + side_margin),
                round(brow_geometry.reference_point.y),
            )
            projection_point = (
                round(brow_geometry.eye_axis_projection.x + side_margin),
                round(brow_geometry.eye_axis_projection.y),
            )
            cv2.line(
                annotated,
                reference_point,
                projection_point,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
            cv2.drawMarker(
                annotated,
                reference_point,
                (255, 255, 255),
                cv2.MARKER_DIAMOND,
                max(10, radius * 3),
                2,
                cv2.LINE_AA,
            )
            cv2.drawMarker(
                annotated,
                projection_point,
                (255, 255, 255),
                cv2.MARKER_CROSS,
                max(9, radius * 3),
                2,
                cv2.LINE_AA,
            )
            indices = ",".join(str(point.index) for point in brow.points)
            summary_lines.extend(
                (
                    f"BROW REF {indices}",
                    "BROW/EYE "
                    f"{(geometry_payload['brow_eye'][side]['ratio'] if geometry_payload is not None else brow_geometry.ratio):.4f}",
                )
            )

        rule = rules_by_side.get(side)
        if rule is not None and face_width_px is not None:
            rule_points = _rule_pixel_points(
                rule, image_width, image_height
            )
            eye_width_px = euclidean_distance(
                points["inner_corner"], points["outer_corner"]
            )
            eye_height_px = euclidean_distance(
                points["upper_lid"], points["lower_lid"]
            )
            lower_lid_geometry = calculate_lower_lid_space(
                rule_points["lower_lid"],
                rule_points["infraorbital"],
                eye_width_px,
            )
            inner_angle = angle_at_vertex_deg(
                points["inner_corner"],
                rule_points["upper_inner"],
                rule_points["lower_inner"],
            )

            feature_color = (255, 180, 0)
            angle_color = (0, 128, 255)
            for lower_lid_point, infraorbital_point in zip(
                rule_points["lower_lid"],
                rule_points["infraorbital"],
            ):
                lower_canvas = (
                    round(lower_lid_point.x + side_margin),
                    round(lower_lid_point.y),
                )
                infra_canvas = (
                    round(infraorbital_point.x + side_margin),
                    round(infraorbital_point.y),
                )
                cv2.line(
                    annotated,
                    lower_canvas,
                    infra_canvas,
                    feature_color,
                    2,
                    cv2.LINE_AA,
                )
                cv2.circle(
                    annotated, infra_canvas, max(2, radius - 1), feature_color, -1
                )

            inner_vertex = (
                round(points["inner_corner"].x + side_margin),
                round(points["inner_corner"].y),
            )
            upper_inner = (
                round(rule_points["upper_inner"].x + side_margin),
                round(rule_points["upper_inner"].y),
            )
            lower_inner = (
                round(rule_points["lower_inner"].x + side_margin),
                round(rule_points["lower_inner"].y),
            )
            cv2.line(
                annotated,
                inner_vertex,
                upper_inner,
                angle_color,
                2,
                cv2.LINE_AA,
            )
            cv2.line(
                annotated,
                inner_vertex,
                lower_inner,
                angle_color,
                2,
                cv2.LINE_AA,
            )
            cv2.circle(
                annotated, upper_inner, max(2, radius - 1), angle_color, -1
            )
            cv2.circle(
                annotated, lower_inner, max(2, radius - 1), angle_color, -1
            )
            summary_lines.extend(
                (
                    "REL EYE "
                    f"{(geometry_payload['relative_eye_length'][f'relative_eye_length_{side}'] if geometry_payload is not None else eye_width_px / face_width_px):.4f}",
                    f"EYE W/H {eye_width_px / eye_height_px:.4f}",
                    "LOWER LID "
                    f"{(geometry_payload['lower_lid_space'][f'lower_lid_space_ratio_{side}'] if geometry_payload is not None else lower_lid_geometry.ratio):.4f}",
                    "INNER ANGLE "
                    f"{(geometry_payload['inner_corner_angle'][f'inner_corner_angle_{side}_deg'] if geometry_payload is not None else inner_angle):.2f} deg",
                )
            )

        for row, summary in enumerate(summary_lines):
            text_y = min(summary_y + row * line_gap, image_height - 8)
            cv2.putText(
                annotated,
                summary,
                (label_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale * 0.88,
                (0, 0, 0),
                thickness + 2,
                cv2.LINE_AA,
            )
            cv2.putText(
                annotated,
                summary,
                (label_x, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale * 0.88,
                color,
                thickness,
                cv2.LINE_AA,
            )
    return annotated


def save_geometry_json(output_path: Path, payload: dict) -> None:
    """Write strict JSON; allow_nan=False rejects NaN and infinity."""
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
        raise FaceLandmarkerError(
            f"Face geometry JSON 写入失败：{output_path}：{exc}"
        ) from exc


def process_eye_geometry(
    image_path: Path,
    model_path: Path,
    debug_output_path: Path,
    json_output_path: Path,
    input_is_mirrored: bool = False,
    profile_output_path: Optional[Path] = None,
) -> dict:
    """Run the existing detector once, then create eye debug and JSON outputs."""
    image = read_image(image_path)
    with FaceLandmarkerDetector(model_path=model_path, max_faces=1) as detector:
        face_landmarks = detector.detect(image)

    eyes = extract_eye_landmarks(face_landmarks, input_is_mirrored)
    brows = extract_brow_landmarks(face_landmarks, input_is_mirrored)
    rule_landmarks = extract_rule_landmarks(
        face_landmarks, input_is_mirrored
    )
    image_height, image_width = image.shape[:2]
    payload = build_face_geometry_payload(
        eyes,
        image_width=image_width,
        image_height=image_height,
        input_is_mirrored=input_is_mirrored,
        brows=brows,
        rule_landmarks=rule_landmarks,
    )
    debug_image = draw_eye_landmarks(
        image,
        eyes,
        brows,
        rule_landmarks,
        geometry_payload=payload,
    )
    save_image(debug_output_path, debug_image)
    save_geometry_json(json_output_path, payload)
    if profile_output_path is not None:
        profile = build_face_profile(
            payload, raw_geometry_source=Path(json_output_path).name
        )
        save_face_profile(profile_output_path, profile)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="提取并可视化眼部关键点，计算第一批眼部几何特征。"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_IMAGE_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument(
        "--debug-output", type=Path, default=DEFAULT_EYE_DEBUG_PATH
    )
    parser.add_argument(
        "--json-output", type=Path, default=DEFAULT_GEOMETRY_JSON_PATH
    )
    parser.add_argument(
        "--profile-output", type=Path, default=DEFAULT_PROFILE_PATH
    )
    parser.add_argument(
        "--mirrored-input",
        action="store_true",
        help="输入文件已经水平镜像；交换左右眼组以保持人物本人 left/right。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = process_eye_geometry(
            image_path=args.input,
            model_path=args.model,
            debug_output_path=args.debug_output,
            json_output_path=args.json_output,
            input_is_mirrored=args.mirrored_input,
            profile_output_path=args.profile_output,
        )
    except (FaceLandmarkerError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    left = payload["eyes"]["left"]
    right = payload["eyes"]["right"]
    geometry = payload["geometry"]
    tail = payload["eye_tail_angle"]
    brow_eye = payload["brow_eye"]
    relative_eye_length = payload["relative_eye_length"]
    eye_width_height_ratio = payload["eye_width_height_ratio"]
    lower_lid_space = payload["lower_lid_space"]
    inner_corner_angle = payload["inner_corner_angle"]
    asymmetry = payload["asymmetry"]
    print(
        "左眼 width/height/aspect_ratio："
        f"{left['width_px']} px / {left['height_px']} px / "
        f"{left['aspect_ratio']}"
    )
    print(
        "右眼 width/height/aspect_ratio："
        f"{right['width_px']} px / {right['height_px']} px / "
        f"{right['aspect_ratio']}"
    )
    print(
        "眼距 / 平均眼宽 / eye_spacing_ratio："
        f"{geometry['inner_eye_distance_px']} px / "
        f"{geometry['mean_eye_width_px']} px / "
        f"{geometry['eye_spacing_ratio']}"
    )
    print(
        "眼尾角 left / right / mean："
        f"{tail['left_eye_tail_angle_deg']}° / "
        f"{tail['right_eye_tail_angle_deg']}° / "
        f"{tail['mean_eye_tail_angle_deg']}°"
    )
    print(
        "眉眼距离 left / right；ratio left / right / mean："
        f"{brow_eye['left_brow_eye_distance_px']} px / "
        f"{brow_eye['right_brow_eye_distance_px']} px；"
        f"{brow_eye['left_brow_eye_ratio']} / "
        f"{brow_eye['right_brow_eye_ratio']} / "
        f"{brow_eye['mean_brow_eye_ratio']}"
    )
    print(
        "相对眼长 left / right / mean；face width："
        f"{relative_eye_length['relative_eye_length_left']} / "
        f"{relative_eye_length['relative_eye_length_right']} / "
        f"{relative_eye_length['relative_eye_length_mean']}；"
        f"{relative_eye_length['face_width_px']} px"
    )
    print(
        "眼宽高比 left / right / mean："
        f"{eye_width_height_ratio['eye_width_height_ratio_left']} / "
        f"{eye_width_height_ratio['eye_width_height_ratio_right']} / "
        f"{eye_width_height_ratio['eye_width_height_ratio_mean']}"
    )
    print(
        "下眼睑空间 px left / right / mean；ratio left / right / mean："
        f"{lower_lid_space['lower_lid_space_px_left']} / "
        f"{lower_lid_space['lower_lid_space_px_right']} / "
        f"{lower_lid_space['lower_lid_space_px_mean']}；"
        f"{lower_lid_space['lower_lid_space_ratio_left']} / "
        f"{lower_lid_space['lower_lid_space_ratio_right']} / "
        f"{lower_lid_space['lower_lid_space_ratio_mean']}"
    )
    print(
        "内眼角角度 left / right / mean："
        f"{inner_corner_angle['inner_corner_angle_left_deg']}° / "
        f"{inner_corner_angle['inner_corner_angle_right_deg']}° / "
        f"{inner_corner_angle['inner_corner_angle_mean_deg']}°"
    )
    print(
        "左右差异 width / height / aspect / angle："
        f"{asymmetry['eye_width_asymmetry']} / "
        f"{asymmetry['eye_height_asymmetry']} / "
        f"{asymmetry['eye_aspect_ratio_asymmetry']} / "
        f"{asymmetry['eye_tail_angle_difference_deg']}°"
    )
    print(f"Eye debug 图：{args.debug_output.resolve()}")
    print(f"Face geometry JSON：{args.json_output.resolve()}")
    print(f"Face Profile JSON：{args.profile_output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
