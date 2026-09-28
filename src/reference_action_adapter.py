"""Adapt local tutorial action geometry to the existing Cat Eye recipe contract."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__:
    from .personalization_engine import (
        PersonalizationEngineError,
        load_json_object,
        personalize_recipe,
        save_json_output,
    )
else:
    from personalization_engine import (  # type: ignore
        PersonalizationEngineError,
        load_json_object,
        personalize_recipe,
        save_json_output,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANUAL_RECIPE = PROJECT_ROOT / "examples" / "cat_eye_standard_recipe.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "reference_action"


class ReferenceActionAdapterError(ValueError):
    """Raised when a reference cannot be mapped to the A04 action baseline."""


def _finite(geometry: Mapping[str, Any], key: str) -> float:
    value = geometry.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ReferenceActionAdapterError(f"Reference geometry {key} must be numeric.")
    number = float(value)
    if not math.isfinite(number):
        raise ReferenceActionAdapterError(f"Reference geometry {key} must be finite.")
    return number


def adapt_a04_action(
    reference_geometry: Mapping[str, Any],
    manual_action: Mapping[str, Any],
) -> dict[str, Any]:
    """Replace A04's manual baseline while preserving its unrelated settings.

    The existing engine still consumes extension_factor as a multiplier. A
    reference-sourced action starts that multiplier at 1.0 and carries its
    measured geometric length in a separate reference_extension_ratio field.
    """

    if reference_geometry.get("version") != "0.1":
        raise ReferenceActionAdapterError("Expected ReferenceActionGeometry v0.1.")
    if reference_geometry.get("action_id") != "A04":
        raise ReferenceActionAdapterError("Reference action_id must be A04.")
    if reference_geometry.get("source_type") != "local_eye_tutorial":
        raise ReferenceActionAdapterError(
            "Reference source_type must be local_eye_tutorial."
        )
    quality = reference_geometry.get("quality")
    if (
        not isinstance(quality, Mapping)
        or quality.get("annotation_complete") is not True
        or quality.get("manual_annotation") is not True
        or quality.get("source_is_full_face") is not False
    ):
        raise ReferenceActionAdapterError(
            "Reference must be a complete manual local-eye annotation."
        )
    reference_id = reference_geometry.get("reference_id")
    if not isinstance(reference_id, str) or not reference_id:
        raise ReferenceActionAdapterError("reference_id must be non-empty.")
    if manual_action.get("action_id") != "A04":
        raise ReferenceActionAdapterError("Manual fallback action must be A04.")
    manual_parameters = manual_action.get("parameters")
    geometry = reference_geometry.get("geometry")
    if not isinstance(manual_parameters, Mapping) or not isinstance(geometry, Mapping):
        raise ReferenceActionAdapterError("Missing manual parameters or reference geometry.")

    direction = _finite(geometry, "direction_relative_to_eye_axis_deg")
    reference_extension_ratio = _finite(geometry, "eyeliner_extension_ratio")
    if reference_extension_ratio <= 0:
        raise ReferenceActionAdapterError("eyeliner_extension_ratio must be positive.")
    start_value = geometry.get("start_position_ratio")
    start = None if start_value is None else _finite(geometry, "start_position_ratio")

    action = copy.deepcopy(dict(manual_action))
    parameters = copy.deepcopy(dict(manual_parameters))
    parameters["direction_angle_deg"] = direction
    parameters["extension_factor"] = 1.0
    parameters["reference_extension_ratio"] = reference_extension_ratio
    if start is not None:
        parameters["start_position_ratio"] = start
    action["parameters"] = parameters
    action["reference_parameters"] = {
        "direction_relative_to_eye_axis_deg": direction,
        "reference_extension_ratio": reference_extension_ratio,
        "start_position_ratio": start,
    }
    action["source"] = {
        "type": "reference_tutorial_annotation",
        "reference_id": reference_id,
    }
    action["parameter_semantics"] = {
        "direction_angle_deg": "direction_relative_to_eye_axis_deg",
        "extension_factor": "adaptation_factor",
        "reference_extension_ratio": "normalized_geometric_length",
    }
    return action


def build_standard_recipe(
    manual_recipe: Mapping[str, Any],
    reference_geometry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return manual recipe unchanged as fallback, or replace its A04 action."""

    if manual_recipe.get("target_effect") != "cat_eye":
        raise ReferenceActionAdapterError("Manual recipe target_effect must be cat_eye.")
    actions = manual_recipe.get("actions")
    if not isinstance(actions, list):
        raise ReferenceActionAdapterError("Manual recipe actions must be an array.")
    recipe = copy.deepcopy(dict(manual_recipe))
    if reference_geometry is None:
        return recipe
    matches = [index for index, action in enumerate(actions) if isinstance(action, Mapping) and action.get("action_id") == "A04"]
    if len(matches) != 1:
        raise ReferenceActionAdapterError("Manual recipe must contain exactly one A04 action.")
    recipe["actions"][matches[0]] = adapt_a04_action(
        reference_geometry, actions[matches[0]]
    )
    return recipe


