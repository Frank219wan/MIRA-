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
    SUBJECT_RIGHT_BROW_INDICES,
    SUBJECT_RIGHT_EYE_INDICES,
    build_face_geometry_payload,
    draw_eye_landmarks,
    extract_brow_landmarks,
    extract_eye_landmarks,
    save_geometry_json,
)


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
    }
    for index, (x, y) in coordinates.items():
        landmarks[index] = SimpleNamespace(x=x, y=y, z=-0.01)
    return landmarks


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

    def test_payload_is_finite_and_json_can_be_written(self):
        eyes = extract_eye_landmarks(fake_face_landmarks())
        brows = extract_brow_landmarks(fake_face_landmarks())
        payload = build_face_geometry_payload(
            eyes, 1000, 800, brows=brows
        )

        self.assertGreater(payload["eyes"]["left"]["width_px"], 0)
        self.assertGreater(payload["eyes"]["left"]["height_px"], 0)
        self.assertGreater(payload["geometry"]["eye_spacing_ratio"], 0)
        self.assertGreater(payload["brow_eye"]["mean_brow_eye_ratio"], 0)
        self.assertIn("mean_eye_tail_angle_deg", payload["eye_tail_angle"])
        self.assertIn("eye_width_asymmetry", payload["asymmetry"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / "face_geometry.json"
            save_geometry_json(output_path, payload)
            loaded = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertTrue(loaded["face_detected"])
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


if __name__ == "__main__":
    unittest.main()
