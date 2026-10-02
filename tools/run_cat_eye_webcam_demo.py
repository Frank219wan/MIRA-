"""Run the local MIRA Main Demo with the Mac default webcam."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.face_landmarker import (  # noqa: E402
    DEFAULT_MODEL_PATH,
    FaceLandmarkerDetector,
    FaceLandmarkerError,
)
from src.face_scan_aggregator import (  # noqa: E402
    MIN_VALID_FRAMES,
    FaceScanAggregator,
)
from src.personalization_engine import load_json_object  # noqa: E402
from src.webcam_cat_eye_demo import (  # noqa: E402
    WebcamDemoSession,
    WebcamSessionStateError,
    ar_landmarks_from_face_landmarks,
    assert_current_session,
    build_session_live_guidance,
    build_webcam_session,
    face_profile_from_landmarks,
    format_terminal_summary,
    render_live_guidance,
    save_session_results,
)


WINDOW_TITLE = "MIRA Cat Eye Demo"
DEFAULT_REFERENCE = (
    PROJECT_ROOT / "data" / "fixtures" / "main_demo" / "main_demo_reference.json"
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "webcam_cat_eye_demo"


class WebcamDemoRuntimeError(RuntimeError):
    """Raised for local camera/runtime failures with user-facing messages."""


def _scan_overlay(frame: Any, valid: int, target: int, message: str) -> Any:
    canvas = cv2.flip(frame, 1)
    lines = (
        "MIRA Cat Eye Demo",
        "Look at the camera",
        "Scanning your eye geometry...",
        message,
        f"Valid frames: {valid} / {target}",
        "Q quit",
    )
    for index, line in enumerate(lines):
        cv2.putText(
            canvas,
            line,
            (18, 34 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            line,
            (18, 34 + index * 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return canvas


def collect_stable_scan(
    capture: Any,
    detector: FaceLandmarkerDetector,
    *,
    target_frames: int,
    timeout_sec: float,
) -> dict[str, Any]:
    """Acquire profiles from raw frames; mirror only the displayed preview."""

    if target_frames < MIN_VALID_FRAMES:
        raise WebcamDemoRuntimeError(
            f"scan target must be at least {MIN_VALID_FRAMES}."
        )
    aggregator = FaceScanAggregator(min_valid_frames=MIN_VALID_FRAMES)
    valid = 0
    attempts = 0
    read_failures = 0
    deadline = time.monotonic() + timeout_sec
    while valid < target_frames and time.monotonic() < deadline:
        ok, raw_frame = capture.read()
        if not ok or raw_frame is None or raw_frame.size == 0:
            read_failures += 1
            if read_failures >= 10:
                raise WebcamDemoRuntimeError(
                    "Camera stopped returning frames during Face Scan."
                )
            continue
        read_failures = 0
        attempts += 1
        message = "Scanning Face... hold still"
        try:
            face_landmarks = detector.detect(raw_frame)
            height, width = raw_frame.shape[:2]
            profile = face_profile_from_landmarks(
                face_landmarks,
                image_width=width,
                image_height=height,
                frame_id=f"{attempts:04d}",
                input_is_mirrored=False,
            )
            if aggregator.add_profile(
                profile, frame_id=f"webcam_{attempts:04d}"
            ):
                valid += 1
            else:
                message = "Frame geometry was not usable; hold still..."
        except (FaceLandmarkerError, ValueError) as exc:
            aggregator.add_failure(
                frame_id=f"webcam_{attempts:04d}", reason=str(exc)
            )
            message = "Face not detected clearly; look at the camera..."
        cv2.imshow(
            WINDOW_TITLE,
            _scan_overlay(raw_frame, valid, target_frames, message),
        )
        if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
            raise KeyboardInterrupt
    if valid < MIN_VALID_FRAMES:
        raise WebcamDemoRuntimeError(
            "Not enough valid Face Profile frames: "
            f"{valid}; at least {MIN_VALID_FRAMES} are required."
        )
    if valid < target_frames:
        print(
            f"Scan timeout reached; using {valid} valid frames "
            f"(target was {target_frames})."
        )
    return aggregator.finalize()


def run_live_guidance(
    capture: Any,
    detector: FaceLandmarkerDetector,
    *,
    session: WebcamDemoSession,
    output_dir: Path,
) -> None:
    assert_current_session(session)
    mode = "personalized"
    latest_guidance: dict[str, Any] | None = None
    consecutive_read_failures = 0
    while True:
        ok, raw_frame = capture.read()
        if not ok or raw_frame is None or raw_frame.size == 0:
            consecutive_read_failures += 1
            if consecutive_read_failures >= 10:
                raise WebcamDemoRuntimeError(
                    "Camera stopped returning frames during Live Guidance."
                )
            continue
        consecutive_read_failures = 0
        display = cv2.flip(raw_frame, 1)
        try:
            face_landmarks = detector.detect(raw_frame)
            height, width = raw_frame.shape[:2]
            ar_landmarks = ar_landmarks_from_face_landmarks(
                face_landmarks,
                image_width=width,
                image_height=height,
                subject_side=session.subject_side,
                input_is_mirrored=False,
            )
            latest_guidance = build_session_live_guidance(
                ar_landmarks, session
            )
            display = render_live_guidance(
                raw_frame,
                latest_guidance,
                session,
                mode=mode,
                mirrored_preview=True,
            )
        except (FaceLandmarkerError, ValueError):
            cv2.putText(
                display,
                "Face not detected - keep your eye visible",
                (18, 38),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.65,
                (0, 0, 255),
                2,
                cv2.LINE_AA,
            )
        cv2.imshow(WINDOW_TITLE, display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            return
        if key in (ord("p"), ord("P")):
            mode = "personalized"
        elif key in (ord("r"), ord("R")):
            mode = "reference"
        elif key in (ord("b"), ord("B")):
            mode = "both"
        elif key in (ord("s"), ord("S")):
            if latest_guidance is None:
                print("Nothing saved: no valid AR guidance frame yet.")
                continue
            paths = save_session_results(
                output_dir,
                session=session,
                guidance_snapshot=latest_guidance,
            )
            print("Saved JSON session:")
            for path in paths:
                print(f"  {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--scan-target", type=int, default=30)
    parser.add_argument("--scan-timeout", type=float, default=20.0)
    parser.add_argument("--side", choices=("left", "right"), default="right")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        capture.release()
        print(
            "MIRA Webcam Demo failed: could not open the default camera. "
            "Check macOS Camera permission for Terminal/Python.",
            file=sys.stderr,
        )
        return 1
    try:
        reference_fixture = load_json_object(args.reference)
        if reference_fixture.get("reference_id") != "cat_eye_main_demo":
            raise WebcamDemoRuntimeError(
                "Expected reference_id cat_eye_main_demo."
            )
        with FaceLandmarkerDetector(
            model_path=args.model, max_faces=1
        ) as detector:
            scan = collect_stable_scan(
                capture,
                detector,
                target_frames=args.scan_target,
                timeout_sec=args.scan_timeout,
            )
            stable_profile = scan["aggregated_face_profile"]
            session = build_webcam_session(
                stable_profile,
                reference_fixture,
                subject_side=args.side,
                valid_frame_count=scan["valid_frame_count"],
                target_frame_count=args.scan_target,
            )
            print(format_terminal_summary(session))
            print(
                "\nLIVE GUIDANCE — P personalized | R reference | "
                "B both | S save | Q quit"
            )
            run_live_guidance(
                capture,
                detector,
                session=session,
                output_dir=args.output,
            )
    except KeyboardInterrupt:
        print("MIRA Webcam Demo canceled.")
        return 0
    except (
        OSError,
        ValueError,
        FaceLandmarkerError,
        WebcamSessionStateError,
        WebcamDemoRuntimeError,
    ) as exc:
        print(f"MIRA Webcam Demo failed: {exc}", file=sys.stderr)
        return 1
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
