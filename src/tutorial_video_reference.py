"""Bridge timestamped tutorial-video frames into the existing CV pipeline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

import cv2

from .personalization_engine import load_json_object, save_json_output
from .reference_action_geometry import build_reference_action_geometry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "tutorial_video_reference"


class TutorialVideoReferenceError(ValueError):
    """Raised when a tutorial frame or reference package cannot be produced."""


def _finite_timestamp(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TutorialVideoReferenceError(f"{label} timestamp must be numeric.")
    timestamp = float(value)
    if not math.isfinite(timestamp):
        raise TutorialVideoReferenceError(f"{label} timestamp must be finite.")
    if timestamp < 0.0:
        raise TutorialVideoReferenceError(
            f"{label} timestamp must be greater than or equal to zero."
        )
    return timestamp


def _video_metadata(capture: Any, video_path: Path) -> tuple[float, int, float]:
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count_value = float(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    if not math.isfinite(fps) or fps <= 0.0:
        raise TutorialVideoReferenceError(
            f"Video has invalid or unavailable FPS metadata: {video_path.name}"
        )
    if (
        not math.isfinite(frame_count_value)
        or frame_count_value < 1.0
    ):
        raise TutorialVideoReferenceError(
            f"Video has invalid or unavailable frame count: {video_path.name}"
        )
    frame_count = int(round(frame_count_value))
    duration = frame_count / fps
    if not math.isfinite(duration) or duration <= 0.0:
        raise TutorialVideoReferenceError(
            f"Video has invalid duration metadata: {video_path.name}"
        )
    return fps, frame_count, duration


def extract_frame(video_path: Path | str, timestamp_sec: float) -> Any:
    """Return the frame containing ``timestamp_sec`` without silent fallback."""

    path = Path(video_path)
    timestamp = _finite_timestamp(timestamp_sec, "Frame")
    if not path.is_file():
        raise TutorialVideoReferenceError(f"Video file does not exist: {path}")
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        capture.release()
        raise TutorialVideoReferenceError(f"Could not open video: {path.name}")
    try:
        fps, frame_count, duration = _video_metadata(capture, path)
        if timestamp >= duration:
            raise TutorialVideoReferenceError(
                f"Timestamp {timestamp_sec} is outside video duration "
                f"[0, {duration:.6f}) seconds."
            )
        frame_index = int(math.floor(timestamp * fps + 1e-9))
        if frame_index < 0 or frame_index >= frame_count:
            raise TutorialVideoReferenceError(
                f"Timestamp {timestamp_sec} resolves outside the video frames."
            )
        if not capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index):
            raise TutorialVideoReferenceError(
                f"Could not seek to frame {frame_index} at {timestamp_sec} seconds."
            )
        ok, frame = capture.read()
        if not ok or frame is None or frame.size == 0:
            raise TutorialVideoReferenceError(
                f"Could not decode frame {frame_index} at {timestamp_sec} seconds."
            )
        return frame
    finally:
        capture.release()


def extract_reference_frames(
    video_path: Path | str,
    *,
    before_timestamp: float,
    a04_action_timestamp: float,
    after_timestamp: float,
    video_id: str | None = None,
) -> dict[str, Any]:
    """Extract BEFORE/A04/AFTER frames and portable source metadata."""

    path = Path(video_path)
    timestamps = {
        "before": _finite_timestamp(before_timestamp, "BEFORE"),
        "A04": _finite_timestamp(a04_action_timestamp, "A04"),
        "after": _finite_timestamp(after_timestamp, "AFTER"),
    }
    if not timestamps["before"] <= timestamps["A04"] <= timestamps["after"]:
        raise TutorialVideoReferenceError(
            "Timestamps must satisfy before <= A04 <= after."
        )
    identifier = video_id if video_id is not None else path.stem
    if not isinstance(identifier, str) or not identifier.strip():
        raise TutorialVideoReferenceError("video_id must be a non-empty string.")
    frames = {
        label: extract_frame(path, timestamp)
        for label, timestamp in timestamps.items()
    }
    return {
        "frames": frames,
        "metadata": {
            "source_type": "video",
            "video_id": identifier,
            "video_filename": path.name,
            "timestamps": timestamps,
        },
    }


def _write_frame(path: Path, frame: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(path), frame):
        raise TutorialVideoReferenceError(f"Could not write extracted frame: {path}")


def run_video_reference_pipeline(
    *,
    video_path: Path,
    before_timestamp: float,
    a04_action_timestamp: float,
    after_timestamp: float,
    annotation: Mapping[str, Any],
    tutorial_id: str,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    model_path: Path = DEFAULT_MODEL_PATH,
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    """Extract frames and reuse the existing Face Profile/A04 geometry pipeline."""

    from .eye_landmarks import process_eye_geometry
    from .reference_package import build_reference_package

    extracted = extract_reference_frames(
        video_path,
        before_timestamp=before_timestamp,
        a04_action_timestamp=a04_action_timestamp,
        after_timestamp=after_timestamp,
        video_id=tutorial_id,
    )
    output_dir = Path(output_dir)
    frame_paths = {
        "before": output_dir / "before_frame.jpg",
        "A04": output_dir / "a04_action_frame.jpg",
        "after": output_dir / "after_frame.jpg",
    }
    for label, path in frame_paths.items():
        _write_frame(path, extracted["frames"][label])

    profile_path = output_dir / "blogger_before_face_profile.json"
    process_eye_geometry(
        image_path=frame_paths["before"],
        model_path=model_path,
        debug_output_path=output_dir / "blogger_before_debug.jpg",
        json_output_path=output_dir / "blogger_before_geometry.json",
        input_is_mirrored=input_is_mirrored,
        profile_output_path=profile_path,
    )
    blogger_profile = load_json_object(profile_path)
    reference_action = build_reference_action_geometry(
        annotation,
        reference_id=tutorial_id,
    )
    package = build_reference_package(
        tutorial_id=tutorial_id,
        video_filename=Path(video_path).name,
        timestamps={
            "before_sec": before_timestamp,
            "A04_sec": a04_action_timestamp,
            "after_sec": after_timestamp,
        },
        blogger_face_profile=blogger_profile,
        reference_action_geometry=reference_action,
        after_frame_available=True,
    )
    save_json_output(output_dir / "reference_action_geometry.json", reference_action)
    save_json_output(output_dir / "reference_package.json", package)
    return package


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--before", type=float, required=True)
    parser.add_argument("--a04", type=float, required=True)
    parser.add_argument("--after", type=float, required=True)
    parser.add_argument("--annotation", type=Path, required=True)
    parser.add_argument("--tutorial-id", default="cat_eye_video_demo")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--mirrored-input", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        annotation = load_json_object(args.annotation)
        package = run_video_reference_pipeline(
            video_path=args.video,
            before_timestamp=args.before,
            a04_action_timestamp=args.a04,
            after_timestamp=args.after,
            annotation=annotation,
            tutorial_id=args.tutorial_id,
            output_dir=args.output,
            model_path=args.model,
            input_is_mirrored=args.mirrored_input,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Tutorial video reference failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "reference_package": str(args.output / "reference_package.json"),
                "tutorial_id": package["tutorial_id"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
