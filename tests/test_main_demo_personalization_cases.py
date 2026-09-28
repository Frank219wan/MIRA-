import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from src.main_demo_personalization_cases import (
    DEAD_ZONE_STATUS,
    EXPECTED_REFERENCE,
    calculate_case,
    generate_outputs,
)


def profile(tail=7.109, length=0.2123, lower=0.1413):
    return {
        "version": "0.3",
        "eye_geometry": {
            "eye_tail_angle": {"mean": tail},
            "relative_eye_length": {"mean": length},
            "lower_lid_space_ratio": {"mean": lower},
        },
    }


class MainDemoPersonalizationCasesTests(unittest.TestCase):
    def test_identity_consistency_keeps_every_reference_parameter(self):
        blogger = profile()
        result = calculate_case(
            blogger,
            blogger,
            EXPECTED_REFERENCE,
            case="identity",
        )

        self.assertEqual(
            result["A04"]["direction"]["personalized_direction_deg"],
            EXPECTED_REFERENCE["direction_relative_to_eye_axis_deg"],
        )
        self.assertEqual(
            result["A04"]["extension"]["personalized_extension_ratio"],
            EXPECTED_REFERENCE["reference_extension_ratio"],
        )
        self.assertEqual(result["A02"]["personalized_range_factor"], 1.0)
        self.assertEqual(result["A02"]["personalized_intensity_factor"], 1.0)
        self.assertEqual(result["triggered_rules"], [])

    def test_dead_zone_can_keep_reference_while_raw_result_is_preserved(self):
        blogger = profile()
        user = profile(tail=6.37, length=0.2047, lower=0.1448)

        enabled = calculate_case(
            blogger, user, EXPECTED_REFERENCE, case="face11"
        )
        disabled = calculate_case(
            blogger,
            user,
            EXPECTED_REFERENCE,
            case="face11",
            dead_zone_enabled=False,
        )

        self.assertEqual(enabled["triggered_rules"], [])
        self.assertNotEqual(
            disabled["A04"]["direction"]["personalized_direction_deg"],
            enabled["A04"]["direction"]["personalized_direction_deg"],
        )
        self.assertEqual(enabled["dead_zone_config"]["status"], DEAD_ZONE_STATUS)

    def test_rule_direction_comes_from_signed_blogger_user_difference(self):
        blogger = profile()
        user = profile(tail=11.635, length=0.1898, lower=0.1697)
        result = calculate_case(
            blogger, user, EXPECTED_REFERENCE, case="face06"
        )

        self.assertEqual(result["triggered_rules"], ["R02", "R03", "R06"])

    def test_inputs_are_not_mutated_and_output_is_strict_finite_json(self):
        blogger = profile()
        user = profile(tail=11.635, length=0.1898, lower=0.1697)
        before = copy.deepcopy((blogger, user, EXPECTED_REFERENCE))

        result = calculate_case(
            blogger, user, EXPECTED_REFERENCE, case="face06"
        )
        serialized = json.dumps(result, allow_nan=False)

        self.assertEqual((blogger, user, EXPECTED_REFERENCE), before)
        self.assertNotIn("NaN", serialized)
        self.assertNotIn("Infinity", serialized)

        def finite(value):
            if isinstance(value, dict):
                return all(finite(item) for item in value.values())
            if isinstance(value, list):
                return all(finite(item) for item in value)
            return not isinstance(value, float) or math.isfinite(value)

        self.assertTrue(finite(result))

    def test_generate_outputs_writes_all_case_artifacts(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            result = generate_outputs(
                profile(),
                {
                    "face06": profile(11.635, 0.1898, 0.1697),
                    "face11": profile(6.37, 0.2047, 0.1448),
                },
                EXPECTED_REFERENCE,
                output,
            )

            expected = {
                "face06_personalization.json",
                "face11_personalization.json",
                "face06_vs_reference.csv",
                "face11_vs_reference.csv",
                "face06_explanation.json",
                "face11_explanation.json",
                "face06_face11_summary.csv",
                "dead_zone_comparison.csv",
                "identity_consistency.json",
            }
            self.assertTrue(expected.issubset({path.name for path in output.iterdir()}))
            self.assertTrue(result["identity_consistency"]["passed"])


if __name__ == "__main__":
    unittest.main()
