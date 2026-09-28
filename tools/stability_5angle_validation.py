"""Validation-only five-angle Face Profile and Cat Eye output repeatability run."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import fmean
from typing import Any, Mapping

from src.eye_landmarks import process_eye_geometry
from src.face_landmarker import DEFAULT_MODEL_PATH, FaceLandmarkerError
from src.personalization_engine import (
    PersonalizationEngineError,
    load_json_object,
    personalize_recipe,
    save_json_output,
)
from src.reference_action_adapter import (
    ReferenceActionAdapterError,
    build_standard_recipe,
    personalize_reference_recipe,
)
from src.repeatability_analysis import calculate_feature_statistics


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "data" / "output" / "stability_5angle_validation"
MANUAL_RECIPE = ROOT / "examples" / "cat_eye_standard_recipe.json"
INPUT_SUFFIXES = {".jpg", ".jpeg", ".png"}
FEATURE_PATHS = {
    "eye_tail_angle.mean": ("eye_geometry", "eye_tail_angle", "mean"),
    "relative_eye_length.mean": ("eye_geometry", "relative_eye_length", "mean"),
    "lower_lid_space_ratio.mean": ("eye_geometry", "lower_lid_space_ratio", "mean"),
    "inner_corner_angle.mean_deg": ("eye_geometry", "inner_corner_angle", "mean_deg"),
    "brow_eye_ratio.mean": ("eye_geometry", "brow_eye_ratio", "mean"),
}
OUTPUT_FIELDS = (
    "personalized_direction_deg",
    "extension_adaptation_factor",
    "personalized_extension_factor",
    "personalized_extension_ratio",
    "lower_lid_range_factor",
    "lower_lid_intensity_factor",
)


def _strict_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{label} must be finite")
    return number


def _at(data: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    value: Any = data
    for part in path:
        if not isinstance(value, Mapping) or part not in value:
            raise ValueError("Missing field: " + ".".join(path))
        value = value[part]
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _image_paths() -> list[Path]:
    paths: list[Path] = []
    for number in range(1, 6):
        stem = f"stability_{number:02d}"
        matches = [
            path for path in INPUT_DIR.iterdir()
            if path.is_file()
            and path.stem.lower() == stem
            and path.suffix.lower() in INPUT_SUFFIXES
        ]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one image for {stem}; found {len(matches)}")
        paths.append(matches[0])
    return paths


def _reference_geometry() -> tuple[Path | None, dict[str, Any] | None]:
    candidates: list[tuple[Path, dict[str, Any]]] = []
    for directory in (ROOT / "examples" / "reference", ROOT / "data" / "output" / "reference_action"):
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                value = load_json_object(path)
            except PersonalizationEngineError:
                continue
            quality = value.get("quality")
            if (
                value.get("version") == "0.1"
                and value.get("action_id") == "A04"
                and value.get("source_type") == "local_eye_tutorial"
                and isinstance(quality, Mapping)
                and quality.get("annotation_complete") is True
                and quality.get("manual_annotation") is True
                and quality.get("source_is_full_face") is False
            ):
                candidates.append((path, value))
    if len(candidates) > 1:
        raise ValueError("Multiple valid Reference Action Geometry files; choose one explicitly")
    return candidates[0] if candidates else (None, None)


def _pearson(first: list[float], second: list[float]) -> float | None:
    if len(first) < 3 or len(first) != len(second):
        return None
    first_mean, second_mean = fmean(first), fmean(second)
    first_centered = [value - first_mean for value in first]
    second_centered = [value - second_mean for value in second]
    denominator = math.sqrt(
        sum(value * value for value in first_centered)
        * sum(value * value for value in second_centered)
    )
    return None if denominator == 0 else sum(
        a * b for a, b in zip(first_centered, second_centered)
    ) / denominator


def _write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: "" if row.get(key) is None else row[key] for key in columns})


def run() -> dict[str, Any]:
    images = _image_paths()
    reference_path, reference_geometry = _reference_geometry()
    recipe = build_standard_recipe(load_json_object(MANUAL_RECIPE), reference_geometry)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples: list[dict[str, Any]] = []

    for image in images:
        stem = image.stem.lower()
        geometry_path = OUTPUT_DIR / f"{stem}_geometry.json"
        profile_path = OUTPUT_DIR / f"{stem}_profile.json"
        debug_path = OUTPUT_DIR / f"{stem}_debug.jpg"
        personalized_path = OUTPUT_DIR / f"{stem}_personalization.json"
        sample: dict[str, Any] = {
            "filename": image.name,
            "input_sha256": _sha256(image),
            "detection_success": False,
            "failure_reason": None,
            "profile_path": None,
            "personalization_path": None,
            "face_profile": {},
            "personalized_action": {},
        }
        try:
            geometry = process_eye_geometry(
                image_path=image,
                model_path=DEFAULT_MODEL_PATH,
                debug_output_path=debug_path,
                json_output_path=geometry_path,
                profile_output_path=profile_path,
            )
            profile = load_json_object(profile_path)
            if profile.get("version") != "0.3":
                raise ValueError("Face Profile is not v0.3")
            features = {
                name: _strict_number(_at(profile, path), name)
                for name, path in FEATURE_PATHS.items()
            }
            pose = _at(geometry, ("pose_normalization",))
            if not isinstance(pose, Mapping):
                raise ValueError("Missing pose_normalization object")
            roll = pose.get("roll_angle_deg")
            roll = None if roll is None else _strict_number(roll, "roll_angle_deg")
            pose_normalized = pose.get("applied") is True
            if reference_geometry is None:
                personalized = personalize_recipe(profile, recipe, "cat_eye")
            else:
                personalized = personalize_reference_recipe(profile, recipe, "cat_eye")
            actions = {action["action_id"]: action for action in personalized["personalized_actions"]}
            a04 = actions["A04"]
            a02 = actions["A02"]
            extension_adjustments = [
                adjustment for adjustment in a04["adjustments"]
                if adjustment.get("rule_ids") == ["R03", "R04"]
            ]
            if len(extension_adjustments) != 1:
                raise ValueError("Expected exactly one R03/R04 adjustment")
            adaptation = _strict_number(
                extension_adjustments[0]["adjustment_value"],
                "extension_adaptation_factor",
            )
            a04_params = a04["personalized_parameters"]
            a02_params = a02["personalized_parameters"]
            product = {
                "personalized_direction_deg": _strict_number(
                    a04_params["direction_angle_deg"], "personalized_direction_deg"
                ),
                "extension_adaptation_factor": adaptation,
                "personalized_extension_factor": _strict_number(
                    a04_params["extension_factor"], "personalized_extension_factor"
                ),
                "personalized_extension_ratio": (
                    None if reference_geometry is None else _strict_number(
                        a04_params["personalized_extension_ratio"],
                        "personalized_extension_ratio",
                    )
                ),
                "lower_lid_range_factor": _strict_number(
                    a02_params["range_factor"], "lower_lid_range_factor"
                ),
                "lower_lid_intensity_factor": _strict_number(
                    a02_params["intensity_factor"], "lower_lid_intensity_factor"
                ),
            }
            save_json_output(personalized_path, personalized)
            sample.update({
                "detection_success": True,
                "profile_path": str(profile_path.relative_to(ROOT)),
                "personalization_path": str(personalized_path.relative_to(ROOT)),
                "geometry_path": str(geometry_path.relative_to(ROOT)),
                "debug_path": str(debug_path.relative_to(ROOT)),
                "pose_normalized": pose_normalized,
                "roll_angle_deg": roll,
                "face_profile": features,
                "personalized_action": product,
            })
        except (FaceLandmarkerError, PersonalizationEngineError, ReferenceActionAdapterError, OSError, ValueError, KeyError) as exc:
            sample["failure_reason"] = str(exc)
            print(f"{image.name}: {type(exc).__name__}: {exc}")
        samples.append(sample)

    successful = [sample for sample in samples if sample["detection_success"]]
    if len(successful) < 2:
        raise ValueError(f"At least 2 successful photos needed for sample std; got {len(successful)}")
    feature_stats = {
        name: calculate_feature_statistics(
            sample["face_profile"][name] for sample in successful
        ) for name in FEATURE_PATHS
    }
    product_stats = {
        name: (
            None if name == "personalized_extension_ratio" and reference_geometry is None
            else calculate_feature_statistics(
                sample["personalized_action"][name] for sample in successful
            )
        ) for name in OUTPUT_FIELDS
    }
    measurement_ranking = sorted(
        FEATURE_PATHS,
        key=lambda name: feature_stats[name]["cv"],
    )
    product_ranking = sorted(
        (name for name in OUTPUT_FIELDS if product_stats[name] is not None),
        key=lambda name: product_stats[name]["cv"],
    )
    deviation_leaders = {}
    for name in FEATURE_PATHS:
        values = [(sample["filename"], sample["face_profile"][name]) for sample in successful]
        deviation_leaders[name] = max(
            (
                {
                    "filename": filename,
                    "difference_from_other_four_mean": value - fmean(
                        other_value for other_name, other_value in values
                        if other_name != filename
                    ),
                } for filename, value in values
            ),
            key=lambda item: abs(item["difference_from_other_four_mean"]),
        )
    roll_values = [sample["roll_angle_deg"] for sample in successful]
    roll_diagnostics = {
        "roll_statistics": (
            calculate_feature_statistics(roll_values)
            if all(value is not None for value in roll_values) else None
        ),
        "pearson_roll_vs_eye_tail_angle": (
            _pearson(roll_values, [sample["face_profile"]["eye_tail_angle.mean"] for sample in successful])
            if all(value is not None for value in roll_values) else None
        ),
        "pearson_roll_vs_personalized_direction": (
            _pearson(roll_values, [sample["personalized_action"]["personalized_direction_deg"] for sample in successful])
            if all(value is not None for value in roll_values) else None
        ),
        "yaw_pitch_proxy": None,
        "caveat": "Only roll is measured; yaw and pitch cannot be inferred reliably from these outputs. Correlations from five photos are descriptive, not causal.",
    }
    face_csv = OUTPUT_DIR / "face_profile_stability.csv"
    product_csv = OUTPUT_DIR / "personalization_stability.csv"
    _write_csv(face_csv, [
        {
            "filename": sample["filename"],
            "detection_success": sample["detection_success"],
            "failure_reason": sample["failure_reason"],
            "pose_normalized": sample.get("pose_normalized"),
            "roll_angle_deg": sample.get("roll_angle_deg"),
            **sample["face_profile"],
        } for sample in samples
    ], ["filename", "detection_success", "failure_reason", "pose_normalized", "roll_angle_deg", *FEATURE_PATHS])
    _write_csv(product_csv, [
        {
            "filename": sample["filename"],
            "detection_success": sample["detection_success"],
            "failure_reason": sample["failure_reason"],
            **sample["personalized_action"],
        } for sample in samples
    ], ["filename", "detection_success", "failure_reason", *OUTPUT_FIELDS])
    report = {
        "validation_scope": "same_person_five_angle_measurement_and_product_stability",
        "face_profile_version": "0.3",
        "input_count": len(images),
        "successful_count": len(successful),
        "failed_count": len(images) - len(successful),
        "baseline": {
            "type": "reference_action_geometry" if reference_geometry else "manual_fallback",
            "recipe": str(MANUAL_RECIPE.relative_to(ROOT)),
            "recipe_sha256": _sha256(MANUAL_RECIPE),
            "reference_geometry": str(reference_path.relative_to(ROOT)) if reference_path else None,
            "reference_geometry_sha256": _sha256(reference_path) if reference_path else None,
            "reference_extension_ratio": (
                _strict_number(_at(reference_geometry, ("geometry", "eyeliner_extension_ratio")), "reference_extension_ratio")
                if reference_geometry else None
            ),
        },
        "statistics_method": {
            "std": "sample (n-1)",
            "cv": "sample std / abs(mean), null when abs(mean) <= 1e-9",
            "missing_values": "not imputed; failed photos excluded from statistics",
            "outliers_removed": False,
        },
        "samples": samples,
        "face_profile_statistics": feature_stats,
        "personalization_statistics": product_stats,
        "pose_diagnostics": roll_diagnostics,
        "diagnostics": {
            "measurement_ranking_by_cv_low_to_high": measurement_ranking,
            "product_ranking_by_cv_low_to_high": product_ranking,
            "largest_leave_one_out_deviation_per_feature": deviation_leaders,
            "interpretation_limit": "CV is descriptive only; no product tolerance or outlier threshold is defined.",
        },
    }
    save_json_output(OUTPUT_DIR / "stability_report.json", report)
    return report


if __name__ == "__main__":
    result = run()
    print(json.dumps({
        "successful_count": result["successful_count"],
        "failed_count": result["failed_count"],
        "baseline": result["baseline"]["type"],
        "output_dir": str(OUTPUT_DIR),
    }, ensure_ascii=False))
