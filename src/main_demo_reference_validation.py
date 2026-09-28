"""Run the full-face Blogger reference validation without changing production math."""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping

import cv2

if __package__:
    from .eye_landmarks import process_eye_geometry
    from .face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT
    from .personalization_engine import load_json_object, save_json_output
    from .reference_action_adapter import (
        build_standard_recipe,
        personalize_reference_recipe,
    )
    from .reference_action_annotator import annotate_image
    from .reference_action_geometry import save_reference_action_geometry
else:
    from eye_landmarks import process_eye_geometry  # type: ignore
    from face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT  # type: ignore
    from personalization_engine import load_json_object, save_json_output  # type: ignore
    from reference_action_adapter import (  # type: ignore
        build_standard_recipe,
        personalize_reference_recipe,
    )
    from reference_action_annotator import annotate_image  # type: ignore
    from reference_action_geometry import save_reference_action_geometry  # type: ignore


DEFAULT_IMAGE = PROJECT_ROOT / "examples" / "reference" / "cat_eye_reference_full.jpg"
DEFAULT_POINTS = (
    PROJECT_ROOT / "examples" / "reference"
    / "cat_eye_reference_full_after_points.json"
)
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "output" / "main_demo_reference"
STABLE_PROFILE = (
    PROJECT_ROOT / "data" / "output" / "stable_face_scan_validation"
    / "stable_face_profile.json"
)
MANUAL_RECIPE = PROJECT_ROOT / "examples" / "cat_eye_standard_recipe.json"
CALIBRATION_PROFILE_DIR = (
    PROJECT_ROOT / "data" / "output" / "rule_calibration_dataset"
    / "individual_profiles"
)
CALIBRATION_STATS = (
    PROJECT_ROOT / "data" / "output" / "rule_calibration_dataset"
    / "02_rule_feature_statistics.csv"
)

FEATURES = (
    ("eye_tail_angle.mean", ("eye_geometry", "eye_tail_angle", "mean")),
    (
        "relative_eye_length.mean",
        ("eye_geometry", "relative_eye_length", "mean"),
    ),
    (
        "lower_lid_space_ratio.mean",
        ("eye_geometry", "lower_lid_space_ratio", "mean"),
    ),
    (
        "inner_corner_angle.mean_deg",
        ("eye_geometry", "inner_corner_angle", "mean_deg"),
    ),
    ("brow_eye_ratio.mean", ("eye_geometry", "brow_eye_ratio", "mean")),
)


class MainDemoValidationError(ValueError):
    """Raised when required validation evidence is missing or invalid."""


def detect_horizontal_split(image: Any, low: float = 0.49, high: float = 0.51) -> int:
    """Find the strongest adjacent-row discontinuity near the image midpoint."""

    if image is None or image.size == 0:
        raise MainDemoValidationError("Reference image is empty.")
    height = image.shape[0]
    start = max(1, int(math.floor(height * low)))
    stop = min(height, int(math.ceil(height * high)))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    candidates = [
        (float(cv2.absdiff(gray[y], gray[y - 1]).mean()), y)
        for y in range(start, stop)
    ]
    if not candidates:
        raise MainDemoValidationError("Split search range is empty.")
    return max(candidates)[1]


def _strict_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _profile_value(profile: Mapping[str, Any], path: tuple[str, ...]) -> float:
    value: Any = profile
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise MainDemoValidationError("Missing profile field: " + ".".join(path))
        value = value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MainDemoValidationError("Non-numeric profile field: " + ".".join(path))
    number = float(value)
    if not math.isfinite(number):
        raise MainDemoValidationError("Non-finite profile field: " + ".".join(path))
    return number


def _feature_values(profile: Mapping[str, Any]) -> dict[str, float]:
    return {name: _profile_value(profile, path) for name, path in FEATURES}


