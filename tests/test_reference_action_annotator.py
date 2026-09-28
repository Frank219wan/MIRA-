import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.reference_action_annotator import AnnotationError, annotate_image, crop_image


class ReferenceActionAnnotatorTests(unittest.TestCase):
    def test_crop_uses_configured_split_instead_of_fixed_half(self):
        image = np.zeros((100, 200, 3), dtype=np.uint8)

        cropped, bounds = crop_image(image, crop="bottom", split=0.6)

        self.assertEqual(cropped.shape[:2], (40, 200))
        self.assertEqual(bounds, {"x": 0, "y": 60, "width": 200, "height": 40})

    def test_manual_points_file_produces_geometry_and_debug_overlay(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "local_eye.png"
            points_path = root / "points.json"
            result_path = root / "reference.json"
            debug_path = root / "reference_debug.jpg"
            image = np.zeros((200, 300, 3), dtype=np.uint8)
            self.assertTrue(cv2.imwrite(str(image_path), image))
            points_path.write_text(
                json.dumps({
                    "eye_inner": {"x": 20, "y": 80},
                    "eye_outer": {"x": 120, "y": 80},
                    "eyeliner_tip": {"x": 140, "y": 60},
                }),
                encoding="utf-8",
            )

            result = annotate_image(
                image_path,
                output_json=result_path,
                debug_output=debug_path,
                crop="bottom",
                split=0.25,
                points_json=points_path,
            )

            self.assertEqual(result["geometry"]["direction_relative_to_eye_axis_deg"], 45.0)
            self.assertEqual(
                result["source"]["crop_roi_original_image_px"]["y"], 50
            )
            self.assertTrue(result_path.is_file())
            self.assertTrue(debug_path.is_file())

    def test_point_outside_selected_crop_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            image_path = root / "eye.png"
            points_path = root / "points.json"
            cv2.imwrite(str(image_path), np.zeros((100, 100, 3), dtype=np.uint8))
            points_path.write_text(
                json.dumps({
                    "eye_inner": {"x": 10, "y": 10},
                    "eye_outer": {"x": 60, "y": 10},
                    "eyeliner_tip": {"x": 120, "y": 0},
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(AnnotationError, "outside the selected crop"):
                annotate_image(
                    image_path,
                    output_json=root / "reference.json",
                    debug_output=root / "reference.jpg",
                    points_json=points_path,
                )


if __name__ == "__main__":
    unittest.main()
