import copy
import unittest

from src.contracts.cv_actions import PersonalizedActionWrapper
from src.contracts.makeup import MakeupActionUnit
from src.contracts.my_tutorial import FaceProfileReference
from src.personalization_engine import personalize_action
from src.services.tutorial_explanation import (
    TutorialExplanationError,
    TutorialExplanationService,
    build_explanation_facts,
)


def standard_action() -> MakeupActionUnit:
    return MakeupActionUnit(
        step_index=5,
        area="upper lash line",
        goal="define",
        product_requirement="eyeliner",
        tool="liner brush",
        motion="short stroke",
        intensity="light",
        target_result="clean lash-line definition",
    )


def wrapper(*, tail: float = 8.0, length: float = 0.20) -> PersonalizedActionWrapper:
    cv_standard = {
        "action_id": "A04",
        "parameters": {"direction_angle_deg": 10.0, "extension_factor": 1.0},
    }
    result = personalize_action(
        {
            "version": "0.3",
            "eye_geometry": {
                "eye_tail_angle": {"mean": tail},
                "relative_eye_length": {"mean": length},
                "lower_lid_space_ratio": {"mean": 0.15},
            },
        },
        cv_standard,
        "cat_eye",
    )
    return PersonalizedActionWrapper.model_validate(
        {
            "recipe_id": "cat_eye_standard_v0",
            "step_index": 5,
            "face_profile_version": "0.3",
            "personalized_action": result,
            "provenance": {
                "mapping_version": "1.0",
                "mapping_id": "test-approved-a04",
                "source_step_index": 5,
                "standard_makeup_action": cv_standard,
            },
        }
    )


class NumericOverwriteProvider:
    provider_name = "malicious-mock"
    model_name = "test-only"

    def generate(self, **_):
        return {
            "where": "upper lash line",
            "how": "change the angle to 999",
            "why": "provider text",
            "stop_when": "provider text",
        }


