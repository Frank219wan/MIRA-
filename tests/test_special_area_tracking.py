import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from src.special_area_profile import build_special_area, build_special_area_profile
from src.special_area_tracking import (
    TRACKING_ACTIVE,
    TRACKING_FACE_LOST,
    SpecialAreaLiveSessionError,
    SpecialAreaTrackingError,
    build_live_session,
    build_tracking_binding,
    live_session_payload,
    mark_face_lost,
    normalized_to_display_pixel,
    project_tracking_binding,
    save_live_session_json,
    update_live_session,
)
from tools.run_special_area_webcam_demo import LIVE_GUIDANCE


SOURCE_LANDMARKS = [
    (0.18, 0.20),
    (0.34, 0.19),
    (0.47, 0.24),
    (0.50, 0.39),
    (0.39, 0.50),
    (0.23, 0.49),
    (0.14, 0.35),
    (0.29, 0.29),
    (0.41, 0.34),
    (0.30, 0.43),
]


def profile_for(preference: str = "KEEP", location: str = "subject_right_cheek"):
    area = build_special_area(
        area_id="area_01",
        user_label="birthmark",
        location=location,
        preference=preference,
        polygon=[
            {"x_norm": 0.25, "y_norm": 0.28},
            {"x_norm": 0.39, "y_norm": 0.28},
            {"x_norm": 0.42, "y_norm": 0.41},
            {"x_norm": 0.27, "y_norm": 0.44},
        ],
    )
    return build_special_area_profile("subject01_front", [area])


def transform_landmarks(transform):
    return [transform(x, y) for x, y in SOURCE_LANDMARKS]


