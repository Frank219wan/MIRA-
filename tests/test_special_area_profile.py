import json
import math
import tempfile
import unittest
from pathlib import Path

from src.special_area_profile import (
    SpecialAreaProfileError,
    VALID_PREFERENCES,
    build_special_area,
    build_special_area_profile,
    normalize_pixel_polygon,
    save_strict_json,
)


def valid_polygon() -> list[dict[str, float]]:
    return [
        {"x_norm": 0.20, "y_norm": 0.30},
        {"x_norm": 0.40, "y_norm": 0.30},
        {"x_norm": 0.30, "y_norm": 0.50},
    ]


def valid_area(preference: str = "KEEP", user_label: str = "birthmark") -> dict:
    return build_special_area(
        area_id="area_01",
        user_label=user_label,
        location="subject_left_cheek",
        preference=preference,
        polygon=valid_polygon(),
    )


class SpecialAreaProfileTests(unittest.TestCase):
    def test_all_four_preferences_are_valid(self):
        for preference in VALID_PREFERENCES:
            with self.subTest(preference=preference):
                profile = build_special_area_profile(
                    "subject01_front", [valid_area(preference)]
                )
                self.assertEqual(profile["areas"][0]["preference"], preference)

    def test_invalid_preference_is_rejected(self):
        with self.assertRaisesRegex(SpecialAreaProfileError, "preference"):
            valid_area("AUTO_COVER")

    def test_subject_left_and_right_cheek_locations_are_valid(self):
        for location in ("subject_left_cheek", "subject_right_cheek"):
            with self.subTest(location=location):
                area = build_special_area(
                    area_id="area_01",
                    user_label="",
                    location=location,
                    preference="KEEP",
                    polygon=valid_polygon(),
                )
                profile = build_special_area_profile("subject01_front", [area])
                self.assertEqual(profile["areas"][0]["location"], location)

    def test_legacy_ambiguous_cheek_locations_are_rejected(self):
        for location in ("left_cheek", "right_cheek"):
            with self.subTest(location=location):
                with self.assertRaisesRegex(SpecialAreaProfileError, "location"):
                    build_special_area(
                        area_id="area_01",
                        user_label="",
                        location=location,
                        preference="KEEP",
                        polygon=valid_polygon(),
                    )

    def test_polygon_with_fewer_than_three_points_is_rejected(self):
        with self.assertRaisesRegex(SpecialAreaProfileError, "at least 3"):
            build_special_area(
                area_id="area_01",
                user_label="",
                location="other",
                preference="KEEP",
                polygon=valid_polygon()[:2],
            )

    def test_out_of_range_and_non_finite_coordinates_are_rejected(self):
        for invalid in (-0.01, 1.01, float("nan"), float("inf")):
            polygon = valid_polygon()
            polygon[0] = {"x_norm": invalid, "y_norm": 0.3}
            with self.subTest(value=invalid):
                with self.assertRaises(SpecialAreaProfileError):
                    build_special_area(
                        area_id="area_01",
                        user_label="",
                        location="other",
                        preference="KEEP",
                        polygon=polygon,
                    )

    def test_empty_user_label_is_allowed_and_is_user_provided(self):
        area = valid_area(user_label="")
        self.assertEqual(area["user_label"], "")
        self.assertEqual(area["label_source"], "user_provided")

    def test_label_source_must_be_user_provided(self):
        area = valid_area()
        area["label_source"] = "inferred"
        with self.assertRaisesRegex(SpecialAreaProfileError, "label_source"):
            build_special_area_profile("subject01_front", [area])

    def test_pixel_polygon_is_normalized_by_full_dimensions(self):
        polygon = normalize_pixel_polygon([(10, 20), (30, 20), (20, 40)], 100, 200)
        self.assertEqual(polygon[0], {"x_norm": 0.1, "y_norm": 0.1})

    def test_multiple_areas_are_supported(self):
        first = valid_area()
        second = valid_area("BLEND")
        second["area_id"] = "area_02"
        profile = build_special_area_profile("subject01_front", [first, second])
        self.assertEqual(len(profile["areas"]), 2)

    def test_strict_json_has_no_non_finite_values_or_private_paths(self):
        profile = build_special_area_profile("subject01_front", [valid_area()])
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "special_area_profile.json"
            save_strict_json(output, profile)
            serialized = output.read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        self.assertTrue(math.isfinite(parsed["areas"][0]["polygon"][0]["x_norm"]))
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("wansiyu", serialized)


if __name__ == "__main__":
    unittest.main()
