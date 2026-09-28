import json
import math
import tempfile
import unittest
from pathlib import Path

from src.eye_local_profile import (
    EyeLocalKeypoints,
    EyeLocalProfileError,
    build_eye_local_profile,
    save_eye_local_profile,
)
from src.face_geometry import Point2D


def keypoints() -> EyeLocalKeypoints:
    return EyeLocalKeypoints(
        eye_inner=Point2D(10.0, 20.0),
        eye_outer=Point2D(50.0, 16.0),
        eye_upper=Point2D(30.0, 12.0),
        eye_lower=Point2D(30.0, 28.0),
        inner_upper=Point2D(14.0, 16.0),
        inner_lower=Point2D(15.0, 24.0),
        brow_references=(
            Point2D(15.0, 5.0),
            Point2D(30.0, 2.0),
            Point2D(45.0, 4.0),
        ),
        lower_lid_points=(
            Point2D(20.0, 25.0),
            Point2D(30.0, 28.0),
            Point2D(40.0, 24.0),
        ),
        lower_lid_references=(
            Point2D(20.0, 31.0),
            Point2D(30.0, 34.0),
            Point2D(40.0, 30.0),
        ),
    )


def transform(
    value: EyeLocalKeypoints, *, scale: float = 1.0, dx: float = 0.0, dy: float = 0.0
) -> EyeLocalKeypoints:
    def point(item: Point2D) -> Point2D:
        return Point2D(item.x * scale + dx, item.y * scale + dy)

    def group(items):
        return tuple(point(item) for item in items) if items is not None else None

    return EyeLocalKeypoints(
        eye_inner=point(value.eye_inner),
        eye_outer=point(value.eye_outer),
        eye_upper=point(value.eye_upper),
        eye_lower=point(value.eye_lower),
        inner_upper=point(value.inner_upper),
        inner_lower=point(value.inner_lower),
        brow_references=group(value.brow_references),
        lower_lid_points=group(value.lower_lid_points),
        lower_lid_references=group(value.lower_lid_references),
    )


def profile(points: EyeLocalKeypoints, source_type: str = "user_face") -> dict:
    return build_eye_local_profile(points, source_type=source_type, side="right")


class EyeLocalProfileTests(unittest.TestCase):
    def test_tutorial_and_user_sources_share_identical_geometry(self):
        tutorial = profile(keypoints(), "tutorial_reference")
        user = profile(keypoints(), "user_face")
        self.assertEqual(tutorial["geometry"], user["geometry"])

    def test_uniform_scale_preserves_normalized_geometry(self):
        original = profile(keypoints())["geometry"]
        scaled = profile(transform(keypoints(), scale=3.5))["geometry"]
        for name in (
            "eye_width_height_ratio",
            "inner_corner_angle_deg",
            "lower_lid_space_ratio_local",
            "brow_eye_ratio_local",
        ):
            with self.subTest(name=name):
                self.assertAlmostEqual(original[name], scaled[name], places=5)

    def test_translation_preserves_normalized_geometry(self):
        original = profile(keypoints())["geometry"]
        moved = profile(transform(keypoints(), dx=123.0, dy=-47.0))["geometry"]
        for name in (
            "eye_width_height_ratio",
            "inner_corner_angle_deg",
            "lower_lid_space_ratio_local",
            "brow_eye_ratio_local",
        ):
            with self.subTest(name=name):
                self.assertAlmostEqual(original[name], moved[name], places=5)

    def test_invalid_eye_width_has_clear_error(self):
        points = keypoints()
        invalid = EyeLocalKeypoints(
            eye_inner=points.eye_inner,
            eye_outer=points.eye_inner,
            eye_upper=points.eye_upper,
            eye_lower=points.eye_lower,
            inner_upper=points.inner_upper,
            inner_lower=points.inner_lower,
        )
        with self.assertRaisesRegex(EyeLocalProfileError, "Eye width|eye width"):
            profile(invalid)

    def test_optional_brow_and_lower_lid_are_null(self):
        points = keypoints()
        optional_missing = EyeLocalKeypoints(
            eye_inner=points.eye_inner,
            eye_outer=points.eye_outer,
            eye_upper=points.eye_upper,
            eye_lower=points.eye_lower,
            inner_upper=points.inner_upper,
            inner_lower=points.inner_lower,
        )
        geometry = profile(optional_missing)["geometry"]
        self.assertIsNone(geometry["brow_eye_ratio_local"])
        self.assertIsNone(geometry["lower_lid_space_ratio_local"])

    def test_partial_lower_lid_group_is_rejected(self):
        points = keypoints()
        invalid = EyeLocalKeypoints(
            eye_inner=points.eye_inner,
            eye_outer=points.eye_outer,
            eye_upper=points.eye_upper,
            eye_lower=points.eye_lower,
            inner_upper=points.inner_upper,
            inner_lower=points.inner_lower,
            lower_lid_points=points.lower_lid_points,
        )
        with self.assertRaisesRegex(EyeLocalProfileError, "both be present"):
            profile(invalid)

    def test_saved_json_is_strict_and_finite(self):
        result = profile(keypoints())
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "eye_local_profile.json"
            save_eye_local_profile(path, result)
            serialized = path.read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        self.assertEqual(parsed["version"], "0.1")
        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)
        for value in parsed["geometry"].values():
            self.assertTrue(value is None or math.isfinite(value))


if __name__ == "__main__":
    unittest.main()
