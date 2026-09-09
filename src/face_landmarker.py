"""Detect and visualize face landmarks with the MediaPipe Tasks API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

import cv2
import mediapipe as mp


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE_PATH = PROJECT_ROOT / "data" / "input" / "selfie.jpg"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "data" / "output" / "landmarks_result.jpg"
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"


class FaceLandmarkerError(RuntimeError):
    """Raised when the face-landmark pipeline cannot complete."""


class FaceLandmarkerDetector:
    """Reusable single-image face-landmark detector."""

    def __init__(
        self,
        model_path: Path,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_presence_confidence: float = 0.5,
    ) -> None:
        self.model_path = Path(model_path)
        if not self.model_path.is_file():
            raise FaceLandmarkerError(
                f"MediaPipe 模型不存在：{self.model_path}\n"
                "请将 Face Landmarker 模型保存为 models/face_landmarker.task。"
            )

        options = mp.tasks.vision.FaceLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(
                model_asset_path=str(self.model_path),
                delegate=mp.tasks.BaseOptions.Delegate.CPU,
            ),
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_faces=max_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_presence_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        try:
            self._landmarker = (
                mp.tasks.vision.FaceLandmarker.create_from_options(options)
            )
        except (OSError, RuntimeError, ValueError) as exc:
            raise FaceLandmarkerError(
                f"无法加载 MediaPipe Face Landmarker 模型：{exc}"
            ) from exc

    def __enter__(self) -> "FaceLandmarkerDetector":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    def close(self) -> None:
        """Release native MediaPipe resources."""
        self._landmarker.close()

    def detect(self, bgr_image):
        """Return landmarks for the first detected face in an OpenCV BGR image."""
        if bgr_image is None or bgr_image.size == 0:
            raise FaceLandmarkerError("输入图片为空，无法进行人脸检测。")

        rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        mediapipe_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=rgb_image,
        )

        try:
            result = self._landmarker.detect(mediapipe_image)
        except (RuntimeError, ValueError) as exc:
            raise FaceLandmarkerError(f"人脸关键点检测失败：{exc}") from exc

        return require_first_face_landmarks(result)


def require_first_face_landmarks(result):
    """Return the first face or raise the pipeline's standard no-face error."""
    if not result.face_landmarks:
        raise FaceLandmarkerError(
            "未检测到人脸。请使用光线充足、无遮挡、面部正对镜头的自拍图片。"
        )
    return result.face_landmarks[0]


def read_image(image_path: Path):
    """Read an image with OpenCV and provide a useful error on failure."""
    image_path = Path(image_path)
    if not image_path.is_file():
        raise FaceLandmarkerError(f"输入图片不存在：{image_path}")

    image = cv2.imread(str(image_path))
    if image is None:
        raise FaceLandmarkerError(
            f"OpenCV 无法读取图片：{image_path}。请确认文件是有效的 JPG 图片。"
        )
    return image


def draw_landmarks(
    bgr_image,
    landmarks: Sequence,
    color: tuple[int, int, int] = (0, 255, 0),
    radius: int = 1,
):
    """Draw normalized landmarks on a copy of an OpenCV BGR image."""
    annotated = bgr_image.copy()
    height, width = annotated.shape[:2]

    for landmark in landmarks:
        x = min(max(round(landmark.x * (width - 1)), 0), width - 1)
        y = min(max(round(landmark.y * (height - 1)), 0), height - 1)
        cv2.circle(annotated, (x, y), radius, color, thickness=-1)

    return annotated


def save_image(output_path: Path, image) -> None:
    """Create the output directory and save an OpenCV image."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(output_path), image):
        raise FaceLandmarkerError(f"结果图片写入失败：{output_path}")


def process_image(image_path: Path, model_path: Path, output_path: Path) -> int:
    """Run the complete detection pipeline and return the landmark count."""
    image = read_image(image_path)
    with FaceLandmarkerDetector(model_path=model_path, max_faces=1) as detector:
        landmarks = detector.detect(image)

    annotated_image = draw_landmarks(image, landmarks)
    save_image(output_path, annotated_image)
    return len(landmarks)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="使用 MediaPipe Tasks Face Landmarker 检测并绘制人脸关键点。"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_IMAGE_PATH)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        landmark_count = process_image(args.input, args.model, args.output)
    except FaceLandmarkerError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    print(f"检测到的 landmark 数量：{landmark_count}")
    print(f"结果已保存至：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
