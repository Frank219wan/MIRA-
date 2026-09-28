import copy
import json
import unittest
from pathlib import Path

from src.reference_action_adapter import (
    ReferenceActionAdapterError,
    build_standard_recipe,
    personalize_reference_recipe,
)
from src.reference_action_geometry import build_reference_action_geometry


def manual_recipe() -> dict:
    return {
        "recipe_id": "cat_eye_standard_v0",
        "target_effect": "cat_eye",
        "actions": [
            {
                "action_id": "A04",
                "parameters": {
                    "direction_angle_deg": 10.0,
                    "extension_factor": 1.0,
                    "target_region": "outer_third",
                },
            },
            {
                "action_id": "A02",
                "parameters": {"range_factor": 1.0, "intensity_factor": 1.0},
            },
        ],
    }


def reference(include_start: bool = False) -> dict:
    points = {
        "eye_inner": {"x": 0, "y": 0},
        "eye_outer": {"x": 100, "y": 0},
        "eyeliner_tip": {"x": 120, "y": -20},
    }
    if include_start:
        points["eyeliner_start"] = {"x": 75, "y": 0}
    return build_reference_action_geometry(points)


def user_profile() -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": 5.0},
            "relative_eye_length": {"mean": 0.20},
            "lower_lid_space_ratio": {"mean": 0.15},
        },
    }


class ReferenceActionAdapterTests(unittest.TestCase):
    def test_repo_manual_recipe_supplies_string_region_fallback(self):
        path = Path(__file__).resolve().parents[1] / "examples" / "cat_eye_standard_recipe.json"
        manual = json.loads(path.read_text(encoding="utf-8"))

        a04 = build_standard_recipe(manual, reference())["actions"][0]

        self.assertEqual(a04["parameters"]["target_region"], "outer_third")
        self.assertNotIn("start_position_ratio", a04["parameters"])

    def test_no_reference_preserves_manual_recipe_without_mutation(self):
        manual = manual_recipe()
        before = copy.deepcopy(manual)

        result = build_standard_recipe(manual)

        self.assertEqual(result, before)
        self.assertIsNot(result, manual)
        result["actions"][0]["parameters"]["extension_factor"] = 99
        self.assertEqual(manual, before)

    def test_reference_replaces_only_a04_baseline_and_keeps_region_fallback(self):
        manual = manual_recipe()
        before = copy.deepcopy(manual)

        recipe = build_standard_recipe(manual, reference())
        a04, a02 = recipe["actions"]

        self.assertEqual(a04["parameters"]["direction_angle_deg"], 45.0)
        self.assertEqual(a04["parameters"]["extension_factor"], 1.0)
        self.assertAlmostEqual(a04["parameters"]["reference_extension_ratio"], 0.282843)
        self.assertAlmostEqual(
            a04["reference_parameters"]["reference_extension_ratio"], 0.282843
        )
        self.assertEqual(a04["parameter_semantics"]["extension_factor"], "adaptation_factor")
        self.assertEqual(a04["parameters"]["target_region"], "outer_third")
        self.assertNotIn("start_position_ratio", a04["parameters"])
        self.assertIsNone(a04["reference_parameters"]["start_position_ratio"])
        self.assertEqual(a02, manual["actions"][1])
        self.assertEqual(manual, before)

    def test_reference_start_position_is_preserved(self):
        a04 = build_standard_recipe(manual_recipe(), reference(True))["actions"][0]

        self.assertEqual(a04["parameters"]["start_position_ratio"], 0.75)
        self.assertEqual(a04["reference_parameters"]["start_position_ratio"], 0.75)

    def test_existing_personalization_engine_consumes_reference_recipe(self):
        recipe = build_standard_recipe(manual_recipe(), reference(True))

        result = personalize_reference_recipe(user_profile(), recipe, "cat_eye")
        a04, a02 = result["personalized_actions"]

        self.assertEqual(a04["original_parameters"]["direction_angle_deg"], 45.0)
        self.assertEqual(a04["original_parameters"]["extension_factor"], 1.0)
        self.assertAlmostEqual(
            a04["original_parameters"]["reference_extension_ratio"], 0.282843
        )
        self.assertGreater(
            a04["personalized_parameters"]["direction_angle_deg"], 45.0
        )
        self.assertEqual(a04["personalized_parameters"]["start_position_ratio"], 0.75)
        self.assertEqual(a04["applied_rules"], ["R01", "R02", "R03", "R04"])
        self.assertEqual(a02["applied_rules"], ["R05", "R06"])

    def test_reference_ratio_multiplies_adaptation_factor(self):
        recipe = build_standard_recipe(manual_recipe(), reference())

        a04 = personalize_reference_recipe(user_profile(), recipe)["personalized_actions"][0]
        parameters = a04["personalized_parameters"]
        r03_r04 = next(
            adjustment for adjustment in a04["adjustments"]
            if adjustment["rule_ids"] == ["R03", "R04"]
        )

        self.assertEqual(
            parameters["extension_adaptation_factor"], r03_r04["adjustment_value"]
        )
        self.assertEqual(
            parameters["personalized_extension_ratio"],
            parameters["reference_extension_ratio"]
            * parameters["extension_adaptation_factor"],
        )
        self.assertEqual(
            parameters["extension_factor"], parameters["extension_adaptation_factor"]
        )
        self.assertNotEqual(
            parameters["reference_extension_ratio"], parameters["extension_factor"]
        )

    def test_manual_recipe_personalization_fallback_stays_unchanged(self):
        manual = manual_recipe()
        manual["actions"][0]["parameters"]["extension_factor"] = 1.25
        recipe = build_standard_recipe(manual)

        a04 = personalize_reference_recipe(user_profile(), recipe)["personalized_actions"][0]

        self.assertEqual(a04["original_parameters"]["extension_factor"], 1.25)
        self.assertNotIn("reference_extension_ratio", a04["personalized_parameters"])
        self.assertNotIn("extension_adaptation_factor", a04["personalized_parameters"])
        self.assertNotIn("personalized_extension_ratio", a04["personalized_parameters"])
        r03_r04 = next(
            adjustment for adjustment in a04["adjustments"]
            if adjustment["rule_ids"] == ["R03", "R04"]
        )
        self.assertEqual(
            a04["personalized_parameters"]["extension_factor"],
            r03_r04["personalized_value"],
        )

    def test_personalized_reference_output_is_strict_json(self):
        recipe = build_standard_recipe(manual_recipe(), reference())
        result = personalize_reference_recipe(user_profile(), recipe)

        json.loads(
            json.dumps(result, allow_nan=False),
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )

    def test_incomplete_reference_is_rejected(self):
        geometry = reference()
        geometry["quality"]["annotation_complete"] = False

        with self.assertRaisesRegex(ReferenceActionAdapterError, "complete manual"):
            build_standard_recipe(manual_recipe(), geometry)


if __name__ == "__main__":
    unittest.main()
