import copy
import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.contracts.cv_actions import (
    DecodedActionMappingConfig,
    PersonalizedActionWrapper,
)
from src.contracts.cv_adaptation import validate_cv_face_profile
from src.contracts.makeup import MakeupActionUnit, StandardRecipe
from src.contracts.my_tutorial import MyTutorialResponse
from src.personalization_engine import personalize_action
from src.services.decoded_action_adapter import (
    DecodedActionMappingError,
    adapt_decoded_action,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class WeekTwoContractTests(unittest.TestCase):
    def test_face_profile_v03_is_accepted_without_reshaping(self):
        profile = load_fixture("face_profile_v0_3.json")
        self.assertIs(validate_cv_face_profile(profile), profile)

    def test_legacy_face_profile_v01_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported Face Profile version"):
            validate_cv_face_profile(load_fixture("face_profile_v0_1.json"))

    def test_incomplete_v03_is_rejected(self):
        profile = load_fixture("face_profile_v0_3.json")
        del profile["eye_geometry"]["relative_eye_length"]
        with self.assertRaisesRegex(ValueError, "relative_eye_length"):
            validate_cv_face_profile(profile)

    def test_standard_recipe_v1_shape_remains_frozen(self):
        recipe = StandardRecipe.model_validate(load_fixture("standard_recipe_v1.json"))
        self.assertEqual(recipe.schema_version, "1.0")
        self.assertEqual(
            set(MakeupActionUnit.model_fields),
            {
                "step_index",
                "area",
                "goal",
                "product_requirement",
                "tool",
                "motion",
                "intensity",
                "target_result",
                "time_range_seconds",
                "confidence",
            },
        )

    def test_adapter_preserves_source_step_and_mapping_provenance(self):
        action = MakeupActionUnit(
            step_index=3,
            area="upper lash line",
            goal="define",
            product_requirement="eyeliner",
            tool="liner brush",
            motion="short stroke",
            intensity="light",
            target_result="clean lash-line definition",
        )
        config = DecodedActionMappingConfig.model_validate(
            {
                "mapping_version": "1.0",
                "mappings": [
                    {
                        "mapping_id": "approved-eyeliner-a04-v1",
                        "action_id": "A04",
                        "source": {
                            "area": "upper lash line",
                            "goal": "define",
                            "product_requirement": "eyeliner",
                        },
                        "parameters": {
                            "direction_angle_deg": 10.0,
                            "extension_factor": 1.0,
                        },
                        "required_product_inputs": [],
                        "status": "approved",
                    }
                ],
            }
        )
        result = adapt_decoded_action(action, config)
        self.assertEqual(result.source_step_index, 3)
        self.assertEqual(result.mapping_id, "approved-eyeliner-a04-v1")
        self.assertEqual(result.mapping_version, "1.0")
        self.assertEqual(result.standard_makeup_action.action_id, "A04")

    def test_repository_mapping_placeholder_cannot_execute(self):
        config = DecodedActionMappingConfig.model_validate(
            load_fixture("decoded_cv_action_mapping_v1.json")
        )
        action = MakeupActionUnit(
            step_index=5,
            area="upper lash line",
            goal="define",
            product_requirement="eyeliner",
            tool="liner brush",
            motion="short stroke",
            intensity="light",
            target_result="clean lash-line definition",
        )
        with self.assertRaisesRegex(DecodedActionMappingError, "requires product input"):
            adapt_decoded_action(action, config)

    def test_personalized_wrapper_preserves_cv_numeric_output(self):
        cv_action = {
            "action_id": "A04",
            "parameters": {"direction_angle_deg": 10.0, "extension_factor": 1.0},
        }
        cv_output = personalize_action(
            {
                "version": "0.3",
                "eye_geometry": {
                    "eye_tail_angle": {"mean": 8.0},
                    "relative_eye_length": {"mean": 0.20},
                    "lower_lid_space_ratio": {"mean": 0.15},
                },
            },
            cv_action,
            "cat_eye",
        )
        before = copy.deepcopy(cv_output)
        wrapper = PersonalizedActionWrapper.model_validate(
            {
                "recipe_id": "recipe-1",
                "step_index": 5,
                "face_profile_version": "0.3",
                "personalized_action": cv_output,
                "provenance": {
                    "mapping_version": "1.0",
                    "mapping_id": "approved-eyeliner-a04-v1",
                    "source_step_index": 5,
                    "standard_makeup_action": cv_action,
                },
            }
        )
        self.assertEqual(wrapper.personalized_action.model_dump(), before)
        self.assertEqual(cv_output, before)

    def test_my_tutorial_v02_exposes_wording_and_no_ar_contract(self):
        properties = MyTutorialResponse.model_json_schema()["$defs"]["MyTutorialStep"][
            "properties"
        ]
        self.assertTrue(
            {"action_id", "where", "how", "why", "stop_when"}.issubset(properties)
        )
        self.assertNotIn("ar_guidance", properties)
        self.assertNotIn("ar_guidance_status", properties)


if __name__ == "__main__":
    unittest.main()
