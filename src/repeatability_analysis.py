"""Measure Face Profile repeatability across photos of one person.

This module deliberately treats the existing Face Landmarker, geometry, and
Face Profile code as the measurement pipeline.  It only adds aggregation and
reporting around those outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import fmean, stdev
from typing import Any, Iterable, Mapping, Sequence

if __package__:
    from .eye_landmarks import process_eye_geometry
    from .face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError
    from .face_profile import FACE_PROFILE_VERSION, FaceProfileError
else:
    from eye_landmarks import process_eye_geometry
    from face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError
    from face_profile import FACE_PROFILE_VERSION, FaceProfileError


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_WORK_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "repeatability_v0.3"
DEFAULT_JSON_REPORT_PATH = (
    PROJECT_ROOT / "data" / "output" / "repeatability_report_v0.3.json"
)
DEFAULT_CSV_REPORT_PATH = (
    PROJECT_ROOT / "data" / "output" / "repeatability_report_v0.3.csv"
)
DEFAULT_BASELINE_REPORT_PATH = (
    PROJECT_ROOT / "data" / "output" / "repeatability_report.json"
)

CV_MEAN_EPSILON = 1e-9
OUTLIER_Z_THRESHOLD = 2.0

FEATURE_SPECS: tuple[dict[str, Any], ...] = (
    {
        "name": "eye_tail_angle.mean",
        "path": ("eye_geometry", "eye_tail_angle", "mean"),
        "unit": "degree",
    },
    {
        "name": "relative_eye_length.mean",
        "path": ("eye_geometry", "relative_eye_length", "mean"),
        "unit": "ratio",
    },
    {
        "name": "brow_eye_ratio.mean",
        "path": ("eye_geometry", "brow_eye_ratio", "mean"),
        "unit": "ratio",
    },
    {
        "name": "lower_lid_space_ratio.mean",
        "path": ("eye_geometry", "lower_lid_space_ratio", "mean"),
        "unit": "ratio",
    },
    {
        "name": "inner_corner_angle.mean_deg",
        "path": ("eye_geometry", "inner_corner_angle", "mean_deg"),
        "unit": "degree",
    },
)


class RepeatabilityAnalysisError(ValueError):
    """Raised when repeatability analysis cannot produce a valid report."""


def discover_repeat_images(input_dir: Path | str = DEFAULT_INPUT_DIR) -> list[Path]:
    """Return repeat_*.jpg/jpeg inputs, matching the suffix case-insensitively."""

    directory = Path(input_dir)
    if not directory.is_dir():
        raise RepeatabilityAnalysisError(f"Input directory does not exist: {directory}")

    images = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name.lower().startswith("repeat_")
        and path.suffix.lower() in {".jpg", ".jpeg"}
    ]
    return sorted(images, key=lambda path: path.name.lower())


def validate_image_paths(image_paths: Iterable[Path | str]) -> list[Path]:
    """Validate an explicit or discovered input set before model inference."""

    paths = [Path(path).expanduser().resolve() for path in image_paths]
    if len(paths) < 2:
        raise RepeatabilityAnalysisError(
            f"Repeatability analysis requires at least 2 images; received {len(paths)}."
        )

    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RepeatabilityAnalysisError(
            "Input image file(s) do not exist: " + ", ".join(missing)
        )

    unsupported = [
        str(path) for path in paths if path.suffix.lower() not in {".jpg", ".jpeg", ".png"}
    ]
    if unsupported:
        raise RepeatabilityAnalysisError(
            "Unsupported input image type(s): " + ", ".join(unsupported)
        )
    return paths


def _profile_number(profile: Mapping[str, Any], path: Sequence[str]) -> float:
    value: Any = profile
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise RepeatabilityAnalysisError(
                f"Face Profile is missing required field: {'.'.join(path)}"
            )
        value = value[key]

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RepeatabilityAnalysisError(
            f"Face Profile field {'.'.join(path)} must be numeric."
        )
    number = float(value)
    if not math.isfinite(number):
        raise RepeatabilityAnalysisError(
            f"Face Profile field {'.'.join(path)} must be finite."
        )
    return number


def extract_core_features(profile: Mapping[str, Any]) -> dict[str, float]:
    """Extract the five requested metrics from the current Face Profile."""

    return {
        spec["name"]: _profile_number(profile, spec["path"])
        for spec in FEATURE_SPECS
    }


def calculate_feature_statistics(
    values: Iterable[float],
    *,
    cv_mean_epsilon: float = CV_MEAN_EPSILON,
) -> dict[str, float | int | None]:
    """Calculate sample statistics and a finite-or-null coefficient of variation."""

    numbers = [float(value) for value in values]
    if len(numbers) < 2:
        raise RepeatabilityAnalysisError(
            f"Feature statistics require at least 2 values; received {len(numbers)}."
        )
    if cv_mean_epsilon < 0:
        raise RepeatabilityAnalysisError("CV mean epsilon must be non-negative.")
    if not all(math.isfinite(value) for value in numbers):
        raise RepeatabilityAnalysisError("Feature values must not contain NaN or infinity.")

    mean_value = fmean(numbers)
    std_value = stdev(numbers)
    min_value = min(numbers)
    max_value = max(numbers)
    range_value = max_value - min_value
    cv_value = None if abs(mean_value) <= cv_mean_epsilon else std_value / abs(mean_value)

    return {
        "n": len(numbers),
        "mean": mean_value,
        "std": std_value,
        "min": min_value,
        "max": max_value,
        "range": range_value,
        "cv": cv_value,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _round_number(value: float | int | None, digits: int = 10) -> float | int | None:
    if value is None or isinstance(value, int):
        return value
    return round(value, digits)


def build_repeatability_report(
    samples: Sequence[Mapping[str, Any]],
    *,
    input_is_mirrored: bool = False,
    cv_mean_epsilon: float = CV_MEAN_EPSILON,
) -> dict[str, Any]:
    """Aggregate successful sample measurements without removing outliers."""

    successful = [sample for sample in samples if sample.get("face_detected") is True]
    if len(successful) < 2:
        raise RepeatabilityAnalysisError(
            "Repeatability analysis requires at least 2 successfully detected faces; "
            f"received {len(successful)}."
        )

    feature_reports: dict[str, dict[str, Any]] = {}
    technical_flags: list[dict[str, Any]] = []

    for spec in FEATURE_SPECS:
        feature_name = spec["name"]
        values = [float(sample["features"][feature_name]) for sample in successful]
        raw_stats = calculate_feature_statistics(
            values, cv_mean_epsilon=cv_mean_epsilon
        )
        mean_value = float(raw_stats["mean"])
        std_value = float(raw_stats["std"])

        per_image_values = []
        manual_review_samples = []
        for sample, value in zip(successful, values):
            deviation = value - mean_value
            z_score = None if std_value == 0 else abs(deviation) / std_value
            value_record = {
                "filename": sample["filename"],
                "value": _round_number(value),
                "deviation_from_mean": _round_number(deviation),
                "absolute_z_score": _round_number(z_score),
            }
            per_image_values.append(value_record)
            if z_score is not None and z_score > OUTLIER_Z_THRESHOLD:
                manual_review_samples.append(sample["filename"])
                technical_flags.append(
                    {
                        "type": "sample_over_2_sample_std",
                        "feature": feature_name,
                        "filename": sample["filename"],
                        "absolute_z_score": _round_number(z_score),
                        "action": "manual_review_only",
                    }
                )

        feature_reports[feature_name] = {
            "unit": spec["unit"],
            **{key: _round_number(value) for key, value in raw_stats.items()},
            "values": per_image_values,
            "manual_review_samples": manual_review_samples,
        }

    ranking = sorted(
        (
            {"feature": name, "cv": stats["cv"]}
            for name, stats in feature_reports.items()
            if stats["cv"] is not None
        ),
        key=lambda item: (item["cv"], item["feature"]),
    )

    return {
        "report_version": "1.1",
        "face_profile_version": FACE_PROFILE_VERSION,
        "analysis_scope": "repeatability_only",
        "input": {
            "requested_count": len(samples),
            "successful_count": len(successful),
            "failed_count": len(samples) - len(successful),
            "input_is_mirrored": input_is_mirrored,
        },
        "statistics": {
            "standard_deviation": "sample (n-1)",
            "cv_definition": "std / abs(mean)",
            "cv_near_zero_epsilon": cv_mean_epsilon,
            "outlier_review_rule": "absolute deviation greater than 2 sample standard deviations",
            "outliers_removed": False,
        },
        "samples": list(samples),
        "features": feature_reports,
        "stability_ranking_by_cv": ranking,
        "most_stable_by_cv": ranking[0] if ranking else None,
        "most_variable_by_cv": ranking[-1] if ranking else None,
        "technical_flags": technical_flags,
    }


def save_report_json(report: Mapping[str, Any], output_path: Path | str) -> None:
    """Write strict JSON, rejecting NaN and infinity."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def save_report_csv(report: Mapping[str, Any], output_path: Path | str) -> None:
    """Write one summary row per feature with a column for every input photo."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    samples = report["samples"]
    sample_columns = [
        f"sample_{index}:{sample['filename']}" for index, sample in enumerate(samples, start=1)
    ]
    fieldnames = [
        "feature",
        "unit",
        "n",
        "mean",
        "std",
        "min",
        "max",
        "range",
        "cv",
        "manual_review_samples",
        *sample_columns,
    ]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for spec in FEATURE_SPECS:
            feature_name = spec["name"]
            feature_report = report["features"][feature_name]
            row = {
                "feature": feature_name,
                "unit": feature_report["unit"],
                "n": feature_report["n"],
                "mean": feature_report["mean"],
                "std": feature_report["std"],
                "min": feature_report["min"],
                "max": feature_report["max"],
                "range": feature_report["range"],
                "cv": "" if feature_report["cv"] is None else feature_report["cv"],
                "manual_review_samples": ";".join(feature_report["manual_review_samples"]),
            }
            for index, sample in enumerate(samples, start=1):
                column = f"sample_{index}:{sample['filename']}"
                if sample.get("face_detected") is True:
                    row[column] = sample["features"][feature_name]
                else:
                    row[column] = ""
            writer.writerow(row)


def add_baseline_comparison(
    report: dict[str, Any],
    baseline_report: Mapping[str, Any],
) -> None:
    """Attach before/after statistics without changing either measurement set."""

    baseline_features = baseline_report.get("features")
    if not isinstance(baseline_features, Mapping):
        raise RepeatabilityAnalysisError(
            "Baseline repeatability report is missing its features object."
        )

    comparisons: dict[str, dict[str, Any]] = {}
    for spec in FEATURE_SPECS:
        feature_name = spec["name"]
        before = baseline_features.get(feature_name)
        after = report["features"].get(feature_name)
        if not isinstance(before, Mapping) or not isinstance(after, Mapping):
            raise RepeatabilityAnalysisError(
                f"Baseline comparison is missing feature: {feature_name}"
            )
        before_std = _profile_number(before, ("std",))
        after_std = _profile_number(after, ("std",))
        before_cv_value = before.get("cv")
        after_cv_value = after.get("cv")
        before_cv = (
            None
            if before_cv_value is None
            else _profile_number(before, ("cv",))
        )
        after_cv = (
            None
            if after_cv_value is None
            else _profile_number(after, ("cv",))
        )
        comparisons[feature_name] = {
            "before_std": _round_number(before_std),
            "after_std": _round_number(after_std),
            "std_change": _round_number(after_std - before_std),
            "before_cv": _round_number(before_cv),
            "after_cv": _round_number(after_cv),
            "cv_change": (
                None
                if before_cv is None or after_cv is None
                else _round_number(after_cv - before_cv)
            ),
        }

    report["comparison_to_baseline"] = {
        "available": True,
        "baseline_face_profile_version": baseline_report.get(
            "face_profile_version"
        ),
        "current_face_profile_version": FACE_PROFILE_VERSION,
        "features": comparisons,
    }


def attach_baseline_report(
    report: dict[str, Any], baseline_report_path: Path | str
) -> None:
    path = Path(baseline_report_path)
    if not path.is_file():
        report["comparison_to_baseline"] = {
            "available": False,
            "reason": f"Baseline report not found: {path}",
        }
        return
    try:
        with path.open(encoding="utf-8") as handle:
            baseline_report = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise RepeatabilityAnalysisError(
            f"Could not read baseline repeatability report {path}: {exc}"
        ) from exc
    if not isinstance(baseline_report, Mapping):
        raise RepeatabilityAnalysisError(
            "Baseline repeatability report must be a JSON object."
        )
    add_baseline_comparison(report, baseline_report)


def analyze_repeatability(
    image_paths: Iterable[Path | str],
    *,
    model_path: Path | str = DEFAULT_MODEL_PATH,
    work_output_dir: Path | str = DEFAULT_WORK_OUTPUT_DIR,
    json_output_path: Path | str = DEFAULT_JSON_REPORT_PATH,
    csv_output_path: Path | str = DEFAULT_CSV_REPORT_PATH,
    input_is_mirrored: bool = False,
    cv_mean_epsilon: float = CV_MEAN_EPSILON,
    baseline_report_path: Path | str | None = None,
) -> dict[str, Any]:
    """Run the existing pipeline for each image, then aggregate its profile values."""

    paths = validate_image_paths(image_paths)
    work_dir = Path(work_output_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    samples: list[dict[str, Any]] = []
    for index, image_path in enumerate(paths, start=1):
        output_stem = f"{index:02d}_{image_path.stem}"
        geometry_path = work_dir / f"{output_stem}_geometry.json"
        profile_path = work_dir / f"{output_stem}_profile.json"
        debug_path = work_dir / f"{output_stem}_debug.jpg"
        sample: dict[str, Any] = {
            "filename": image_path.name,
            "image_path": _display_path(image_path),
            "face_detected": False,
        }

        try:
            geometry = process_eye_geometry(
                image_path=image_path,
                model_path=Path(model_path),
                debug_output_path=debug_path,
                json_output_path=geometry_path,
                input_is_mirrored=input_is_mirrored,
                profile_output_path=profile_path,
            )
            with profile_path.open(encoding="utf-8") as profile_file:
                profile = json.load(profile_file)
            sample.update(
                {
                    "face_detected": True,
                    "face_profile_version": profile.get("version"),
                    "pose_normalization": geometry.get(
                        "pose_normalization"
                    ),
                    "features": extract_core_features(profile),
                    "geometry_output": _display_path(geometry_path),
                    "profile_output": _display_path(profile_path),
                    "debug_output": _display_path(debug_path),
                }
            )
        except (
            FaceLandmarkerError,
            FaceProfileError,
            RepeatabilityAnalysisError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            sample["error"] = str(exc)

        samples.append(sample)

    report = build_repeatability_report(
        samples,
        input_is_mirrored=input_is_mirrored,
        cv_mean_epsilon=cv_mean_epsilon,
    )
    if baseline_report_path is not None:
        attach_baseline_report(report, baseline_report_path)
    save_report_json(report, json_output_path)
    save_report_csv(report, csv_output_path)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Measure Face Profile repeatability across photos of one person."
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_DIR,
        help="Directory searched for repeat_*.jpg/jpeg when --images is omitted.",
    )
    parser.add_argument(
        "--images",
        nargs="+",
        type=Path,
        help="Explicit image list; overrides repeat_* discovery.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--work-output-dir", type=Path, default=DEFAULT_WORK_OUTPUT_DIR)
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON_REPORT_PATH)
    parser.add_argument("--csv-output", type=Path, default=DEFAULT_CSV_REPORT_PATH)
    parser.add_argument(
        "--baseline-report",
        type=Path,
        default=DEFAULT_BASELINE_REPORT_PATH,
        help="Optional earlier report used for before/after statistics.",
    )
    parser.add_argument(
        "--mirrored-input",
        action="store_true",
        help="Interpret inputs as mirrored selfie images using the existing pipeline semantics.",
    )
    parser.add_argument(
        "--cv-mean-epsilon",
        type=float,
        default=CV_MEAN_EPSILON,
        help="Absolute mean at or below this value yields a null CV.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        images = (
            args.images
            if args.images is not None
            else discover_repeat_images(args.input_dir)
        )
        report = analyze_repeatability(
            images,
            model_path=args.model,
            work_output_dir=args.work_output_dir,
            json_output_path=args.json_output,
            csv_output_path=args.csv_output,
            input_is_mirrored=args.mirrored_input,
            cv_mean_epsilon=args.cv_mean_epsilon,
            baseline_report_path=args.baseline_report,
        )
    except RepeatabilityAnalysisError as exc:
        raise SystemExit(f"Repeatability analysis failed: {exc}") from exc

    print(
        "Repeatability analysis complete: "
        f"{report['input']['successful_count']}/{report['input']['requested_count']} "
        "faces detected."
    )
    print(f"JSON: {args.json_output}")
    print(f"CSV:  {args.csv_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
