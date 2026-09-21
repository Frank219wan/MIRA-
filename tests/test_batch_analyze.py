import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.batch_analyze import SUMMARY_FIELDS, analyze_batch
from src.eye_landmarks import save_geometry_json
from src.face_landmarker import FaceLandmarkerError


def fake_geometry_payload(seed: float = 0.0) -> dict:
    return {
        "face_detected": True,
        "geometry": {"eye_spacing_ratio": 1.3 + seed},
        "relative_eye_length": {
            "relative_eye_length_left": 0.23 + seed,
            "relative_eye_length_right": 0.24 + seed,
            "relative_eye_length_mean": 0.235 + seed,
        },
        "eye_width_height_ratio": {
            "eye_width_height_ratio_left": 3.1 + seed,
            "eye_width_height_ratio_right": 3.2 + seed,
            "eye_width_height_ratio_mean": 3.15 + seed,
        },
        "eye_tail_angle": {
            "left_eye_tail_angle_deg": 5.0 + seed,
            "right_eye_tail_angle_deg": 6.0 + seed,
            "mean_eye_tail_angle_deg": 5.5 + seed,
        },
        "brow_eye": {
            "left_brow_eye_ratio": 0.6 + seed,
            "right_brow_eye_ratio": 0.7 + seed,
        },
        "lower_lid_space": {
            "lower_lid_space_px_left": 10.0 + seed,
            "lower_lid_space_px_right": 11.0 + seed,
            "lower_lid_space_px_mean": 10.5 + seed,
            "lower_lid_space_ratio_left": 0.18 + seed,
            "lower_lid_space_ratio_right": 0.19 + seed,
            "lower_lid_space_ratio_mean": 0.185 + seed,
        },
        "inner_corner_angle": {
            "inner_corner_angle_left_deg": 50.0 + seed,
            "inner_corner_angle_right_deg": 52.0 + seed,
            "inner_corner_angle_mean_deg": 51.0 + seed,
        },
        "asymmetry": {
            "eye_width_asymmetry": 0.01 + seed,
            "eye_height_asymmetry": 0.02 + seed,
            "eye_aspect_ratio_asymmetry": 0.03 + seed,
        },
    }


class BatchAnalyzeTests(unittest.TestCase):
    def test_batch_continues_after_one_image_error_and_writes_csv(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            input_dir = root / "input"
            output_dir = root / "batch"
            summary_path = root / "face_summary.csv"
            input_dir.mkdir()
            for filename in ("face_02.jpg", "face_01.jpg", "face_03.jpg"):
                (input_dir / filename).write_bytes(b"test")

            def fake_process(**kwargs):
                image_path = kwargs["image_path"]
                if image_path.name == "face_02.jpg":
                    raise FaceLandmarkerError("未检测到人脸。")
                seed = 0.1 if image_path.name == "face_03.jpg" else 0.0
                payload = fake_geometry_payload(seed)
                save_geometry_json(kwargs["json_output_path"], payload)
                return payload

            with patch(
                "src.batch_analyze.process_eye_geometry",
                side_effect=fake_process,
            ) as process_mock:
                rows = analyze_batch(
                    input_dir=input_dir,
                    model_path=root / "model.task",
                    batch_output_dir=output_dir,
                    summary_csv_path=summary_path,
                )

            self.assertEqual(process_mock.call_count, 3)
            self.assertEqual(
                [row["filename"] for row in rows],
                ["face_01.jpg", "face_02.jpg", "face_03.jpg"],
            )
            self.assertEqual(rows[0]["error"], "")
            self.assertIn("未检测到人脸", rows[1]["error"])
            self.assertEqual(rows[2]["error"], "")

            with summary_path.open(encoding="utf-8", newline="") as csv_file:
                csv_rows = list(csv.DictReader(csv_file))
            self.assertEqual(tuple(csv_rows[0].keys()), SUMMARY_FIELDS)
            self.assertEqual(len(csv_rows), 3)
            self.assertEqual(csv_rows[1]["eye_spacing_ratio"], "")
            self.assertEqual(csv_rows[1]["relative_eye_length_mean"], "")
            self.assertIn("未检测到人脸", csv_rows[1]["error"])

            error_payload = json.loads(
                (output_dir / "face_02_geometry.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertFalse(error_payload["face_detected"])
            self.assertIn("未检测到人脸", error_payload["error"])


if __name__ == "__main__":
    unittest.main()
