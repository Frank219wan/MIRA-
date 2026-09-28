"""Run the existing eye-geometry pipeline over every JPG in data/input."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Iterable, Mapping

try:
    from .eye_landmarks import process_eye_geometry, save_geometry_json
    from .face_landmarker import (
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerError,
    )
except ImportError:  # Support: python src/batch_analyze.py
    from eye_landmarks import (  # type: ignore
        process_eye_geometry,
        save_geometry_json,
    )
    from face_landmarker import (  # type: ignore
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerError,
    )


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_BATCH_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "batch"
DEFAULT_SUMMARY_CSV_PATH = PROJECT_ROOT / "data" / "output" / "face_summary.csv"

SUMMARY_FIELDS = (
    "filename",
    "eye_tail_angle_left",
    "eye_tail_angle_right",
    "mean_eye_tail_angle",
    "eye_spacing_ratio",
    "relative_eye_length_left",
    "relative_eye_length_right",
    "relative_eye_length_mean",
    "eye_width_height_ratio_left",
    "eye_width_height_ratio_right",
    "eye_width_height_ratio_mean",
    "left_brow_eye_ratio",
    "right_brow_eye_ratio",
    "lower_lid_space_px_left",
    "lower_lid_space_px_right",
    "lower_lid_space_px_mean",
    "lower_lid_space_ratio_left",
    "lower_lid_space_ratio_right",
    "lower_lid_space_ratio_mean",
    "inner_corner_angle_left_deg",
    "inner_corner_angle_right_deg",
    "inner_corner_angle_mean_deg",
    "eye_width_asymmetry",
    "eye_height_asymmetry",
    "eye_aspect_ratio_asymmetry",
    "error",
)


def discover_jpg_images(input_dir: Path) -> list[Path]:
    """Return lowercase .jpg inputs in deterministic filename order."""
    input_dir = Path(input_dir)
    if not input_dir.is_dir():
        raise FaceLandmarkerError(f"批处理输入目录不存在：{input_dir}")
    return sorted(
        (path for path in input_dir.glob("*.jpg") if path.is_file()),
        key=lambda path: path.name,
    )


def _success_row(filename: str, payload: Mapping) -> dict:
    tail = payload["eye_tail_angle"]
    geometry = payload["geometry"]
    relative_eye_length = payload["relative_eye_length"]
    eye_width_height_ratio = payload["eye_width_height_ratio"]
    brow_eye = payload["brow_eye"]
    lower_lid_space = payload["lower_lid_space"]
    inner_corner_angle = payload["inner_corner_angle"]
    asymmetry = payload["asymmetry"]
    return {
        "filename": filename,
        "eye_tail_angle_left": tail["left_eye_tail_angle_deg"],
        "eye_tail_angle_right": tail["right_eye_tail_angle_deg"],
        "mean_eye_tail_angle": tail["mean_eye_tail_angle_deg"],
        "eye_spacing_ratio": geometry["eye_spacing_ratio"],
        "relative_eye_length_left": relative_eye_length[
            "relative_eye_length_left"
        ],
        "relative_eye_length_right": relative_eye_length[
            "relative_eye_length_right"
        ],
        "relative_eye_length_mean": relative_eye_length[
            "relative_eye_length_mean"
        ],
        "eye_width_height_ratio_left": eye_width_height_ratio[
            "eye_width_height_ratio_left"
        ],
        "eye_width_height_ratio_right": eye_width_height_ratio[
            "eye_width_height_ratio_right"
        ],
        "eye_width_height_ratio_mean": eye_width_height_ratio[
            "eye_width_height_ratio_mean"
        ],
        "left_brow_eye_ratio": brow_eye["left_brow_eye_ratio"],
        "right_brow_eye_ratio": brow_eye["right_brow_eye_ratio"],
        "lower_lid_space_px_left": lower_lid_space[
            "lower_lid_space_px_left"
        ],
        "lower_lid_space_px_right": lower_lid_space[
            "lower_lid_space_px_right"
        ],
        "lower_lid_space_px_mean": lower_lid_space[
            "lower_lid_space_px_mean"
        ],
        "lower_lid_space_ratio_left": lower_lid_space[
            "lower_lid_space_ratio_left"
        ],
        "lower_lid_space_ratio_right": lower_lid_space[
            "lower_lid_space_ratio_right"
        ],
        "lower_lid_space_ratio_mean": lower_lid_space[
            "lower_lid_space_ratio_mean"
        ],
        "inner_corner_angle_left_deg": inner_corner_angle[
            "inner_corner_angle_left_deg"
        ],
        "inner_corner_angle_right_deg": inner_corner_angle[
            "inner_corner_angle_right_deg"
        ],
        "inner_corner_angle_mean_deg": inner_corner_angle[
            "inner_corner_angle_mean_deg"
        ],
        "eye_width_asymmetry": asymmetry["eye_width_asymmetry"],
        "eye_height_asymmetry": asymmetry["eye_height_asymmetry"],
        "eye_aspect_ratio_asymmetry": asymmetry[
            "eye_aspect_ratio_asymmetry"
        ],
        "error": "",
    }


def _error_row(filename: str, error_message: str) -> dict:
    row = {field: "" for field in SUMMARY_FIELDS}
    row["filename"] = filename
    row["error"] = error_message
    return row


def save_summary_csv(output_path: Path, rows: Iterable[Mapping]) -> None:
    """Write the batch summary with a stable schema and UTF-8 encoding."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=SUMMARY_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, csv.Error) as exc:
        raise FaceLandmarkerError(
            f"Batch summary CSV 写入失败：{output_path}：{exc}"
        ) from exc