class SpecialAreaTrackingTests(unittest.TestCase):
    def setUp(self):
        self.profile = profile_for()
        self.binding = build_tracking_binding(
            self.profile, SOURCE_LANDMARKS, neighbor_count=10
        )

    def assert_polygon_close(self, actual, expected, places=8):
        self.assertEqual(len(actual), len(expected))
        for actual_point, expected_point in zip(actual, expected):
            self.assertAlmostEqual(
                actual_point["x_norm"], expected_point["x_norm"], places=places
            )
            self.assertAlmostEqual(
                actual_point["y_norm"], expected_point["y_norm"], places=places
            )

    def test_identity_reprojection_matches_source_polygon(self):
        projected = project_tracking_binding(
            self.binding, SOURCE_LANDMARKS, source_profile=self.profile
        )
        self.assert_polygon_close(
            projected[0]["polygon"], self.profile["areas"][0]["polygon"]
        )
        for point in self.binding["areas"][0]["points"]:
            self.assertEqual(len(set(point["landmark_indices"])), 3)
            self.assertAlmostEqual(sum(point["weights"]), 1.0)

    def test_translation_moves_polygon_by_the_same_offset(self):
        dx, dy = 0.08, 0.05
        live = transform_landmarks(lambda x, y: (x + dx, y + dy))
        projected = project_tracking_binding(self.binding, live)[0]["polygon"]
        expected = [
            {"x_norm": point["x_norm"] + dx, "y_norm": point["y_norm"] + dy}
            for point in self.profile["areas"][0]["polygon"]
        ]
        self.assert_polygon_close(projected, expected)

    def test_uniform_scale_scales_polygon(self):
        scale = 1.25
        live = transform_landmarks(lambda x, y: (x * scale, y * scale))
        projected = project_tracking_binding(self.binding, live)[0]["polygon"]
        expected = [
            {
                "x_norm": point["x_norm"] * scale,
                "y_norm": point["y_norm"] * scale,
            }
            for point in self.profile["areas"][0]["polygon"]
        ]
        self.assert_polygon_close(projected, expected)

    def test_rotation_rotates_polygon(self):
        angle = math.radians(17.0)
        center_x, center_y = 0.35, 0.35

        def rotate(x, y):
            offset_x, offset_y = x - center_x, y - center_y
            return (
                center_x + math.cos(angle) * offset_x - math.sin(angle) * offset_y,
                center_y + math.sin(angle) * offset_x + math.cos(angle) * offset_y,
            )

        live = transform_landmarks(rotate)
        projected = project_tracking_binding(self.binding, live)[0]["polygon"]
        expected = [
            dict(zip(("x_norm", "y_norm"), rotate(point["x_norm"], point["y_norm"])))
            for point in self.profile["areas"][0]["polygon"]
        ]
        self.assert_polygon_close(projected, expected)

    def test_local_deformation_uses_saved_barycentric_weights(self):
        live = list(SOURCE_LANDMARKS)
        point_binding = self.binding["areas"][0]["points"][0]
        offsets = ((0.02, 0.00), (0.00, 0.03), (-0.01, 0.01))
        for index, offset in zip(point_binding["landmark_indices"], offsets):
            x, y = live[index]
            live[index] = (x + offset[0], y + offset[1])
        expected_x = sum(
            weight * live[index][0]
            for index, weight in zip(
                point_binding["landmark_indices"], point_binding["weights"]
            )
        )
        expected_y = sum(
            weight * live[index][1]
            for index, weight in zip(
                point_binding["landmark_indices"], point_binding["weights"]
            )
        )
        projected = project_tracking_binding(self.binding, live)[0]["polygon"][0]
        self.assertAlmostEqual(projected["x_norm"], expected_x)
        self.assertAlmostEqual(projected["y_norm"], expected_y)

    def test_degenerate_triangle_candidates_are_rejected(self):
        collinear = [(0.1 + index * 0.05, 0.2) for index in range(10)]
        with self.assertRaisesRegex(SpecialAreaTrackingError, "non-degenerate"):
            build_tracking_binding(self.profile, collinear, neighbor_count=10)

    def test_nan_and_infinity_are_rejected(self):
        for invalid in (float("nan"), float("inf")):
            source = list(SOURCE_LANDMARKS)
            source[0] = (invalid, 0.2)
            with self.subTest(stage="source", invalid=invalid):
                with self.assertRaisesRegex(SpecialAreaTrackingError, "finite"):
                    build_tracking_binding(self.profile, source)

            live = list(SOURCE_LANDMARKS)
            selected_index = self.binding["areas"][0]["points"][0][
                "landmark_indices"
            ][0]
            live[selected_index] = (invalid, 0.2)
            with self.subTest(stage="live", invalid=invalid):
                with self.assertRaisesRegex(SpecialAreaTrackingError, "finite"):
                    project_tracking_binding(self.binding, live)

    def test_polygon_needs_at_least_three_points(self):
        malformed = copy.deepcopy(self.profile)
        malformed["areas"][0]["polygon"] = malformed["areas"][0]["polygon"][:2]
        with self.assertRaisesRegex(ValueError, "at least 3"):
            build_tracking_binding(malformed, SOURCE_LANDMARKS)

    def test_all_preferences_preserve_user_metadata(self):
        for preference in ("KEEP", "BLEND", "COVER", "HIGHLIGHT"):
            with self.subTest(preference=preference):
                profile = profile_for(preference)
                binding = build_tracking_binding(profile, SOURCE_LANDMARKS)
                projected = project_tracking_binding(binding, SOURCE_LANDMARKS)[0]
                self.assertEqual(projected["preference"], preference)
                self.assertEqual(projected["user_label"], "birthmark")
                self.assertEqual(projected["location"], "subject_right_cheek")

    def test_live_guidance_matches_each_frozen_preference(self):
        self.assertEqual(
            LIVE_GUIDANCE,
            {
                "KEEP": (
                    "Keep visible",
                    "Avoid heavy coverage",
                    "Blend edges only",
                ),
                "BLEND": (
                    "Light blending",
                    "Reduce contrast",
                    "Do not fully cover",
                ),
                "COVER": (
                    "Apply locally",
                    "Build coverage gradually",
                    "Blend edges",
                ),
                "HIGHLIGHT": (
                    "Keep visible",
                    "Avoid high coverage",
                    "Integrate with the overall look",
                ),
            },
        )

    def test_display_mirror_does_not_change_subject_side(self):
        session = build_live_session(
            self.profile,
            self.binding,
            source_image_identifier="subject01_front",
            session_id="mirror-session",
        )
        update_live_session(session, SOURCE_LANDMARKS)
        raw_point = session.current_live_areas[0]["polygon"][0]
        raw_pixel = normalized_to_display_pixel(
            raw_point, width=101, height=101, mirrored_preview=False
        )
        mirrored_pixel = normalized_to_display_pixel(
            raw_point, width=101, height=101, mirrored_preview=True
        )
        self.assertEqual(raw_pixel[0] + mirrored_pixel[0], 100)
        self.assertEqual(
            session.current_live_areas[0]["location"], "subject_right_cheek"
        )
        self.assertEqual(
            session.tracking_binding["areas"][0]["location"],
            "subject_right_cheek",
        )

    def test_source_profile_hash_mismatch_is_rejected(self):
        changed_profile = profile_for("COVER")
        with self.assertRaisesRegex(
            SpecialAreaLiveSessionError, "profile hash mismatch"
        ):
            build_live_session(
                changed_profile,
                self.binding,
                source_image_identifier="subject01_front",
            )

    def test_face_lost_clears_the_previous_polygon(self):
        session = build_live_session(
            self.profile,
            self.binding,
            source_image_identifier="subject01_front",
            session_id="face-lost-session",
        )
        update_live_session(session, SOURCE_LANDMARKS)
        self.assertEqual(session.tracking_status, TRACKING_ACTIVE)
        self.assertTrue(session.current_live_areas)
        mark_face_lost(session)
        self.assertEqual(session.tracking_status, TRACKING_FACE_LOST)
        self.assertEqual(session.current_live_areas, [])

    def test_saved_session_is_strict_metadata_only(self):
        session = build_live_session(
            self.profile,
            self.binding,
            source_image_identifier="subject01_front",
            session_id="save-session",
        )
        update_live_session(session, SOURCE_LANDMARKS)
        payload = live_session_payload(session)
        self.assertEqual(payload["session_id"], "save-session")
        self.assertEqual(payload["smoothing"], {"enabled": False, "alpha": None})
        self.assertNotIn("frame", payload)
        with tempfile.TemporaryDirectory() as temporary:
            path = save_live_session_json(Path(temporary) / "session.json", session)
            serialized = path.read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        self.assertEqual(parsed["tracking_status"], TRACKING_ACTIVE)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("wansiyu", serialized)


if __name__ == "__main__":
    unittest.main()
