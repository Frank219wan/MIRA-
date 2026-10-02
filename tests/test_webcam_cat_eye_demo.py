import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from src.webcam_cat_eye_demo import (
    WebcamSessionStateError,
    ar_landmarks_from_face_landmarks,
    assert_current_session,
    build_live_overlay_lines,
    build_session_live_guidance,
    build_webcam_session,
    format_terminal_summary,
    guidance_layers,
    preview_pixel,
    render_live_guidance,
    save_session_results,
    stable_scan_from_profiles,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "data" / "fixtures" / "main_demo"
AR_LANDMARKS = {
    "side": "right",
    "side_semantics": "subject_right",
    "input_is_mirrored": False,
    "eye_inner": {"x_norm": 0.35, "y_norm": 0.5},
    "eye_outer": {"x_norm": 0.65, "y_norm": 0.49},
    "lower_lid_path": [
        {"x_norm": 0.65, "y_norm": 0.51},
        {"x_norm": 0.58, "y_norm": 0.53},
        {"x_norm": 0.50, "y_norm": 0.54},
        {"x_norm": 0.42, "y_norm": 0.53},
        {"x_norm": 0.35, "y_norm": 0.51},
    ],
}


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def fake_face_landmarks():
    landmarks = [
        SimpleNamespace(x=0.5, y=0.5, z=0.0) for _ in range(478)
    ]
    # Subject-right eye group for an unmirrored input (image-left).
    for index, x, y in (
        (133, 0.40, 0.50),
        (33, 0.20, 0.48),
        (144, 0.20, 0.51),
        (145, 0.30, 0.53),
        (153, 0.40, 0.51),
    ):
        landmarks[index] = SimpleNamespace(x=x, y=y, z=0.0)
    # Subject-left eye group, selected for subject-right only when the pixels
    # themselves were already mirrored before landmark extraction.
    for index, x, y in (
        (362, 0.60, 0.50),
        (263, 0.80, 0.48),
        (373, 0.60, 0.51),
        (374, 0.70, 0.53),
        (380, 0.80, 0.51),
    ):
        landmarks[index] = SimpleNamespace(x=x, y=y, z=0.0)
    return landmarks


def profile_with_means(base, *, tail, length, lower):
    profile = copy.deepcopy(base)
    for group, value in (
        ("eye_tail_angle", tail),
        ("relative_eye_length", length),
        ("lower_lid_space_ratio", lower),
    ):
        profile["eye_geometry"][group].update(
            {"left": value, "right": value, "mean": value}
        )
    profile["symmetry"]["eye_tail_angle_difference"] = 0.0
    return profile


class WebcamCatEyeDemoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reference = fixture("main_demo_reference.json")
        cls.face06_profile = fixture("face_06_face_profile.json")
        cls.face11_profile = fixture("face_11_face_profile.json")
        cls.face06_expected = fixture("face_06_personalization.json")
        cls.face11_expected = fixture("face_11_personalization.json")

    def stable_profile(self, profile):
        scan = stable_scan_from_profiles(
            [copy.deepcopy(profile) for _ in range(3)]
        )
        self.assertEqual(scan["valid_frame_count"], 3)
        self.assertEqual(scan["aggregated_face_profile"]["version"], "0.3")
        return scan["aggregated_face_profile"]

    def session_from_profile(self, profile, session_id, sample_id="webcam_user"):
        return build_webcam_session(
            profile,
            self.reference,
            subject_side="right",
            valid_frame_count=3,
            target_frame_count=30,
            session_id=session_id,
            sample_id=sample_id,
        )

    def test_face06_scan_reproduces_validated_adaptation(self):
        profile = self.stable_profile(self.face06_profile)
        session = self.session_from_profile(profile, "face06-session", "face06")
        result = session.personalization

        self.assertEqual(session.reference_package["mode"], "existing_reference")
        self.assertEqual(result, self.face06_expected["source_validation_result"])
        self.assertEqual(result["triggered_rules"], ["R02", "R03", "R06"])
        guidance = build_session_live_guidance(AR_LANDMARKS, session)
        self.assertNotEqual(
            guidance["reference"]["A04"]["endpoint"],
            guidance["personalized"]["A04"]["endpoint"],
        )
        summary = session.session_summary
        self.assertIn("decreases", summary["tutorial"]["A04"]["direction_why"])
        self.assertIn("increases", summary["tutorial"]["A04"]["extension_why"])
        self.assertIn("increases", summary["tutorial"]["A02"]["why"])

    def test_face11_scan_keeps_reference_geometry(self):
        profile = self.stable_profile(self.face11_profile)
        session = self.session_from_profile(profile, "face11-session", "face11")
        result = session.personalization

        self.assertEqual(result, self.face11_expected["source_validation_result"])
        self.assertEqual(result["triggered_rules"], [])
        guidance = build_session_live_guidance(AR_LANDMARKS, session)
        for field in (
            "anchor",
            "endpoint",
            "direction_relative_to_eye_axis_deg",
            "extension_ratio",
            "start_position_ratio",
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    guidance["reference"]["A04"][field],
                    guidance["personalized"]["A04"][field],
                )

    def test_p_r_b_modes_select_the_expected_layers(self):
        session = self.session_from_profile(
            self.face06_profile, "mode-session", "face06"
        )
        guidance = build_session_live_guidance(AR_LANDMARKS, session)

        self.assertEqual(
            [name for name, _ in guidance_layers(guidance, "personalized")],
            ["personalized"],
        )
        self.assertEqual(
            [name for name, _ in guidance_layers(guidance, "reference")],
            ["reference"],
        )
        self.assertEqual(
            [name for name, _ in guidance_layers(guidance, "both")],
            ["reference", "personalized"],
        )

    def test_subject_side_is_preserved_before_display_mirroring(self):
        landmarks = fake_face_landmarks()
        raw = ar_landmarks_from_face_landmarks(
            landmarks,
            image_width=101,
            image_height=101,
            subject_side="right",
            input_is_mirrored=False,
        )
        already_mirrored = ar_landmarks_from_face_landmarks(
            landmarks,
            image_width=101,
            image_height=101,
            subject_side="right",
            input_is_mirrored=True,
        )

        self.assertEqual(raw["side_semantics"], "subject_right")
        self.assertAlmostEqual(raw["eye_inner"]["x_norm"], 0.40)
        self.assertAlmostEqual(already_mirrored["eye_inner"]["x_norm"], 0.60)
        self.assertEqual(
            preview_pixel(
                raw["eye_inner"],
                width=101,
                height=101,
                mirrored_preview=False,
            ),
            (40, 50),
        )
        self.assertEqual(
            preview_pixel(
                raw["eye_inner"],
                width=101,
                height=101,
                mirrored_preview=True,
            ),
            (60, 50),
        )

    def test_renderer_draws_each_mode_without_mutating_raw_frame(self):
        session = self.session_from_profile(
            self.face06_profile, "renderer-session", "face06"
        )
        guidance = build_session_live_guidance(AR_LANDMARKS, session)
        raw_frame = np.zeros((240, 360, 3), dtype=np.uint8)

        for mode in ("personalized", "reference", "both"):
            with self.subTest(mode=mode):
                rendered = render_live_guidance(
                    raw_frame, guidance, session, mode=mode
                )
                self.assertEqual(rendered.shape, raw_frame.shape)
                self.assertGreater(int(rendered.sum()), 0)
        self.assertEqual(int(raw_frame.sum()), 0)

    def test_keep_reference_summary_is_neutral_and_explicit(self):
        session = self.session_from_profile(
            self.face11_profile, "keep-session", "face11"
        )
        summary = session.session_summary
        terminal = format_terminal_summary(session)

        self.assertEqual(summary["decision"], "KEEP_REFERENCE")
        self.assertNotIn("beautiful", terminal.lower())
        self.assertIn("Keep Reference", summary["tutorial"]["A04"]["direction_why"])
        self.assertIn("Keep Reference", summary["tutorial"]["A04"]["extension_why"])
        self.assertIn("Keep Reference", summary["tutorial"]["A02"]["why"])
        self.assertIn("Direction:", terminal)
        self.assertIn("Range factor:", terminal)

    def test_save_writes_strict_json_only(self):
        session = self.session_from_profile(
            self.face06_profile, "save-session", "face06"
        )
        guidance = build_session_live_guidance(AR_LANDMARKS, session)
        with tempfile.TemporaryDirectory() as temporary:
            paths = save_session_results(
                temporary,
                session=session,
                guidance_snapshot=guidance,
            )

            self.assertEqual(len(paths), 4)
            self.assertEqual(
                {path.suffix for path in Path(temporary).iterdir()}, {".json"}
            )
            for path in paths:
                json.loads(
                    path.read_text(encoding="utf-8"),
                    parse_constant=lambda value: (_ for _ in ()).throw(
                        ValueError(value)
                    ),
                )

    def test_consecutive_sessions_replace_ui_and_ar_state(self):
        session_a = self.session_from_profile(
            profile_with_means(
                self.face11_profile,
                tail=3.333,
                length=0.19635,
                lower=0.15035,
            ),
            "aaaa1111-session-a",
        )
        guidance_a = build_session_live_guidance(AR_LANDMARKS, session_a)
        text_a = "\n".join(
            build_live_overlay_lines(
                session_a, guidance_a, mode="personalized"
            )
        )

        session_b = self.session_from_profile(
            profile_with_means(
                self.face11_profile,
                tail=4.4275,
                length=0.1882,
                lower=0.1703,
            ),
            "bbbb2222-session-b",
        )
        guidance_b = build_session_live_guidance(AR_LANDMARKS, session_b)
        text_b = "\n".join(
            build_live_overlay_lines(
                session_b, guidance_b, mode="personalized"
            )
        )

        self.assertIn("Mine 7.29 deg", text_a)
        self.assertIn("Mine 34.5%", text_a)
        self.assertIn("Rules: R01 / R06", text_a)
        self.assertIn("Session: aaaa1111", text_a)
        self.assertIn("Mine 6.85 deg", text_b)
        self.assertIn("Mine 38.4%", text_b)
        self.assertIn("Rules: R01 / R03 / R06", text_b)
        self.assertIn("Session: bbbb2222", text_b)
        self.assertNotIn("7.29", text_b)
        self.assertNotIn("Rules: R01 / R06", text_b)
        self.assertEqual(session_a.overlay_summary["rules"], ["R01", "R06"])
        self.assertEqual(
            session_b.overlay_summary["rules"], ["R01", "R03", "R06"]
        )
        self.assertAlmostEqual(
            session_a.overlay_summary["direction_mine_deg"], 7.292066
        )
        self.assertAlmostEqual(
            session_b.overlay_summary["direction_mine_deg"], 6.854266
        )

        a04_a = guidance_a["personalized"]["A04"]
        a04_b = guidance_b["personalized"]["A04"]
        self.assertAlmostEqual(a04_a["extension_ratio"], 0.34493)
        self.assertAlmostEqual(a04_b["extension_ratio"], 0.384410197751)
        self.assertGreater(
            a04_b["extension_length_norm"],
            a04_a["extension_length_norm"],
        )

    def test_mixed_session_guidance_is_rejected_instead_of_rendered(self):
        session_a = self.session_from_profile(
            self.face06_profile, "mismatch-a", "face06"
        )
        session_b = self.session_from_profile(
            self.face11_profile, "mismatch-b", "face11"
        )
        guidance_a = build_session_live_guidance(AR_LANDMARKS, session_a)

        with self.assertRaisesRegex(
            WebcamSessionStateError,
            "live overlay state does not match current personalization session",
        ):
            render_live_guidance(
                np.zeros((240, 360, 3), dtype=np.uint8),
                guidance_a,
                session_b,
                mode="personalized",
            )

        stale_overlay = replace(
            session_b, overlay_summary=session_a.overlay_summary
        )
        with self.assertRaisesRegex(
            WebcamSessionStateError, "overlay summary is stale"
        ):
            assert_current_session(stale_overlay)

        stale_summary_value = copy.deepcopy(session_b.session_summary)
        stale_summary_value["triggered_rules"] = list(
            session_a.overlay_summary["rules"]
        )
        stale_summary = replace(
            session_b, session_summary=stale_summary_value
        )
        with self.assertRaisesRegex(
            WebcamSessionStateError, "session summary rules are stale"
        ):
            assert_current_session(stale_summary)

    def test_consecutive_saves_cannot_mix_profile_personalization_or_ar(self):
        session_a = self.session_from_profile(
            profile_with_means(
                self.face11_profile,
                tail=3.333,
                length=0.19635,
                lower=0.15035,
            ),
            "save-session-a",
        )
        session_b = self.session_from_profile(
            profile_with_means(
                self.face11_profile,
                tail=4.4275,
                length=0.1882,
                lower=0.1703,
            ),
            "save-session-b",
        )
        guidance_a = build_session_live_guidance(AR_LANDMARKS, session_a)
        guidance_b = build_session_live_guidance(AR_LANDMARKS, session_b)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            save_session_results(
                output, session=session_a, guidance_snapshot=guidance_a
            )
            saved_a = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in output.iterdir()
            }
            save_session_results(
                output, session=session_b, guidance_snapshot=guidance_b
            )
            saved_b = {
                path.name: json.loads(path.read_text(encoding="utf-8"))
                for path in output.iterdir()
            }

            self.assertEqual(
                saved_a["stable_face_profile.json"]["eye_geometry"]
                ["eye_tail_angle"]["mean"],
                3.333,
            )
            self.assertEqual(
                saved_a["personalization.json"]["triggered_rules"],
                ["R01", "R06"],
            )
            self.assertEqual(
                saved_b["stable_face_profile.json"]["eye_geometry"]
                ["eye_tail_angle"]["mean"],
                4.4275,
            )
            self.assertEqual(
                saved_b["personalization.json"]["triggered_rules"],
                ["R01", "R03", "R06"],
            )
            self.assertAlmostEqual(
                saved_b["personalization.json"]["A04"]["direction"]
                ["personalized_direction_deg"],
                6.854266,
            )
            self.assertAlmostEqual(
                saved_b["personalization.json"]["A04"]["extension"]
                ["personalized_extension_ratio"],
                0.384410197751,
            )
            self.assertEqual(
                saved_b["ar_guidance_snapshot.json"]["session_id"],
                "save-session-b",
            )
            self.assertEqual(
                saved_b["session_summary.json"]["session"]["session_id"],
                "save-session-b",
            )
            with self.assertRaisesRegex(
                WebcamSessionStateError,
                "AR guidance uses another session_id",
            ):
                save_session_results(
                    output,
                    session=session_b,
                    guidance_snapshot=guidance_a,
                )


if __name__ == "__main__":
    unittest.main()
