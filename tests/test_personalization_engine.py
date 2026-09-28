import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from src.personalization_engine import (
    PersonalizationEngineError,
    personalize_action,
    personalize_recipe,
    personalize_request,
    save_json_output,
)


def face_profile(
    *,
    eye_tail_angle: float = 8.0,
    relative_eye_length: float = 0.20,
    lower_lid_space_ratio: float = 0.15,
) -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": eye_tail_angle},
            "relative_eye_length": {"mean": relative_eye_length},
            "lower_lid_space_ratio": {"mean": lower_lid_space_ratio},
        },
    }


def eyeliner_action() -> dict:
    return {
        "action_id": "A04",
        "parameters": {
            "direction_angle_deg": 10.0,
            "extension_factor": 1.0,
            "finish": "defined",
        },
    }


def lower_lid_action() -> dict:
    return {
        "action_id": "A02",
        "parameters": {
            "range_factor": 1.0,
            "intensity_factor": 1.0,
        },
    }


def all_numbers_are_finite(value) -> bool:
    if isinstance(value, dict):
        return all(all_numbers_are_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_numbers_are_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


class PersonalizationEngineTests(unittest.TestCase):
    def test_same_standard_action_changes_with_face_profile(self):
        first = personalize_action(
            face_profile(eye_tail_angle=2.0, relative_eye_length=0.18),
            eyeliner_action(),
            "cat_eye",
        )
        second = personalize_action(
            face_profile(eye_tail_angle=12.0, relative_eye_length=0.22),
            eyeliner_action(),
            "cat_eye",
        )

        self.assertNotEqual(
            first["personalized_parameters"],
            second["personalized_parameters"],
        )

    def test_required_output_schema_and_active_rules(self):
        eyeliner = personalize_action(
            face_profile(), eyeliner_action(), "cat_eye"
        )
        lower_lid = personalize_action(
            face_profile(), lower_lid_action(), "cat_eye"
        )

        self.assertEqual(
            set(eyeliner),
            {
                "action_id",
                "original_parameters",
                "personalized_parameters",
                "applied_rules",
                "adjustments",
            },
        )
        self.assertEqual(eyeliner["applied_rules"], ["R01", "R02", "R03", "R04"])
        self.assertEqual(lower_lid["applied_rules"], ["R05", "R06"])

    def test_original_parameters_and_input_are_not_modified(self):
        action = eyeliner_action()
        before = copy.deepcopy(action)

        result = personalize_action(face_profile(), action, "cat_eye")

        self.assertEqual(action, before)
        self.assertEqual(result["original_parameters"], before["parameters"])
        self.assertEqual(result["original_parameters"]["finish"], "defined")
        self.assertEqual(result["personalized_parameters"]["finish"], "defined")
        self.assertIsNot(result["original_parameters"], action["parameters"])

    def test_documented_single_action_request_schema(self):
        request = {
            "face_profile": face_profile(),
            "standard_makeup_action": eyeliner_action(),
            "target_effect": "cat_eye",
        }

        result = personalize_request(request)

        self.assertEqual(result["action_id"], "A04")
        self.assertEqual(result["original_parameters"]["extension_factor"], 1.0)

    def test_recipe_personalizes_a04_and_a02(self):
        recipe = {
            "recipe_id": "cat_eye_standard_v0",
            "actions": [eyeliner_action(), lower_lid_action()],
        }

        result = personalize_recipe(face_profile(), recipe, "cat_eye")

        self.assertEqual(result["recipe_id"], "cat_eye_standard_v0")
        self.assertEqual(
            [action["action_id"] for action in result["personalized_actions"]],
            ["A04", "A02"],
        )

    def test_output_is_strict_json_without_nan_or_infinity(self):
        result = personalize_recipe(
            face_profile(),
            {
                "recipe_id": "cat_eye_standard_v0",
                "actions": [eyeliner_action(), lower_lid_action()],
            },
            "cat_eye",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "personalized.json"
            save_json_output(path, result)
            serialized = path.read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )

        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)
        self.assertTrue(all_numbers_are_finite(parsed))

    def test_non_finite_profile_value_is_rejected(self):
        with self.assertRaisesRegex(PersonalizationEngineError, "finite"):
            personalize_action(
                face_profile(eye_tail_angle=float("nan")),
                eyeliner_action(),
                "cat_eye",
            )

    def test_requires_face_profile_v03_and_cat_eye(self):
        old_profile = face_profile()
        old_profile["version"] = "0.2"
        with self.assertRaisesRegex(PersonalizationEngineError, "v0.3"):
            personalize_action(old_profile, eyeliner_action(), "cat_eye")
        with self.assertRaisesRegex(PersonalizationEngineError, "target_effect"):
            personalize_action(face_profile(), eyeliner_action(), "natural")


if __name__ == "__main__":
    unittest.main()
