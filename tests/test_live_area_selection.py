import copy
import inspect
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.live_area_selection import (
    LiveAreaSelectionError,
    LiveAreaSelectionSession,
    LiveAreaSelectionState,
    begin_freeze_selection,
    cancel_pending_selection,
    commit_pending_selection,
    display_normalized_to_raw,
    display_pixels_to_raw_polygon,
    is_simple_polygon,
    live_area_selection_payload,
    mark_live_face_lost,
    normalize_display_polygon,
    normalize_polygon,
    polygon_signed_area,
    raw_polygon_to_display_pixels,
    save_live_area_selection,
    set_pending_polygon,
    update_live_tracking,
)
from src.special_area_selector import (
    build_polygon_preview_geometry,
    polygon_key_action,
)
from src.special_area_tracking import (
    SpecialAreaLiveSessionError,
    assert_binding_matches_profile,
)
from tools.run_live_area_selection_demo import prompt_area_metadata


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
RAW_POLYGON = [
    {"x_norm": 0.25, "y_norm": 0.28},
    {"x_norm": 0.39, "y_norm": 0.28},
    {"x_norm": 0.42, "y_norm": 0.41},
    {"x_norm": 0.27, "y_norm": 0.44},
]


def configure(
    session: LiveAreaSelectionSession,
    *,
    preference: str = "KEEP",
    location: str = "subject_right_cheek",
):
    begin_freeze_selection(session, [SOURCE_LANDMARKS])
    set_pending_polygon(session, RAW_POLYGON)
    return commit_pending_selection(
        session,
        user_label="birthmark",
        location=location,
        preference=preference,
    )


