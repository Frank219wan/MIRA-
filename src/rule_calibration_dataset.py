"""Build a demo rule-calibration dataset from the existing Face Profile pipeline.

No geometry or rule formula is implemented here. The current calibration is
read for coverage reporting and is never changed.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from statistics import fmean, median, stdev
from typing import Any, Mapping, Sequence

if __package__:
    from .eye_landmarks import process_eye_geometry
    from .face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError
    from .face_profile import FACE_PROFILE_VERSION, FaceProfileError
    from .makeup_rules import DEFAULT_RULE_CALIBRATION, LinearCalibration
    from .personalization_engine import load_json_object, save_json_output
    from .repeatability_analysis import extract_core_features
else:
    from eye_landmarks import process_eye_geometry  # type: ignore
    from face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError  # type: ignore
    from face_profile import FACE_PROFILE_VERSION, FaceProfileError  # type: ignore
    from makeup_rules import DEFAULT_RULE_CALIBRATION, LinearCalibration  # type: ignore
    from personalization_engine import load_json_object, save_json_output  # type: ignore
    from repeatability_analysis import extract_core_features  # type: ignore


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "rule_calibration_dataset"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
NEAR_ANCHOR_FRACTION = 0.10

FEATURES = (
    ("eye_tail_angle.mean", "degree"),
    ("relative_eye_length.mean", "ratio"),
    ("lower_lid_space_ratio.mean", "ratio"),
    ("inner_corner_angle.mean_deg", "degree"),
    ("brow_eye_ratio.mean", "ratio"),
)
CORE_FEATURES = tuple(name for name, _ in FEATURES[:3])

PROFILE_FIELDS = (
    "person_id", "filename", "detection_success", "failure_reason",
    "pose_normalized", "roll_angle_deg",
    *(name for name, _ in FEATURES),
    "R01_R02_input", "R03_R04_input", "R05_R06_input",
    "R07_R10_reference_only", "profile_path", "debug_path",
)
STAT_FIELDS = (
    "feature", "unit", "n", "mean", "median", "std", "min", "max",
    "range", "percentile_25", "percentile_75",
)
COVERAGE_FIELDS = (
    "rule_group", "output_parameter", "output_semantics", "feature", "input_low", "input_high",
    "output_low", "output_high", "n", "sample_min", "sample_max",
    "covers_sample_range", "below_low_count", "above_high_count",
    "outside_anchor_count", "near_low_count", "near_high_count",
    "clamp_low_count", "clamp_high_count", "clamp_count",
    "below_low_people", "above_high_people", "near_low_people",
    "near_high_people", "clamp_people",
)


class RuleDatasetError(ValueError):
    """Raised when a dataset cannot be generated from the requested inputs."""


def discover_face_images(input_dir: Path | str) -> list[tuple[str, Path | None]]:
    """Resolve exactly face_01 through face_11 using each file's real suffix."""

    directory = Path(input_dir)
    if not directory.is_dir():
        raise RuleDatasetError(f"Input directory does not exist: {directory}")
    found = [
        path for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    ]
    result = []
    for number in range(1, 12):
        person_id = f"face_{number:02d}"
        matches = sorted(
            (path for path in found if path.stem.lower() == person_id),
            key=lambda path: path.name.lower(),
        )
        if len(matches) > 1:
            raise RuleDatasetError(
                f"Multiple image files match {person_id}: "
                + ", ".join(path.name for path in matches)
            )
        result.append((person_id, matches[0] if matches else None))
    return result


def percentile_linear(values: Sequence[float], fraction: float) -> float:
    """Linearly interpolate at index (n-1)*fraction in sorted observations."""

    if not values or not 0 <= fraction <= 1:
        raise RuleDatasetError("Percentile requires values and a fraction in [0, 1].")
    sorted_values = sorted(values)
    index = (len(sorted_values) - 1) * fraction
    lower_index = math.floor(index)
    upper_index = math.ceil(index)
    position = index - lower_index
    return sorted_values[lower_index] + position * (
        sorted_values[upper_index] - sorted_values[lower_index]
    )


