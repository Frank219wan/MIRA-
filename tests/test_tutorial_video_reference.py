import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from src.tutorial_video_reference import (
    TutorialVideoReferenceError,
    extract_frame,
    extract_reference_frames,
)
from src.personalization_engine import load_json_object
from src.reference_action_geometry import build_reference_action_geometry
from src.reference_package import (
    ReferencePackageError,
    build_reference_package,
    package_existing_reference,
    personalize_reference_package,
    save_reference_package,
)


ROOT = Path(__file__).resolve().parents[1]
MAIN_DEMO = ROOT / "data" / "fixtures" / "main_demo"


def write_synthetic_video(path: Path, *, fps: float = 5.0, frames: int = 5):
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24)
    )
    if not writer.isOpened():
        raise RuntimeError("Synthetic video writer is unavailable.")
    try:
        for index in range(frames):
            frame = np.full((24, 32, 3), index * 40, dtype=np.uint8)
            cv2.circle(frame, (4 + index, 8), 2, (0, 255, 0), -1)
            writer.write(frame)
    finally:
        writer.release()


class TutorialVideoReferenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.video = Path(self.temporary.name) / "synthetic.avi"
        write_synthetic_video(self.video)

    def tearDown(self):
        self.temporary.cleanup()

    def test_extracts_requested_frame_and_three_frame_bundle(self):
        first = extract_frame(self.video, 0.0)
        third = extract_frame(self.video, 0.4)
        self.assertEqual(first.shape, (24, 32, 3))
        self.assertGreater(float(third.mean()), float(first.mean()) + 40.0)

        result = extract_reference_frames(
            self.video,
            before_timestamp=0.0,
            a04_action_timestamp=0.4,
            after_timestamp=0.8,
            video_id="synthetic_demo",
        )
        self.assertEqual(set(result["frames"]), {"before", "A04", "after"})
        self.assertEqual(result["metadata"]["source_type"], "video")
        self.assertEqual(result["metadata"]["video_filename"], "synthetic.avi")
        self.assertEqual(result["metadata"]["video_id"], "synthetic_demo")

    def test_negative_timestamp_is_rejected(self):
        with self.assertRaisesRegex(TutorialVideoReferenceError, "greater than"):
            extract_frame(self.video, -0.1)

    def test_timestamp_at_or_beyond_duration_is_rejected(self):
        for timestamp in (1.0, 2.0):
            with self.subTest(timestamp=timestamp):
                with self.assertRaisesRegex(
                    TutorialVideoReferenceError, "outside video duration"
                ):
                    extract_frame(self.video, timestamp)

    def test_missing_or_bad_video_is_rejected(self):
        with self.assertRaisesRegex(TutorialVideoReferenceError, "does not exist"):
            extract_frame(Path(self.temporary.name) / "missing.avi", 0.0)
        broken = Path(self.temporary.name) / "broken.avi"
        broken.write_text("not a video", encoding="utf-8")
        with self.assertRaisesRegex(TutorialVideoReferenceError, "Could not open"):
            extract_frame(broken, 0.0)

    def test_timestamps_must_be_ordered(self):
        with self.assertRaisesRegex(TutorialVideoReferenceError, "before <= A04"):
            extract_reference_frames(
                self.video,
                before_timestamp=0.4,
                a04_action_timestamp=0.2,
                after_timestamp=0.8,
            )

    def test_video_reference_package_is_strict_portable_json(self):
        profile = load_json_object(MAIN_DEMO / "face_06_face_profile.json")
        private_directory = "/" + "Users/private"
        reference = build_reference_action_geometry(
            {
                "eye_inner": {"x": 20, "y": 20},
                "eye_outer": {"x": 80, "y": 18},
                "eyeliner_tip": {"x": 100, "y": 12},
                "eyeliner_start": {"x": 76, "y": 18},
            },
            reference_id="synthetic_video_reference",
            source_image=private_directory + "/tutorial.jpg",
        )
        package = build_reference_package(
            tutorial_id="synthetic_video_reference",
            video_filename=private_directory + "/tutorial.mp4",
            timestamps={"before_sec": 0.0, "A04_sec": 0.4, "after_sec": 0.8},
            blogger_face_profile=profile,
            reference_action_geometry=reference,
            after_frame_available=True,
        )
        output = Path(self.temporary.name) / "reference_package.json"
        save_reference_package(output, package)
        serialized = output.read_text(encoding="utf-8")
        parsed = json.loads(
            serialized,
            parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
        )

        self.assertEqual(parsed["schema_version"], "0.1")
        self.assertEqual(parsed["mode"], "video_reference")
        self.assertEqual(parsed["source"]["video_filename"], "tutorial.mp4")
        self.assertEqual(parsed["blogger_face_profile"]["version"], "0.3")
        self.assertIn("A04", parsed["reference_actions"])
        self.assertNotIn("/" + "Users/", serialized)
        self.assertNotIn("tutorial.jpg", serialized)

    def test_existing_reference_package_reproduces_face06_and_face11(self):
        reference_fixture = load_json_object(
            MAIN_DEMO / "main_demo_reference.json"
        )
        package = package_existing_reference(reference_fixture)
        for sample_id in ("face_06", "face_11"):
            with self.subTest(sample_id=sample_id):
                profile = load_json_object(
                    MAIN_DEMO / f"{sample_id}_face_profile.json"
                )
                fixture = load_json_object(
                    MAIN_DEMO / f"{sample_id}_personalization.json"
                )
                result = personalize_reference_package(
                    package, profile, sample_id=sample_id
                )
                self.assertEqual(result, fixture["source_validation_result"])

    def test_reference_package_rejects_private_profile_content(self):
        profile = load_json_object(MAIN_DEMO / "face_06_face_profile.json")
        profile["note"] = "/" + "Users/private/source"
        reference = build_reference_action_geometry(
            {
                "eye_inner": {"x": 20, "y": 20},
                "eye_outer": {"x": 80, "y": 18},
                "eyeliner_tip": {"x": 100, "y": 12},
                "eyeliner_start": {"x": 76, "y": 18},
            }
        )
        with self.assertRaisesRegex(ReferencePackageError, "non-portable"):
            build_reference_package(
                tutorial_id="private",
                video_filename="tutorial.mp4",
                timestamps={
                    "before_sec": 0.0,
                    "A04_sec": 0.4,
                    "after_sec": 0.8,
                },
                blogger_face_profile=profile,
                reference_action_geometry=reference,
                after_frame_available=True,
            )


if __name__ == "__main__":
    unittest.main()
