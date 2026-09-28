"""Reference-relative A04 personalization built on the existing R01-R04 maps.

Absolute mode remains the existing reference recipe path.  Relative mode only
changes A04 direction and extension; A02 is copied from that same absolute run.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any, Mapping

if __package__:
    from .face_landmarker import PROJECT_ROOT
    from .makeup_rules import (
        DEFAULT_RULE_CALIBRATION,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
    )
    from .personalization_engine import load_json_object, save_json_output
    from .reference_action_adapter import (
        build_standard_recipe,
        personalize_reference_recipe,
    )
else:
    from face_landmarker import PROJECT_ROOT  # type: ignore
    from makeup_rules import (  # type: ignore
        DEFAULT_RULE_CALIBRATION,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
    )
    from personalization_engine import load_json_object, save_json_output  # type: ignore
    from reference_action_adapter import (  # type: ignore
        build_standard_recipe,
        personalize_reference_recipe,
    )


DEFAULT_BLOGGER_PROFILE = (
    PROJECT_ROOT / "data" / "output" / "main_demo_reference"
    / "blogger_before_face_profile.json"
)
DEFAULT_REFERENCE_ACTION = (
    PROJECT_ROOT / "data" / "output" / "main_demo_reference"
    / "blogger_after_reference_action.json"
)
DEFAULT_USER_PROFILE = (
    PROJECT_ROOT / "data" / "output" / "stable_face_scan_validation"
    / "stable_face_profile.json"
)
DEFAULT_RECIPE = PROJECT_ROOT / "examples" / "cat_eye_standard_recipe.json"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "output" / "reference_relative_personalization"
)
MODES = frozenset(("absolute", "reference_relative"))


class ReferenceRelativePersonalizationError(ValueError):
    """Raised when reference-relative personalization cannot be computed."""


def _profile_number(profile: Mapping[str, Any], path: tuple[str, ...]) -> float:
    if profile.get("version") != "0.3":
        raise ReferenceRelativePersonalizationError(
            "Reference-relative mode requires Face Profile v0.3."
        )
    value: Any = profile
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise ReferenceRelativePersonalizationError(
                "Face Profile is missing required field: " + ".".join(path)
            )
        value = value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceRelativePersonalizationError(
            "Face Profile field must be numeric: " + ".".join(path)
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceRelativePersonalizationError(
            "Face Profile field must be finite: " + ".".join(path)
        )
    return number


def _reference_number(reference: Mapping[str, Any], key: str) -> float:
    value = reference.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceRelativePersonalizationError(
            f"Reference parameter {key} must be numeric."
        )
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceRelativePersonalizationError(
            f"Reference parameter {key} must be finite."
        )
    return number


def _assert_strict_finite(value: Any, path: str = "output") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _assert_strict_finite(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_strict_finite(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise ReferenceRelativePersonalizationError(
            f"Output contains NaN or infinity: {path}"
        )


def _reference_a04_parameters(standard_recipe: Mapping[str, Any]) -> Mapping[str, Any]:
    actions = standard_recipe.get("actions")
    if not isinstance(actions, list):
        raise ReferenceRelativePersonalizationError("Recipe actions must be an array.")
    matches = [
        action for action in actions
        if isinstance(action, Mapping) and action.get("action_id") == "A04"
    ]
    if len(matches) != 1:
        raise ReferenceRelativePersonalizationError("Expected exactly one A04 action.")
    reference = matches[0].get("reference_parameters")
    if not isinstance(reference, Mapping):
        raise ReferenceRelativePersonalizationError(
            "A04 is missing reference_parameters."
        )
    return reference


def _absolute_a02(absolute_output: Mapping[str, Any]) -> Mapping[str, Any]:
    actions = absolute_output.get("personalized_actions")
    if not isinstance(actions, list):
        raise ReferenceRelativePersonalizationError(
            "Absolute personalization output is missing actions."
        )
    matches = [
        action for action in actions
        if isinstance(action, Mapping) and action.get("action_id") == "A02"
    ]
    if len(matches) != 1:
        raise ReferenceRelativePersonalizationError("Expected exactly one A02 action.")
    return matches[0]


def calculate_reference_relative_a04(
    blogger_profile: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    reference_parameters: Mapping[str, Any],
    *,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Calculate A04 deltas using the production R01-R04 mappings."""

    blogger_tail = _profile_number(
        blogger_profile, ("eye_geometry", "eye_tail_angle", "mean")
    )
    user_tail = _profile_number(
        user_profile, ("eye_geometry", "eye_tail_angle", "mean")
    )
    blogger_length = _profile_number(
        blogger_profile, ("eye_geometry", "relative_eye_length", "mean")
    )
    user_length = _profile_number(
        user_profile, ("eye_geometry", "relative_eye_length", "mean")
    )
    reference_direction = _reference_number(
        reference_parameters, "direction_relative_to_eye_axis_deg"
    )
    reference_extension = _reference_number(
        reference_parameters, "reference_extension_ratio"
    )
    if reference_extension <= 0.0:
        raise ReferenceRelativePersonalizationError(
            "reference_extension_ratio must be positive."
        )
    start_position = reference_parameters.get("start_position_ratio")
    if start_position is not None:
        start_position = _reference_number(
            reference_parameters, "start_position_ratio"
        )

    blogger_direction_map = apply_eyeliner_direction(
        blogger_tail, 0.0, calibration
    )
    user_direction_map = apply_eyeliner_direction(user_tail, 0.0, calibration)
    blogger_correction = float(blogger_direction_map["adjustment_value"])
    user_correction = float(user_direction_map["adjustment_value"])
    relative_direction = round(user_correction - blogger_correction, 6)
    personalized_direction = round(reference_direction + relative_direction, 6)

    blogger_extension_map = apply_eyeliner_extension(
        blogger_length, 1.0, calibration
    )
    user_extension_map = apply_eyeliner_extension(
        user_length, 1.0, calibration
    )
    blogger_factor = float(blogger_extension_map["adjustment_value"])
    user_factor = float(user_extension_map["adjustment_value"])
    if blogger_factor <= 0.0:
        raise ReferenceRelativePersonalizationError(
            "Blogger extension adaptation factor must be greater than zero."
        )
    relative_factor = user_factor / blogger_factor
    personalized_extension = reference_extension * relative_factor
    relative_factor_output = round(relative_factor, 12)
    personalized_extension_output = round(personalized_extension, 12)

    result = {
        "reference": {
            "direction_deg": reference_direction,
            "extension_ratio": reference_extension,
            "start_position_ratio": start_position,
        },
        "blogger_profile": {
            "eye_tail_angle": blogger_tail,
            "relative_eye_length": blogger_length,
        },
        "user_profile": {
            "eye_tail_angle": user_tail,
            "relative_eye_length": user_length,
        },
        "direction": {
            "blogger_correction_deg": blogger_correction,
            "user_correction_deg": user_correction,
            "relative_adjustment_deg": relative_direction,
            "personalized_direction_deg": personalized_direction,
        },
        "extension": {
            "blogger_adaptation_factor": blogger_factor,
            "user_adaptation_factor": user_factor,
            "relative_adaptation_factor": relative_factor_output,
            "personalized_extension_ratio": personalized_extension_output,
        },
        "start_position_ratio": start_position,
        "applied_rules": ["R01", "R02", "R03", "R04"],
    }
    _assert_strict_finite(result)
    return result


