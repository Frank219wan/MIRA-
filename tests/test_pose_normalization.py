import math
import unittest

from src.face_geometry import Point2D, eye_tail_angle_deg
from src.pose_normalization import (
    PoseNormalizationError,
    normalize_face_roll,
    rotate_point,
)


class PoseNormalizationTests(unittest.TestCase):
    def test_plus_and_minus_five_degree_roll_normalize_to_same_eye_angle(self):
        base = {
            1: Point2D(60.0, 50.0),
            2: Point2D(80.0, 46.0),
            3: Point2D(40.0, 50.0),
            4: Point2D(20.0, 46.0),
        }
        center = Point2D(50.0, 50.0)
        raw_angles = []
        normalized_angles = []

        for roll_deg in (-5.0, 0.0, 5.0):
            rolled = {
                index: rotate_point(point, center, roll_deg)
                for index, point in base.items()
            }
            raw_angles.append(eye_tail_angle_deg(rolled[1], rolled[2]))
            result = normalize_face_roll(
                rolled,
                left_eye_center_indices=(1, 2),
                right_eye_center_indices=(3, 4),
            )
            normalized_angles.append(
                eye_tail_angle_deg(
                    result.normalized_points[1],
                    result.normalized_points[2],
                )
            )
            self.assertAlmostEqual(result.roll_angle_deg, roll_deg, places=6)

        raw_range = max(raw_angles) - min(raw_angles)
        normalized_range = max(normalized_angles) - min(normalized_angles)
        self.assertGreater(raw_range, 9.0)
        self.assertLess(normalized_range, 1e-9)

    def test_degenerate_eye_centers_have_clear_error(self):
        points = {
            1: Point2D(0.0, 0.0),
            2: Point2D(2.0, 0.0),
            3: Point2D(0.0, 0.0),
            4: Point2D(2.0, 0.0),
        }

        with self.assertRaisesRegex(
            PoseNormalizationError, "too close"
        ):
            normalize_face_roll(
                points,
                left_eye_center_indices=(1, 2),
                right_eye_center_indices=(3, 4),
            )

    def test_normalized_coordinates_are_finite(self):
        points = {
            1: Point2D(60.0, 51.0),
            2: Point2D(80.0, 49.0),
            3: Point2D(40.0, 49.0),
            4: Point2D(20.0, 47.0),
        }
        result = normalize_face_roll(
            points,
            left_eye_center_indices=(1, 2),
            right_eye_center_indices=(3, 4),
        )

        self.assertTrue(math.isfinite(result.roll_angle_deg))
        for point in result.normalized_points.values():
            self.assertTrue(math.isfinite(point.x))
            self.assertTrue(math.isfinite(point.y))


if __name__ == "__main__":
    unittest.main()
