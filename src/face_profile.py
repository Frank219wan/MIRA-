"""Build the stable, high-level Face Profile contract from raw geometry."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GEOMETRY_PATH = PROJECT_ROOT / "data" / "output" / "face_geometry.json"
DEFAULT_PROFILE_PATH = PROJECT_ROOT / "data" / "output" / "face_profile.json"
FACE_PROFILE_VERSION = "0.1"


class FaceProfileError(ValueError):
    """Raised when geometry cannot satisfy the Face Profile contract."""


def _required_value(data: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    traversed: list[str] = []
    for key in path:
        traversed.append(key)
        if not isinstance(current, Mapping) or key not in current:
            raise FaceProfileError(
                "Face geometry 缺少必要字段：" + ".".join(traversed)
            )
        current = current[key]
    return current


def _required_finite_number(
    data: Mapping[str, Any], path: tuple[str, ...]
) -> float:
    value = _required_value(data, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FaceProfileError(
            f"Face geometry 字段必须是数值：{'.'.join(path)}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise FaceProfileError(
            f"Face geometry 字段不能是 NaN 或 infinity：{'.'.join(path)}"
        )
    return number


def build_face_profile(
    geometry: Mapping[str, Any],
    raw_geometry_source: str = "face_geometry.json",
) -> dict:
    """Map validated continuous geometry values to Face Profile v0.1.

    This is deliberately an output-contract layer: it performs no landmark
    inference, geometry calculation, classification, or aesthetic judgement.
    """
    if not isinstance(geometry, Mapping):
        raise FaceProfileError("Face geometry 输入必须是 dict/object。")
    if geometry.get("face_detected") is not True:
        raise FaceProfileError("Face geometry 未包含成功的人脸检测结果。")

    number = lambda *path: _required_finite_number(geometry, tuple(path))
    profile = {
        "version": FACE_PROFILE_VERSION,
        "eye_geometry": {
            "eye_tail_angle": {
                "left": number(
                    "eye_tail_angle", "left_eye_tail_angle_deg"
                ),
                "right": number(
                    "eye_tail_angle", "right_eye_tail_angle_deg"
                ),
                "mean": number(
                    "eye_tail_angle", "mean_eye_tail_angle_deg"
                ),
            },
            "eye_spacing_ratio": number("geometry", "eye_spacing_ratio"),
            "brow_eye_ratio": {
                "left": number("brow_eye", "left_brow_eye_ratio"),
                "right": number("brow_eye", "right_brow_eye_ratio"),
                "mean": number("brow_eye", "mean_brow_eye_ratio"),
            },
        },
        "symmetry": {
            "eye_width": number("asymmetry", "eye_width_asymmetry"),
            "eye_height": number("asymmetry", "eye_height_asymmetry"),
            "eye_aspect_ratio": number(
                "asymmetry", "eye_aspect_ratio_asymmetry"
            ),
            "eye_tail_angle_difference": number(
                "asymmetry", "eye_tail_angle_difference_deg"
            ),
        },
        "raw_geometry_reference": {"source": raw_geometry_source},
        "confidence": {
            "pose_normalized": False,
            "expression_controlled": False,
        },
    }
    return profile


def load_geometry_json(input_path: Path) -> dict:
    """Load a geometry object from strict JSON with a clear error message."""
    input_path = Path(input_path)
    if not input_path.is_file():
        raise FaceProfileError(f"Face geometry JSON 不存在：{input_path}")
    try:
        with input_path.open(encoding="utf-8") as input_file:
            geometry = json.load(input_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise FaceProfileError(
            f"Face geometry JSON 读取失败：{input_path}：{exc}"
        ) from exc
    if not isinstance(geometry, dict):
        raise FaceProfileError("Face geometry JSON 顶层必须是 object。")
    return geometry


def save_face_profile(output_path: Path, profile: Mapping[str, Any]) -> None:
    """Write a Face Profile as strict JSON, rejecting NaN and infinity."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as output_file:
            json.dump(
                profile,
                output_file,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            output_file.write("\n")
    except (OSError, ValueError) as exc:
        raise FaceProfileError(
            f"Face Profile JSON 写入失败：{output_path}：{exc}"
        ) from exc


def build_face_profile_file(
    geometry_path: Path = DEFAULT_GEOMETRY_PATH,
    profile_path: Path = DEFAULT_PROFILE_PATH,
) -> dict:
    """Load geometry, build its profile, and write the profile JSON."""
    geometry_path = Path(geometry_path)
    geometry = load_geometry_json(geometry_path)
    profile = build_face_profile(
        geometry, raw_geometry_source=geometry_path.name
    )
    save_face_profile(profile_path, profile)
    return profile


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="从 face_geometry.json 构建 Face Profile v0.1。"
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_GEOMETRY_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_PROFILE_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        build_face_profile_file(args.input, args.output)
    except FaceProfileError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 1
    print(f"Face Profile：{args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
