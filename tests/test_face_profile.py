import json
import math
import tempfile
import unittest
from pathlib import Path

from src.face_profile import (
    FaceProfileError,
    build_face_profile,
    build_face_profile_file,
)


def valid_geometry() -> dict:
    return {
        "face_detected": True,
        "geometry": {"eye_spacing_ratio": 1.3851},
        "eye_tail_angle": {
            "left_eye_tail_angle_deg": 10.059,
            "right_eye_tail_angle_deg": 10.712,
            "mean_eye_tail_angle_deg": 10.386,
        },
        "brow_eye": {
            "left_brow_eye_ratio": 0.6777,
            "right_brow_eye_ratio": 0.6467,
            "mean_brow_eye_ratio": 0.6622,
        },
        "asymmetry": {
            "eye_width_asymmetry": 0.013,
            "eye_height_asymmetry": 0.0299,
            "eye_aspect_ratio_asymmetry": 0.0169,
            "eye_tail_angle_difference_deg": 0.653,
        },
    }


def all_numbers_are_finite(value) -> bool:
    if isinstance(value, dict):
        return all(all_numbers_are_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_numbers_are_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


class FaceProfileTests(unittest.TestCase):
    def test_geometry_dict_generates_profile(self):
        profile = build_face_profile(valid_geometry())
        self.assertEqual(profile["version"], "0.1")
        self.assertEqual(
            profile["eye_geometry"]["eye_spacing_ratio"], 1.3851
        )
        self.assertEqual(profile["symmetry"]["eye_width"], 0.013)

    def test_profile_contains_required_sections(self):
        profile = build_face_profile(valid_geometry())
        for key in ("version", "eye_geometry", "symmetry", "confidence"):
            self.assertIn(key, profile)
        self.assertFalse(profile["confidence"]["pose_normalized"])
        self.assertFalse(profile["confidence"]["expression_controlled"])

    def test_profile_file_is_written_and_all_numbers_are_finite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            geometry_path = root / "face_geometry.json"
            profile_path = root / "face_profile.json"
            geometry_path.write_text(
                json.dumps(valid_geometry()), encoding="utf-8"
            )

            build_face_profile_file(geometry_path, profile_path)
            profile = json.loads(profile_path.read_text(encoding="utf-8"))

        self.assertTrue(all_numbers_are_finite(profile))
        self.assertEqual(
            profile["raw_geometry_reference"]["source"],
            "face_geometry.json",
        )

    def test_non_finite_geometry_is_rejected(self):
        for invalid_value in (float("nan"), float("inf")):
            geometry = valid_geometry()
            geometry["geometry"]["eye_spacing_ratio"] = invalid_value
            with self.subTest(invalid_value=invalid_value):
                with self.assertRaisesRegex(
                    FaceProfileError, "不能是 NaN 或 infinity"
                ):
                    build_face_profile(geometry)

    def test_missing_geometry_field_has_clear_error(self):
        geometry = valid_geometry()
        del geometry["brow_eye"]["mean_brow_eye_ratio"]
        with self.assertRaisesRegex(
            FaceProfileError, "brow_eye.mean_brow_eye_ratio"
        ):
            build_face_profile(geometry)


if __name__ == "__main__":
    unittest.main()
