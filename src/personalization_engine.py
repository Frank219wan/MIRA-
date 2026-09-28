"""Execute deterministic Personalization Engine v0 makeup rules."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

if __package__:
    from .makeup_rules import (
        DEFAULT_RULE_CALIBRATION,
        MakeupRuleError,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
        apply_lower_lid_intensity,
        apply_lower_lid_range,
    )
else:
    from makeup_rules import (  # type: ignore
        DEFAULT_RULE_CALIBRATION,
        MakeupRuleError,
        RuleCalibration,
        apply_eyeliner_direction,
        apply_eyeliner_extension,
        apply_lower_lid_intensity,
        apply_lower_lid_range,
    )


SUPPORTED_FACE_PROFILE_VERSION = "0.3"
SUPPORTED_TARGET_EFFECT = "cat_eye"


class PersonalizationEngineError(ValueError):
    """Raised when an input cannot produce a valid personalized action."""


def _required_mapping(data: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = data.get(key)
    if not isinstance(value, Mapping):
        raise PersonalizationEngineError(f"{key} must be a JSON object.")
    return value


def _profile_number(profile: Mapping[str, Any], path: tuple[str, ...]) -> float:
    value: Any = profile
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            raise PersonalizationEngineError(
                "Face Profile is missing required field: " + ".".join(path)
            )
        value = value[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PersonalizationEngineError(
            "Face Profile field must be numeric: " + ".".join(path)
        )
    number = float(value)
    if not math.isfinite(number):
        raise PersonalizationEngineError(
            "Face Profile field must be finite: " + ".".join(path)
        )
    return number


def _parameter_number(parameters: Mapping[str, Any], name: str) -> float:
    if name not in parameters:
        raise PersonalizationEngineError(
            f"Standard action is missing parameter: {name}"
        )
    value = parameters[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PersonalizationEngineError(
            f"Standard action parameter must be numeric: {name}"
        )
    number = float(value)
    if not math.isfinite(number):
        raise PersonalizationEngineError(
            f"Standard action parameter must be finite: {name}"
        )
    return number


def _assert_finite_json_numbers(value: Any, path: str = "output") -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            _assert_finite_json_numbers(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _assert_finite_json_numbers(nested, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise PersonalizationEngineError(
            f"Personalization output contains NaN or infinity: {path}"
        )


def _validate_common_input(
    face_profile: Mapping[str, Any], target_effect: str
) -> None:
    if face_profile.get("version") != SUPPORTED_FACE_PROFILE_VERSION:
        raise PersonalizationEngineError(
            "Personalization Engine v0 requires Face Profile v0.3."
        )
    if target_effect != SUPPORTED_TARGET_EFFECT:
        raise PersonalizationEngineError(
            f"Unsupported target_effect: {target_effect!r}; expected 'cat_eye'."
        )


def _rule_ids(adjustments: Sequence[Mapping[str, Any]]) -> list[str]:
    result: list[str] = []
    for adjustment in adjustments:
        for rule_id in adjustment["rule_ids"]:
            if rule_id not in result:
                result.append(rule_id)
    return result


def personalize_action(
    face_profile: Mapping[str, Any],
    standard_makeup_action: Mapping[str, Any],
    target_effect: str,
    *,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Personalize one A04 or A02 action while preserving its parameters."""

    _validate_common_input(face_profile, target_effect)
    action_id = standard_makeup_action.get("action_id")
    if not isinstance(action_id, str) or not action_id:
        raise PersonalizationEngineError(
            "standard_makeup_action.action_id must be a non-empty string."
        )
    parameters = _required_mapping(standard_makeup_action, "parameters")
    original_parameters = copy.deepcopy(dict(parameters))
    personalized_parameters = copy.deepcopy(dict(parameters))
    adjustments: list[dict[str, Any]] = []

    try:
        if action_id == "A04":
            tail_angle = _profile_number(
                face_profile,
                ("eye_geometry", "eye_tail_angle", "mean"),
            )
            relative_eye_length = _profile_number(
                face_profile,
                ("eye_geometry", "relative_eye_length", "mean"),
            )
            direction = apply_eyeliner_direction(
                tail_angle,
                _parameter_number(parameters, "direction_angle_deg"),
                calibration,
            )
            extension = apply_eyeliner_extension(
                relative_eye_length,
                _parameter_number(parameters, "extension_factor"),
                calibration,
            )
            adjustments.extend((direction, extension))
        elif action_id == "A02":
            lower_lid_space = _profile_number(
                face_profile,
                ("eye_geometry", "lower_lid_space_ratio", "mean"),
            )
            range_adjustment = apply_lower_lid_range(
                lower_lid_space,
                _parameter_number(parameters, "range_factor"),
                calibration,
            )
            intensity_adjustment = apply_lower_lid_intensity(
                lower_lid_space,
                _parameter_number(parameters, "intensity_factor"),
                calibration,
            )
            adjustments.extend((range_adjustment, intensity_adjustment))
        else:
            raise PersonalizationEngineError(
                f"Personalization Engine v0 supports A04 and A02; received {action_id!r}."
            )
    except MakeupRuleError as exc:
        raise PersonalizationEngineError(str(exc)) from exc

    for adjustment in adjustments:
        personalized_parameters[adjustment["parameter"]] = adjustment[
            "personalized_value"
        ]

    output = {
        "action_id": action_id,
        "original_parameters": original_parameters,
        "personalized_parameters": personalized_parameters,
        "applied_rules": _rule_ids(adjustments),
        "adjustments": adjustments,
    }
    _assert_finite_json_numbers(output)
    return output


