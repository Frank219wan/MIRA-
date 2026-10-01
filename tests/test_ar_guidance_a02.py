import json
import math
import unittest
from pathlib import Path

from src.ar_guidance import build_a02_guidance


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "main_demo"
LANDMARKS = {
    "eye_outer": {"x_norm": 0.7, "y_norm": 0.48},
    "lower_lid_path": [
        {"x_norm": 0.7, "y_norm": 0.5},
        {"x_norm": 0.62, "y_norm": 0.525},
        {"x_norm": 0.54, "y_norm": 0.535},
        {"x_norm": 0.46, "y_norm": 0.525},
        {"x_norm": 0.38, "y_norm": 0.5},
    ],
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class A02GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.reference = fixture("main_demo_reference.json")["reference_action"][
            "A02"
        ]
        self.face06 = fixture("face_06_personalization.json")
        self.face11 = fixture("face_11_personalization.json")

    def test_face06_target_region_extends_beyond_reference(self):
        baseline = build_a02_guidance(LANDMARKS, self.reference, "right")
        personalized = build_a02_guidance(
            LANDMARKS, self.face06["A02"], "right"
        )
        self.assertNotEqual(baseline["polygon"], personalized["polygon"])
        self.assertGreater(
            personalized["range_semantics"]["applied_fraction"],
            baseline["range_semantics"]["applied_fraction"],
        )
        self.assertEqual(
            personalized["intensity_factor"],
            self.face06["A02"]["personalized_intensity_factor"],
        )
        self.assertEqual(
            personalized["intensity_semantics"],
            "metadata_only_not_ui_opacity",
        )

    def test_face11_target_region_equals_reference(self):
        baseline = build_a02_guidance(LANDMARKS, self.reference, "right")
        personalized = build_a02_guidance(
            LANDMARKS, self.face11["A02"], "right"
        )
        self.assertEqual(baseline["polygon"], personalized["polygon"])
        self.assertEqual(baseline["centerline"], personalized["centerline"])
        self.assertEqual(baseline["range_factor"], personalized["range_factor"])
        self.assertEqual(
            baseline["intensity_factor"], personalized["intensity_factor"]
        )

    def test_polygon_coordinates_are_normalized_and_finite(self):
        guidance = build_a02_guidance(
            LANDMARKS, self.face06["A02"], "right"
        )
        self.assertGreaterEqual(len(guidance["polygon"]), 4)
        for point in guidance["polygon"]:
            for coordinate in point.values():
                self.assertTrue(math.isfinite(coordinate))
                self.assertGreaterEqual(coordinate, 0.0)
                self.assertLessEqual(coordinate, 1.0)


if __name__ == "__main__":
    unittest.main()
