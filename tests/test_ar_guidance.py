import json
import math
import unittest
from pathlib import Path

import numpy as np

from src.ar_guidance import (
    ARGuidanceError,
    build_a04_guidance,
    evaluate_a04_stability,
)
from src.reference_package import package_existing_reference
from tools.render_ar_guidance_debug import render_debug
from tools.run_main_demo_pipeline import run_demo


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "main_demo"
LANDMARKS = {
    "side": "right",
    "eye_inner": {"x_norm": 0.35, "y_norm": 0.5},
    "eye_outer": {"x_norm": 0.65, "y_norm": 0.49},
    "lower_lid_path": [
        {"x_norm": 0.65, "y_norm": 0.51},
        {"x_norm": 0.58, "y_norm": 0.53},
        {"x_norm": 0.5, "y_norm": 0.54},
        {"x_norm": 0.42, "y_norm": 0.53},
        {"x_norm": 0.35, "y_norm": 0.51},
    ],
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def line_length(guidance):
    anchor = guidance["anchor"]
    endpoint = guidance["endpoint"]
    return math.hypot(
        endpoint["x_norm"] - anchor["x_norm"],
        endpoint["y_norm"] - anchor["y_norm"],
    )


def endpoint_angle(guidance):
    inner = guidance["eye_axis"]["inner"]
    outer = guidance["eye_axis"]["outer"]
    anchor = guidance["anchor"]
    endpoint = guidance["endpoint"]
    axis_x = outer["x_norm"] - inner["x_norm"]
    axis_y = outer["y_norm"] - inner["y_norm"]
    line_x = endpoint["x_norm"] - anchor["x_norm"]
    line_y = endpoint["y_norm"] - anchor["y_norm"]
    dot = axis_x * line_x + axis_y * line_y
    cross = axis_x * line_y - axis_y * line_x
    return math.degrees(
        math.atan2(-math.copysign(1.0, axis_x) * cross, dot)
    )


class A04GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.reference = fixture("main_demo_reference.json")["reference_action"][
            "A04"
        ]
        self.face06 = fixture("face_06_personalization.json")
        self.face11 = fixture("face_11_personalization.json")

    def test_identity_action_produces_identical_geometry(self):
        first = build_a04_guidance(LANDMARKS, self.reference, "right")
        second = build_a04_guidance(LANDMARKS, self.reference, "right")
        self.assertEqual(first["anchor"], second["anchor"])
        self.assertEqual(first["endpoint"], second["endpoint"])
        self.assertEqual(
            first["direction_relative_to_eye_axis_deg"],
            second["direction_relative_to_eye_axis_deg"],
        )
        self.assertEqual(first["extension_ratio"], second["extension_ratio"])

    def test_direction_change_changes_endpoint_angle(self):
        baseline = build_a04_guidance(LANDMARKS, self.reference, "right")
        changed_action = dict(self.reference)
        changed_action["direction_relative_to_eye_axis_deg"] = 20.0
        changed = build_a04_guidance(LANDMARKS, changed_action, "right")
        self.assertNotEqual(baseline["endpoint"], changed["endpoint"])
        self.assertAlmostEqual(endpoint_angle(baseline), 5.781666, places=8)
        self.assertAlmostEqual(endpoint_angle(changed), 20.0, places=8)

    def test_extension_increase_increases_line_length(self):
        baseline = build_a04_guidance(LANDMARKS, self.reference, "right")
        longer_action = dict(self.reference)
        longer_action["reference_extension_ratio"] = 0.5
        longer = build_a04_guidance(LANDMARKS, longer_action, "right")
        self.assertGreater(line_length(longer), line_length(baseline))

    def test_face06_geometry_changes_and_line_is_longer(self):
        baseline = build_a04_guidance(LANDMARKS, self.reference, "right")
        personalized = build_a04_guidance(
            LANDMARKS, self.face06["A04"], "right"
        )
        self.assertNotEqual(baseline["endpoint"], personalized["endpoint"])
        self.assertGreater(line_length(personalized), line_length(baseline))
        self.assertAlmostEqual(endpoint_angle(personalized), 3.971266, places=8)

    def test_face11_keep_reference_geometry_is_identical(self):
        self.assertEqual(self.face11["decision"], "KEEP_REFERENCE")
        baseline = build_a04_guidance(LANDMARKS, self.reference, "right")
        personalized = build_a04_guidance(
            LANDMARKS, self.face11["A04"], "right"
        )
        for field in (
            "anchor",
            "endpoint",
            "direction_relative_to_eye_axis_deg",
            "extension_ratio",
            "start_position_ratio",
        ):
            with self.subTest(field=field):
                self.assertEqual(baseline[field], personalized[field])

    def test_positive_direction_is_visually_up_for_either_axis_orientation(self):
        action = {
            "direction_relative_to_eye_axis_deg": 15.0,
            "reference_extension_ratio": 0.2,
            "start_position_ratio": 1.0,
        }
        rightward = build_a04_guidance(LANDMARKS, action, "right")
        leftward_landmarks = {
            "eye_inner": LANDMARKS["eye_outer"],
            "eye_outer": LANDMARKS["eye_inner"],
        }
        leftward = build_a04_guidance(leftward_landmarks, action, "left")
        self.assertLess(
            rightward["endpoint"]["y_norm"], rightward["anchor"]["y_norm"]
        )
        self.assertLess(
            leftward["endpoint"]["y_norm"], leftward["anchor"]["y_norm"]
        )
        self.assertAlmostEqual(endpoint_angle(rightward), 15.0, places=8)
        self.assertAlmostEqual(endpoint_angle(leftward), 15.0, places=8)

    def test_output_is_normalized_finite_and_invalid_output_is_rejected(self):
        guidance = build_a04_guidance(LANDMARKS, self.reference, "right")
        for point_name in ("anchor", "endpoint"):
            for value in guidance[point_name].values():
                self.assertTrue(math.isfinite(value))
                self.assertGreaterEqual(value, 0.0)
                self.assertLessEqual(value, 1.0)
        with self.assertRaisesRegex(ARGuidanceError, "outside normalized"):
            build_a04_guidance(
                {
                    "eye_inner": {"x_norm": 0.8, "y_norm": 0.5},
                    "eye_outer": {"x_norm": 0.99, "y_norm": 0.5},
                },
                self.reference,
                "right",
            )

    def test_temporal_stability_measures_jitter_without_smoothing(self):
        frames = []
        for offset in (0.0, 0.001, -0.001):
            landmarks = {
                "eye_inner": {"x_norm": 0.35 + offset, "y_norm": 0.5},
                "eye_outer": {"x_norm": 0.65 + offset, "y_norm": 0.49},
            }
            frames.append(
                build_a04_guidance(landmarks, self.reference, "right")
            )
        stability = evaluate_a04_stability(frames)
        self.assertEqual(stability["frame_count"], 3)
        self.assertFalse(stability["smoothing_applied"])
        self.assertGreater(stability["anchor_displacement_norm"]["max"], 0.0)
        self.assertGreater(stability["endpoint_displacement_norm"]["max"], 0.0)
        self.assertEqual(stability["direction_jitter_deg"]["max"], 0.0)

    def test_unified_demo_pipeline_reproduces_fixtures_and_ar_identity(self):
        package = package_existing_reference(
            fixture("main_demo_reference.json")
        )
        for sample_id, expected_fixture in (
            ("face_06", self.face06),
            ("face_11", self.face11),
        ):
            with self.subTest(sample_id=sample_id):
                outputs = run_demo(
                    reference_package=package,
                    user_profile=fixture(f"{sample_id}_face_profile.json"),
                    landmarks=LANDMARKS,
                    sample_id=sample_id,
                )
                self.assertEqual(
                    outputs["personalization"],
                    expected_fixture["source_validation_result"],
                )
                reference = outputs["ar_guidance"]["reference"]["A04"]
                personalized = outputs["ar_guidance"]["personalized"]["A04"]
                if sample_id == "face_06":
                    self.assertNotEqual(reference["endpoint"], personalized["endpoint"])
                else:
                    for field in (
                        "anchor",
                        "endpoint",
                        "direction_relative_to_eye_axis_deg",
                        "extension_ratio",
                        "start_position_ratio",
                    ):
                        self.assertEqual(reference[field], personalized[field])

    def test_debug_renderer_draws_both_lines_without_changing_geometry(self):
        reference = build_a04_guidance(LANDMARKS, self.reference, "right")
        personalized = build_a04_guidance(
            LANDMARKS, self.face06["A04"], "right"
        )
        image = np.zeros((200, 300, 3), dtype=np.uint8)
        rendered = render_debug(image, reference, personalized)
        self.assertEqual(rendered.shape, image.shape)
        self.assertGreater(int(rendered.sum()), 0)
        self.assertEqual(int(image.sum()), 0)


if __name__ == "__main__":
    unittest.main()
