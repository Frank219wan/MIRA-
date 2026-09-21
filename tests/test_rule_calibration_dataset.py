import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.face_landmarker import FaceLandmarkerError
from src.rule_calibration_dataset import (
    build_dataset,
    calculate_coverage,
    calculate_statistics,
    discover_face_images,
)


def _row(person_id: str, tail: float, length: float, lid: float) -> dict:
    return {
        "person_id": person_id,
        "detection_success": True,
        "eye_tail_angle.mean": tail,
        "relative_eye_length.mean": length,
        "lower_lid_space_ratio.mean": lid,
    }


def _profile(tail: float) -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": tail},
            "relative_eye_length": {"mean": 0.2},
            "lower_lid_space_ratio": {"mean": 0.15},
            "inner_corner_angle": {"mean_deg": 65.0},
            "brow_eye_ratio": {"mean": 0.65},
        },
        "confidence": {"pose_normalized": True},
    }


class RuleCalibrationDatasetTests(unittest.TestCase):
    def test_discovery_handles_real_extension_and_missing_number(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "face_01.JPG").touch()
            (root / "face_03.png").touch()
            (root / "face_12.jpg").touch()

            images = discover_face_images(root)

        self.assertEqual(len(images), 11)
        self.assertEqual(images[0][1].name, "face_01.JPG")
        self.assertIsNone(images[1][1])
        self.assertEqual(images[2][1].name, "face_03.png")

    def test_statistics_use_successes_only_and_linear_quartiles(self):
        rows = [
            _row(f"face_{index:02d}", float(value), 0.2, 0.15)
            for index, value in enumerate((1, 2, 3, 4, 5), start=1)
        ]
        rows.append({"person_id": "face_06", "detection_success": False})

        stats = calculate_statistics(rows)[0]

        self.assertEqual(stats["n"], 5)
        self.assertEqual(stats["median"], 3)
        self.assertEqual(stats["percentile_25"], 2)
        self.assertEqual(stats["percentile_75"], 4)
        self.assertEqual(stats["range"], 4)

    def test_coverage_separates_near_from_strict_clamp(self):
        rows = [
            _row("face_01", -1.0, 0.17, 0.12),
            _row("face_02", 0.0, 0.20, 0.15),
            _row("face_03", 15.0, 0.23, 0.18),
            _row("face_04", 16.0, 0.24, 0.19),
        ]

        coverage = calculate_coverage(rows)
        tail = coverage[0]

        self.assertEqual(tail["near_low_people"], ["face_02"])
        self.assertEqual(tail["near_high_people"], ["face_03"])
        self.assertEqual(tail["clamp_people"], ["face_01", "face_04"])
        self.assertEqual(tail["clamp_count"], 2)
        self.assertFalse(tail["covers_sample_range"])
        self.assertEqual(coverage[2]["output_parameter"], "range_factor")
        self.assertEqual(coverage[3]["output_parameter"], "intensity_factor")

    def test_pipeline_failure_keeps_blank_values_and_excludes_statistics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            input_dir.mkdir()
            (input_dir / "face_01.jpg").touch()
            (input_dir / "face_02.JPG").touch()

            def fake_process(**kwargs):
                if kwargs["image_path"].name == "face_02.JPG":
                    raise FaceLandmarkerError("no face")
                kwargs["profile_output_path"].write_text(
                    json.dumps(_profile(5.0)), encoding="utf-8"
                )
                return {
                    "pose_normalization": {
                        "applied": True,
                        "roll_angle_deg": 1.25,
                    }
                }

            with patch(
                "src.rule_calibration_dataset.process_eye_geometry",
                side_effect=fake_process,
            ) as process_mock:
                report = build_dataset(input_dir, root / "output", root / "model.task")

            self.assertEqual(process_mock.call_count, 2)
            self.assertEqual(report["requested_count"], 11)
            self.assertEqual(report["present_image_count"], 2)
            self.assertEqual(report["success_count"], 1)
            self.assertEqual(report["failure_count"], 10)
            self.assertEqual(report["feature_statistics"][0]["n"], 1)
            self.assertIsNone(report["feature_statistics"][0]["std"])
            self.assertEqual(report["people"][0]["R01_R02_input"], 5.0)
            self.assertEqual(report["people"][0]["roll_angle_deg"], 1.25)
            self.assertEqual(report["people"][1]["failure_reason"], "no face")
            self.assertNotIn("eye_tail_angle.mean", report["people"][1])

            with (root / "output" / "01_face_profile_for_rules.csv").open(
                encoding="utf-8", newline=""
            ) as handle:
                csv_rows = list(csv.DictReader(handle))
            self.assertEqual(len(csv_rows), 11)
            self.assertEqual(csv_rows[1]["eye_tail_angle.mean"], "")
            self.assertEqual(csv_rows[1]["failure_reason"], "no face")

            serialized = (root / "output" / "rule_calibration_dataset.json").read_text(
                encoding="utf-8"
            )
            self.assertNotIn("NaN", serialized)
            self.assertNotIn("Infinity", serialized)


if __name__ == "__main__":
    unittest.main()
