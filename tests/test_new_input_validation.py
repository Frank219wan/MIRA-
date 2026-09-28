import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.new_input_validation import (
    active_direction,
    analyze_new_inputs,
    calculate_feature_ranges,
    discover_new_images,
)


def _profile(value: float) -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": value},
            "relative_eye_length": {"mean": 0.20 + value / 1000},
            "brow_eye_ratio": {"mean": 0.60 + value / 100},
            "lower_lid_space_ratio": {"mean": 0.14 + value / 1000},
            "inner_corner_angle": {"mean_deg": 60.0 + value},
        },
    }


class NewInputValidationTests(unittest.TestCase):
    def test_discovers_new_prefix_and_supported_suffixes_case_insensitively(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            expected = [
                root / "new_01.JPG",
                root / "NEW_02.jpg",
                root / "new_03.png",
            ]
            for path in expected:
                path.touch()
            (root / "face_01.jpg").touch()
            (root / "new_04.gif").touch()

            self.assertEqual(discover_new_images(root), expected)

    def test_active_direction_reports_parameter_change_only(self):
        self.assertEqual(active_direction(1.0, 1.1), "increase")
        self.assertEqual(active_direction(1.0, 0.9), "decrease")
        self.assertEqual(active_direction(1.0, 1.0), "unchanged")

    def test_feature_ranges_are_min_max_and_range(self):
        records = [
            {
                "face_detected": True,
                "features": {
                    "eye_tail_angle.mean": value,
                    "relative_eye_length.mean": value,
                    "brow_eye_ratio.mean": value,
                    "lower_lid_space_ratio.mean": value,
                    "inner_corner_angle.mean_deg": value,
                },
            }
            for value in (1.0, 4.0, 2.0)
        ]

        ranges = calculate_feature_ranges(records)

        self.assertEqual(ranges["eye_tail_angle.mean"]["min"], 1.0)
        self.assertEqual(ranges["eye_tail_angle.mean"]["max"], 4.0)
        self.assertEqual(ranges["eye_tail_angle.mean"]["range"], 3.0)

    def test_analysis_reuses_pipeline_and_engine_and_writes_one_row_per_person(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            images = [root / "new_a.jpg", root / "new_b.png"]
            for image in images:
                image.touch()
            recipe_path = root / "recipe.json"
            recipe_path.write_text(
                json.dumps(
                    {
                        "recipe_id": "cat_eye_standard_v0",
                        "target_effect": "cat_eye",
                        "actions": [
                            {
                                "action_id": "A04",
                                "parameters": {
                                    "direction_angle_deg": 10.0,
                                    "extension_factor": 1.0,
                                },
                            },
                            {
                                "action_id": "A02",
                                "parameters": {
                                    "range_factor": 1.0,
                                    "intensity_factor": 1.0,
                                },
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            def fake_process(**kwargs):
                value = 2.0 if kwargs["image_path"].name == "new_a.jpg" else 8.0
                kwargs["profile_output_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["profile_output_path"].write_text(
                    json.dumps(_profile(value)), encoding="utf-8"
                )
                return {
                    "face_detected": True,
                    "pose_normalization": {
                        "roll_angle_deg": 1.0,
                        "applied": True,
                    },
                }

            with patch(
                "src.new_input_validation.process_eye_geometry",
                side_effect=fake_process,
            ) as process_mock:
                report = analyze_new_inputs(
                    images,
                    model_path=root / "model.task",
                    recipe_path=recipe_path,
                    output_root=root / "output",
                )

            self.assertEqual(process_mock.call_count, 2)
            self.assertEqual(report["input"]["face_detection_success_count"], 2)
            self.assertEqual(report["input"]["personalization_success_count"], 2)
            self.assertNotEqual(
                report["people"][0]["personalization"]["direction_angle_deg"],
                report["people"][1]["personalization"]["direction_angle_deg"],
            )
            self.assertEqual(
                report["people"][0]["personalization"]["applied_rule_groups"],
                ["R01/R02", "R03/R04", "R05", "R06"],
            )

            report_path = root / "output" / "new_input_validation.json"
            serialized = report_path.read_text(encoding="utf-8")
            self.assertNotIn("NaN", serialized)
            self.assertNotIn("Infinity", serialized)
            json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )

            with (
                root / "output" / "new_input_face_comparison.csv"
            ).open(encoding="utf-8", newline="") as handle:
                face_rows = list(csv.DictReader(handle))
            with (
                root / "output" / "new_input_personalization_comparison.csv"
            ).open(encoding="utf-8", newline="") as handle:
                personalization_rows = list(csv.DictReader(handle))
            self.assertEqual(len(face_rows), 2)
            self.assertEqual(len(personalization_rows), 2)
            self.assertEqual(
                personalization_rows[0]["direction_angle_active_direction"],
                "increase",
            )
            self.assertEqual(
                len(
                    list(
                        (root / "output" / "individual_profiles").glob(
                            "*_face_profile.json"
                        )
                    )
                ),
                2,
            )
            self.assertEqual(
                len(
                    list(
                        (root / "output" / "individual_personalization").glob(
                            "*_personalization.json"
                        )
                    )
                ),
                2,
            )


if __name__ == "__main__":
    unittest.main()