def analyze_batch(
    input_dir: Path = DEFAULT_INPUT_DIR,
    model_path: Path = DEFAULT_MODEL_PATH,
    batch_output_dir: Path = DEFAULT_BATCH_OUTPUT_DIR,
    summary_csv_path: Path = DEFAULT_SUMMARY_CSV_PATH,
    input_is_mirrored: bool = False,
) -> list[dict]:
    """Analyze every input JPG while isolating failures to individual rows."""
    image_paths = discover_jpg_images(input_dir)
    if not image_paths:
        raise FaceLandmarkerError(
            f"批处理输入目录中没有找到 JPG 图片：{Path(input_dir)}"
        )

    batch_output_dir = Path(batch_output_dir)
    batch_output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for image_path in image_paths:
        geometry_path = batch_output_dir / f"{image_path.stem}_geometry.json"
        debug_path = batch_output_dir / f"{image_path.stem}_debug.jpg"
        try:
            # Reuse the complete, tested single-image pipeline. Detection,
            # landmark extraction, geometry, validation, and JSON writing stay
            # owned by their existing modules.
            payload = process_eye_geometry(
                image_path=image_path,
                model_path=model_path,
                debug_output_path=debug_path,
                json_output_path=geometry_path,
                input_is_mirrored=input_is_mirrored,
            )
            row = _success_row(image_path.name, payload)
            print(f"成功：{image_path.name} -> {geometry_path}")
        except (FaceLandmarkerError, ValueError) as exc:
            error_message = str(exc)
            error_payload = {
                "face_detected": False,
                "filename": image_path.name,
                "error": error_message,
            }
            save_geometry_json(geometry_path, error_payload)
            row = _error_row(image_path.name, error_message)
            print(f"失败：{image_path.name}：{error_message}", file=sys.stderr)
        rows.append(row)

    save_summary_csv(summary_csv_path, rows)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="批量分析 data/input/*.jpg 并生成 geometry JSON 与 CSV。"
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument(
        "--batch-output-dir", type=Path, default=DEFAULT_BATCH_OUTPUT_DIR
    )
    parser.add_argument(
        "--summary-csv", type=Path, default=DEFAULT_SUMMARY_CSV_PATH
    )
    parser.add_argument(
        "--mirrored-input",
        action="store_true",
        help="所有输入文件均已水平镜像；保持人物本人 left/right 语义。",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        rows = analyze_batch(
            input_dir=args.input_dir,
            model_path=args.model,
            batch_output_dir=args.batch_output_dir,
            summary_csv_path=args.summary_csv,
            input_is_mirrored=args.mirrored_input,
        )
    except FaceLandmarkerError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1

    success_count = sum(not row["error"] for row in rows)
    print(f"Batch 完成：成功 {success_count}/{len(rows)}")
    print(f"CSV：{args.summary_csv.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