def personalize_request(
    request: Mapping[str, Any],
    *,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Execute the documented single-action request schema."""

    face_profile = _required_mapping(request, "face_profile")
    action = _required_mapping(request, "standard_makeup_action")
    target_effect = request.get("target_effect")
    if not isinstance(target_effect, str):
        raise PersonalizationEngineError("target_effect must be a string.")
    return personalize_action(
        face_profile,
        action,
        target_effect,
        calibration=calibration,
    )


def personalize_recipe(
    face_profile: Mapping[str, Any],
    standard_recipe: Mapping[str, Any],
    target_effect: str,
    *,
    calibration: RuleCalibration = DEFAULT_RULE_CALIBRATION,
) -> dict[str, Any]:
    """Apply the single-action engine to every action in one standard recipe."""

    _validate_common_input(face_profile, target_effect)
    recipe_id = standard_recipe.get("recipe_id")
    if not isinstance(recipe_id, str) or not recipe_id:
        raise PersonalizationEngineError(
            "standard_recipe.recipe_id must be a non-empty string."
        )
    actions = standard_recipe.get("actions")
    if (
        not isinstance(actions, Sequence)
        or isinstance(actions, (str, bytes))
        or not actions
    ):
        raise PersonalizationEngineError(
            "standard_recipe.actions must be a non-empty array."
        )
    personalized_actions = []
    for action in actions:
        if not isinstance(action, Mapping):
            raise PersonalizationEngineError(
                "Every standard recipe action must be a JSON object."
            )
        personalized_actions.append(
            personalize_action(
                face_profile,
                action,
                target_effect,
                calibration=calibration,
            )
        )
    output = {
        "recipe_id": recipe_id,
        "target_effect": target_effect,
        "personalized_actions": personalized_actions,
    }
    _assert_finite_json_numbers(output)
    return output


def load_json_object(path: Path | str) -> dict[str, Any]:
    input_path = Path(path)
    if not input_path.is_file():
        raise PersonalizationEngineError(f"Input JSON does not exist: {input_path}")
    try:
        with input_path.open(encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise PersonalizationEngineError(
            f"Could not read input JSON {input_path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise PersonalizationEngineError("Input JSON must contain an object.")
    return value


def save_json_output(path: Path | str, output: Mapping[str, Any]) -> None:
    _assert_finite_json_numbers(output)
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(
                output,
                handle,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            handle.write("\n")
    except (OSError, TypeError, ValueError) as exc:
        raise PersonalizationEngineError(
            f"Could not write personalization JSON {output_path}: {exc}"
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Personalization Engine v0 for one makeup action."
    )
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        request = load_json_object(args.input)
        output = personalize_request(request)
        save_json_output(args.output, output)
    except PersonalizationEngineError as exc:
        print(f"Personalization failed: {exc}", file=sys.stderr)
        return 1
    print(f"Personalized action: {args.output.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
