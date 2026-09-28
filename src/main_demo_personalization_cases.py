"""Validation-only Face06/Face11 personalization with candidate dead zones.

This module orchestrates the frozen Face Profile v0.3 values and the existing
R01-R06 production mappings.  Dead-zone decisions live only in this validation
layer and do not alter ``makeup_rules.DEFAULT_RULE_CALIBRATION``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

if __package__:
    from .makeup_rules import (
        DEFAULT_RULE_CALIBRATION,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
        apply_lower_lid_intensity,
        apply_lower_lid_range,
    )
    from .personalization_engine import load_json_object, save_json_output
else:
    from makeup_rules import (  # type: ignore
        DEFAULT_RULE_CALIBRATION,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
        apply_lower_lid_intensity,
        apply_lower_lid_range,
    )
    from personalization_engine import (  # type: ignore
        load_json_object,
        save_json_output,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]


DEFAULT_BLOGGER_PROFILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "blogger_user_comparison"
    / "blogger_bare_face_profile.json"
)
DEFAULT_REFERENCE_RECIPE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "reference_action"
    / "cat_eye_reference_standard_action.json"
)
DEFAULT_FACE06_PROFILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "rule_calibration_dataset"
    / "individual_profiles"
    / "face_06_face_profile.json"
)
DEFAULT_FACE11_PROFILE = (
    PROJECT_ROOT
    / "data"
    / "output"
    / "rule_calibration_dataset"
    / "individual_profiles"
    / "face_11_face_profile.json"
)
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "output" / "main_demo_personalization_cases"
)

DEAD_ZONE_STATUS = "expert_rule_v0_pending_validation"
EXPECTED_REFERENCE = {
    "direction_relative_to_eye_axis_deg": 5.781666,
    "reference_extension_ratio": 0.344930,
    "start_position_ratio": 0.985925,
}


class MainDemoValidationError(ValueError):
    """Raised when a validation input or result is invalid."""


@dataclass(frozen=True)
class DeadZoneConfig:
    """Candidate validation thresholds; these are not production calibration."""

    eye_tail_angle_deg: float = 1.25
    relative_eye_length: float = 0.019
    lower_lid_space_ratio: float = 0.0045
    status: str = DEAD_ZONE_STATUS

    def __post_init__(self) -> None:
        values = (
            self.eye_tail_angle_deg,
            self.relative_eye_length,
            self.lower_lid_space_ratio,
        )
        if not all(math.isfinite(value) and value >= 0.0 for value in values):
            raise MainDemoValidationError(
                "Dead-zone thresholds must be non-negative finite numbers."
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "scope": "validation_only",
            "eye_tail_angle_deg": self.eye_tail_angle_deg,
            "relative_eye_length": self.relative_eye_length,
            "lower_lid_space_ratio": self.lower_lid_space_ratio,
        }


DEFAULT_DEAD_ZONE = DeadZoneConfig()

FEATURE_PATHS: Mapping[str, tuple[str, ...]] = {
    "eye_tail_angle.mean": ("eye_geometry", "eye_tail_angle", "mean"),
    "relative_eye_length.mean": (
        "eye_geometry",
        "relative_eye_length",
        "mean",
    ),
    "lower_lid_space_ratio.mean": (
        "eye_geometry",
        "lower_lid_space_ratio",
        "mean",
    ),
}


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MainDemoValidationError(f"{label} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise MainDemoValidationError(f"{label} must be finite.")
    return number


def _profile_number(profile: Mapping[str, Any], feature: str) -> float:
    if profile.get("version") != "0.3":
        raise MainDemoValidationError("Face Profile v0.3 is required.")
    value: Any = profile
    for key in FEATURE_PATHS[feature]:
        if not isinstance(value, Mapping) or key not in value:
            raise MainDemoValidationError(
                f"Face Profile is missing {'.'.join(FEATURE_PATHS[feature])}."
            )
        value = value[key]
    return _finite_number(value, feature)


def _reference_parameters(recipe: Mapping[str, Any]) -> dict[str, float]:
    actions = recipe.get("actions")
    if not isinstance(actions, list):
        raise MainDemoValidationError("Reference recipe actions must be an array.")
    matches = [
        action
        for action in actions
        if isinstance(action, Mapping) and action.get("action_id") == "A04"
    ]
    if len(matches) != 1:
        raise MainDemoValidationError("Expected exactly one reference A04 action.")
    parameters = matches[0].get("reference_parameters")
    if not isinstance(parameters, Mapping):
        raise MainDemoValidationError("Reference A04 parameters are missing.")
    result = {
        key: _finite_number(parameters.get(key), key)
        for key in EXPECTED_REFERENCE
    }
    for key, expected in EXPECTED_REFERENCE.items():
        if not math.isclose(result[key], expected, abs_tol=1e-12):
            raise MainDemoValidationError(
                f"Reference mismatch for {key}: expected {expected}, "
                f"got {result[key]}."
            )
    return result


def _assert_strict_finite(value: Any, path: str = "output") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _assert_strict_finite(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_strict_finite(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise MainDemoValidationError(
            f"Output contains NaN or infinity: {path}."
        )


def _decision(
    difference: float,
    threshold: float,
    lower_rule: str,
    higher_rule: str,
    *,
    dead_zone_enabled: bool,
) -> dict[str, Any]:
    inside = abs(difference) <= threshold if dead_zone_enabled else False
    if inside or difference == 0.0:
        return {
            "inside_dead_zone": inside,
            "keep_reference": True,
            "triggered_rule": None,
            "decision": "KEEP_REFERENCE",
            "reason": (
                "difference_within_dead_zone"
                if inside
                else "profiles_are_identical"
            ),
        }
    return {
        "inside_dead_zone": False,
        "keep_reference": False,
        "triggered_rule": lower_rule if difference < 0.0 else higher_rule,
        "decision": "APPLY_RELATIVE_ADJUSTMENT",
        "reason": (
            "difference_outside_dead_zone"
            if dead_zone_enabled
            else "dead_zone_disabled"
        ),
    }


def calculate_case(
    blogger_profile: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    reference_parameters: Mapping[str, Any],
    *,
    case: str,
    dead_zone_enabled: bool = True,
    dead_zone: DeadZoneConfig = DEFAULT_DEAD_ZONE,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Calculate one validation case by reusing all production mappings."""

    blogger = {
        feature: _profile_number(blogger_profile, feature)
        for feature in FEATURE_PATHS
    }
    user = {
        feature: _profile_number(user_profile, feature)
        for feature in FEATURE_PATHS
    }
    differences = {
        feature: round(user[feature] - blogger[feature], 6)
        for feature in FEATURE_PATHS
    }
    reference_direction = _finite_number(
        reference_parameters.get("direction_relative_to_eye_axis_deg"),
        "direction_relative_to_eye_axis_deg",
    )
    reference_extension = _finite_number(
        reference_parameters.get("reference_extension_ratio"),
        "reference_extension_ratio",
    )
    start_position = _finite_number(
        reference_parameters.get("start_position_ratio"),
        "start_position_ratio",
    )

    tail_decision = _decision(
        differences["eye_tail_angle.mean"],
        dead_zone.eye_tail_angle_deg,
        "R01",
        "R02",
        dead_zone_enabled=dead_zone_enabled,
    )
    length_decision = _decision(
        differences["relative_eye_length.mean"],
        dead_zone.relative_eye_length,
        "R03",
        "R04",
        dead_zone_enabled=dead_zone_enabled,
    )
    lower_decision = _decision(
        differences["lower_lid_space_ratio.mean"],
        dead_zone.lower_lid_space_ratio,
        "R05",
        "R06",
        dead_zone_enabled=dead_zone_enabled,
    )

    blogger_direction = float(
        apply_eyeliner_direction(
            blogger["eye_tail_angle.mean"], 0.0, calibration
        )["adjustment_value"]
    )
    user_direction = float(
        apply_eyeliner_direction(
            user["eye_tail_angle.mean"], 0.0, calibration
        )["adjustment_value"]
    )
    raw_direction_adjustment = user_direction - blogger_direction
    direction_adjustment = (
        0.0 if tail_decision["keep_reference"] else raw_direction_adjustment
    )

    blogger_extension = float(
        apply_eyeliner_extension(
            blogger["relative_eye_length.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    user_extension = float(
        apply_eyeliner_extension(
            user["relative_eye_length.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    if blogger_extension <= 0.0:
        raise MainDemoValidationError(
            "Blogger extension factor must be greater than zero."
        )
    raw_extension_factor = user_extension / blogger_extension
    extension_factor = (
        1.0 if length_decision["keep_reference"] else raw_extension_factor
    )

    blogger_range = float(
        apply_lower_lid_range(
            blogger["lower_lid_space_ratio.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    user_range = float(
        apply_lower_lid_range(
            user["lower_lid_space_ratio.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    blogger_intensity = float(
        apply_lower_lid_intensity(
            blogger["lower_lid_space_ratio.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    user_intensity = float(
        apply_lower_lid_intensity(
            user["lower_lid_space_ratio.mean"], 1.0, calibration
        )["adjustment_value"]
    )
    if blogger_range <= 0.0 or blogger_intensity <= 0.0:
        raise MainDemoValidationError(
            "Blogger lower-lid mapping factors must be greater than zero."
        )
    raw_range_factor = user_range / blogger_range
    raw_intensity_factor = user_intensity / blogger_intensity
    range_factor = 1.0 if lower_decision["keep_reference"] else raw_range_factor
    intensity_factor = (
        1.0 if lower_decision["keep_reference"] else raw_intensity_factor
    )

    feature_decisions = {
        "eye_tail_angle.mean": {
            "blogger": blogger["eye_tail_angle.mean"],
            "user": user["eye_tail_angle.mean"],
            "difference": differences["eye_tail_angle.mean"],
            "threshold": dead_zone.eye_tail_angle_deg,
            **tail_decision,
        },
        "relative_eye_length.mean": {
            "blogger": blogger["relative_eye_length.mean"],
            "user": user["relative_eye_length.mean"],
            "difference": differences["relative_eye_length.mean"],
            "threshold": dead_zone.relative_eye_length,
            **length_decision,
        },
        "lower_lid_space_ratio.mean": {
            "blogger": blogger["lower_lid_space_ratio.mean"],
            "user": user["lower_lid_space_ratio.mean"],
            "difference": differences["lower_lid_space_ratio.mean"],
            "threshold": dead_zone.lower_lid_space_ratio,
            **lower_decision,
        },
    }
    triggered_rules = [
        decision["triggered_rule"]
        for decision in feature_decisions.values()
        if decision["triggered_rule"] is not None
    ]
    result = {
        "case": case,
        "mode": (
            "reference_relative_with_validation_dead_zone"
            if dead_zone_enabled
            else "reference_relative_dead_zone_disabled"
        ),
        "dead_zone_enabled": dead_zone_enabled,
        "dead_zone_config": dead_zone.as_dict(),
        "blogger_p0": blogger,
        "user_p0": user,
        "differences": {
            "delta_eye_tail": differences["eye_tail_angle.mean"],
            "delta_relative_eye_length": differences[
                "relative_eye_length.mean"
            ],
            "delta_lower_lid_space": differences[
                "lower_lid_space_ratio.mean"
            ],
        },
        "feature_decisions": feature_decisions,
        "A04": {
            "direction": {
                "reference_direction_deg": reference_direction,
                "blogger_correction_deg": blogger_direction,
                "user_correction_deg": user_direction,
                "raw_relative_adjustment_deg": round(
                    raw_direction_adjustment, 6
                ),
                "relative_adjustment_deg": round(direction_adjustment, 6),
                "personalized_direction_deg": round(
                    reference_direction + direction_adjustment, 6
                ),
            },
            "extension": {
                "reference_extension_ratio": reference_extension,
                "blogger_adaptation_factor": blogger_extension,
                "user_adaptation_factor": user_extension,
                "raw_relative_adaptation_factor": round(
                    raw_extension_factor, 12
                ),
                "relative_adaptation_factor": round(extension_factor, 12),
                "personalized_extension_ratio": round(
                    reference_extension * extension_factor, 12
                ),
            },
            "start_position_ratio": start_position,
        },
        "A02": {
            "reference_range_factor": 1.0,
            "reference_intensity_factor": 1.0,
            "blogger_range_mapping_factor": blogger_range,
            "user_range_mapping_factor": user_range,
            "raw_relative_range_factor": round(raw_range_factor, 12),
            "personalized_range_factor": round(range_factor, 12),
            "blogger_intensity_mapping_factor": blogger_intensity,
            "user_intensity_mapping_factor": user_intensity,
            "raw_relative_intensity_factor": round(
                raw_intensity_factor, 12
            ),
            "personalized_intensity_factor": round(intensity_factor, 12),
        },
        "triggered_rules": triggered_rules,
    }
    _assert_strict_finite(result)
    return result


def _summary_rows(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    decisions = result["feature_decisions"]
    a04 = result["A04"]
    a02 = result["A02"]
    specs = (
        (
            "eye_tail_angle.mean",
            "A04.direction",
            a04["direction"]["reference_direction_deg"],
            a04["direction"]["relative_adjustment_deg"],
            a04["direction"]["personalized_direction_deg"],
        ),
        (
            "relative_eye_length.mean",
            "A04.extension",
            a04["extension"]["reference_extension_ratio"],
            a04["extension"]["relative_adaptation_factor"],
            a04["extension"]["personalized_extension_ratio"],
        ),
        (
            "lower_lid_space_ratio.mean",
            "A02.range",
            a02["reference_range_factor"],
            a02["personalized_range_factor"],
            a02["personalized_range_factor"],
        ),
        (
            "lower_lid_space_ratio.mean",
            "A02.intensity",
            a02["reference_intensity_factor"],
            a02["personalized_intensity_factor"],
            a02["personalized_intensity_factor"],
        ),
    )
    rows: list[dict[str, Any]] = []
    for feature, parameter, reference, adjustment, personalized in specs:
        decision = decisions[feature]
        rows.append(
            {
                "case": result["case"],
                "feature": feature,
                "parameter": parameter,
                "blogger": decision["blogger"],
                "user": decision["user"],
                "difference": decision["difference"],
                "threshold": decision["threshold"],
                "inside_dead_zone": decision["inside_dead_zone"],
                "triggered_rule": decision["triggered_rule"],
                "reference_value": reference,
                "adjustment": adjustment,
                "personalized_value": personalized,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise MainDemoValidationError(f"Cannot write empty CSV: {path}.")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_outputs(
    blogger_profile: Mapping[str, Any],
    cases: Mapping[str, Mapping[str, Any]],
    reference_parameters: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    enabled: dict[str, dict[str, Any]] = {}
    disabled: dict[str, dict[str, Any]] = {}
    summary_rows: list[dict[str, Any]] = []
    comparison_rows: list[dict[str, Any]] = []

    for case, profile in cases.items():
        on = calculate_case(
            blogger_profile,
            profile,
            reference_parameters,
            case=case,
            dead_zone_enabled=True,
        )
        off = calculate_case(
            blogger_profile,
            profile,
            reference_parameters,
            case=case,
            dead_zone_enabled=False,
        )
        enabled[case] = on
        disabled[case] = off
        save_json_output(output_dir / f"{case}_personalization.json", on)
        explanation = {
            "case": case,
            "reference_policy": "blogger_to_user_difference",
            "dead_zone_status": DEAD_ZONE_STATUS,
            "dead_zone_enabled": on,
            "dead_zone_disabled": off,
        }
        save_json_output(output_dir / f"{case}_explanation.json", explanation)
        case_rows = _summary_rows(on)
        summary_rows.extend(case_rows)
        _write_csv(output_dir / f"{case}_vs_reference.csv", case_rows)

        on_values = {
            "direction": on["A04"]["direction"][
                "personalized_direction_deg"
            ],
            "extension": on["A04"]["extension"][
                "personalized_extension_ratio"
            ],
            "lower_range": on["A02"]["personalized_range_factor"],
            "lower_intensity": on["A02"][
                "personalized_intensity_factor"
            ],
        }
        off_values = {
            "direction": off["A04"]["direction"][
                "personalized_direction_deg"
            ],
            "extension": off["A04"]["extension"][
                "personalized_extension_ratio"
            ],
            "lower_range": off["A02"]["personalized_range_factor"],
            "lower_intensity": off["A02"][
                "personalized_intensity_factor"
            ],
        }
        reference_values = {
            "direction": reference_parameters[
                "direction_relative_to_eye_axis_deg"
            ],
            "extension": reference_parameters["reference_extension_ratio"],
            "lower_range": 1.0,
            "lower_intensity": 1.0,
        }
        for parameter in on_values:
            comparison_rows.append(
                {
                    "case": case,
                    "parameter": parameter,
                    "reference_value": reference_values[parameter],
                    "dead_zone_disabled": off_values[parameter],
                    "dead_zone_enabled": on_values[parameter],
                    "enabled_minus_disabled": round(
                        on_values[parameter] - off_values[parameter], 12
                    ),
                }
            )

    identity = calculate_case(
        blogger_profile,
        blogger_profile,
        reference_parameters,
        case="identity",
        dead_zone_enabled=True,
    )
    identity_passed = (
        identity["A04"]["direction"]["personalized_direction_deg"]
        == reference_parameters["direction_relative_to_eye_axis_deg"]
        and identity["A04"]["extension"]["personalized_extension_ratio"]
        == reference_parameters["reference_extension_ratio"]
        and identity["A02"]["personalized_range_factor"] == 1.0
        and identity["A02"]["personalized_intensity_factor"] == 1.0
        and identity["triggered_rules"] == []
    )
    identity_result = {
        "property": "identity_consistency",
        "passed": identity_passed,
        "result": identity,
    }
    save_json_output(output_dir / "identity_consistency.json", identity_result)
    _write_csv(output_dir / "face06_face11_summary.csv", summary_rows)
    _write_csv(output_dir / "dead_zone_comparison.csv", comparison_rows)
    return {
        "enabled": enabled,
        "disabled": disabled,
        "identity_consistency": identity_result,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Face06/Face11 Main Demo personalization validation."
    )
    parser.add_argument("--blogger-profile", type=Path, default=DEFAULT_BLOGGER_PROFILE)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE_RECIPE)
    parser.add_argument("--face06", type=Path, default=DEFAULT_FACE06_PROFILE)
    parser.add_argument("--face11", type=Path, default=DEFAULT_FACE11_PROFILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        blogger = load_json_object(args.blogger_profile)
        reference_recipe = load_json_object(args.reference)
        reference_parameters = _reference_parameters(reference_recipe)
        cases = {
            "face06": load_json_object(args.face06),
            "face11": load_json_object(args.face11),
        }
        results = generate_outputs(
            blogger, cases, reference_parameters, args.output_dir
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 1
    print(json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
