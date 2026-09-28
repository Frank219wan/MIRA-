import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.face_scan_aggregator import (
    FaceScanAggregationError,
    FaceScanAggregator,
    feature_dispersion,
    run_stable_face_scan,
)
from src.personalization_engine import personalize_recipe


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads(
    (ROOT / "data" / "fixtures" / "face_profile_v0_3.json").read_text(encoding="utf-8")
)
RECIPE = json.loads(
    (ROOT / "examples" / "cat_eye_standard_recipe.json").read_text(encoding="utf-8")
)


def profile_with_tail(value: float) -> dict:
    result = copy.deepcopy(FIXTURE)
    result["eye_geometry"]["eye_tail_angle"]["mean"] = value
    return result


class FaceScanAggregatorTests(unittest.TestCase):
    def test_single_extreme_frame_does_not_move_median(self):
        aggregator = FaceScanAggregator()
        for index, value in enumerate((1, 1, 1, 1, 10), start=1):
            self.assertTrue(aggregator.add_profile(profile_with_tail(value), frame_id=str(index)))

        result = aggregator.finalize()
        stats = result["aggregation"]["features"]["eye_tail_angle.mean"]

        self.assertEqual(result["aggregated_face_profile"]["eye_geometry"]["eye_tail_angle"]["mean"], 1)
        self.assertEqual(stats["median"], 1)
        self.assertEqual(stats["max"], 10)
        self.assertEqual(result["valid_frame_count"], 5)
        self.assertFalse(result["aggregation"]["outliers_removed"])

    def test_identical_profiles_have_zero_mad_and_range(self):
        aggregator = FaceScanAggregator()
        for _ in range(5):
            aggregator.add_profile(FIXTURE)

        for stats in aggregator.finalize()["aggregation"]["features"].values():
            self.assertEqual(stats["n"], 5)
            self.assertEqual(stats["std"], 0)
            self.assertEqual(stats["range"], 0)
            self.assertEqual(stats["iqr"], 0)
            self.assertEqual(stats["mad"], 0)

    def test_order_does_not_change_scan(self):
        frames = [(f"frame_{index}", profile_with_tail(value)) for index, value in enumerate((1, 2, 3, 4, 10))]
        first, second = FaceScanAggregator(), FaceScanAggregator()
        for frame_id, profile in frames:
            first.add_profile(profile, frame_id=frame_id)
        for frame_id, profile in reversed(frames):
            second.add_profile(profile, frame_id=frame_id)

        self.assertEqual(first.finalize(), second.finalize())

    def test_below_minimum_has_clear_error(self):
        aggregator = FaceScanAggregator()
        aggregator.add_profile(FIXTURE)
        aggregator.add_profile(FIXTURE)

        with self.assertRaisesRegex(FaceScanAggregationError, "at least 3 valid profiles; got 2"):
            aggregator.finalize()

    def test_rejects_invalid_or_unusable_frames_without_imputing(self):
        bad_version = copy.deepcopy(FIXTURE)
        bad_version["version"] = "0.2"
        bad_pose = copy.deepcopy(FIXTURE)
        bad_pose["confidence"]["pose_normalized"] = False
        bad_number = copy.deepcopy(FIXTURE)
        bad_number["eye_geometry"]["relative_eye_length"]["mean"] = float("nan")
        degenerate = copy.deepcopy(FIXTURE)
        degenerate["eye_geometry"]["relative_eye_length"]["mean"] = 0
        aggregator = FaceScanAggregator()
        for index, invalid in enumerate((bad_version, bad_pose, bad_number, degenerate)):
            self.assertFalse(aggregator.add_profile(invalid, frame_id=f"invalid_{index}"))
        aggregator.add_failure(frame_id="no_face", reason="No face detected")
        for index in range(3):
            self.assertTrue(aggregator.add_profile(FIXTURE, frame_id=f"valid_{index}"))

        result = aggregator.finalize()

        self.assertEqual(result["frame_count"], 8)
        self.assertEqual(result["valid_frame_count"], 3)
        self.assertEqual(result["quality_information"]["invalid_frame_count"], 5)
        self.assertEqual(result["aggregation"]["features"]["relative_eye_length.mean"]["n"], 3)
        self.assertEqual(len([f for f in result["quality_information"]["frames"] if not f["valid"]]), 5)
        json.dumps(result, allow_nan=False)

    def test_stable_profile_is_full_v03_contract_and_direct_engine_input(self):
        aggregator = FaceScanAggregator()
        for value in (6, 7, 8):
            aggregator.add_profile(profile_with_tail(value))

        profile = aggregator.finalize()["aggregated_face_profile"]
        personalized = personalize_recipe(profile, RECIPE, "cat_eye")

        self.assertEqual(profile["version"], "0.3")
        self.assertEqual(set(profile["symmetry"]), set(FIXTURE["symmetry"]))
        self.assertEqual(profile["eye_geometry"]["eye_tail_angle"]["mean"], 7)
        for group in ("eye_tail_angle", "relative_eye_length", "brow_eye_ratio", "lower_lid_space_ratio"):
            values = profile["eye_geometry"][group]
            self.assertAlmostEqual((values["left"] + values["right"]) / 2, values["mean"])
        tail = profile["eye_geometry"]["eye_tail_angle"]
        self.assertAlmostEqual(profile["symmetry"]["eye_tail_angle_difference"], abs(tail["left"] - tail["right"]))
        self.assertEqual(len(personalized["personalized_actions"]), 2)
        json.dumps(profile, allow_nan=False)
        json.dumps(personalized, allow_nan=False)

    def test_mad_and_inclusive_quartiles(self):
        stats = feature_dispersion([6.05, 7.019, 7.641, 7.946, 11.012])

        self.assertEqual(stats["median"], 7.641)
        self.assertEqual(stats["q1"], 7.019)
        self.assertEqual(stats["q3"], 7.946)
        self.assertAlmostEqual(stats["mad"], 0.622)

    def test_saved_profile_json_mode_outputs_comparison(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            paths = []
            for index, value in enumerate((6, 7, 8), start=1):
                path = directory / f"frame_{index}.json"
                path.write_text(json.dumps(profile_with_tail(value)), encoding="utf-8")
                paths.append(path)
            output = directory / "output"

            scan = run_stable_face_scan(profile_paths=paths, output_dir=output)

            self.assertEqual(scan["valid_frame_count"], 3)
            with (output / "single_vs_stable_personalization.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 4)
            self.assertEqual(rows[-1]["profile_type"], "median_aggregate")
            for name in ("stable_face_scan.json", "stable_face_profile.json", "stable_personalization.json"):
                json.loads((output / name).read_text(encoding="utf-8"), parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


if __name__ == "__main__":
    unittest.main()