def _profile_validation(geometry: Mapping[str, Any], width: int, height: int) -> dict[str, Any]:
    face_width = geometry["relative_eye_length"]
    references = face_width["face_width_reference_landmarks"]
    reference_pixels = [item["pixel"] for item in references]
    face_width_in_bounds = all(
        0 <= point["x"] < width and 0 <= point["y"] < height
        for point in reference_pixels
    )
    face_width_lateral = (
        reference_pixels[0]["x"] < width * 0.2
        and reference_pixels[1]["x"] > width * 0.8
    )
    brow_points = [
        point["pixel"]
        for side in ("left", "right")
        for point in geometry["brow_eye"][side]["reference_landmarks"]
    ]
    brows_in_bounds = all(
        0 <= point["x"] < width and 0 <= point["y"] < height
        for point in brow_points
    )
    core = _feature_values(
        {
            "eye_geometry": {
                "eye_tail_angle": {
                    "mean": geometry["eye_tail_angle"]["mean_eye_tail_angle_deg"]
                },
                "relative_eye_length": {
                    "mean": face_width["relative_eye_length_mean"]
                },
                "lower_lid_space_ratio": {
                    "mean": geometry["lower_lid_space"]["lower_lid_space_ratio_mean"]
                },
                "inner_corner_angle": {
                    "mean_deg": geometry["inner_corner_angle"]["inner_corner_angle_mean_deg"]
                },
                "brow_eye_ratio": {
                    "mean": geometry["brow_eye"]["mean_brow_eye_ratio"]
                },
            }
        }
    )
    nondegenerate = all(math.isfinite(value) and value > 0 for value in core.values())
    return {
        "face_detection_success": geometry.get("face_detected") is True,
        "both_eye_landmark_groups_present": set(geometry["eyes"]) == {"left", "right"},
        "face_width_landmark_indices": face_width["face_width_landmark_indices"],
        "face_width_points_in_bounds": face_width_in_bounds,
        "face_width_points_lateral_and_reasonable": face_width_lateral,
        "face_width_px": face_width["face_width_px"],
        "both_brow_groups_in_bounds": brows_in_bounds,
        "nondegenerate_core_geometry": nondegenerate,
        "pose_normalized": geometry["confidence"]["pose_normalized"],
        "roll_angle_deg": geometry["pose_normalization"]["roll_angle_deg"],
        "relative_eye_length_available": True,
        "usable_full_face_profile_v03": all(
            (
                geometry.get("face_detected") is True,
                face_width_in_bounds,
                face_width_lateral,
                brows_in_bounds,
                nondegenerate,
                geometry["confidence"]["pose_normalized"] is True,
            )
        ),
    }


def _find_action(personalization: Mapping[str, Any], action_id: str) -> Mapping[str, Any]:
    matches = [
        action
        for action in personalization["personalized_actions"]
        if action.get("action_id") == action_id
    ]
    if len(matches) != 1:
        raise MainDemoValidationError(f"Expected one {action_id} action.")
    return matches[0]


def _find_adjustment(action: Mapping[str, Any], parameter: str) -> Mapping[str, Any]:
    matches = [
        adjustment
        for adjustment in action["adjustments"]
        if adjustment.get("parameter") == parameter
    ]
    if len(matches) != 1:
        raise MainDemoValidationError(f"Expected one adjustment for {parameter}.")
    return matches[0]


def _calibration_n_unchanged() -> bool:
    with CALIBRATION_STATS.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    return bool(rows) and all(int(float(row["n"])) == 11 for row in rows)


