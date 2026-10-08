import json
import unittest

from src.special_area_profile import build_special_area, build_special_area_profile
from src.special_area_tutorial_adapter import (
    DECISION_SOURCE,
    GUIDANCE_BY_PREFERENCE,
    adapt_special_area_tutorial,
)
from tools.run_special_area_image_demo import build_session_summary


def profile_for(preference: str, label: str = "") -> dict:
    area = build_special_area(
        area_id="area_01",
        user_label=label,
        location="subject_left_cheek",
        preference=preference,
        polygon=[
            {"x_norm": 0.2, "y_norm": 0.3},
            {"x_norm": 0.4, "y_norm": 0.3},
            {"x_norm": 0.3, "y_norm": 0.5},
        ],
    )
    return build_special_area_profile("subject01_front", [area])


class SpecialAreaTutorialAdapterTests(unittest.TestCase):
    def test_all_preferences_generate_the_approved_guidance(self):
        for preference, expected_text in GUIDANCE_BY_PREFERENCE.items():
            with self.subTest(preference=preference):
                tutorial = adapt_special_area_tutorial(profile_for(preference))
                block = tutorial["guidance_blocks"][0]
                self.assertEqual(block["guidance_zh"], expected_text)
                self.assertEqual(block["preference"], preference)

    def test_keep_does_not_reverse_the_user_intent(self):
        text = adapt_special_area_tutorial(profile_for("KEEP"))["guidance_blocks"][0][
            "guidance_zh"
        ]
        self.assertNotIn("遮盖该区域", text)
        self.assertNotIn("进行局部遮盖", text)
        self.assertIn("保留该区域原有可见度", text)

    def test_blend_does_not_command_complete_cover(self):
        text = adapt_special_area_tutorial(profile_for("BLEND"))["guidance_blocks"][0][
            "guidance_zh"
        ]
        self.assertIn("不追求完全遮盖", text)
        self.assertIn("轻度均匀和边缘过渡", text)
        self.assertIn("降低它与周围肤色的视觉反差", text)
        self.assertNotIn("进行完全遮盖", text)

    def test_cover_explicitly_uses_local_cover_and_edge_transition(self):
        text = adapt_special_area_tutorial(profile_for("COVER"))["guidance_blocks"][0][
            "guidance_zh"
        ]
        self.assertIn("局部遮盖", text)
        self.assertIn("边缘过渡", text)

    def test_highlight_preserves_visibility_without_requesting_cover(self):
        text = adapt_special_area_tutorial(profile_for("HIGHLIGHT"))[
            "guidance_blocks"
        ][0]["guidance_zh"]
        self.assertIn("保留标记区域的可见度", text)
        self.assertIn("避免使用高遮盖产品覆盖", text)
        self.assertNotIn("进行局部遮盖", text)

    def test_decision_source_is_user_preference(self):
        block = adapt_special_area_tutorial(profile_for("HIGHLIGHT"))["guidance_blocks"][0]
        self.assertEqual(DECISION_SOURCE, "user_preference")
        self.assertEqual(block["decision_source"], "user_preference")

    def test_tutorial_and_summary_are_strict_private_json(self):
        profile = profile_for("BLEND", "anything else")
        payloads = (
            adapt_special_area_tutorial(profile),
            build_session_summary(profile, "subject01_front.jpg"),
        )
        for payload in payloads:
            serialized = json.dumps(payload, ensure_ascii=False, allow_nan=False)
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
            self.assertIsInstance(parsed, dict)
            self.assertNotIn("/Users/", serialized)
            self.assertNotIn("wansiyu", serialized)

    def test_adapter_supports_multiple_areas(self):
        first = profile_for("KEEP")["areas"][0]
        second = profile_for("COVER")["areas"][0]
        second["area_id"] = "area_02"
        tutorial = adapt_special_area_tutorial(
            build_special_area_profile("subject01_front", [first, second])
        )
        self.assertEqual(len(tutorial["guidance_blocks"]), 2)


if __name__ == "__main__":
    unittest.main()
