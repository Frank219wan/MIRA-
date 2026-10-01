import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.contracts.my_tutorial import MyTutorialResponse
from src.services.reference_relative_personalization_adapter import (
    REFERENCE_RELATIVE_ADAPTER_VERSION,
    ReferenceRelativePersonalizationAdapter,
    ReferenceRelativePersonalizationAdapterError,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "main_demo"
REFERENCE = FIXTURES / "main_demo_reference.json"


class ReferenceRelativePersonalizationAdapterTests(unittest.TestCase):
    def adapter(self, face: str) -> ReferenceRelativePersonalizationAdapter:
        return ReferenceRelativePersonalizationAdapter(
            source_fixture_path=FIXTURES / f"{face}_personalization.json",
            reference_fixture_path=REFERENCE,
        )

    def test_face_06_a04_exact_conversion(self) -> None:
        wrapper = self.adapter("face_06").adapt(
            "A04", recipe_id="recipe-main-eye-demo-v1", step_index=5
        )
        action = wrapper.personalized_action
        self.assertEqual(
            action.original_parameters,
            {
                "reference_direction_deg": 5.781666,
                "reference_extension_ratio": 0.34493,
                "start_position_ratio": 0.985925,
            },
        )
        self.assertEqual(
            action.personalized_parameters,
            {
                "personalized_direction_deg": 3.971266,
                "personalized_extension_ratio": 0.38178899654,
                "start_position_ratio": 0.985925,
            },
        )
        self.assertEqual(action.applied_rules, ["R02", "R03"])
        self.assertEqual(
            [item.adjustment_value for item in action.adjustments],
            [-1.8104, 1.106859352738],
        )
        self.assertEqual(
            [item.feature_path for item in action.adjustments],
            ["eye_tail_angle.mean", "relative_eye_length.mean"],
        )
        self.assertEqual(wrapper.provenance.adapter_version, REFERENCE_RELATIVE_ADAPTER_VERSION)
        self.assertEqual(wrapper.provenance.face_profile_id, "face_06")
        self.assertEqual(wrapper.provenance.source_mode, "reference_relative")
        self.assertEqual(
            wrapper.provenance.source_field_paths[
                "adjustments.personalized_direction_deg"
            ],
            "source:$.A04.relative_direction_adjustment + $.feature_decisions[effect=A04.direction]",
        )

    def test_face_06_a02_exact_conversion(self) -> None:
        action = self.adapter("face_06").adapt(
            "A02", recipe_id="recipe-main-eye-demo-v1", step_index=6
        ).personalized_action
        self.assertEqual(
            action.original_parameters,
            {"reference_range_factor": 1.0, "reference_intensity_factor": 1.0},
        )
        self.assertEqual(
            action.personalized_parameters,
            {
                "personalized_range_factor": 1.156646442361,
                "personalized_intensity_factor": 1.102787187839,
            },
        )
        self.assertEqual(action.applied_rules, ["R06"])
        self.assertEqual(len(action.adjustments), 2)
        self.assertEqual(
            [item.adjustment_value for item in action.adjustments],
            [1.156646442361, 1.102787187839],
        )

    def test_face_11_a04_keeps_committed_reference_and_empty_rules(self) -> None:
        action = self.adapter("face_11").adapt(
            "A04", recipe_id="recipe-main-eye-demo-v1", step_index=5
        ).personalized_action
        self.assertEqual(action.applied_rules, [])
        self.assertEqual(action.adjustments, [])
        self.assertEqual(action.personalized_parameters["personalized_direction_deg"], 5.781666)
        self.assertEqual(
            action.personalized_parameters["personalized_extension_ratio"], 0.34493
        )

    def test_face_11_a02_does_not_apply_nonidentity_raw_values(self) -> None:
        source = json.loads(
            (FIXTURES / "face_11_personalization.json").read_text(encoding="utf-8")
        )
        self.assertNotEqual(source["A02"]["raw_relative_range_factor"], 1.0)
        action = self.adapter("face_11").adapt(
            "A02", recipe_id="recipe-main-eye-demo-v1", step_index=6
        ).personalized_action
        self.assertEqual(action.applied_rules, [])
        self.assertEqual(action.adjustments, [])
        self.assertEqual(
            action.personalized_parameters,
            {"personalized_range_factor": 1.0, "personalized_intensity_factor": 1.0},
        )

    def test_missing_unambiguous_adjustment_field_fails(self) -> None:
        payload = json.loads(
            (FIXTURES / "face_06_personalization.json").read_text(encoding="utf-8")
        )
        broken = copy.deepcopy(payload)
        del broken["A04"]["relative_direction_adjustment"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text(json.dumps(broken), encoding="utf-8")
            adapter = ReferenceRelativePersonalizationAdapter(
                source_fixture_path=path,
                reference_fixture_path=REFERENCE,
            )
            with self.assertRaisesRegex(
                ReferenceRelativePersonalizationAdapterError,
                "A04.relative_direction_adjustment",
            ):
                adapter.adapt("A04", recipe_id="recipe", step_index=1)

    def test_ambiguous_duplicate_feature_decision_fails(self) -> None:
        payload = json.loads(
            (FIXTURES / "face_06_personalization.json").read_text(encoding="utf-8")
        )
        payload["feature_decisions"].append(copy.deepcopy(payload["feature_decisions"][0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ambiguous.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(
                ReferenceRelativePersonalizationAdapterError,
                "triggered_rules must exactly match",
            ):
                adapter = ReferenceRelativePersonalizationAdapter(
                    source_fixture_path=path,
                    reference_fixture_path=REFERENCE,
                )
                adapter.adapt("A04", recipe_id="recipe", step_index=1)

    def test_adapter_does_not_call_or_recompute_cv_personalization(self) -> None:
        with patch(
            "src.personalization_engine.personalize_action",
            side_effect=AssertionError("CV personalization must not run"),
        ) as personalization:
            wrapper = self.adapter("face_06").adapt(
                "A04", recipe_id="recipe-main-eye-demo-v1", step_index=5
            )
        personalization.assert_not_called()
        self.assertEqual(
            wrapper.personalized_action.personalized_parameters[
                "personalized_extension_ratio"
            ],
            0.38178899654,
        )

    def test_generated_tutorials_validate_and_preserve_adapter_output(self) -> None:
        for face in ("face_06", "face_11"):
            payload = json.loads(
                (ROOT / "data" / "fixtures" / f"{face}_my_tutorial_v0_2.json").read_text(
                    encoding="utf-8"
                )
            )
            tutorial = MyTutorialResponse.model_validate(payload)
            self.assertEqual(tutorial.schema_version, "0.2")
            self.assertEqual(len(tutorial.steps), 1)
            expected = self.adapter(face).adapt(
                "A04", recipe_id="recipe-main-eye-demo-v1", step_index=5
            )
            self.assertEqual(
                tutorial.steps[0].cv_personalized_action.personalized_action,
                expected.personalized_action,
            )


if __name__ == "__main__":
    unittest.main()
