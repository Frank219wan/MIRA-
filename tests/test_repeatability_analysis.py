import csv
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.repeatability_analysis import (
    RepeatabilityAnalysisError,
    add_baseline_comparison,
    analyze_repeatability,
    build_repeatability_report,
    calculate_feature_statistics,
    discover_repeat_images,
    save_report_csv,
    save_report_json,
    validate_image_paths,
)


def _features(value: float) -> dict[str, float]:
    return {
        "eye_tail_angle.mean": value,
        "relative_eye_length.mean": value,
        "brow_eye_ratio.mean": value,
        "lower_lid_space_ratio.mean": value,
        "inner_corner_angle.mean_deg": value,
    }


def _profile(value: float) -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": value},
            "relative_eye_length": {"mean": value},
            "brow_eye_ratio": {"mean": value},
            "lower_lid_space_ratio": {"mean": value},
            "inner_corner_angle": {"mean_deg": value},
        },
    }


class RepeatabilityAnalysisTests(unittest.TestCase):
    def test_identical_values_have_zero_std_and_range(self):
        stats = calculate_feature_statistics([3.5] * 5)

        self.assertEqual(stats["n"], 5)
        self.assertEqual(stats["std"], 0)
        self.assertEqual(stats["range"], 0)
        self.assertEqual(stats["cv"], 0)

    def test_range_and_sample_cv_are_correct(self):
        stats = calculate_feature_statistics([1.0, 2.0, 3.0])

        self.assertAlmostEqual(stats["mean"], 2.0)
        self.assertAlmostEqual(stats["std"], 1.0)
        self.assertEqual(stats["min"], 1.0)
        self.assertEqual(stats["max"], 3.0)
        self.assertEqual(stats["range"], 2.0)
        self.assertAlmostEqual(stats["cv"], 0.5)

    def test_near_zero_mean_has_null_cv_instead_of_infinity(self):
        stats = calculate_feature_statistics([-1.0, 0.0, 1.0])

        self.assertEqual(stats["mean"], 0.0)
        self.assertIsNone(stats["cv"])

    def test_validate_image_paths_requires_at_least_two_images(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            only_image = Path(temporary_directory) / "repeat_01.jpg"
            only_image.touch()

            with self.assertRaisesRegex(
                RepeatabilityAnalysisError, "at least 2 images"
            ):
                validate_image_paths([only_image])

    def test_discovery_accepts_uppercase_jpg_suffix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            expected = [root / "repeat_01.JPG", root / "repeat_02.jpg"]
            for path in expected:
                path.touch()
            (root / "face_01.jpg").touch()
            (root / "repeat_03.png").touch()

            self.assertEqual(discover_repeat_images(root), expected)

    def test_report_outputs_are_strict_json_and_include_raw_csv_values(self):
        samples = [
            {
                "filename": f"repeat_{index:02d}.jpg",
                "face_detected": True,
                "features": _features(value),
            }
            for index, value in enumerate([1.0, 2.0, 3.0, 4.0, 5.0], start=1)
        ]
        report = build_repeatability_report(samples)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            json_path = root / "report.json"
            csv_path = root / "report.csv"
            save_report_json(report, json_path)
            save_report_csv(report, csv_path)

            serialized = json_path.read_text(encoding="utf-8")
            self.assertNotIn("NaN", serialized)
            self.assertNotIn("Infinity", serialized)
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
            self.assertEqual(parsed["features"]["eye_tail_angle.mean"]["n"], 5)

            with csv_path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 5)
            self.assertEqual(rows[0]["sample_1:repeat_01.jpg"], "1.0")
            self.assertEqual(rows[0]["sample_5:repeat_05.jpg"], "5.0")

        def assert_finite_or_none(value: object) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    assert_finite_or_none(child)
            elif isinstance(value, list):
                for child in value:
                    assert_finite_or_none(child)
            elif isinstance(value, float):
                self.assertTrue(math.isfinite(value))

        assert_finite_or_none(parsed)

    def test_report_requires_two_successful_detections(self):
        samples = [
            {
                "filename": "repeat_01.jpg",
                "face_detected": True,
                "features": _features(1.0),
            },
            {"filename": "repeat_02.jpg", "face_detected": False, "error": "no face"},
        ]

        with self.assertRaisesRegex(
            RepeatabilityAnalysisError, "successfully detected faces"
        ):
            build_repeatability_report(samples)

    def test_baseline_comparison_contains_before_and_after_values(self):
        before_samples = [
            {
                "filename": f"before_{index}.jpg",
                "face_detected": True,
                "features": _features(value),
            }
            for index, value in enumerate([1.0, 3.0], start=1)
        ]
        after_samples = [
            {
                "filename": f"after_{index}.jpg",
                "face_detected": True,
                "features": _features(value),
            }
            for index, value in enumerate([1.5, 2.5], start=1)
        ]
        baseline = build_repeatability_report(before_samples)
        current = build_repeatability_report(after_samples)

        add_baseline_comparison(current, baseline)

        comparison = current["comparison_to_baseline"]["features"][
            "eye_tail_angle.mean"
        ]
        self.assertGreater(comparison["before_std"], comparison["after_std"])
        self.assertGreater(comparison["before_cv"], comparison["after_cv"])

    def test_analysis_reuses_existing_pipeline_profile_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            images = [root / "repeat_01.jpg", root / "repeat_02.jpg"]
            for image in images:
                image.touch()

            def fake_process(**kwargs):
                value = 1.0 if kwargs["image_path"].name == "repeat_01.jpg" else 2.0
                kwargs["profile_output_path"].parent.mkdir(parents=True, exist_ok=True)
                kwargs["profile_output_path"].write_text(
                    json.dumps(_profile(value)), encoding="utf-8"
                )
                return {"face_detected": True}

            with patch(
                "src.repeatability_analysis.process_eye_geometry",
                side_effect=fake_process,
            ) as process_mock:
                report = analyze_repeatability(
                    images,
                    model_path=root / "model.task",
                    work_output_dir=root / "work",
                    json_output_path=root / "report.json",
                    csv_output_path=root / "report.csv",
                )

            self.assertEqual(process_mock.call_count, 2)
            self.assertEqual(report["input"]["successful_count"], 2)
            self.assertEqual(
                report["features"]["relative_eye_length.mean"]["values"][1]["value"],
                2.0,
            )
            self.assertTrue((root / "report.json").is_file())
            self.assertTrue((root / "report.csv").is_file())


if __name__ == "__main__":
    unittest.main()