class LiveAreaSelectionTests(unittest.TestCase):
    @staticmethod
    def live_preview_normalizer(points):
        normalized_raw = normalize_display_polygon(
            points,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        return raw_polygon_to_display_pixels(
            normalized_raw,
            width=101,
            height=101,
            mirrored_preview=True,
        )

    def test_unordered_live_preview_is_a_simple_normalized_polygon(self):
        clicks = [(20, 20), (80, 80), (80, 20), (20, 80)]
        preview = build_polygon_preview_geometry(
            clicks,
            normalize_for_preview=self.live_preview_normalizer,
        )
        self.assertTrue(preview.closed)
        self.assertNotEqual(preview.path_points, clicks)
        preview_raw = display_pixels_to_raw_polygon(
            preview.path_points,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        self.assertTrue(is_simple_polygon(preview_raw))

    def test_preview_and_enter_use_identical_normalized_order(self):
        clicks = [(20, 20), (80, 80), (80, 20), (20, 80)]
        preview = build_polygon_preview_geometry(
            clicks,
            normalize_for_preview=self.live_preview_normalizer,
        )
        final_raw = normalize_display_polygon(
            clicks,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        final_display = raw_polygon_to_display_pixels(
            final_raw,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        self.assertEqual(preview.path_points, final_display)
        session = LiveAreaSelectionSession(session_id="preview-final")
        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        set_pending_polygon(session, final_raw)
        self.assertEqual(session.pending_polygon, final_raw)

    def test_one_and_two_point_previews_never_close(self):
        one = build_polygon_preview_geometry(
            [(20, 20)],
            normalize_for_preview=self.live_preview_normalizer,
        )
        two = build_polygon_preview_geometry(
            [(20, 20), (80, 20)],
            normalize_for_preview=self.live_preview_normalizer,
        )
        self.assertFalse(one.closed)
        self.assertEqual(one.path_points, [])
        self.assertFalse(two.closed)
        self.assertEqual(two.path_points, [(20, 20), (80, 20)])

    def test_invalid_draft_draws_markers_without_polygon_path(self):
        collinear = [(20, 20), (50, 50), (80, 80)]
        preview = build_polygon_preview_geometry(
            collinear,
            normalize_for_preview=self.live_preview_normalizer,
        )
        self.assertEqual(preview.marker_points, collinear)
        self.assertEqual(preview.path_points, [])
        self.assertFalse(preview.closed)

    def test_mirror_raw_normalize_display_preview_round_trip(self):
        clicks = [(15, 20), (85, 75), (80, 15), (20, 80), (50, 45)]
        normalized_raw = normalize_display_polygon(
            clicks,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        display_preview = self.live_preview_normalizer(clicks)
        round_trip_raw = display_pixels_to_raw_polygon(
            display_preview,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        self.assertEqual(len(round_trip_raw), len(normalized_raw))
        for actual, expected in zip(round_trip_raw, normalized_raw):
            self.assertAlmostEqual(actual["x_norm"], expected["x_norm"])
            self.assertAlmostEqual(actual["y_norm"], expected["y_norm"])

    def test_clockwise_and_counterclockwise_polygons_remain_valid(self):
        clockwise = [
            (0.2, 0.2),
            (0.2, 0.8),
            (0.8, 0.8),
            (0.8, 0.2),
        ]
        counterclockwise = list(reversed(clockwise))
        for points in (clockwise, counterclockwise):
            with self.subTest(points=points):
                normalized = normalize_polygon(points)
                self.assertTrue(is_simple_polygon(normalized))
                self.assertGreater(abs(polygon_signed_area(normalized)), 1e-6)

    def test_bow_tie_is_reordered_into_simple_polygon(self):
        bow_tie = [
            (0.2, 0.2),
            (0.8, 0.8),
            (0.8, 0.2),
            (0.2, 0.8),
        ]
        self.assertFalse(is_simple_polygon(bow_tie))
        normalized = normalize_polygon(bow_tie)
        self.assertTrue(is_simple_polygon(normalized))
        self.assertEqual(
            {(point["x_norm"], point["y_norm"]) for point in normalized},
            set(bow_tie),
        )

    def test_polygon_still_intersecting_after_sort_is_rejected(self):
        with self.assertRaisesRegex(
            LiveAreaSelectionError, "Invalid polygon: edges intersect"
        ) as caught:
            normalize_polygon(
                [
                    (0.1, 0.1),
                    (0.3, 0.3),
                    (0.5, 0.5),
                    (0.7, 0.9),
                    (0.9, 0.7),
                ]
            )
        self.assertIn("Please redraw the area.", str(caught.exception))

    def test_duplicate_and_near_duplicate_points_are_removed(self):
        base = [
            (0.2, 0.2),
            (0.8, 0.2),
            (0.8, 0.8),
            (0.2, 0.8),
        ]
        duplicate = normalize_polygon(base + [(0.2, 0.2)])
        near_duplicate = normalize_polygon(base + [(0.20005, 0.20004)])
        self.assertEqual(len(duplicate), 4)
        self.assertEqual(len(near_duplicate), 4)
        self.assertTrue(is_simple_polygon(duplicate))
        self.assertTrue(is_simple_polygon(near_duplicate))

    def test_deduplication_must_leave_three_unique_points(self):
        with self.assertRaisesRegex(
            LiveAreaSelectionError, "At least 3 unique polygon points"
        ):
            normalize_polygon(
                [(0.2, 0.2), (0.2, 0.2), (0.8, 0.8), (0.80001, 0.80001)]
            )

    def test_collinear_and_near_zero_area_polygon_is_rejected(self):
        with self.assertRaisesRegex(
            LiveAreaSelectionError, "Area is too small or degenerate"
        ) as caught:
            normalize_polygon([(0.2, 0.2), (0.5, 0.5), (0.8, 0.8)])
        self.assertIn("Please redraw the area.", str(caught.exception))

    def test_normalization_preserves_concave_point_set_without_convex_hull(self):
        concave = [
            (0.2, 0.2),
            (0.8, 0.8),
            (0.5, 0.42),
            (0.8, 0.2),
            (0.2, 0.8),
        ]
        normalized = normalize_polygon(concave)
        self.assertEqual(len(normalized), len(concave))
        self.assertEqual(
            {(point["x_norm"], point["y_norm"]) for point in normalized},
            set(concave),
        )
        self.assertTrue(is_simple_polygon(normalized))

    def test_mirrored_display_click_converts_to_raw_coordinate(self):
        raw = display_normalized_to_raw(
            {"x_norm": 0.20, "y_norm": 0.35}, mirrored_preview=True
        )
        self.assertAlmostEqual(raw["x_norm"], 0.80)
        self.assertAlmostEqual(raw["y_norm"], 0.35)

    def test_display_pixel_y_is_unchanged(self):
        polygon = display_pixels_to_raw_polygon(
            [(20, 30), (30, 40), (40, 20)],
            width=101,
            height=101,
            mirrored_preview=True,
        )
        self.assertAlmostEqual(polygon[0]["x_norm"], 0.80)
        self.assertAlmostEqual(polygon[0]["y_norm"], 0.30)

    def test_mirrored_clicks_are_converted_before_polygon_normalization(self):
        display_bow_tie = [(20, 20), (80, 80), (80, 20), (20, 80)]
        raw = display_pixels_to_raw_polygon(
            display_bow_tie,
            width=101,
            height=101,
            mirrored_preview=True,
        )
        self.assertFalse(is_simple_polygon(raw))
        normalized = normalize_polygon(raw)
        self.assertTrue(is_simple_polygon(normalized))
        self.assertEqual(
            {
                (round(point["x_norm"], 12), round(point["y_norm"], 12))
                for point in normalized
            },
            {(0.8, 0.2), (0.2, 0.8), (0.2, 0.2), (0.8, 0.8)},
        )

    def test_polygon_requires_at_least_three_points(self):
        with self.assertRaisesRegex(LiveAreaSelectionError, "At least 3"):
            display_pixels_to_raw_polygon(
                [(20, 30), (30, 40)], width=101, height=101
            )

    def test_enter_and_space_confirm_only_with_three_points(self):
        self.assertEqual(polygon_key_action(13, 3), "confirm")
        self.assertEqual(polygon_key_action(32, 3), "confirm")
        self.assertIsNone(polygon_key_action(13, 2))
        self.assertIsNone(polygon_key_action(32, 2))
        self.assertIsNone(polygon_key_action(32, 3, allow_space=False))

    def test_escape_cancels(self):
        self.assertEqual(polygon_key_action(27, 4), "cancel")

    def test_cancel_reselection_preserves_old_active_binding(self):
        session = LiveAreaSelectionSession(session_id="cancel-reselect")
        active = configure(session)
        update_live_tracking(session, SOURCE_LANDMARKS)
        old_profile = copy.deepcopy(active.source_profile)
        old_binding = copy.deepcopy(active.tracking_binding)

        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        cancel_pending_selection(session)

        self.assertEqual(session.state, LiveAreaSelectionState.LIVE_TRACKING)
        self.assertEqual(session.selection_revision, 1)
        self.assertEqual(session.active_tracking_session.source_profile, old_profile)
        self.assertEqual(
            session.active_tracking_session.tracking_binding,
            old_binding,
        )

    def test_first_time_cancel_returns_to_unconfigured(self):
        session = LiveAreaSelectionSession(session_id="first-cancel")
        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        cancel_pending_selection(session)
        self.assertEqual(session.state, LiveAreaSelectionState.LIVE_UNCONFIGURED)
        self.assertIsNone(session.active_tracking_session)

    def test_profile_accepts_only_current_subject_side_names(self):
        for location in ("subject_left_cheek", "subject_right_cheek"):
            with self.subTest(location=location):
                session = LiveAreaSelectionSession()
                tracking = configure(session, location=location)
                self.assertEqual(
                    tracking.source_profile["areas"][0]["location"], location
                )

        legacy = LiveAreaSelectionSession()
        begin_freeze_selection(legacy, [SOURCE_LANDMARKS])
        set_pending_polygon(legacy, RAW_POLYGON)
        with self.assertRaises(LiveAreaSelectionError):
            commit_pending_selection(
                legacy,
                user_label="",
                location="right_cheek",
                preference="KEEP",
            )

    def test_all_preferences_are_preserved(self):
        for preference in ("KEEP", "BLEND", "COVER", "HIGHLIGHT"):
            with self.subTest(preference=preference):
                session = LiveAreaSelectionSession()
                tracking = configure(session, preference=preference)
                area = tracking.source_profile["areas"][0]
                self.assertEqual(area["preference"], preference)
                self.assertEqual(area["source"], "user_selected")
                self.assertEqual(area["label_source"], "user_provided")

    def test_preference_has_no_default_cover(self):
        parameter = inspect.signature(commit_pending_selection).parameters[
            "preference"
        ]
        self.assertIs(parameter.default, inspect.Parameter.empty)

        answers = iter(("", "1", "", "1"))
        label, location, preference = prompt_area_metadata(lambda _prompt: next(answers))
        self.assertEqual(label, "")
        self.assertEqual(location, "subject_left_cheek")
        self.assertEqual(preference, "KEEP")

    def test_freeze_without_face_is_rejected_without_state_change(self):
        session = LiveAreaSelectionSession()
        with self.assertRaisesRegex(LiveAreaSelectionError, "no face detected"):
            begin_freeze_selection(session, [])
        self.assertEqual(session.state, LiveAreaSelectionState.LIVE_UNCONFIGURED)

    def test_freeze_with_multiple_faces_is_rejected(self):
        session = LiveAreaSelectionSession()
        with self.assertRaisesRegex(LiveAreaSelectionError, "multiple faces"):
            begin_freeze_selection(session, [SOURCE_LANDMARKS, SOURCE_LANDMARKS])
        self.assertEqual(session.state, LiveAreaSelectionState.LIVE_UNCONFIGURED)

    def test_identity_reprojection_is_within_tolerance(self):
        session = LiveAreaSelectionSession(session_id="identity")
        configure(session)
        self.assertLessEqual(session.identity_reprojection_max_error, 1e-6)
        self.assertEqual(len(session.active_tracking_session.source_profile["areas"]), 1)

    def test_profile_receives_normalized_order_with_coordinates_unchanged(self):
        unordered = [RAW_POLYGON[index] for index in (0, 2, 1, 3)]
        session = LiveAreaSelectionSession(session_id="normalized-profile")
        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        set_pending_polygon(session, unordered)
        tracking = commit_pending_selection(
            session,
            user_label="birthmark",
            location="subject_right_cheek",
            preference="KEEP",
        )
        profile_polygon = tracking.source_profile["areas"][0]["polygon"]
        self.assertEqual(len(profile_polygon), len(unordered))
        self.assertEqual(
            {(point["x_norm"], point["y_norm"]) for point in profile_polygon},
            {(point["x_norm"], point["y_norm"]) for point in unordered},
        )
        self.assertTrue(is_simple_polygon(profile_polygon))
        self.assertLessEqual(session.identity_reprojection_max_error, 1e-6)

    def test_failed_identity_check_does_not_replace_old_selection(self):
        session = LiveAreaSelectionSession(session_id="identity-failure")
        old_active = configure(session)
        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        set_pending_polygon(session, RAW_POLYGON)

        with patch(
            "src.live_area_selection._identity_reprojection_error",
            return_value=0.01,
        ):
            with self.assertRaisesRegex(
                LiveAreaSelectionError, "Failed to bind selected area safely"
            ):
                commit_pending_selection(
                    session,
                    user_label="new",
                    location="subject_left_cheek",
                    preference="HIGHLIGHT",
                )

        self.assertIs(session.active_tracking_session, old_active)
        self.assertEqual(session.selection_revision, 1)
        self.assertEqual(session.state, LiveAreaSelectionState.FREEZE_SELECTING)

    def test_new_revision_rejects_old_binding_with_new_profile(self):
        session = LiveAreaSelectionSession(session_id="revision")
        first = configure(session, preference="KEEP")
        old_binding = copy.deepcopy(first.tracking_binding)

        begin_freeze_selection(session, [SOURCE_LANDMARKS])
        set_pending_polygon(session, RAW_POLYGON)
        second = commit_pending_selection(
            session,
            user_label="birthmark",
            location="subject_right_cheek",
            preference="BLEND",
        )

        self.assertEqual(session.selection_revision, 2)
        self.assertNotEqual(
            old_binding["source_profile_hash"],
            second.tracking_binding["source_profile_hash"],
        )
        with self.assertRaises(SpecialAreaLiveSessionError):
            assert_binding_matches_profile(old_binding, second.source_profile)

    def test_face_lost_clears_polygon_and_valid_landmarks_recover(self):
        session = LiveAreaSelectionSession()
        configure(session)
        update_live_tracking(session, SOURCE_LANDMARKS)
        self.assertTrue(session.active_tracking_session.current_live_areas)

        mark_live_face_lost(session)
        self.assertEqual(session.state, LiveAreaSelectionState.FACE_LOST)
        self.assertEqual(session.active_tracking_session.current_live_areas, [])

        update_live_tracking(session, SOURCE_LANDMARKS)
        self.assertEqual(session.state, LiveAreaSelectionState.LIVE_TRACKING)
        self.assertTrue(session.active_tracking_session.current_live_areas)

    def test_session_json_is_strict_and_contains_no_image_or_private_path(self):
        session = LiveAreaSelectionSession(session_id="strict-json")
        configure(session)
        update_live_tracking(session, SOURCE_LANDMARKS)
        payload = live_area_selection_payload(session)
        self.assertEqual(payload["selection_revision"], 1)
        self.assertEqual(
            payload["special_area_profile_hash"],
            payload["tracking_binding_profile_hash"],
        )

        with tempfile.TemporaryDirectory() as temporary:
            paths = save_live_area_selection(Path(temporary) / "output", session)
            self.assertEqual(
                {path.name for path in paths},
                {
                    "special_area_profile.json",
                    "special_area_tracking_binding.json",
                    "special_area_live_session.json",
                },
            )
            serialized = paths[-1].read_text(encoding="utf-8")
            parsed = json.loads(
                serialized,
                parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
            )
        self.assertEqual(parsed["workflow"], "live_area_selection")
        self.assertNotIn("raw_frame", serialized)
        self.assertNotIn("image_bytes", serialized)
        self.assertNotIn("/Users/", serialized)
        self.assertNotIn("wansiyu", serialized)
        self.assertTrue(math.isfinite(parsed["identity_reprojection_max_error"]))


if __name__ == "__main__":
    unittest.main()
