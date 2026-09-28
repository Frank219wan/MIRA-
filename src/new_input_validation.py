"""Validate continuous personalization sensitivity across new real inputs.

The module orchestrates the existing Face Landmarker -> Geometry -> Face
Profile v0.3 pipeline and Personalization Engine v0.  It adds reporting only;
it does not calculate landmarks, geometry features, or makeup rules itself.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

if __package__:
    from .eye_landmarks import process_eye_geometry
    from .face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError
    from .face_profile import FaceProfileError
    from .personalization_engine import (
        PersonalizationEngineError,
        load_json_object,
        personalize_recipe,
        save_json_output,
    )
    from .repeatability_analysis import FEATURE_SPECS, extract_core_features
else:
    from eye_landmarks import process_eye_geometry  # type: ignore
    from face_landmarker import (  # type: ignore
        DEFAULT_MODEL_PATH,
        PROJECT_ROOT,
        FaceLandmarkerError,
    )
    from face_profile import FaceProfileError  # type: ignore
    from personalization_engine import (  # type: ignore
        PersonalizationEngineError,
        load_json_object,
        personalize_recipe,
        save_json_output,
    )
    from repeatability_analysis import (  # type: ignore
        FEATURE_SPECS,
        extract_core_features,
    )


DEFAULT_INPUT_DIR = PROJECT_ROOT / "data" / "input"
DEFAULT_RECIPE_PATH = PROJECT_ROOT / "examples" / "cat_eye_standard_recipe.json"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "data" / "output" / "new_input_validation"
DEFAULT_FACE_COMPARISON_PATH = DEFAULT_OUTPUT_ROOT / "new_input_face_comparison.csv"
DEFAULT_PERSONALIZATION_COMPARISON_PATH = (
    DEFAULT_OUTPUT_ROOT / "new_input_personalization_comparison.csv"
)
DEFAULT_REPORT_PATH = DEFAULT_OUTPUT_ROOT / "new_input_validation.json"

SUPPORTED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}
PERSONALIZATION_PARAMETERS = (
    "direction_angle_deg",
    "extension_factor",
    "range_factor",
    "intensity_factor",
)


class NewInputValidationError(ValueError):
    """Raised when the validation run cannot be configured or serialized."""


def discover_new_images(input_dir: Path | str = DEFAULT_INPUT_DIR) -> list[Path]:
    """Find new_* images with case-insensitive prefix and suffix matching."""

    directory = Path(input_dir)
    if not directory.is_dir():
        raise NewInputValidationError(f"Input directory does not exist: {directory}")
    return sorted(
        (
            path
            for path in directory.iterdir()
            if path.is_file()
            and path.name.lower().startswith("new_")
            and path.suffix.lower() in SUPPORTED_IMAGE_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )


def validate_image_paths(image_paths: Iterable[Path | str]) -> list[Path]:
    paths = [Path(path).expanduser().resolve() for path in image_paths]
    if not paths:
        raise NewInputValidationError(
            "No new input images were found. Add new_*.jpg/JPG/png files or use --images."
        )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise NewInputValidationError(
            "Input image file(s) do not exist: " + ", ".join(missing)
        )
    unsupported = [
        str(path)
        for path in paths
        if path.suffix.lower() not in SUPPORTED_IMAGE_SUFFIXES
    ]
    if unsupported:
        raise NewInputValidationError(
            "Unsupported input image type(s): " + ", ".join(unsupported)
        )
    return paths


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT.resolve()))
    except ValueError:
        return str(path.resolve())


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise NewInputValidationError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise NewInputValidationError(f"{label} must be finite.")
    return number


def _action_by_id(
    personalization: Mapping[str, Any], action_id: str
) -> Mapping[str, Any]:
    actions = personalization.get("personalized_actions")
    if not isinstance(actions, Sequence) or isinstance(actions, (str, bytes)):
        raise NewInputValidationError(
            "Personalization output is missing personalized_actions."
        )
    for action in actions:
        if isinstance(action, Mapping) and action.get("action_id") == action_id:
            return action
    raise NewInputValidationError(
        f"Personalization output is missing action {action_id}."
    )


def _parameter(action: Mapping[str, Any], section: str, name: str) -> float:
    values = action.get(section)
    if not isinstance(values, Mapping) or name not in values:
        raise NewInputValidationError(
            f"Personalization output is missing {section}.{name}."
        )
    return _finite_number(values[name], f"{section}.{name}")


def active_direction(original: float, personalized: float) -> str:
    """Describe a parameter change without assigning any eye-type label."""

    original_value = _finite_number(original, "original parameter")
    personalized_value = _finite_number(personalized, "personalized parameter")
    if math.isclose(original_value, personalized_value, abs_tol=1e-12):
        return "unchanged"
    return "increase" if personalized_value > original_value else "decrease"


def summarize_personalization(
    personalization: Mapping[str, Any],
) -> dict[str, Any]:
    """Flatten A04/A02 outputs while preserving rule groups and direction."""

    a04 = _action_by_id(personalization, "A04")
    a02 = _action_by_id(personalization, "A02")
    action_parameters = {
        "direction_angle_deg": (a04, "direction_angle_deg"),
        "extension_factor": (a04, "extension_factor"),
        "range_factor": (a02, "range_factor"),
        "intensity_factor": (a02, "intensity_factor"),
    }

    parameter_values: dict[str, float] = {}
    parameter_directions: dict[str, str] = {}
    for output_name, (action, parameter_name) in action_parameters.items():
        original = _parameter(action, "original_parameters", parameter_name)
        personalized = _parameter(
            action, "personalized_parameters", parameter_name
        )
        parameter_values[output_name] = personalized
        parameter_directions[output_name] = active_direction(
            original, personalized
        )

    applied_rules: list[str] = []
    rule_groups: list[str] = []
    for action in (a04, a02):
        action_rules = action.get("applied_rules")
        if isinstance(action_rules, Sequence) and not isinstance(
            action_rules, (str, bytes)
        ):
            for rule_id in action_rules:
                if isinstance(rule_id, str) and rule_id not in applied_rules:
                    applied_rules.append(rule_id)
        adjustments = action.get("adjustments")
        if isinstance(adjustments, Sequence) and not isinstance(
            adjustments, (str, bytes)
        ):
            for adjustment in adjustments:
                if not isinstance(adjustment, Mapping):
                    continue
                rule_ids = adjustment.get("rule_ids")
                if isinstance(rule_ids, Sequence) and not isinstance(
                    rule_ids, (str, bytes)
                ):
                    group = "/".join(
                        str(rule_id) for rule_id in rule_ids
                    )
                    if group and group not in rule_groups:
                        rule_groups.append(group)

    return {
        **parameter_values,
        "applied_rules": applied_rules,
        "applied_rule_groups": rule_groups,
        "active_directions": parameter_directions,
    }


def calculate_feature_ranges(
    records: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, float | int]]:
    """Calculate cross-person min/max/range without classifying the values."""

    successful = [
        record for record in records if record.get("face_detected") is True
    ]
    ranges: dict[str, dict[str, float | int]] = {}
    for spec in FEATURE_SPECS:
        name = spec["name"]
        values = [
            _finite_number(record["features"][name], name)
            for record in successful
        ]
        if values:
            minimum = min(values)
            maximum = max(values)
            ranges[name] = {
                "n": len(values),
                "min": round(minimum, 10),
                "max": round(maximum, 10),
                "range": round(maximum - minimum, 10),
            }
    return ranges


def _pairwise_differences(
    records: Sequence[Mapping[str, Any]],
    value_key: str,
    names: Sequence[str],
) -> list[dict[str, Any]]:
    eligible = [
        record
        for record in records
        if isinstance(record.get(value_key), Mapping)
    ]
    pairs = []
    for first, second in combinations(eligible, 2):
        first_values = first[value_key]
        second_values = second[value_key]
        differences = {
            name: round(
                abs(
                    _finite_number(first_values[name], name)
                    - _finite_number(second_values[name], name)
                ),
                10,
            )
            for name in names
        }
        pairs.append(
            {
                "person_a": first["person_id"],
                "person_b": second["person_id"],
                "absolute_differences": differences,
            }
        )
    return pairs


def build_validation_report(
    records: Sequence[Mapping[str, Any]],
    recipe_path: Path,
    *,
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    face_successes = sum(
        record.get("face_detected") is True for record in records
    )
    personalization_successes = sum(
        isinstance(record.get("personalization"), Mapping)
        for record in records
    )
    feature_names = [spec["name"] for spec in FEATURE_SPECS]
    return {
        "report_version": "1.0",
        "analysis_scope": "continuous_personalization_sensitivity",
        "face_profile_version": "0.3",
        "personalization_engine_version": "0",
        "target_effect": "cat_eye",
        "input": {
            "requested_count": len(records),
            "face_detection_success_count": face_successes,
            "face_detection_failure_count": len(records) - face_successes,
            "personalization_success_count": personalization_successes,
            "input_is_mirrored": input_is_mirrored,
            "recipe": _display_path(recipe_path),
        },
        "people": list(records),
        "feature_ranges": calculate_feature_ranges(records),
        "pairwise_face_profile_absolute_differences": _pairwise_differences(
            records,
            "features",
            feature_names,
        ),
        "pairwise_personalization_absolute_differences": _pairwise_differences(
            records,
            "personalization",
            PERSONALIZATION_PARAMETERS,
        ),
        "interpretation_limits": [
            "Continuous measurements only; no eye-type labels are produced.",
            "Calibration is provisional and is not claimed to be makeup-science validated.",
            "A numeric difference does not prove that a different makeup action is required.",
            "Face Profile v0.3 does not represent the complete eye appearance.",
            "Small or identical personalized outputs are retained without amplification.",
        ],
    }


def save_face_comparison_csv(
    records: Sequence[Mapping[str, Any]], output_path: Path | str
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    feature_names = [spec["name"] for spec in FEATURE_SPECS]
    fields = [
        "person_id",
        "filename",
        "face_detected",
        *feature_names,
        "roll_angle_deg",
        "pose_normalized",
        "error_stage",
        "error",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            features = record.get("features", {})
            pose = record.get("pose_normalization", {})
            row = {
                "person_id": record["person_id"],
                "filename": record["filename"],
                "face_detected": record.get("face_detected", False),
                "roll_angle_deg": pose.get("roll_angle_deg", "")
                if isinstance(pose, Mapping)
                else "",
                "pose_normalized": pose.get("applied", "")
                if isinstance(pose, Mapping)
                else "",
                "error_stage": record.get("error_stage", ""),
                "error": record.get("error", ""),
            }
            for name in feature_names:
                row[name] = features.get(name, "")
            writer.writerow(row)


def save_personalization_comparison_csv(
    records: Sequence[Mapping[str, Any]], output_path: Path | str
) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "person_id",
        "filename",
        *PERSONALIZATION_PARAMETERS,
        "applied_rule_groups",
        "applied_rules",
        "direction_angle_active_direction",
        "extension_active_direction",
        "range_active_direction",
        "intensity_active_direction",
        "error_stage",
        "error",
    ]
    direction_fields = {
        "direction_angle_active_direction": "direction_angle_deg",
        "extension_active_direction": "extension_factor",
        "range_active_direction": "range_factor",
        "intensity_active_direction": "intensity_factor",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            personalization = record.get("personalization", {})
            row = {
                "person_id": record["person_id"],
                "filename": record["filename"],
                "error_stage": record.get("error_stage", ""),
                "error": record.get("error", ""),
            }
            for name in PERSONALIZATION_PARAMETERS:
                row[name] = personalization.get(name, "")
            row["applied_rule_groups"] = ";".join(
                personalization.get("applied_rule_groups", [])
            )
            row["applied_rules"] = ";".join(
                personalization.get("applied_rules", [])
            )
            directions = personalization.get("active_directions", {})
            for output_field, parameter_name in direction_fields.items():
                row[output_field] = directions.get(parameter_name, "")
            writer.writerow(row)


def analyze_new_inputs(
    image_paths: Iterable[Path | str],
    *,
    model_path: Path | str = DEFAULT_MODEL_PATH,
    recipe_path: Path | str = DEFAULT_RECIPE_PATH,
    output_root: Path | str = DEFAULT_OUTPUT_ROOT,
    input_is_mirrored: bool = False,
) -> dict[str, Any]:
    """Run the existing CV and personalization pipelines over each input."""

    paths = validate_image_paths(image_paths)
    recipe_file = Path(recipe_path)
    recipe = load_json_object(recipe_file)
    if recipe.get("target_effect") != "cat_eye":
        raise NewInputValidationError(
            "Validation recipe must declare target_effect='cat_eye'."
        )

    root = Path(output_root)
    profile_dir = root / "individual_profiles"
    personalization_dir = root / "individual_personalization"
    profile_dir.mkdir(parents=True, exist_ok=True)
    personalization_dir.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, Any]] = []
    for index, image_path in enumerate(paths, start=1):
        person_id = f"Person {index:02d}"
        output_stem = f"person_{index:02d}_{image_path.stem}"
        geometry_path = profile_dir / f"{output_stem}_geometry.json"
        profile_path = profile_dir / f"{output_stem}_face_profile.json"
        debug_path = profile_dir / f"{output_stem}_debug.jpg"
        personalization_path = (
            personalization_dir / f"{output_stem}_personalization.json"
        )
        record: dict[str, Any] = {
            "person_id": person_id,
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
            profile = load_json_object(profile_path)
            features = extract_core_features(profile)
            record.update(
                {
                    "face_detected": True,
                    "face_profile_version": profile.get("version"),
                    "features": features,
                    "pose_normalization": geometry.get("pose_normalization", {}),
                    "geometry_output": _display_path(geometry_path),
                    "profile_output": _display_path(profile_path),
                    "debug_output": _display_path(debug_path),
                }
            )

            personalization_result = personalize_recipe(
                profile,
                recipe,
                "cat_eye",
            )
            save_json_output(personalization_path, personalization_result)
            record.update(
                {
                    "personalization": summarize_personalization(
                        personalization_result
                    ),
                    "personalization_output": _display_path(
                        personalization_path
                    ),
                }
            )
        except (
            FaceLandmarkerError,
            FaceProfileError,
            PersonalizationEngineError,
            NewInputValidationError,
            OSError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:
            record["error_stage"] = (
                "personalization" if record["face_detected"] else "face_pipeline"
            )
            record["error"] = str(exc)

        records.append(record)

    report = build_validation_report(
        records,
        recipe_file,
        input_is_mirrored=input_is_mirrored,
    )
    save_face_comparison_csv(records, root / "new_input_face_comparison.csv")
    save_personalization_comparison_csv(
        records,
        root / "new_input_personalization_comparison.csv",
    )
    save_json_output(root / "new_input_validation.json", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate continuous personalization sensitivity on new inputs."
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument(
        "--images",
        nargs="+",
        type=Path,
        help="Explicit images; overrides automatic new_* discovery.",
    )
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE_PATH)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--mirrored-input",
        action="store_true",
        help="Interpret every input as mirrored using existing CV semantics.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        images = (
            args.images
            if args.images is not None
            else discover_new_images(args.input_dir)
        )
        report = analyze_new_inputs(
            images,
            model_path=args.model,
            recipe_path=args.recipe,
            output_root=args.output_root,
            input_is_mirrored=args.mirrored_input,
        )
    except (
        NewInputValidationError,
        PersonalizationEngineError,
    ) as exc:
        print(f"New-input validation failed: {exc}", file=sys.stderr)
        return 1

    summary = report["input"]
    print(
        "New-input validation complete: "
        f"{summary['face_detection_success_count']}/"
        f"{summary['requested_count']} faces detected; "
        f"{summary['personalization_success_count']} personalized."
    )
    print(f"Output: {Path(args.output_root).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
