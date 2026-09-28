import copy
import json
import math
import unittest

from src.makeup_rules import (
    LinearCalibration,
    RuleCalibration,
    apply_eyeliner_direction,
    apply_eyeliner_extension,
)
from src.reference_action_adapter import (
    build_standard_recipe,
    personalize_reference_recipe,
)
from src.reference_action_geometry import build_reference_action_geometry
from src.reference_relative_personalization import (
    ReferenceRelativePersonalizationError,
    calculate_reference_relative_a04,
    personalize_reference_relative,
    personalize_reference_with_mode,
)


def profile(tail: float = 8.0, length: float = 0.20, lower: float = 0.15) -> dict:
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": tail},
            "relative_eye_length": {"mean": length},
            "lower_lid_space_ratio": {"mean": lower},
        },
    }


def reference() -> dict:
    return build_reference_action_geometry(
        {
            "eye_inner": {"x": 0, "y": 0},
            "eye_outer": {"x": 100, "y": 0},
            "eyeliner_tip": {"x": 120, "y": -20},
            "eyeliner_start": {"x": 80, "y": 10},
        }
    )


def recipe() -> dict:
    return {
        "recipe_id": "cat_eye_standard_v0",
        "target_effect": "cat_eye",
        "actions": [
            {
                "action_id": "A04",
                "parameters": {
                    "direction_angle_deg": 10.0,
                    "extension_factor": 1.0,
                    "target_region": "outer_third",
                },
            },
            {
                "action_id": "A02",
                "parameters": {"range_factor": 1.0, "intensity_factor": 1.0},
            },
        ],
    }


class ReferenceRelativePersonalizationTests(unittest.TestCase):
    def test_identity_consistency(self):
        same = profile(tail=8.5, length=0.199)
        result = personalize_reference_relative(same, same, reference(), recipe())
        a04 = result["A04"]

        self.assertEqual(a04["direction"]["relative_adjustment_deg"], 0.0)
        self.assertEqual(
            a04["direction"]["personalized_direction_deg"],
            a04["reference"]["direction_deg"],
        )
        self.assertEqual(a04["extension"]["relative_adaptation_factor"], 1.0)
        self.assertEqual(
            a04["extension"]["personalized_extension_ratio"],
            a04["reference"]["extension_ratio"],
        )

    def test_direction_is_user_correction_minus_blogger_correction(self):
        blogger = profile(tail=9.0)
        user = profile(tail=6.0)
        result = personalize_reference_relative(blogger, user, reference(), recipe())
        direction = result["A04"]["direction"]
        expected_blogger = apply_eyeliner_direction(9.0, 0.0)["adjustment_value"]
        expected_user = apply_eyeliner_direction(6.0, 0.0)["adjustment_value"]

        self.assertEqual(direction["blogger_correction_deg"], expected_blogger)
        self.assertEqual(direction["user_correction_deg"], expected_user)
        self.assertAlmostEqual(
            direction["relative_adjustment_deg"],
            expected_user - expected_blogger,
            places=6,
        )

    def test_extension_is_user_factor_divided_by_blogger_factor(self):
        blogger = profile(length=0.19)
        user = profile(length=0.21)
        result = personalize_reference_relative(blogger, user, reference(), recipe())
        extension = result["A04"]["extension"]
        blogger_factor = apply_eyeliner_extension(0.19, 1.0)["adjustment_value"]
        user_factor = apply_eyeliner_extension(0.21, 1.0)["adjustment_value"]

        self.assertEqual(extension["blogger_adaptation_factor"], blogger_factor)
        self.assertEqual(extension["user_adaptation_factor"], user_factor)
        self.assertAlmostEqual(
            extension["relative_adaptation_factor"],
            user_factor / blogger_factor,
            places=11,
        )

    def test_absolute_mode_is_exact_existing_output(self):
        blogger = profile(tail=9.0, length=0.19)
        user = profile(tail=6.0, length=0.21)
        expected = personalize_reference_recipe(
            user, build_standard_recipe(recipe(), reference())
        )

        actual = personalize_reference_with_mode(
            blogger, user, reference(), recipe(), mode="absolute"
        )

        self.assertEqual(actual, expected)

    def test_inputs_are_not_mutated(self):
        inputs = (profile(), profile(7.0, 0.21), reference(), recipe())
        before = copy.deepcopy(inputs)

        personalize_reference_relative(*inputs)

        self.assertEqual(inputs, before)

    def test_nonpositive_blogger_extension_factor_fails_clearly(self):
        invalid_calibration = RuleCalibration(
            eyeliner_extension_multiplier=LinearCalibration(
                feature_low=0.17,
                feature_high=0.23,
                output_at_low=0.0,
                output_at_high=0.0,
            )
        )
        reference_parameters = {
            "direction_relative_to_eye_axis_deg": 30.0,
            "reference_extension_ratio": 0.35,
            "start_position_ratio": 0.95,
        }

        with self.assertRaisesRegex(
            ReferenceRelativePersonalizationError, "greater than zero"
        ):
            calculate_reference_relative_a04(
                profile(),
                profile(),
                reference_parameters,
                calibration=invalid_calibration,
            )

    def test_output_is_strict_finite_json(self):
        result = personalize_reference_relative(
            profile(), profile(7.0, 0.21), reference(), recipe()
        )
        serialized = json.dumps(result, allow_nan=False)
        parsed = json.loads(
            serialized,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )

        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)

        def finite(value):
            if isinstance(value, dict):
                return all(finite(item) for item in value.values())
            if isinstance(value, list):
                return all(finite(item) for item in value)
            return not isinstance(value, float) or math.isfinite(value)

        self.assertTrue(finite(parsed))


if __name__ == "__main__":
    unittest.main()