def calculate_statistics(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Use only valid detected profiles; std is sample std (n-1)."""

    successful = [row for row in rows if row["detection_success"]]
    results = []
    for name, unit in FEATURES[:3]:
        values = [float(row[name]) for row in successful]
        results.append({
            "feature": name,
            "unit": unit,
            "n": len(values),
            "mean": fmean(values) if values else None,
            "median": median(values) if values else None,
            "std": stdev(values) if len(values) >= 2 else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "range": max(values) - min(values) if values else None,
            "percentile_25": percentile_linear(values, 0.25) if values else None,
            "percentile_75": percentile_linear(values, 0.75) if values else None,
        })
    return results


def current_calibration_specs() -> tuple[tuple[str, str, str, LinearCalibration], ...]:
    calibration = DEFAULT_RULE_CALIBRATION
    return (
        ("R01/R02", "direction_angle_deg", CORE_FEATURES[0], calibration.eyeliner_direction_correction_deg),
        ("R03/R04", "extension_factor", CORE_FEATURES[1], calibration.eyeliner_extension_multiplier),
        ("R05/R06", "range_factor", CORE_FEATURES[2], calibration.lower_lid_range_multiplier),
        ("R05/R06", "intensity_factor", CORE_FEATURES[2], calibration.lower_lid_intensity_multiplier),
    )


def calculate_coverage(
    rows: Sequence[Mapping[str, Any]],
    *,
    near_fraction: float = NEAR_ANCHOR_FRACTION,
) -> list[dict[str, Any]]:
    """Report anchor coverage; clamp means strictly outside an input anchor."""

    if not 0 <= near_fraction < 0.5:
        raise RuleDatasetError("near_fraction must be in [0, 0.5).")
    successful = [row for row in rows if row["detection_success"]]
    reports = []
    for group, parameter, feature, anchor in current_calibration_specs():
        values = [(str(row["person_id"]), float(row[feature])) for row in successful]
        span = anchor.feature_high - anchor.feature_low
        near_distance = span * near_fraction
        below = [person for person, value in values if value < anchor.feature_low]
        above = [person for person, value in values if value > anchor.feature_high]
        near_low = [person for person, value in values if anchor.feature_low <= value <= anchor.feature_low + near_distance]
        near_high = [person for person, value in values if anchor.feature_high - near_distance <= value <= anchor.feature_high]
        sample_min = min((value for _, value in values), default=None)
        sample_max = max((value for _, value in values), default=None)
        reports.append({
            "rule_group": group,
            "output_parameter": parameter,
            "output_semantics": "additive_correction_deg" if parameter == "direction_angle_deg" else "multiplier",
            "feature": feature,
            "input_low": anchor.feature_low,
            "input_high": anchor.feature_high,
            "output_low": anchor.output_at_low,
            "output_high": anchor.output_at_high,
            "n": len(values),
            "sample_min": sample_min,
            "sample_max": sample_max,
            "covers_sample_range": bool(values) and not below and not above,
            "below_low_count": len(below),
            "above_high_count": len(above),
            "outside_anchor_count": len(below) + len(above),
            "near_low_count": len(near_low),
            "near_high_count": len(near_high),
            "clamp_low_count": len(below),
            "clamp_high_count": len(above),
            "clamp_count": len(below) + len(above),
            "below_low_people": below,
            "above_high_people": above,
            "near_low_people": near_low,
            "near_high_people": near_high,
            "clamp_people": below + above,
        })
    return reports


def _save_csv(path: Path, fields: Sequence[str], rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({
                field: ";".join(value) if isinstance(value := row.get(field), list)
                else "" if value is None else value
                for field in fields
            })


def _strict_profile(path: Path) -> Mapping[str, Any]:
    # load_json_object validates the top level; parse_constant catches NaN/Infinity.
    profile = load_json_object(path)
    with path.open(encoding="utf-8") as handle:
        json.load(handle, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    if profile.get("version") != FACE_PROFILE_VERSION:
        raise RuleDatasetError(f"Expected Face Profile {FACE_PROFILE_VERSION}.")
    return profile


def build_dataset(
    input_dir: Path | str = DEFAULT_INPUT_DIR,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    model_path: Path | str = DEFAULT_MODEL_PATH,
) -> dict[str, Any]:
    """Run each requested image through the unchanged Face Profile v0.3 pipeline."""

    images = discover_face_images(input_dir)
    output = Path(output_dir)
    profile_dir = output / "individual_profiles"
    profile_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for person_id, image_path in images:
        row: dict[str, Any] = {
            "person_id": person_id,
            "filename": image_path.name if image_path else "",
            "detection_success": False,
            "failure_reason": "",
            "pose_normalized": "",
            "roll_angle_deg": "",
            "R07_R10_reference_only": "yes",
        }
        if image_path is None:
            row["failure_reason"] = "Image file not found for this person_id."
            rows.append(row)
            continue
        geometry_path = profile_dir / f"{person_id}_geometry.json"
        profile_path = profile_dir / f"{person_id}_face_profile.json"
        debug_path = profile_dir / f"{person_id}_debug.jpg"
        try:
            geometry = process_eye_geometry(
                image_path=image_path,
                model_path=Path(model_path),
                debug_output_path=debug_path,
                json_output_path=geometry_path,
                profile_output_path=profile_path,
            )
            profile = _strict_profile(profile_path)
            features = extract_core_features(profile)
            pose = geometry.get("pose_normalization")
            if not isinstance(pose, Mapping):
                raise RuleDatasetError("Geometry lacks pose_normalization metadata.")
            roll = pose.get("roll_angle_deg")
            if roll is not None and (isinstance(roll, bool) or not isinstance(roll, (int, float)) or not math.isfinite(roll)):
                raise RuleDatasetError("Invalid roll_angle_deg metadata.")
            if profile.get("confidence", {}).get("pose_normalized") is not (pose.get("applied") is True):
                raise RuleDatasetError("Pose normalization metadata disagrees with Face Profile.")
            row.update({
                "detection_success": True,
                "pose_normalized": pose.get("applied") is True,
                "roll_angle_deg": roll if roll is not None else "",
                **features,
                "R01_R02_input": features[CORE_FEATURES[0]],
                "R03_R04_input": features[CORE_FEATURES[1]],
                "R05_R06_input": features[CORE_FEATURES[2]],
                "profile_path": str(profile_path.relative_to(output)),
                "debug_path": str(debug_path.relative_to(output)),
            })
        except (
            FaceLandmarkerError, FaceProfileError, RuleDatasetError,
            OSError, ValueError,
        ) as exc:
            row["failure_reason"] = str(exc)
        rows.append(row)

    statistics = calculate_statistics(rows)
    coverage = calculate_coverage(rows)
    report = {
        "dataset_version": "1.0",
        "scope": "demo_sample_distribution_only",
        "face_profile_version": FACE_PROFILE_VERSION,
        "requested_person_ids": [person_id for person_id, _ in images],
        "requested_count": len(images),
        "present_image_count": sum(path is not None for _, path in images),
        "success_count": sum(row["detection_success"] for row in rows),
        "failure_count": sum(not row["detection_success"] for row in rows),
        "statistics_method": {
            "std": "sample standard deviation (n-1); null when n < 2",
            "percentile": "linear interpolation at sorted index (n-1)*fraction",
        },
        "coverage_method": {
            "near_anchor_fraction_of_input_span": NEAR_ANCHOR_FRACTION,
            "near_anchor": "inside interval and within 10% of span from endpoint, inclusive",
            "clamp": "strictly below input low or above input high; endpoint itself is not counted",
        },
        "r07_r10_status": "reference_only; excluded from first calibration statistics",
        "people": rows,
        "feature_statistics": statistics,
        "current_calibration_coverage": coverage,
        "interpretation_limit": "This is the current demo sample distribution, not a population distribution, scientific threshold, or eye-type boundary.",
    }
    _save_csv(output / "01_face_profile_for_rules.csv", PROFILE_FIELDS, rows)
    _save_csv(output / "02_rule_feature_statistics.csv", STAT_FIELDS, statistics)
    _save_csv(output / "03_current_calibration_coverage.csv", COVERAGE_FIELDS, coverage)
    save_json_output(output / "rule_calibration_dataset.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    args = parser.parse_args()
    try:
        report = build_dataset(args.input_dir, args.output_dir, args.model)
    except RuleDatasetError as exc:
        print(f"Rule calibration dataset failed: {exc}", file=sys.stderr)
        return 1
    print(f"Profiles: {report['success_count']}/{report['requested_count']} valid; output: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
