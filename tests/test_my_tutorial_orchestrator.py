import copy
import json
import unittest
from pathlib import Path

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.cv_actions import DecodedActionMappingConfig
from src.contracts.makeup import StandardRecipe
from src.contracts.my_tutorial import MyTutorialResponse
from src.personalization_engine import personalize_action
from src.services.decoded_action_adapter import adapt_decoded_action
from src.services.my_tutorial_orchestrator import MyTutorialOrchestrator


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def capabilities(name: str) -> list[ProductCapability]:
    return [
        ProductCapability.model_validate(item)
        for item in fixture(name)["capabilities"]
    ]


class MyTutorialOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.recipe = StandardRecipe.model_validate(fixture("standard_recipe_v1.json"))
        self.happy_kit = BeautyKit.model_validate(
            fixture("beauty_kit_orchestration_demo_v1.json")
        )
        self.happy_capabilities = capabilities(
            "product_capabilities_orchestration_demo_v1.json"
        )
        self.face_a = fixture("face_profile_v0_3.json")
        self.face_b = fixture("face_profile_synthetic_b_v0_3.json")
        self.orchestrator = MyTutorialOrchestrator()

    def generate(self, face_profile=None, kit=None, product_capabilities=None):
        return self.orchestrator.generate(
            recipe=self.recipe,
            beauty_kit=kit or self.happy_kit,
            face_profile=face_profile or self.face_a,
            face_profile_id="synthetic-integration-profile",
            capabilities=product_capabilities or self.happy_capabilities,
            tutorial_id="tutorial-orchestration-test",
            request_id="trace-orchestration-test",
        )

    def test_full_happy_path_and_unsupported_actions(self):
        response = self.generate()
        MyTutorialResponse.model_validate(response.model_dump(mode="json"))
        self.assertEqual(len(response.steps), 5)
        self.assertTrue(all(step.match_result.decision == "strong_match" for step in response.steps))
        self.assertTrue(all(step.where and step.how and step.why and step.stop_when for step in response.steps))
        self.assertEqual(response.steps[0].personalization_status, "not_applicable")
        self.assertEqual(response.steps[0].fallback_status, "standard_action_fallback")
        self.assertEqual(response.steps[4].personalization_status, "personalized")
        self.assertEqual(response.steps[4].action_id, "A04")
        for step in response.steps:
            self.assertEqual(step.provenance.source_recipe_id, self.recipe.recipe_id)
            self.assertEqual(step.provenance.source_step_index, step.step_index)
            self.assertEqual(step.provenance.face_profile_version, "0.3")
            self.assertEqual(step.provenance.mapping_version, "1.0")
            self.assertTrue(step.provenance.matching_id)
            self.assertEqual(step.provenance.applied_rules, step.applied_rules)

    def test_pending_mapping_is_unsupported_without_breaking_tutorial(self):
        production_mapping = DecodedActionMappingConfig.model_validate(
            fixture("decoded_cv_action_mapping_v1.json")
        )
        orchestrator = MyTutorialOrchestrator(mapping_config=production_mapping)
        response = orchestrator.generate(
            recipe=self.recipe,
            beauty_kit=self.happy_kit,
            face_profile=self.face_a,
            face_profile_id="synthetic-integration-profile",
            capabilities=self.happy_capabilities,
            tutorial_id="tutorial-pending-mapping-test",
        )
        step = response.steps[4]
        self.assertEqual(step.personalization_status, "unsupported")
        self.assertEqual(step.action_id, "A04")
        self.assertIsNone(step.cv_personalized_action)
        self.assertEqual(step.fallback_status, "standard_action_fallback")

    def test_complete_committed_demo_response_validates(self):
        payload = fixture("my_tutorial_response_synthetic_demo_v0_2.json")
        response = MyTutorialResponse.model_validate(payload)
        self.assertEqual(response.schema_version, "0.2")
        self.assertEqual(len(response.steps), 5)
        self.assertNotIn("ar_guidance", payload["steps"][0])

    def test_cv_numeric_output_is_preserved_exactly(self):
        source = self.recipe.action_units[4]
        adapted = adapt_decoded_action(source, self.orchestrator.mapping_config)
        expected = personalize_action(
            self.face_a, adapted.standard_makeup_action.model_dump(), "cat_eye"
        )
        step = self.generate().steps[4]
        self.assertEqual(step.reference_parameters, expected["original_parameters"])
        self.assertEqual(step.personalized_parameters, expected["personalized_parameters"])
        self.assertEqual(
            step.cv_personalized_action.personalized_action.model_dump(mode="json"),
            expected,
        )

    def test_matching_evidence_and_provenance_are_preserved(self):
        step = self.generate().steps[4]
        self.assertEqual(step.match_result.match_score, 100)
        self.assertTrue(step.match_result.provenance.score_components)
        self.assertEqual(step.provenance.matching_id.split("-")[0], "match")
        self.assertEqual(step.provenance.product_id, "demo-liner")
        self.assertEqual(step.provenance.mapping_version, "1.0")
        self.assertEqual(step.provenance.applied_rules, step.applied_rules)
        self.assertEqual(
            [item.model_dump() for item in step.provenance.cv_adjustments],
            [
                item.model_dump()
                for item in step.cv_personalized_action.personalized_action.adjustments
            ],
        )

    def test_missing_capability_low_match_and_functional_conflict_are_surfaced(self):
        kit = BeautyKit.model_validate(fixture("beauty_kit_v1.json"))
        caps = capabilities("product_capabilities_demo_v1.json")
        response = self.generate(kit=kit, product_capabilities=caps)
        decisions = {step.step_index: step.match_result.decision for step in response.steps}
        self.assertEqual(decisions[1], "missing_capability")
        self.assertEqual(decisions[3], "low_match")
        self.assertEqual(decisions[4], "functional_conflict")
        self.assertIn("缺少", response.steps[0].why)
        self.assertIn("低匹配", response.steps[2].why)
        self.assertIn("功能冲突", response.steps[3].why)

    def test_two_synthetic_profiles_produce_different_personalization(self):
        first = self.generate(self.face_a).steps[4]
        second = self.generate(self.face_b).steps[4]
        self.assertNotEqual(first.personalized_parameters, second.personalized_parameters)
        self.assertNotEqual(first.how, second.how)

    def test_inputs_are_not_mutated(self):
        recipe = copy.deepcopy(self.recipe.model_dump(mode="json"))
        kit = copy.deepcopy(self.happy_kit.model_dump(mode="json"))
        profile = copy.deepcopy(self.face_a)
        caps = copy.deepcopy(
            [item.model_dump(mode="json") for item in self.happy_capabilities]
        )
        self.generate()
        self.assertEqual(self.recipe.model_dump(mode="json"), recipe)
        self.assertEqual(self.happy_kit.model_dump(mode="json"), kit)
        self.assertEqual(self.face_a, profile)
        self.assertEqual(
            [item.model_dump(mode="json") for item in self.happy_capabilities], caps
        )


if __name__ == "__main__":
    unittest.main()
