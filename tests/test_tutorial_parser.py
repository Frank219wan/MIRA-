import unittest
from pathlib import Path

from src.services.tutorial_parser import (
    MockTutorialVisionProvider,
    TutorialMediaInput,
    TutorialModelOutputError,
    TutorialParser,
)


class TutorialParserTests(unittest.TestCase):
    def setUp(self):
        self.media = TutorialMediaInput(
            media_path=Path("data/input/main_eye_tutorial.mp4"),
            media_kind="video",
            recipe_id="recipe-main-eye-demo-v1",
            title="Main eye tutorial demo",
        )

    def test_mock_provider_parses_video_reference_to_five_step_recipe(self):
        recipe = TutorialParser(MockTutorialVisionProvider()).parse(self.media)
        self.assertEqual(recipe.source_media_path, "data/input/main_eye_tutorial.mp4")
        self.assertEqual(len(recipe.action_units), 5)
        self.assertEqual([unit.step_index for unit in recipe.action_units], [1, 2, 3, 4, 5])

    def test_invalid_model_output_raises_controlled_error(self):
        invalid_output = {"action_units": [{"step_index": 1}]}
        with self.assertRaisesRegex(TutorialModelOutputError, "failed StandardRecipe validation"):
            TutorialParser(MockTutorialVisionProvider(invalid_output)).parse(self.media)

    def test_parser_rejects_well_formed_recipe_with_non_demo_step_count(self):
        output = MockTutorialVisionProvider().output
        four_steps = {"action_units": output["action_units"][:4]}
        with self.assertRaisesRegex(TutorialModelOutputError, "exactly 5"):
            TutorialParser(MockTutorialVisionProvider(four_steps)).parse(self.media)

    def test_validation_failure_is_logged_and_observed_as_debug_metadata(self):
        observed_runs = []
        parser = TutorialParser(MockTutorialVisionProvider({"action_units": [{}]}))
        with self.assertLogs("mira", level="INFO") as logs:
            with self.assertRaises(TutorialModelOutputError):
                parser.parse(
                    self.media,
                    request_id="trace-parser-invalid-1",
                    run_observer=observed_runs.append,
                )
        self.assertEqual(len(observed_runs), 1)
        self.assertEqual(observed_runs[0].request_id, "trace-parser-invalid-1")
        self.assertIsNotNone(observed_runs[0].validation_error)
        self.assertTrue(any("schema_validation_failure" in line for line in logs.output))


if __name__ == "__main__":
    unittest.main()