class TutorialExplanationTests(unittest.TestCase):
    def setUp(self):
        self.face = FaceProfileReference(profile_id="face-test-v03")

    def test_deterministic_delta_calculation(self):
        personalized = wrapper()
        facts = build_explanation_facts(personalized)
        for change in facts.changes:
            expected = round(change.personalized_value - change.reference_value, 12)
            self.assertEqual(change.delta, expected)

    def test_reference_relative_parameter_aliases_use_exact_cv_values(self):
        personalized = PersonalizedActionWrapper.model_validate(
            {
                "recipe_id": "reference-relative-example",
                "step_index": 5,
                "face_profile_version": "0.3",
                "personalized_action": {
                    "action_id": "A04",
                    "original_parameters": {
                        "direction_angle_deg": 5.78,
                        "reference_extension_ratio": 0.3449,
                    },
                    "personalized_parameters": {
                        "direction_angle_deg": 3.97,
                        "personalized_extension_ratio": 0.3818,
                    },
                    "applied_rules": ["R02", "R03"],
                    "adjustments": [
                        {
                            "rule_ids": ["R02"],
                            "feature_path": "eye_geometry.eye_tail_angle.mean",
                            "feature_value": 11.635,
                            "parameter": "direction_angle_deg",
                            "operation": "add",
                            "adjustment_value": -1.81,
                            "original_value": 5.78,
                            "personalized_value": 3.97,
                        },
                        {
                            "rule_ids": ["R03"],
                            "feature_path": "eye_geometry.relative_eye_length.mean",
                            "feature_value": 0.1898,
                            "parameter": "personalized_extension_ratio",
                            "operation": "multiply",
                            "adjustment_value": 1.1069875326,
                            "original_value": 0.3449,
                            "personalized_value": 0.3818,
                        },
                    ],
                },
                "provenance": {
                    "mapping_version": "1.0",
                    "mapping_id": "reference-relative-example",
                    "source_step_index": 5,
                    "standard_makeup_action": {
                        "action_id": "A04",
                        "parameters": {
                            "direction_angle_deg": 5.78,
                            "reference_extension_ratio": 0.3449,
                        },
                    },
                },
            }
        )
        facts = build_explanation_facts(personalized)
        by_parameter = {change.parameter: change for change in facts.changes}
        self.assertEqual(by_parameter["direction_angle_deg"].delta, -1.81)
        self.assertEqual(by_parameter["personalized_extension_ratio"].delta, 0.0369)
        self.assertEqual(facts.applied_rules, ["R02", "R03"])

    def test_a02_range_and_intensity_generate_actionable_fallback(self):
        cv_standard = {
            "action_id": "A02",
            "parameters": {"range_factor": 1.0, "intensity_factor": 1.0},
        }
        result = personalize_action(
            {
                "version": "0.3",
                "eye_geometry": {
                    "eye_tail_angle": {"mean": 8.0},
                    "relative_eye_length": {"mean": 0.20},
                    "lower_lid_space_ratio": {"mean": 0.12},
                },
            },
            cv_standard,
            "cat_eye",
        )
        personalized = PersonalizedActionWrapper.model_validate(
            {
                "recipe_id": "cat_eye_standard_v0",
                "step_index": 2,
                "face_profile_version": "0.3",
                "personalized_action": result,
                "provenance": {
                    "mapping_version": "1.0",
                    "mapping_id": "test-approved-a02",
                    "source_step_index": 2,
                    "standard_makeup_action": cv_standard,
                },
            }
        )
        action = standard_action().model_copy(
            update={
                "step_index": 2,
                "area": "lower lash line",
                "product_requirement": "eye shadow",
            }
        )
        step = TutorialExplanationService().generate_step(
            standard_action=action,
            personalized=personalized,
            face_profile=self.face,
        )
        self.assertIn("收窄覆盖范围", step.how)
        self.assertIn("减轻用量或显色", step.how)
        self.assertEqual(step.applied_rules, ["R05", "R06"])

    def test_template_preserves_cv_numbers_and_rules(self):
        personalized = wrapper()
        cv_before = copy.deepcopy(personalized.personalized_action.model_dump())
        step = TutorialExplanationService().generate_step(
            standard_action=standard_action(),
            personalized=personalized,
            face_profile=self.face,
        )
        self.assertEqual(step.reference_parameters, cv_before["original_parameters"])
        self.assertEqual(
            step.personalized_parameters, cv_before["personalized_parameters"]
        )
        self.assertEqual(step.applied_rules, cv_before["applied_rules"])
        self.assertEqual(personalized.personalized_action.model_dump(), cv_before)

    def test_fallback_generates_all_user_fields(self):
        step = TutorialExplanationService().generate_step(
            standard_action=standard_action(),
            personalized=wrapper(),
            face_profile=self.face,
        )
        self.assertTrue(step.where)
        self.assertTrue(step.how)
        self.assertTrue(step.why)
        self.assertTrue(step.stop_when)
        self.assertEqual(step.fallback_status, "template_fallback")
        self.assertTrue(step.provenance.fallback_used)

    def test_provider_cannot_overwrite_numeric_fields(self):
        personalized = wrapper()
        expected = copy.deepcopy(personalized.personalized_action.model_dump())
        step = TutorialExplanationService(NumericOverwriteProvider()).generate_step(
            standard_action=standard_action(),
            personalized=personalized,
            face_profile=self.face,
        )
        self.assertEqual(step.reference_parameters, expected["original_parameters"])
        self.assertEqual(
            step.personalized_parameters, expected["personalized_parameters"]
        )
        self.assertEqual(step.applied_rules, expected["applied_rules"])
        self.assertEqual(step.fallback_status, "template_fallback")

    def test_distinct_cv_outputs_produce_distinct_instructions(self):
        # Values mirror existing synthetic Face06/Face11 unit cases; they are not
        # used to generate committed user artifacts.
        face06 = wrapper(tail=11.635, length=0.1898)
        face11 = wrapper(tail=6.37, length=0.2047)
        service = TutorialExplanationService()
        first = service.generate_step(
            standard_action=standard_action(),
            personalized=face06,
            face_profile=FaceProfileReference(profile_id="synthetic-face06"),
        )
        second = service.generate_step(
            standard_action=standard_action(),
            personalized=face11,
            face_profile=FaceProfileReference(profile_id="synthetic-face11"),
        )
        self.assertNotEqual(first.personalized_parameters, second.personalized_parameters)
        self.assertNotEqual(first.how, second.how)

    def test_missing_required_cv_data_is_controlled(self):
        personalized = wrapper().model_copy(deep=True)
        personalized.personalized_action.original_parameters.clear()
        personalized.personalized_action.personalized_parameters.clear()
        with self.assertRaisesRegex(TutorialExplanationError, "no comparable numeric"):
            TutorialExplanationService().generate_step(
                standard_action=standard_action(),
                personalized=personalized,
                face_profile=self.face,
            )


if __name__ == "__main__":
    unittest.main()
