import json
import math
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "data" / "fixtures" / "main_demo"
EXPECTED_FILES = {
    "face_06_face_profile.json",
    "face_06_personalization.json",
    "face_11_face_profile.json",
    "face_11_personalization.json",
    "main_demo_reference.json",
}
PROFILE_KEYS = {
    "version",
    "sample_id",
    "source_type",
    "eye_geometry",
    "symmetry",
    "raw_geometry_reference",
    "confidence",
}
EYE_GEOMETRY_KEYS = {
    "eye_tail_angle",
    "eye_spacing_ratio",
    "relative_eye_length",
    "eye_width_height_ratio",
    "brow_eye_ratio",
    "lower_lid_space_ratio",
    "inner_corner_angle",
}
FORBIDDEN_TEXT = (
    "/" + "Users/",
    "wansiyu",
    ".jpg",
    ".jpeg",
    ".png",
    "data:image",
    ";base64,",
)


def load_fixture(name):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def all_finite(value):
    if isinstance(value, dict):
        return all(all_finite(item) for item in value.values())
    if isinstance(value, list):
        return all(all_finite(item) for item in value)
    return not isinstance(value, float) or math.isfinite(value)


class MainDemoFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = load_fixture("main_demo_reference.json")
        cls.face06_profile = load_fixture("face_06_face_profile.json")
        cls.face11_profile = load_fixture("face_11_face_profile.json")
        cls.face06 = load_fixture("face_06_personalization.json")
        cls.face11 = load_fixture("face_11_personalization.json")

    def test_all_expected_json_files_strictly_parse(self):
        self.assertEqual(
            {path.name for path in FIXTURE_DIR.glob("*.json")}, EXPECTED_FILES
        )
        for filename in EXPECTED_FILES:
            with self.subTest(filename=filename):
                parsed = json.loads(
                    (FIXTURE_DIR / filename).read_text(encoding="utf-8"),
                    parse_constant=lambda value: self.fail(
                        f"Non-standard JSON constant {value} in {filename}"
                    ),
                )
                self.assertIsInstance(parsed, dict)
                self.assertTrue(all_finite(parsed))

    def test_profiles_preserve_complete_v03_contract(self):
        for sample_id, profile in (
            ("face_06", self.face06_profile),
            ("face_11", self.face11_profile),
        ):
            with self.subTest(sample_id=sample_id):
                self.assertEqual(profile["version"], "0.3")
                self.assertEqual(profile["sample_id"], sample_id)
                self.assertEqual(profile["source_type"], "safe_fixture")
                self.assertTrue(PROFILE_KEYS.issubset(profile))
                self.assertEqual(set(profile["eye_geometry"]), EYE_GEOMETRY_KEYS)
                self.assertEqual(
                    profile["raw_geometry_reference"], {"source": "safe_fixture"}
                )

    def test_face06_matches_validated_multi_adaptation_case(self):
        self.assertEqual(self.face06["triggered_rules"], ["R02", "R03", "R06"])
        self.assertEqual(self.face06["mode"], "reference_relative")
        self.assertAlmostEqual(
            self.face06["A04"]["reference_direction"], 5.781666
        )
        self.assertAlmostEqual(
            self.face06["A04"]["personalized_direction"], 3.971266
        )
        self.assertAlmostEqual(
            self.face06["A04"]["reference_extension_ratio"], 0.344930
        )
        self.assertAlmostEqual(
            self.face06["A04"]["personalized_extension_ratio"],
            0.381788996540,
        )
        self.assertAlmostEqual(
            self.face06["A02"]["personalized_range_factor"],
            1.156646442361,
        )
        self.assertAlmostEqual(
            self.face06["A02"]["personalized_intensity_factor"],
            1.102787187839,
        )

    def test_face11_keeps_reference_and_preserves_raw_relative_values(self):
        self.assertEqual(self.face11["triggered_rules"], [])
        self.assertEqual(self.face11["decision"], "KEEP_REFERENCE")
        self.assertTrue(
            all(
                item["inside_dead_zone"]
                for item in self.face11["feature_decisions"]
            )
        )
        a04 = self.face11["A04"]
        a02 = self.face11["A02"]
        reference_a04 = self.reference["reference_action"]["A04"]
        reference_a02 = self.reference["reference_action"]["A02"]
        self.assertEqual(
            a04["personalized_direction"],
            reference_a04["direction_relative_to_eye_axis_deg"],
        )
        self.assertEqual(
            a04["personalized_extension_ratio"],
            reference_a04["reference_extension_ratio"],
        )
        self.assertEqual(
            a04["start_position_ratio"],
            reference_a04["start_position_ratio"],
        )
        self.assertEqual(
            a02["personalized_range_factor"], reference_a02["range_factor"]
        )
        self.assertEqual(
            a02["personalized_intensity_factor"],
            reference_a02["intensity_factor"],
        )
        self.assertNotEqual(a04["raw_relative_direction_adjustment"], 0.0)
        self.assertNotEqual(a04["raw_relative_extension_factor"], 1.0)
        self.assertNotEqual(a02["raw_relative_range_factor"], 1.0)
        self.assertNotEqual(a02["raw_relative_intensity_factor"], 1.0)

    def test_complete_source_validation_result_is_retained(self):
        for result in (self.face06, self.face11):
            source = result["source_validation_result"]
            self.assertEqual(source["triggered_rules"], result["triggered_rules"])
            self.assertEqual(
                source["A04"]["direction"]["personalized_direction_deg"],
                result["A04"]["personalized_direction"],
            )
            self.assertEqual(
                source["A04"]["extension"][
                    "personalized_extension_ratio"
                ],
                result["A04"]["personalized_extension_ratio"],
            )
            self.assertEqual(
                source["A02"]["personalized_range_factor"],
                result["A02"]["personalized_range_factor"],
            )
            self.assertEqual(
                source["A02"]["personalized_intensity_factor"],
                result["A02"]["personalized_intensity_factor"],
            )

    def test_each_feature_decision_has_product_fields(self):
        required = {
            "feature",
            "blogger_value",
            "user_value",
            "signed_difference",
            "threshold",
            "inside_dead_zone",
            "triggered_rule",
            "effect",
        }
        for result in (self.face06, self.face11):
            self.assertEqual(len(result["feature_decisions"]), 3)
            for decision in result["feature_decisions"]:
                self.assertTrue(required.issubset(decision))

    def test_fixtures_contain_no_private_paths_or_image_payloads(self):
        for path in FIXTURE_DIR.glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for token in FORBIDDEN_TEXT:
                with self.subTest(path=path.name, token=token):
                    self.assertNotIn(token.lower(), text.lower())


if __name__ == "__main__":
    unittest.main()