def personalize_reference_recipe(
    face_profile: Mapping[str, Any],
    standard_recipe: Mapping[str, Any],
    target_effect: str = "cat_eye",
) -> dict[str, Any]:
    """Personalize a recipe and resolve reference length × R03/R04 multiplier.

    Manual actions retain the existing Personalization Engine output unchanged.
    """

    result = personalize_recipe(face_profile, standard_recipe, target_effect)
    for source_action, personalized_action in zip(
        standard_recipe["actions"], result["personalized_actions"]
    ):
        if not isinstance(source_action, Mapping):
            continue  # personalize_recipe already validates every action.
        source = source_action.get("source")
        if (
            source_action.get("action_id") != "A04"
            or not isinstance(source, Mapping)
            or source.get("type") != "reference_tutorial_annotation"
        ):
            continue
        reference_parameters = source_action.get("reference_parameters")
        if not isinstance(reference_parameters, Mapping):
            raise ReferenceActionAdapterError("Reference action is missing reference_parameters.")
        reference_extension_ratio = _finite(
            reference_parameters, "reference_extension_ratio"
        )
        if reference_extension_ratio <= 0:
            raise ReferenceActionAdapterError("reference_extension_ratio must be positive.")
        adjustments = personalized_action["adjustments"]
        extension_adjustments = [
            adjustment for adjustment in adjustments
            if adjustment.get("parameter") == "extension_factor"
            and adjustment.get("rule_ids") == ["R03", "R04"]
        ]
        if len(extension_adjustments) != 1:
            raise ReferenceActionAdapterError("Expected one R03/R04 extension adjustment.")
        adaptation_factor = _finite(
            extension_adjustments[0], "adjustment_value"
        )
        personalized_extension_ratio = (
            reference_extension_ratio * adaptation_factor
        )
        if not math.isfinite(personalized_extension_ratio):
            raise ReferenceActionAdapterError("Personalized extension ratio is not finite.")
        parameters = personalized_action["personalized_parameters"]
        parameters["reference_extension_ratio"] = reference_extension_ratio
        parameters["extension_adaptation_factor"] = adaptation_factor
        parameters["personalized_extension_ratio"] = personalized_extension_ratio
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reference", type=Path,
        help="ReferenceActionGeometry JSON; omit to retain the manual recipe.",
    )
    parser.add_argument("--manual-recipe", type=Path, default=DEFAULT_MANUAL_RECIPE)
    parser.add_argument(
        "--output-recipe", type=Path,
        default=DEFAULT_OUTPUT_DIR / "cat_eye_reference_recipe.json",
    )
    parser.add_argument(
        "--user-profile", type=Path,
        help="Optional user Face Profile v0.3 for an end-to-end personalization run.",
    )
    parser.add_argument(
        "--personalized-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / "cat_eye_personalized_action.json",
    )
    args = parser.parse_args()
    try:
        manual = load_json_object(args.manual_recipe)
        reference = load_json_object(args.reference) if args.reference else None
        recipe = build_standard_recipe(manual, reference)
        if args.user_profile:
            user_profile = load_json_object(args.user_profile)
            personalized = personalize_reference_recipe(user_profile, recipe, "cat_eye")
            save_json_output(args.personalized_output, personalized)
        save_json_output(args.output_recipe, recipe)
    except (PersonalizationEngineError, ReferenceActionAdapterError, OSError, ValueError) as exc:
        print(f"Reference adapter failed: {exc}", file=sys.stderr)
        return 1
    print(f"Standard recipe: {args.output_recipe}")
    if args.user_profile:
        print(f"Personalized action: {args.personalized_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
