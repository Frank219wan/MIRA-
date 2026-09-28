"""Build EyeLocalProfile v0.1 validation artifacts for tutorial and face_05-11."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

import cv2

if __package__:
    from .eye_local_profile import (
        EyeLocalKeypoints,
        build_eye_local_profile,
        build_eye_local_profile_from_mediapipe,
        mediapipe_keypoints,
        save_eye_local_profile,
    )
    from .face_geometry import Point2D
    from .face_landmarker import (
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerDetector,
        read_image,
    )
else:
    from eye_local_profile import (  # type: ignore
        EyeLocalKeypoints,
        build_eye_local_profile,
        build_eye_local_profile_from_mediapipe,
        mediapipe_keypoints,
        save_eye_local_profile,
    )
    from face_geometry import Point2D  # type: ignore
    from face_landmarker import (  # type: ignore
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerDetector,
        read_image,
    )


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "eye_local_profile"
REFERENCE_IMAGE = PROJECT_ROOT / "examples" / "reference" / "cat_eye_reference.jpg"
REFERENCE_POINTS = (
    PROJECT_ROOT / "examples" / "reference" / "cat_eye_reference_bare_eye_points.json"
)
REFERENCE_ACTION = (
    PROJECT_ROOT / "data" / "output" / "reference_action"
    / "cat_eye_reference_annotation.json"
)
FULL_PROFILE_DIR = (
    PROJECT_ROOT / "data" / "output" / "rule_calibration_dataset"
    / "individual_profiles"
)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(
            handle,
            parse_constant=lambda item: (_ for _ in ()).throw(ValueError(item)),
        )
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _point(value: Mapping[str, Any]) -> Point2D:
    return Point2D(float(value["x"]), float(value["y"]))


def _point_tuple(value: Any) -> tuple[Point2D, ...] | None:
    if value is None:
        return None
    return tuple(_point(item) for item in value)


def _tutorial_profile() -> tuple[dict[str, Any], EyeLocalKeypoints, Any]:
    source = _read_json(REFERENCE_POINTS)
    image = read_image(REFERENCE_IMAGE)
    crop = source["crop"]
    split_y = round(image.shape[0] * float(crop["split"]))
    bare_eye = image[:split_y].copy()
    values = source["points"]
    points = EyeLocalKeypoints(
        eye_inner=_point(values["eye_inner"]),
        eye_outer=_point(values["eye_outer"]),
        eye_upper=_point(values["eye_upper"]),
        eye_lower=_point(values["eye_lower"]),
        inner_upper=_point(values["inner_upper"]),
        inner_lower=_point(values["inner_lower"]),
        brow_references=_point_tuple(values.get("brow_references")),
        lower_lid_points=_point_tuple(values.get("lower_lid_points")),
        lower_lid_references=_point_tuple(values.get("lower_lid_references")),
    )
    quality = dict(source["quality"])
    quality.update(
        {
            "annotation_source": str(REFERENCE_POINTS.relative_to(PROJECT_ROOT)),
            "source_image": str(REFERENCE_IMAGE.relative_to(PROJECT_ROOT)),
            "crop_split": float(crop["split"]),
        }
    )
    profile = build_eye_local_profile(
        points,
        source_type="tutorial_reference",
        side=source["side"],
        quality=quality,
    )
    return profile, points, bare_eye


def _xy(point: Point2D) -> tuple[int, int]:
    return int(round(point.x)), int(round(point.y))


def _draw_debug(image: Any, points: EyeLocalKeypoints, title: str) -> Any:
    canvas = image.copy()
    cv2.line(canvas, _xy(points.eye_inner), _xy(points.eye_outer), (255, 180, 0), 2)
    cv2.line(canvas, _xy(points.eye_upper), _xy(points.eye_lower), (0, 220, 0), 2)
    cv2.line(canvas, _xy(points.eye_inner), _xy(points.inner_upper), (200, 0, 220), 2)
    cv2.line(canvas, _xy(points.eye_inner), _xy(points.inner_lower), (200, 0, 220), 2)
    for point in (
        points.eye_inner,
        points.eye_outer,
        points.eye_upper,
        points.eye_lower,
        points.inner_upper,
        points.inner_lower,
    ):
        cv2.circle(canvas, _xy(point), 4, (0, 80, 255), -1)
    for point in points.brow_references or ():
        cv2.circle(canvas, _xy(point), 4, (0, 255, 255), -1)
    if points.lower_lid_points and points.lower_lid_references:
        for lower, reference in zip(
            points.lower_lid_points, points.lower_lid_references
        ):
            cv2.line(canvas, _xy(lower), _xy(reference), (255, 0, 180), 2)
            cv2.circle(canvas, _xy(lower), 3, (255, 0, 180), -1)
            cv2.circle(canvas, _xy(reference), 3, (255, 0, 180), -1)
    cv2.rectangle(canvas, (0, 0), (min(canvas.shape[1], 560), 30), (20, 20, 20), -1)
    cv2.putText(
        canvas, title, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
        (255, 255, 255), 1, cv2.LINE_AA,
    )
    return canvas


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _comparison_row(sample_id: str, profile: Mapping[str, Any]) -> dict[str, Any]:
    geometry = profile["geometry"]
    quality = profile["quality"]
    return {
        "sample_id": sample_id,
        "source_type": profile["source_type"],
        "side": profile["side"],
        "eye_width_height_ratio": geometry["eye_width_height_ratio"],
        "eye_axis_angle_deg": geometry["eye_axis_angle_deg"],
        "inner_corner_angle_deg": geometry["inner_corner_angle_deg"],
        "lower_lid_space_ratio_local": geometry["lower_lid_space_ratio_local"],
        "brow_eye_ratio_local": geometry["brow_eye_ratio_local"],
        "is_directly_comparable": quality.get("is_directly_comparable", False),
        "quality_note": quality.get(
            "quality_note", "MediaPipe landmarks; assumed unmirrored input."
        ),
    }


def _full_row(
    sample_id: str,
    local: Mapping[str, Any],
    full: Mapping[str, Any] | None,
    reference_action: Mapping[str, Any] | None,
) -> dict[str, Any]:
    local_geometry = local["geometry"]
    eye = full["eye_geometry"] if full is not None else None
    action_geometry = reference_action["geometry"] if reference_action else None
    return {
        "sample_id": sample_id,
        "source_type": local["source_type"],
        "side": local["side"],
        "full_face_eye_tail_angle_mean": eye["eye_tail_angle"]["mean"] if eye else None,
        "full_face_relative_eye_length_mean": eye["relative_eye_length"]["mean"] if eye else None,
        "full_face_lower_lid_space_ratio_mean": eye["lower_lid_space_ratio"]["mean"] if eye else None,
        "full_face_inner_corner_angle_mean_deg": eye["inner_corner_angle"]["mean_deg"] if eye else None,
        "full_face_brow_eye_ratio_mean": eye["brow_eye_ratio"]["mean"] if eye else None,
        "eye_local_width_height_ratio": local_geometry["eye_width_height_ratio"],
        "eye_local_axis_angle_deg": local_geometry["eye_axis_angle_deg"],
        "eye_local_inner_corner_angle_deg": local_geometry["inner_corner_angle_deg"],
        "eye_local_lower_lid_space_ratio": local_geometry["lower_lid_space_ratio_local"],
        "eye_local_brow_eye_ratio": local_geometry["brow_eye_ratio_local"],
        "direction_relative_to_eye_axis_deg": (
            action_geometry["direction_relative_to_eye_axis_deg"] if action_geometry else None
        ),
        "reference_extension_ratio": (
            action_geometry["eyeliner_extension_ratio"] if action_geometry else None
        ),
        "start_position_ratio": (
            action_geometry["start_position_ratio"] if action_geometry else None
        ),
    }


def build_dataset(output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    profiles_dir = output_dir / "individual_profiles"
    debug_dir = output_dir / "debug"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    debug_dir.mkdir(parents=True, exist_ok=True)

    tutorial_profile, tutorial_points, tutorial_image = _tutorial_profile()
    save_eye_local_profile(
        profiles_dir / "cat_eye_reference_bare_eye_local_profile.json",
        tutorial_profile,
    )
    cv2.imwrite(
        str(debug_dir / "cat_eye_reference_bare_debug.jpg"),
        _draw_debug(tutorial_image, tutorial_points, "cat_eye_reference bare eye"),
    )

    profiles: list[tuple[str, dict[str, Any], dict[str, Any] | None]] = [
        ("cat_eye_reference_bare", tutorial_profile, None)
    ]
    with FaceLandmarkerDetector(DEFAULT_MODEL_PATH, max_faces=1) as detector:
        for number in range(5, 12):
            sample_id = f"face_{number:02d}"
            image_path = PROJECT_ROOT / "data" / "input" / f"{sample_id}.jpg"
            image = read_image(image_path)
            landmarks = detector.detect(image)
            height, width = image.shape[:2]
            local_points = mediapipe_keypoints(
                landmarks,
                image_width=width,
                image_height=height,
                subject_side="right",
                input_is_mirrored=False,
            )
            local_profile = build_eye_local_profile_from_mediapipe(
                landmarks,
                image_width=width,
                image_height=height,
                subject_side="right",
                input_is_mirrored=False,
            )
            save_eye_local_profile(
                profiles_dir / f"{sample_id}_eye_local_profile.json", local_profile
            )
            cv2.imwrite(
                str(debug_dir / f"{sample_id}_debug.jpg"),
                _draw_debug(image, local_points, f"{sample_id} subject right / image left"),
            )
            full_profile = _read_json(
                FULL_PROFILE_DIR / f"{sample_id}_face_profile.json"
            )
            profiles.append((sample_id, local_profile, full_profile))

    reference_action = _read_json(REFERENCE_ACTION)
    comparison_rows = [
        _comparison_row(sample_id, profile) for sample_id, profile, _ in profiles
    ]
    comparison_fields = list(comparison_rows[0])
    comparison_path = output_dir / "reference_vs_face05_11.csv"
    _write_csv(comparison_path, comparison_fields, comparison_rows)

    full_rows = [
        _full_row(
            sample_id,
            profile,
            full,
            reference_action if sample_id == "cat_eye_reference_bare" else None,
        )
        for sample_id, profile, full in profiles
    ]
    full_fields = list(full_rows[0])
    full_path = output_dir / "reference_and_users_full_report.csv"
    _write_csv(full_path, full_fields, full_rows)

    report = {
        "version": "0.1",
        "tutorial_split": 0.52,
        "selected_user_eye": {
            "subject_side": "right",
            "image_side": "left",
            "input_is_mirrored": False,
            "reason": "Matches the tutorial eye's inner-right/outer-left visual orientation.",
        },
        "profiles": {sample_id: profile for sample_id, profile, _ in profiles},
        "reference_action_geometry": {
            "direction_relative_to_eye_axis_deg": reference_action["geometry"]["direction_relative_to_eye_axis_deg"],
            "reference_extension_ratio": reference_action["geometry"]["eyeliner_extension_ratio"],
            "start_position_ratio": reference_action["geometry"]["start_position_ratio"],
        },
        "outputs": {
            "comparison_csv": str(comparison_path.relative_to(PROJECT_ROOT)),
            "full_report_csv": str(full_path.relative_to(PROJECT_ROOT)),
        },
    }
    with (output_dir / "eye_local_profile_report.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    report = build_dataset(args.output_dir)
    print(f"Generated {len(report['profiles'])} EyeLocalProfile rows.")
    print(f"Output: {args.output_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
