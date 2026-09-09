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
        Point2D,
        calculate_brow_eye_geometry,
        calculate_eye_asymmetry,
        calculate_eye_geometry,
        calculate_eye_spacing,
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
except ImportError:  # Support: python src/eye_landmarks.py
    from face_geometry import (  # type: ignore
        BrowEyeGeometry,
        EyeGeometry,
        Point2D,
        calculate_brow_eye_geometry,
        calculate_eye_asymmetry,
        calculate_eye_geometry,
        calculate_eye_spacing,
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


def _landmark_payload(
    landmark: LandmarkPoint,
    image_width: int,
    image_height: int,
) -> dict:
    pixel = landmark.to_pixel(image_width, image_height)
    return {
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


def _eye_payload(
    eye: EyeLandmarks,
    geometry: EyeGeometry,
    image_width: int,
    image_height: int,
) -> dict:
    payload = {
        name: _landmark_payload(landmark, image_width, image_height)
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
) -> dict:
    return {
        "reference_landmark_indices": [point.index for point in brow.points],
        "reference_landmarks": [
            _landmark_payload(point, image_width, image_height)
            for point in brow.points
        ],
        "reference_point_px": _point_payload(geometry.reference_point),
        "eye_axis_projection_px": _point_payload(
            geometry.eye_axis_projection
        ),
        "distance_px": round(geometry.distance_px, 3),
        "ratio": round(geometry.ratio, 4),
    }


def build_face_geometry_payload(
    eyes: ExtractedEyes,
    image_width: int,
    image_height: int,
    input_is_mirrored: bool = False,
    brows: Optional[ExtractedBrows] = None,
) -> dict:
    """Build the JSON-ready eye geometry payload from extracted eye points."""
    if image_width <= 1 or image_height <= 1:
        raise FaceLandmarkerError("图片宽高必须大于 1 pixel。")

    left_points = _eye_pixel_points(eyes.left, image_width, image_height)
    right_points = _eye_pixel_points(eyes.right, image_width, image_height)

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
            "eye_side_semantics": "detected person's anatomical left/right",
            "input_is_mirrored": input_is_mirrored,
        },
        "eyes": {
            "left": _eye_payload(
                eyes.left, left_geometry, image_width, image_height
            ),
            "right": _eye_payload(
                eyes.right, right_geometry, image_width, image_height
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

    if brows is not None:
        left_brow_points = _brow_pixel_points(
            brows.left, image_width, image_height
        )
        right_brow_points = _brow_pixel_points(
            brows.right, image_width, image_height
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
            ),
            "right": _brow_payload(
                brows.right,
                right_brow_geometry,
                image_width,
                image_height,
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
):
    """Draw eye geometry plus optional multi-point brow measurements."""
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

    eye_entries = (("left", eyes.left), ("right", eyes.right))
    brows_by_side = (
        {"left": brows.left, "right": brows.right}
        if brows is not None
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

        tail_angle = eye_tail_angle_deg(
            points["inner_corner"], points["outer_corner"]
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
                    f"BROW/EYE {brow_geometry.ratio:.4f}",
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
    image_height, image_width = image.shape[:2]
    payload = build_face_geometry_payload(
        eyes,
        image_width=image_width,
        image_height=image_height,
        input_is_mirrored=input_is_mirrored,
        brows=brows,
    )
    debug_image = draw_eye_landmarks(image, eyes, brows)
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
