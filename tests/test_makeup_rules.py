import unittest

from src.makeup_rules import (
    RULE_REGISTRY,
    apply_eyeliner_direction,
    apply_eyeliner_extension,
    apply_lower_lid_intensity,
    apply_lower_lid_range,
)


class MakeupRulesTests(unittest.TestCase):
    def test_lower_eye_tail_angle_produces_larger_upward_correction(self):
        lower = apply_eyeliner_direction(2.0, 10.0)
        higher = apply_eyeliner_direction(12.0, 10.0)

        self.assertGreater(lower["adjustment_value"], higher["adjustment_value"])
        self.assertGreater(lower["personalized_value"], higher["personalized_value"])

    def test_lower_relative_eye_length_produces_larger_extension(self):
        shorter = apply_eyeliner_extension(0.18, 1.0)
        longer = apply_eyeliner_extension(0.22, 1.0)

        self.assertGreater(shorter["adjustment_value"], longer["adjustment_value"])
        self.assertGreater(shorter["personalized_value"], longer["personalized_value"])

    def test_lower_lid_space_produces_smaller_range_and_intensity(self):
        smaller_range = apply_lower_lid_range(0.13, 1.0)
        larger_range = apply_lower_lid_range(0.17, 1.0)
        smaller_intensity = apply_lower_lid_intensity(0.13, 1.0)
        larger_intensity = apply_lower_lid_intensity(0.17, 1.0)

        self.assertLess(
            smaller_range["personalized_value"],
            larger_range["personalized_value"],
        )
        self.assertLess(
            smaller_intensity["personalized_value"],
            larger_intensity["personalized_value"],
        )

    def test_only_r01_through_r06_are_active(self):
        active = {
            rule_id
            for rule_id, rule in RULE_REGISTRY.items()
            if rule["status"] == "active"
        }

        self.assertEqual(active, {f"R{index:02d}" for index in range(1, 7)})
        self.assertEqual(RULE_REGISTRY["R07"]["status"], "validation_only")
        self.assertEqual(RULE_REGISTRY["R08"]["status"], "validation_only")
        self.assertEqual(RULE_REGISTRY["R09"]["status"], "candidate")
        self.assertEqual(RULE_REGISTRY["R10"]["status"], "candidate")


if __name__ == "__main__":
    unittest.main()
