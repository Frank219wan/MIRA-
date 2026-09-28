import math
import unittest

from src.face_geometry import (
    EyeGeometry,
    Point2D,
    angle_at_vertex_deg,
    calculate_brow_eye_geometry,
    calculate_eye_asymmetry,
    calculate_eye_geometry,
    calculate_eye_spacing,
    calculate_lower_lid_space,
    calculate_relative_eye_length,
    euclidean_distance,
    eye_tail_angle_deg,
)


class FaceGeometryTests(unittest.TestCase):
    def test_euclidean_distance_uses_both_axes(self):
        self.assertEqual(
            euclidean_distance(Point2D(0.0, 0.0), Point2D(3.0, 4.0)),
            5.0,
        )

    def test_eye_dimensions_and_aspect_ratio_are_positive(self):
        geometry = calculate_eye_geometry(
            inner_corner=Point2D(4.0, 1.0),
            outer_corner=Point2D(0.0, 4.0),
            upper_lid=Point2D(2.0, 1.0),
            lower_lid=Point2D(2.0, 3.0),
        )
        self.assertGreater(geometry.width_px, 0)
        self.assertGreater(geometry.height_px, 0)
        self.assertAlmostEqual(geometry.width_px, 5.0)
        self.assertAlmostEqual(geometry.aspect_ratio, 0.4)

    def test_eye_spacing_ratio_is_positive(self):
        spacing = calculate_eye_spacing(
            left_inner_corner=Point2D(7.0, 1.0),
            right_inner_corner=Point2D(3.0, 1.0),
            left_eye_width_px=4.0,
            right_eye_width_px=6.0,
        )
        self.assertGreater(spacing.eye_spacing_ratio, 0)
        self.assertAlmostEqual(spacing.inner_eye_distance_px, 4.0)
        self.assertAlmostEqual(spacing.mean_eye_width_px, 5.0)
        self.assertAlmostEqual(spacing.eye_spacing_ratio, 0.8)

    def test_horizontal_eye_axis_is_zero_degrees(self):
        angle = eye_tail_angle_deg(Point2D(1.0, 2.0), Point2D(5.0, 2.0))
        self.assertAlmostEqual(angle, 0.0)

    def test_upward_eye_tail_is_positive_in_image_coordinates(self):
        angle = eye_tail_angle_deg(Point2D(1.0, 3.0), Point2D(5.0, 2.0))
        self.assertGreater(angle, 0.0)

    def test_downward_eye_tail_is_negative_in_image_coordinates(self):
        angle = eye_tail_angle_deg(Point2D(1.0, 2.0), Point2D(5.0, 3.0))
        self.assertLess(angle, 0.0)

    def test_identical_eye_values_have_zero_asymmetry(self):
        eye = EyeGeometry(width_px=20.0, height_px=8.0, aspect_ratio=0.4)
        result = calculate_eye_asymmetry(eye, eye, 5.0, 5.0)
        self.assertEqual(result.eye_width_asymmetry, 0.0)
        self.assertEqual(result.eye_height_asymmetry, 0.0)
        self.assertEqual(result.eye_aspect_ratio_asymmetry, 0.0)
        self.assertEqual(result.eye_tail_angle_difference_deg, 0.0)

    def test_brow_eye_ratio_is_positive(self):
        result = calculate_brow_eye_geometry(
            brow_points=(
                Point2D(1.0, 0.0),
                Point2D(2.0, -0.2),
                Point2D(3.0, 0.0),
            ),
            inner_corner=Point2D(0.0, 2.0),
            outer_corner=Point2D(4.0, 2.0),
            eye_width_px=4.0,
        )
        self.assertGreater(result.distance_px, 0.0)
        self.assertGreater(result.ratio, 0.0)

    def test_relative_eye_length_is_positive_and_scale_invariant(self):
        left = EyeGeometry(width_px=40.0, height_px=10.0, aspect_ratio=0.25)
        right = EyeGeometry(width_px=42.0, height_px=11.0, aspect_ratio=11 / 42)
        result = calculate_relative_eye_length(
            left,
            right,
            Point2D(0.0, 0.0),
            Point2D(200.0, 0.0),
        )
        scaled = calculate_relative_eye_length(
            EyeGeometry(80.0, 20.0, 0.25),
            EyeGeometry(84.0, 22.0, 11 / 42),
            Point2D(0.0, 0.0),
            Point2D(400.0, 0.0),
        )
        self.assertGreater(result.relative_eye_length_left, 0.0)
        self.assertAlmostEqual(
            result.relative_eye_length_left,
            scaled.relative_eye_length_left,
        )
        self.assertAlmostEqual(
            result.relative_eye_length_mean,
            scaled.relative_eye_length_mean,
        )

    def test_lower_lid_space_ratio_uses_multiple_pairs(self):
        result = calculate_lower_lid_space(
            (
                Point2D(0.0, 0.0),
                Point2D(1.0, 0.0),
                Point2D(2.0, 0.0),
            ),
            (
                Point2D(0.0, 2.0),
                Point2D(1.0, 3.0),
                Point2D(2.0, 4.0),
            ),
            eye_width_px=12.0,
        )
        self.assertEqual(len(result.segment_distances_px), 3)
        self.assertAlmostEqual(result.space_px, 3.0)
        self.assertGreater(result.ratio, 0.0)

    def test_angle_at_vertex_is_finite_and_bounded(self):
        angle = angle_at_vertex_deg(
            Point2D(0.0, 0.0),
            Point2D(1.0, 0.0),
            Point2D(0.0, 1.0),
        )
        self.assertTrue(math.isfinite(angle))
        self.assertGreater(angle, 0.0)
        self.assertLessEqual(angle, 180.0)


if __name__ == "__main__":
    unittest.main()
