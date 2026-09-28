import json
import math
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import cv2
import numpy as np

from src.eye_landmarks import (
    SUBJECT_LEFT_BROW_INDICES,
    SUBJECT_LEFT_EYE_INDICES,
    SUBJECT_LEFT_EYE_RULE_INDICES,
    SUBJECT_RIGHT_BROW_INDICES,
    SUBJECT_RIGHT_EYE_INDICES,
    SUBJECT_RIGHT_EYE_RULE_INDICES,
    build_face_geometry_payload,
    draw_eye_landmarks,
    extract_brow_landmarks,
    extract_eye_landmarks,
    extract_rule_landmarks,
    save_geometry_json,
)
from src.face_geometry import eye_tail_angle_deg
from src.pose_normalization import rotate_point


def fake_face_landmarks():
    landmarks = [
        SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(478)
    ]
    coordinates = {
        362: (0.56, 0.40),
        263: (0.72, 0.41),
        386: (0.64, 0.38),
        374: (0.64, 0.44),
        133: (0.44, 0.40),
        33: (0.28, 0.41),
        159: (0.36, 0.38),
        145: (0.36, 0.44),
        276: (0.57, 0.34),
        283: (0.60, 0.32),
        282: (0.64, 0.31),
        295: (0.68, 0.32),
        285: (0.71, 0.34),
        46: (0.43, 0.34),
        53: (0.40, 0.32),
        52: (0.36, 0.31),
        65: (0.32, 0.32),
        55: (0.29, 0.34),
        234: (0.10, 0.48),
        454: (0.90, 0.48),
        398: (0.575, 0.395),
        382: (0.575, 0.415),
        373: (0.68, 0.435),
        380: (0.60, 0.435),
        254: (0.68, 0.47),
        253: (0.64, 0.47),
        252: (0.60, 0.47),
        173: (0.425, 0.395),
        155: (0.425, 0.415),
        144: (0.32, 0.435),
        153: (0.40, 0.435),
        24: (0.32, 0.47),
        23: (0.36, 0.47),
        22: (0.40, 0.47),
    }
    for index, (x, y) in coordinates.items():
        landmarks[index] = SimpleNamespace(x=x, y=y, z=-0.01)
    return landmarks


