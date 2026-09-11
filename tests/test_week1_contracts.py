import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.cv_adaptation import CVAdaptation
from src.contracts.makeup import MakeupActionUnit, StandardRecipe
from src.contracts.matching import MatchingResult


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def recipe_payload() -> dict:
    return json.loads((FIXTURES / "standard_recipe_v1.json").read_text())


class WeekOneContractTests(unittest.TestCase):
    def test_valid_makeup_action_unit(self):
        unit = MakeupActionUnit(**recipe_payload()["action_units"][0])
        self.assertEqual(unit.step_index, 1)
        self.assertEqual(unit.area, "upper eyelid")

    def test_missing_action_unit_field_is_rejected(self):
        payload = recipe_payload()["action_units"][0]
        del payload["motion"]
        with self.assertRaises(ValidationError):
            MakeupActionUnit(**payload)

    def test_standard_recipe_accepts_non_empty_variable_length_steps(self):
        recipe = StandardRecipe.model_validate(recipe_payload())
        self.assertEqual(len(recipe.action_units), 5)
        self.assertEqual([item.step_index for item in recipe.action_units], [1, 2, 3, 4, 5])

        variable_length_payload = recipe_payload()
        variable_length_payload["action_units"].pop()
        variable_length_recipe = StandardRecipe.model_validate(variable_length_payload)
        self.assertEqual(len(variable_length_recipe.action_units), 4)

    def test_standard_recipe_rejects_empty_steps(self):
        payload = recipe_payload()
        payload["action_units"] = []
        with self.assertRaises(ValidationError):
            StandardRecipe.model_validate(payload)

    def test_cv_adaptation_accepts_actual_cv_face_profile_shape(self):
        face_profile = json.loads((FIXTURES / "face_profile_v0_1.json").read_text())
        envelope = CVAdaptation(recipe_id="recipe-main-eye-demo-v1", face_profile=face_profile)
        self.assertEqual(envelope.face_profile, face_profile)

    def test_cv_adaptation_rejects_unsupported_face_profile_version(self):
        face_profile = json.loads((FIXTURES / "face_profile_v0_1.json").read_text())
        face_profile["version"] = "99.0"
        with self.assertRaisesRegex(ValidationError, "Unsupported Face Profile version"):
            CVAdaptation(recipe_id="recipe-main-eye-demo-v1", face_profile=face_profile)

    def test_non_cv_fixtures_validate_against_their_contracts(self):
        beauty_kit = json.loads((FIXTURES / "beauty_kit_v1.json").read_text())
        capability = json.loads((FIXTURES / "product_capability_v1.json").read_text())
        matching = json.loads((FIXTURES / "matching_result_v1.json").read_text())
        self.assertEqual(BeautyKit.model_validate(beauty_kit).kit_id, "kit-demo-v1")
        self.assertEqual(
            ProductCapability.model_validate(capability).capability_id,
            "capability-neutral-shadow",
        )
        self.assertEqual(
            MatchingResult.model_validate(matching).matching_id, "match-demo-v1"
        )


if __name__ == "__main__":
    unittest.main()