def run_validation(
    image_path: Path = DEFAULT_IMAGE,
    output_dir: Path = DEFAULT_OUTPUT,
    points_path: Path = DEFAULT_POINTS,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    image = cv2.imread(str(image_path))
    if image is None:
        raise MainDemoValidationError(f"Could not read reference image: {image_path}")
    height, width = image.shape[:2]
    split_y = detect_horizontal_split(image)
    before = image[:split_y]
    after = image[split_y:]
    before_path = output_dir / "blogger_before.jpg"
    after_path = output_dir / "blogger_after.jpg"
    if not cv2.imwrite(str(before_path), before) or not cv2.imwrite(str(after_path), after):
        raise MainDemoValidationError("Could not write before/after crops.")

    geometry_path = output_dir / "blogger_before_geometry.json"
    profile_path = output_dir / "blogger_before_face_profile.json"
    before_debug = output_dir / "blogger_before_face_profile_debug.jpg"
    geometry = process_eye_geometry(
        before_path,
        DEFAULT_MODEL_PATH,
        before_debug,
        geometry_path,
        input_is_mirrored=False,
        profile_output_path=profile_path,
    )
    blogger_profile = load_json_object(profile_path)
    validation = _profile_validation(geometry, width, split_y)
    if not validation["usable_full_face_profile_v03"]:
        raise MainDemoValidationError("Blogger BEFORE failed full-face validation.")

    reference_path = output_dir / "blogger_after_reference_action.json"
    after_debug = output_dir / "blogger_after_reference_action_debug.jpg"
    reference = annotate_image(
        after_path,
        output_json=reference_path,
        debug_output=after_debug,
        reference_id="cat_eye_full_main_demo",
        points_json=points_path,
    )
    reference["quality"].update(
        {
            "visual_estimation": True,
            "human_confirmed": False,
            "image_side": "left",
            "subject_side": "unknown",
            "subject_side_if_unmirrored": "right",
            "mirror_status": "unconfirmed",
        }
    )
    reference["source"]["parent_image"] = str(image_path.relative_to(PROJECT_ROOT))
    reference["source"]["parent_split_y_px"] = split_y
    save_reference_action_geometry(reference_path, reference)

    stable_profile = load_json_object(STABLE_PROFILE)
    manual_recipe = load_json_object(MANUAL_RECIPE)
    reference_recipe = build_standard_recipe(manual_recipe, reference)
    recipe_path = output_dir / "blogger_after_reference_recipe.json"
    save_json_output(recipe_path, reference_recipe)
    personalization = personalize_reference_recipe(
        stable_profile, reference_recipe, "cat_eye"
    )
    personalization_path = output_dir / "stable_user_personalized_action.json"
    save_json_output(personalization_path, personalization)

    blogger_values = _feature_values(blogger_profile)
    stable_values = _feature_values(stable_profile)
    comparison_rows: list[dict[str, Any]] = []
    profiles: list[tuple[str, str, Mapping[str, Any]]] = [
        ("blogger_before", "reference_blogger", blogger_profile)
    ]
    profiles.extend(
        (
            f"face_{number:02d}",
            "calibration_user",
            load_json_object(
                CALIBRATION_PROFILE_DIR / f"face_{number:02d}_face_profile.json"
            ),
        )
        for number in range(5, 12)
    )
    for sample_id, role, profile in profiles:
        values = _feature_values(profile)
        comparison_rows.append(
            {
                "sample_id": sample_id,
                "role": role,
                **values,
                "is_full_face": True,
                "is_face_profile_v03": profile.get("version") == "0.3",
                "is_directly_comparable": True,
            }
        )
    blogger_comparison_path = output_dir / "blogger_vs_face05_11.csv"
    _write_csv(
        blogger_comparison_path,
        list(comparison_rows[0]),
        comparison_rows,
    )

    stable_rows = [
        {
            "feature": name,
            "blogger_before": blogger_values[name],
            "stable_user": stable_values[name],
            "absolute_difference": round(
                abs(blogger_values[name] - stable_values[name]), 6
            ),
        }
        for name, _ in FEATURES
    ]
    stable_comparison_path = output_dir / "blogger_vs_stable_user.csv"
    _write_csv(stable_comparison_path, list(stable_rows[0]), stable_rows)

    a04 = _find_action(personalization, "A04")
    a02 = _find_action(personalization, "A02")
    direction = _find_adjustment(a04, "direction_angle_deg")
    extension = _find_adjustment(a04, "extension_factor")
    lower_range = _find_adjustment(a02, "range_factor")
    lower_intensity = _find_adjustment(a02, "intensity_factor")
    reference_geometry = reference["geometry"]
    a04_summary = {
        "reference_direction_deg": reference_geometry["direction_relative_to_eye_axis_deg"],
        "direction_adjustment_deg": direction["adjustment_value"],
        "personalized_direction_deg": a04["personalized_parameters"]["direction_angle_deg"],
        "reference_extension_ratio": a04["personalized_parameters"]["reference_extension_ratio"],
        "extension_adaptation_factor": a04["personalized_parameters"]["extension_adaptation_factor"],
        "personalized_extension_ratio": a04["personalized_parameters"]["personalized_extension_ratio"],
    }
    a02_summary = {
        "range_factor": a02["personalized_parameters"]["range_factor"],
        "intensity_factor": a02["personalized_parameters"]["intensity_factor"],
    }

    main_rows: list[dict[str, Any]] = []
    for name, value in blogger_values.items():
        main_rows.append({"group": "A_blogger_before_face", "metric": name, "value": value})
    for name in (
        "direction_relative_to_eye_axis_deg",
        "eyeliner_extension_ratio",
        "start_position_ratio",
    ):
        report_name = (
            "reference_extension_ratio"
            if name == "eyeliner_extension_ratio"
            else name
        )
        main_rows.append(
            {
                "group": "B_blogger_after_action",
                "metric": report_name,
                "value": reference_geometry[name],
            }
        )
    for name in (
        "eye_tail_angle.mean",
        "relative_eye_length.mean",
        "lower_lid_space_ratio.mean",
    ):
        main_rows.append(
            {"group": "C_stable_user", "metric": name, "value": stable_values[name]}
        )
    for name, value in {**a04_summary, **a02_summary}.items():
        main_rows.append(
            {"group": "C_personalized_result", "metric": name, "value": value}
        )
    main_csv_path = output_dir / "main_demo_reference_report.csv"
    _write_csv(main_csv_path, ["group", "metric", "value"], main_rows)

    report = {
        "version": "1.0",
        "image": {
            "source": str(image_path.relative_to(PROJECT_ROOT)),
            "width_px": width,
            "height_px": height,
            "split_y_px": split_y,
            "split_ratio": split_y / height,
            "before_crop": str(before_path.relative_to(PROJECT_ROOT)),
            "after_crop": str(after_path.relative_to(PROJECT_ROOT)),
        },
        "reference": {
            "before_face_profile": blogger_profile,
            "before_core_features": blogger_values,
            "before_validation": validation,
            "after_action_geometry": reference,
        },
        "user": {
            "stable_face_profile": stable_profile,
            "stable_core_features": stable_values,
        },
        "descriptive_comparison": {
            row["feature"]: {
                "blogger_before": row["blogger_before"],
                "stable_user": row["stable_user"],
                "absolute_difference": row["absolute_difference"],
            }
            for row in stable_rows
        },
        "personalization": {
            "A04": a04_summary,
            "A02": a02_summary,
            "full_engine_output": personalization,
            "extension_calculation": {
                "formula": "reference_extension_ratio * extension_adaptation_factor",
                "reference_extension_ratio": a04_summary["reference_extension_ratio"],
                "extension_adaptation_factor": a04_summary["extension_adaptation_factor"],
                "personalized_extension_ratio": a04_summary["personalized_extension_ratio"],
            },
        },
        "calibration_population": {
            "blogger_included": False,
            "expected_n": 11,
            "existing_statistics_still_n_11": _calibration_n_unchanged(),
        },
        "outputs": {
            "blogger_vs_face05_11": str(blogger_comparison_path.relative_to(PROJECT_ROOT)),
            "blogger_vs_stable_user": str(stable_comparison_path.relative_to(PROJECT_ROOT)),
            "main_demo_csv": str(main_csv_path.relative_to(PROJECT_ROOT)),
            "personalization": str(personalization_path.relative_to(PROJECT_ROOT)),
        },
    }
    report_path = output_dir / "main_demo_reference_report.json"
    _strict_json(report_path, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run_validation(args.image, args.output_dir, args.points)
    print(json.dumps(report["image"], ensure_ascii=False, allow_nan=False))
    print(json.dumps(report["personalization"], ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