def all_numbers_are_finite(value) -> bool:
    if isinstance(value, dict):
        return all(all_numbers_are_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(all_numbers_are_finite(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return True


def rotate_fake_face_landmarks(landmarks, angle_deg: float):
    center = SimpleNamespace(x=0.5, y=0.5)
    rotated = []
    for landmark in landmarks:
        point = rotate_point(
            SimpleNamespace(x=landmark.x, y=landmark.y),
            center,
            angle_deg,
        )
        rotated.append(
            SimpleNamespace(x=point.x, y=point.y, z=landmark.z)
        )
    return rotated


class EyeLandmarkTests(unittest.TestCase):
    def test_unmirrored_indices_are_person_relative(self):
        eyes = extract_eye_landmarks(fake_face_landmarks())
        self.assertEqual(
            eyes.left.inner_corner.index,
            SUBJECT_LEFT_EYE_INDICES.inner_corner,
        )
        self.assertEqual(
            eyes.right.outer_corner.index,
            SUBJECT_RIGHT_EYE_INDICES.outer_corner,
        )

    def test_mirrored_input_swaps_eye_groups(self):
        eyes = extract_eye_landmarks(
            fake_face_landmarks(), input_is_mirrored=True
        )
        self.assertEqual(
            eyes.left.inner_corner.index,
            SUBJECT_RIGHT_EYE_INDICES.inner_corner,
        )
        self.assertEqual(
            eyes.right.inner_corner.index,
            SUBJECT_LEFT_EYE_INDICES.inner_corner,
        )

    def test_brow_groups_are_person_relative_and_mirror_aware(self):
        brows = extract_brow_landmarks(fake_face_landmarks())
        mirrored = extract_brow_landmarks(
            fake_face_landmarks(), input_is_mirrored=True
        )
        self.assertEqual(
            tuple(point.index for point in brows.left.points),
            SUBJECT_LEFT_BROW_INDICES,
        )
        self.assertEqual(
            tuple(point.index for point in mirrored.left.points),
            SUBJECT_RIGHT_BROW_INDICES,
        )

    def test_rule_landmarks_are_person_relative_and_mirror_aware(self):
        rules = extract_rule_landmarks(fake_face_landmarks())
        mirrored = extract_rule_landmarks(
            fake_face_landmarks(), input_is_mirrored=True
        )
        self.assertEqual(
            rules.left.upper_inner.index,
            SUBJECT_LEFT_EYE_RULE_INDICES.upper_inner,
        )
        self.assertEqual(
            tuple(point.index for point in rules.left.lower_lid),
            SUBJECT_LEFT_EYE_RULE_INDICES.lower_lid,
        )
        self.assertEqual(
            mirrored.left.upper_inner.index,
            SUBJECT_RIGHT_EYE_RULE_INDICES.upper_inner,
        )
        self.assertEqual(
            tuple(point.index for point in mirrored.left.lower_lid),
            SUBJECT_RIGHT_EYE_RULE_INDICES.lower_lid,
        )

    def test_payload_is_finite_and_json_can_be_written(self):
        eyes = extract_eye_landmarks(fake_face_landmarks())
        brows = extract_brow_landmarks(fake_face_landmarks())
        rule_landmarks = extract_rule_landmarks(fake_face_landmarks())
        payload = build_face_geometry_payload(
            eyes,
            1000,
            800,
            brows=brows,
            rule_landmarks=rule_landmarks,
        )

        self.assertGreater(payload["eyes"]["left"]["width_px"], 0)
        self.assertGreater(payload["eyes"]["left"]["height_px"], 0)
        self.assertGreater(payload["geometry"]["eye_spacing_ratio"], 0)
        self.assertGreater(payload["brow_eye"]["mean_brow_eye_ratio"], 0)
        self.assertIn("mean_eye_tail_angle_deg", payload["eye_tail_angle"])
        self.assertIn("eye_width_asymmetry", payload["asymmetry"])
        self.assertGreater(
            payload["relative_eye_length"]["relative_eye_length_mean"], 0
        )
        self.assertGreater(
            payload["lower_lid_space"]["lower_lid_space_ratio_mean"], 0
        )
        self.assertGreater(
            payload["inner_corner_angle"]["inner_corner_angle_mean_deg"], 0
        )
        self.assertIn("pose_normalization", payload)
        self.assertTrue(payload["pose_normalization"]["applied"])
        self.assertTrue(payload["confidence"]["pose_normalized"])
        self.assertTrue(
            math.isfinite(payload["pose_normalization"]["roll_angle_deg"])
        )
        self.assertIn(
            "pose_normalized_pixel",
            payload["eyes"]["left"]["inner_corner"],
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "face_geometry.json"
            save_geometry_json(output_path, payload)
            loaded = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertTrue(loaded["face_detected"])
        self.assertTrue(all_numbers_are_finite(loaded))
        self.assertTrue(
            math.isfinite(loaded["geometry"]["eye_spacing_ratio"])
        )
        self.assertTrue(
            math.isfinite(loaded["brow_eye"]["mean_brow_eye_ratio"])
        )
        self.assertTrue(
            math.isfinite(
                loaded["asymmetry"]["eye_tail_angle_difference_deg"]
            )
        )
        self.assertTrue(
            math.isfinite(
                loaded["relative_eye_length"]["relative_eye_length_mean"]
            )
        )
        self.assertTrue(
            math.isfinite(
                loaded["lower_lid_space"]["lower_lid_space_ratio_mean"]
            )
        )
        self.assertTrue(
            math.isfinite(
                loaded["inner_corner_angle"]["inner_corner_angle_mean_deg"]
            )
        )

    def test_payload_ratios_are_stable_under_uniform_image_scaling(self):
        landmarks = fake_face_landmarks()
        eyes = extract_eye_landmarks(landmarks)
        brows = extract_brow_landmarks(landmarks)
        rules = extract_rule_landmarks(landmarks)
        original = build_face_geometry_payload(
            eyes, 1000, 800, brows=brows, rule_landmarks=rules
        )
        scaled = build_face_geometry_payload(
            eyes, 2000, 1600, brows=brows, rule_landmarks=rules
        )
        for section, key in (
            ("relative_eye_length", "relative_eye_length_mean"),
            ("lower_lid_space", "lower_lid_space_ratio_mean"),
        ):
            self.assertAlmostEqual(
                original[section][key], scaled[section][key], places=3
            )

    def test_roll_normalization_reduces_rotated_eye_tail_angle_difference(self):
        base_landmarks = fake_face_landmarks()
        landmark_sets = [
            rotate_fake_face_landmarks(base_landmarks, angle)
            for angle in (-5.0, 0.0, 5.0)
        ]
        raw_left_angles = []
        normalized_left_angles = []

        for landmarks in landmark_sets:
            eyes = extract_eye_landmarks(landmarks)
            left_inner = eyes.left.inner_corner.to_pixel(1001, 1001)
            left_outer = eyes.left.outer_corner.to_pixel(1001, 1001)
            raw_left_angles.append(
                eye_tail_angle_deg(left_inner, left_outer)
            )
            payload = build_face_geometry_payload(
                eyes,
                1001,
                1001,
            )
            normalized_left_angles.append(
                payload["eye_tail_angle"]["left_eye_tail_angle_deg"]
            )
            self.assertTrue(payload["pose_normalization"]["applied"])

        raw_range = max(raw_left_angles) - min(raw_left_angles)
        normalized_range = max(normalized_left_angles) - min(
            normalized_left_angles
        )
        self.assertGreater(raw_range, 9.0)
        self.assertLess(normalized_range, raw_range * 0.05)

    def test_debug_visualization_draws_exactly_eight_unique_points(self):
        image = np.zeros((800, 1000, 3), dtype=np.uint8)
        eyes = extract_eye_landmarks(fake_face_landmarks())

        with patch(
            "src.eye_landmarks.cv2.circle", wraps=cv2.circle
        ) as circle_mock:
            result = draw_eye_landmarks(image, eyes)

        # Each of the 8 landmarks gets a black outline and a colored center.
        self.assertEqual(circle_mock.call_count, 16)
        unique_centers = {call.args[1] for call in circle_mock.call_args_list}
        self.assertEqual(len(unique_centers), 8)
        self.assertEqual(result.shape[0], image.shape[0])

    def test_geometry_debug_draws_only_selected_eye_and_brow_points(self):
        image = np.zeros((800, 1000, 3), dtype=np.uint8)
        landmarks = fake_face_landmarks()
        eyes = extract_eye_landmarks(landmarks)
        brows = extract_brow_landmarks(landmarks)

        with patch(
            "src.eye_landmarks.cv2.circle", wraps=cv2.circle
        ) as circle_mock:
            draw_eye_landmarks(image, eyes, brows)

        # 8 eye + 10 selected brow points, each with outline and center.
        self.assertEqual(circle_mock.call_count, 36)
        unique_centers = {call.args[1] for call in circle_mock.call_args_list}
        self.assertEqual(len(unique_centers), 18)

    def test_v02_debug_draws_lower_lid_lines_and_inner_corner_rays(self):
        image = np.zeros((800, 1000, 3), dtype=np.uint8)
        landmarks = fake_face_landmarks()
        eyes = extract_eye_landmarks(landmarks)
        brows = extract_brow_landmarks(landmarks)
        rules = extract_rule_landmarks(landmarks)

        with patch(
            "src.eye_landmarks.cv2.line", wraps=cv2.line
        ) as line_mock:
            result = draw_eye_landmarks(image, eyes, brows, rules)

        self.assertGreaterEqual(line_mock.call_count, 19)
        self.assertEqual(result.shape[0], image.shape[0])


if __name__ == "__main__":
    unittest.main()
