import json
import math
import tempfile
import unittest
from pathlib import Path

from src.reference_action_geometry import (
    ReferenceActionGeometryError,
    build_reference_action_geometry,
    save_reference_action_geometry,
)


def points() -> dict:
    return {
        "eye_inner": {"x": 0, "y": 0},
        "eye_outer": {"x": 100, "y": 0},
        "eyeliner_tip": {"x": 120, "y": -20},
    }


def transform(annotation: dict, *, angle_deg: float = 0, scale: float = 1) -> dict:
    angle = math.radians(angle_deg)
    cosine, sine = math.cos(angle), math.sin(angle)
    return {
        name: {
            "x": scale * (point["x"] * cosine - point["y"] * sine),
            "y": scale * (point["x"] * sine + point["y"] * cosine),
        }
        for name, point in annotation.items()
    }


class ReferenceActionGeometryTests(unittest.TestCase):
    def test_horizontal_eye_axis_extension_and_upward_direction(self):
        geometry = build_reference_action_geometry(points())["geometry"]

        self.assertAlmostEqual(geometry["eye_width_px"], 100.0)
        self.assertAlmostEqual(
            geometry["eyeliner_extension_ratio"], math.sqrt(800) / 100, places=6
        )
        self.assertAlmostEqual(geometry["direction_relative_to_eye_axis_deg"], 45.0)
        self.assertIsNone(geometry["start_position_ratio"])

    def test_joint_rotation_preserves_relative_direction(self):
        original = build_reference_action_geometry(points())["geometry"]
        rotated = build_reference_action_geometry(
            transform(points(), angle_deg=5)
        )["geometry"]

        self.assertAlmostEqual(
            original["direction_relative_to_eye_axis_deg"],
            rotated["direction_relative_to_eye_axis_deg"],
            places=5,
        )

    def test_upward_is_positive_when_outer_corner_is_screen_left(self):
        annotation = {
            "eye_inner": {"x": 100, "y": 0},
            "eye_outer": {"x": 0, "y": 0},
            "eyeliner_tip": {"x": -20, "y": -20},
        }

        geometry = build_reference_action_geometry(annotation)["geometry"]
        rotated = build_reference_action_geometry(
            transform(annotation, angle_deg=5)
        )["geometry"]

        self.assertAlmostEqual(geometry["direction_relative_to_eye_axis_deg"], 45.0)
        self.assertAlmostEqual(
            rotated["direction_relative_to_eye_axis_deg"], 45.0, places=5
        )

    def test_downward_is_negative_for_either_eye_side(self):
        rightward = points()
        rightward["eyeliner_tip"] = {"x": 120, "y": 20}
        leftward = {
            "eye_inner": {"x": 100, "y": 0},
            "eye_outer": {"x": 0, "y": 0},
            "eyeliner_tip": {"x": -20, "y": 20},
        }

        for annotation in (rightward, leftward):
            with self.subTest(annotation=annotation):
                result = build_reference_action_geometry(annotation)
                self.assertAlmostEqual(
                    result["geometry"]["direction_relative_to_eye_axis_deg"],
                    -45.0,
                )

    def test_uniform_scale_preserves_extension_ratio(self):
        original = build_reference_action_geometry(points())["geometry"]
        scaled = build_reference_action_geometry(
            transform(points(), scale=2)
        )["geometry"]

        self.assertAlmostEqual(
            original["eyeliner_extension_ratio"],
            scaled["eyeliner_extension_ratio"],
            places=5,
        )

    def test_start_position_is_eye_axis_projection_with_perpendicular_offset(self):
        annotation = points()
        annotation["eyeliner_start"] = {"x": 75, "y": 20}

        geometry = build_reference_action_geometry(annotation)["geometry"]

        self.assertEqual(geometry["start_position_ratio"], 0.75)

    def test_start_projection_and_extension_are_scale_and_rotation_invariant(self):
        annotation = points()
        annotation["eyeliner_start"] = {"x": 75, "y": 20}
        original = build_reference_action_geometry(annotation)["geometry"]

        for kwargs in ({"scale": 2}, {"angle_deg": 17}, {"scale": 0.5, "angle_deg": -12}):
            with self.subTest(kwargs=kwargs):
                transformed = build_reference_action_geometry(
                    transform(annotation, **kwargs)
                )["geometry"]
                self.assertAlmostEqual(
                    transformed["start_position_ratio"], original["start_position_ratio"]
                )
                self.assertAlmostEqual(
                    transformed["eyeliner_extension_ratio"],
                    original["eyeliner_extension_ratio"],
                )

    def test_missing_required_points_have_clear_errors(self):
        for name in ("eye_inner", "eye_outer", "eyeliner_tip"):
            annotation = points()
            annotation.pop(name)
            with self.subTest(name=name):
                with self.assertRaisesRegex(ReferenceActionGeometryError, name):
                    build_reference_action_geometry(annotation)

    def test_degenerate_eye_width_is_rejected(self):
        annotation = points()
        annotation["eye_outer"] = {"x": 1e-9, "y": 0}

        with self.assertRaisesRegex(ReferenceActionGeometryError, "eye width"):
            build_reference_action_geometry(annotation)

    def test_start_ratio_and_strict_finite_json(self):
        annotation = points()
        annotation["eyeliner_start"] = {"x": 75, "y": 0}
        result = build_reference_action_geometry(annotation)

        self.assertEqual(result["geometry"]["start_position_ratio"], 0.75)
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "reference.json"
            save_reference_action_geometry(path, result)
            serialized = path.read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        self.assertEqual(parsed["version"], "0.1")
        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)


if __name__ == "__main__":
    unittest.main()