def personalize_reference_relative(
    blogger_profile: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    reference_action_geometry: Mapping[str, Any],
    manual_recipe: Mapping[str, Any],
    target_effect: str = "cat_eye",
    *,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Return relative A04 plus the existing absolute A02 action."""

    if target_effect != "cat_eye":
        raise ReferenceRelativePersonalizationError(
            "Reference-relative v0.1 only supports target_effect='cat_eye'."
        )
    standard_recipe = build_standard_recipe(manual_recipe, reference_action_geometry)
    absolute = personalize_reference_recipe(
        user_profile, standard_recipe, target_effect
    )
    a04 = calculate_reference_relative_a04(
        blogger_profile,
        user_profile,
        _reference_a04_parameters(standard_recipe),
        calibration=calibration,
    )
    result = {
        "mode": "reference_relative",
        "version": "0.1",
        "target_effect": target_effect,
        "A04": a04,
        "A02": {
            "mode": "absolute",
            "personalized_action": dict(_absolute_a02(absolute)),
        },
    }
    _assert_strict_finite(result)
    return result


def personalize_reference_with_mode(
    blogger_profile: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    reference_action_geometry: Mapping[str, Any],
    manual_recipe: Mapping[str, Any],
    target_effect: str = "cat_eye",
    *,
    mode: str = "absolute",
) -> dict[str, Any]:
    """Dispatch modes while keeping absolute as the backward-compatible default."""

    if mode not in MODES:
        raise ReferenceRelativePersonalizationError(
            f"mode must be one of {sorted(MODES)}."
        )
    if mode == "absolute":
        standard_recipe = build_standard_recipe(
            manual_recipe, reference_action_geometry
        )
        return personalize_reference_recipe(
            user_profile, standard_recipe, target_effect
        )
    return personalize_reference_relative(
        blogger_profile,
        user_profile,
        reference_action_geometry,
        manual_recipe,
        target_effect,
    )


def _absolute_a04_values(output: Mapping[str, Any]) -> tuple[float, float]:
    matches = [
        action for action in output["personalized_actions"]
        if action.get("action_id") == "A04"
    ]
    if len(matches) != 1:
        raise ReferenceRelativePersonalizationError("Expected one absolute A04 action.")
    parameters = matches[0]["personalized_parameters"]
    return (
        float(parameters["direction_angle_deg"]),
        float(parameters["personalized_extension_ratio"]),
    )


def generate_validation_outputs(
    blogger_profile: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    reference_action: Mapping[str, Any],
    manual_recipe: Mapping[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Generate the requested absolute/relative demo artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
    absolute = personalize_reference_with_mode(
        blogger_profile,
        user_profile,
        reference_action,
        manual_recipe,
        mode="absolute",
    )
    relative = personalize_reference_with_mode(
        blogger_profile,
        user_profile,
        reference_action,
        manual_recipe,
        mode="reference_relative",
    )
    identity = personalize_reference_relative(
        blogger_profile,
        blogger_profile,
        reference_action,
        manual_recipe,
    )
    absolute_direction, absolute_extension = _absolute_a04_values(absolute)
    relative_a04 = relative["A04"]
    reference_direction = relative_a04["reference"]["direction_deg"]
    reference_extension = relative_a04["reference"]["extension_ratio"]
    relative_direction = relative_a04["direction"]["personalized_direction_deg"]
    relative_extension = relative_a04["extension"]["personalized_extension_ratio"]

    save_json_output(output_dir / "absolute_personalized_action.json", absolute)
    save_json_output(
        output_dir / "reference_relative_personalized_action.json", relative
    )
    comparison_rows = [
        {
            "parameter": "direction_deg",
            "reference": reference_direction,
            "absolute": absolute_direction,
            "reference_relative": relative_direction,
            "difference": round(relative_direction - absolute_direction, 12),
        },
        {
            "parameter": "extension_ratio",
            "reference": reference_extension,
            "absolute": absolute_extension,
            "reference_relative": relative_extension,
            "difference": round(relative_extension - absolute_extension, 12),
        },
    ]
    with (output_dir / "absolute_vs_relative.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(comparison_rows[0]))
        writer.writeheader()
        writer.writerows(comparison_rows)

    explanation = {
        "direction": {
            "blogger_eye_tail": relative_a04["blogger_profile"]["eye_tail_angle"],
            "user_eye_tail": relative_a04["user_profile"]["eye_tail_angle"],
            "blogger_correction": relative_a04["direction"]["blogger_correction_deg"],
            "user_correction": relative_a04["direction"]["user_correction_deg"],
            "difference": relative_a04["direction"]["relative_adjustment_deg"],
            "reference_direction": reference_direction,
            "personalized_direction": relative_direction,
        },
        "extension": {
            "blogger_relative_eye_length": relative_a04["blogger_profile"]["relative_eye_length"],
            "user_relative_eye_length": relative_a04["user_profile"]["relative_eye_length"],
            "blogger_factor": relative_a04["extension"]["blogger_adaptation_factor"],
            "user_factor": relative_a04["extension"]["user_adaptation_factor"],
            "relative_factor": relative_a04["extension"]["relative_adaptation_factor"],
            "reference_extension_ratio": reference_extension,
            "personalized_extension_ratio": relative_extension,
        },
    }
    save_json_output(output_dir / "reference_relative_explanation.json", explanation)

    identity_a04 = identity["A04"]
    identity_validation = {
        "property": "identity_consistency",
        "passed": all(
            (
                identity_a04["direction"]["relative_adjustment_deg"] == 0.0,
                identity_a04["direction"]["personalized_direction_deg"]
                == identity_a04["reference"]["direction_deg"],
                identity_a04["extension"]["relative_adaptation_factor"] == 1.0,
                identity_a04["extension"]["personalized_extension_ratio"]
                == identity_a04["reference"]["extension_ratio"],
            )
        ),
        "direction_relative_adjustment_deg": identity_a04["direction"]["relative_adjustment_deg"],
        "reference_direction_deg": identity_a04["reference"]["direction_deg"],
        "personalized_direction_deg": identity_a04["direction"]["personalized_direction_deg"],
        "extension_relative_factor": identity_a04["extension"]["relative_adaptation_factor"],
        "reference_extension_ratio": identity_a04["reference"]["extension_ratio"],
        "personalized_extension_ratio": identity_a04["extension"]["personalized_extension_ratio"],
    }
    save_json_output(
        output_dir / "identity_consistency_validation.json", identity_validation
    )
    return {
        "absolute": absolute,
        "reference_relative": relative,
        "comparison": comparison_rows,
        "explanation": explanation,
        "identity_consistency": identity_validation,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blogger-profile", type=Path, default=DEFAULT_BLOGGER_PROFILE)
    parser.add_argument("--user-profile", type=Path, default=DEFAULT_USER_PROFILE)
    parser.add_argument("--reference-action", type=Path, default=DEFAULT_REFERENCE_ACTION)
    parser.add_argument("--manual-recipe", type=Path, default=DEFAULT_RECIPE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()
    result = generate_validation_outputs(
        load_json_object(args.blogger_profile),
        load_json_object(args.user_profile),
        load_json_object(args.reference_action),
        load_json_object(args.manual_recipe),
        args.output_dir,
    )
    print(json.dumps(result["explanation"], ensure_ascii=False, allow_nan=False))
    print(json.dumps(result["identity_consistency"], ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
