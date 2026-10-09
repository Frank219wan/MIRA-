"""Select one Special Area from a frozen webcam frame, then track it live."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Mapping, Sequence
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
from src.live_area_selection import (  # noqa: E402
    LiveAreaSelectionError,
    LiveAreaSelectionSession,
    LiveAreaSelectionState,
    begin_freeze_selection,
    cancel_pending_selection,
    commit_pending_selection,
    mark_live_face_lost,
    normalize_display_polygon,
    quit_live_area_selection,
    raw_polygon_to_display_pixels,
    retry_pending_polygon,
    save_live_area_selection,
    set_pending_polygon,
    update_live_tracking,
)
from src.special_area_profile import (  # noqa: E402
    VALID_LOCATIONS,
    VALID_PREFERENCES,
    SpecialAreaProfileError,
)
from src.special_area_selector import (  # noqa: E402
    PolygonSelectionOutcome,
    SpecialAreaSelectionError,
    render_polygon_selection_preview,
    select_polygon_with_outcome,
)
from src.special_area_tracking import (  # noqa: E402
    SpecialAreaLiveSessionError,
    SpecialAreaTrackingError,
)
from tools.run_special_area_webcam_demo import (  # noqa: E402
    SpecialAreaWebcamRuntimeError,
    render_special_area_live,
)


WINDOW_TITLE = "MIRA — LIVE AREA SELECTION"
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT / "data" / "output" / "special_area_live_selection"
)
SELECTION_INSTRUCTIONS = (
    "MIRA - SELECT AREA",
    "Click 3+ points around the area",
    "ENTER / SPACE confirm",
    "U / BACKSPACE undo",
    "C clear",
    "ESC cancel | Q quit",
)
LOCATION_DISPLAY_LABELS = {
    "subject_left_cheek": "subject_left_cheek  - your left cheek",
    "subject_right_cheek": "subject_right_cheek - your right cheek",
}


class LiveAreaSelectionRuntimeError(RuntimeError):
    """Raised for camera or local UI failures."""


def _draw_lines(canvas: Any, lines: Sequence[str]) -> None:
    for index, line in enumerate(lines):
        y = 30 + index * 26
        cv2.putText(
            canvas,
            line,
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 0, 0),
            4,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas,
            line,
            (16, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )


def render_unconfigured(raw_frame: Any, notice: str = "") -> Any:
    """Render the initial camera state; no face geometry is computed here."""

    if raw_frame is None or not hasattr(raw_frame, "size") or raw_frame.size == 0:
        raise LiveAreaSelectionRuntimeError("Camera frame is empty.")
    canvas = cv2.flip(raw_frame, 1)
    lines = [
        "MIRA - LIVE AREA SELECTION",
        "Tracking: NOT CONFIGURED",
        "Press F to freeze frame and select area",
        "Q = quit",
    ]
    if notice:
        lines.append(notice)
    _draw_lines(canvas, lines)
    return canvas


def _choose_required(
    prompt: str,
    choices: Sequence[str],
    *,
    input_fn: Callable[[str], str] = input,
    display_labels: Mapping[str, str] | None = None,
) -> str:
    """Require an explicit listed choice; there is deliberately no default."""

    while True:
        print(prompt)
        for index, choice in enumerate(choices, start=1):
            shown = display_labels.get(choice, choice) if display_labels else choice
            print(f"{index}. {shown}")
        answer = input_fn("> ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        for choice in choices:
            if answer == choice or answer.upper() == choice.upper():
                return choice
        print("Please enter a listed number or value.")


def prompt_area_metadata(
    input_fn: Callable[[str], str] = input,
) -> tuple[str, str, str]:
    """Collect label, subject-relative location, and explicit preference."""

    user_label = input_fn("Optional label for this area:\n> ").strip()
    location = _choose_required(
        "Where is this area?",
        VALID_LOCATIONS,
        input_fn=input_fn,
        display_labels=LOCATION_DISPLAY_LABELS,
    )
    preference = _choose_required(
        "How would you like MIRA to treat this area?",
        VALID_PREFERENCES,
        input_fn=input_fn,
    )
    return user_label, location, preference


def select_from_frozen_frame(
    frozen_raw_frame: Any,
    detected_faces: Sequence[Sequence[Any]],
    workflow: LiveAreaSelectionSession,
    *,
    input_fn: Callable[[str], str] = input,
) -> PolygonSelectionOutcome:
    """Complete one in-memory selection, retrying unsafe polygon bindings."""

    begin_freeze_selection(workflow, detected_faces)
    mirrored_freeze = cv2.flip(frozen_raw_frame, 1)
    height, width = frozen_raw_frame.shape[:2]

    def normalized_preview_points(
        display_points: Sequence[tuple[int, int]],
    ) -> list[tuple[int, int]]:
        normalized_raw = normalize_display_polygon(
            display_points,
            width=width,
            height=height,
            mirrored_preview=True,
        )
        return raw_polygon_to_display_pixels(
            normalized_raw,
            width=width,
            height=height,
            mirrored_preview=True,
        )

    while True:
        outcome = select_polygon_with_outcome(
            mirrored_freeze,
            window_title=WINDOW_TITLE,
            instruction_lines=SELECTION_INSTRUCTIONS,
            allow_space=True,
            normalize_for_preview=normalized_preview_points,
        )
        if outcome.action == "quit":
            quit_live_area_selection(workflow)
            return outcome
        if outcome.action == "cancel":
            cancel_pending_selection(workflow)
            return outcome

        try:
            normalized_raw_polygon = normalize_display_polygon(
                outcome.points,
                width=width,
                height=height,
                mirrored_preview=True,
            )
            # set_pending_polygon repeats the authoritative validation before
            # Profile construction; a valid draft preview never bypasses it.
            set_pending_polygon(workflow, normalized_raw_polygon)
            normalized_polygon = workflow.pending_polygon or []
            normalized_display_points = raw_polygon_to_display_pixels(
                normalized_polygon,
                width=width,
                height=height,
                mirrored_preview=True,
            )
            status = f"Polygon normalized: {len(normalized_polygon)} points"
            preview = render_polygon_selection_preview(
                mirrored_freeze,
                normalized_display_points,
                status=status,
            )
            cv2.imshow(WINDOW_TITLE, preview)
            cv2.waitKey(1)
            print(status)
            user_label, location, preference = prompt_area_metadata(input_fn)
            commit_pending_selection(
                workflow,
                user_label=user_label,
                location=location,
                preference=preference,
            )
        except (
            LiveAreaSelectionError,
            SpecialAreaProfileError,
            SpecialAreaSelectionError,
            SpecialAreaTrackingError,
            SpecialAreaLiveSessionError,
        ) as exc:
            if workflow.state != LiveAreaSelectionState.FREEZE_SELECTING:
                retry_pending_polygon(workflow)
            message = str(exc)
            print(message, file=sys.stderr)
            if "Please redraw the area." not in message:
                print("Please redraw the area.", file=sys.stderr)
            continue
        return outcome


def run_demo(
    capture: Any,
    detector: FaceLandmarkerDetector,
    *,
    output_dir: Path,
) -> None:
    """Run the explicit live-selection state machine on raw camera frames."""

    workflow = LiveAreaSelectionSession()
    debug_enabled = False
    guidance_visible = True
    notice = ""
    consecutive_read_failures = 0

    while workflow.state != LiveAreaSelectionState.QUIT:
        ok, raw_frame = capture.read()
        if not ok or raw_frame is None or raw_frame.size == 0:
            consecutive_read_failures += 1
            if consecutive_read_failures >= 10:
                raise LiveAreaSelectionRuntimeError(
                    "Camera stopped returning frames."
                )
            continue
        consecutive_read_failures = 0
        active = workflow.active_tracking_session
        live_landmarks = None

        if active is None:
            display = render_unconfigured(raw_frame, notice)
        else:
            try:
                faces = detector.detect_all(raw_frame)
                if len(faces) != 1:
                    mark_live_face_lost(workflow)
                else:
                    live_landmarks = faces[0]
                    update_live_tracking(workflow, live_landmarks)
            except (FaceLandmarkerError, SpecialAreaTrackingError):
                mark_live_face_lost(workflow)
                live_landmarks = None
            display = render_special_area_live(
                raw_frame,
                active,
                live_landmarks=live_landmarks,
                mirrored_preview=True,
                debug_enabled=debug_enabled,
                guidance_visible=guidance_visible,
                controls_text=(
                    "Q quit | S save JSON | D debug | P guidance | F reselect"
                ),
                notice_text=notice,
            )

        cv2.imshow(WINDOW_TITLE, display)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q")):
            quit_live_area_selection(workflow)
            continue
        if key in (ord("f"), ord("F")):
            frozen_raw_frame = raw_frame.copy()
            had_active_selection = workflow.active_tracking_session is not None
            try:
                frozen_faces = detector.detect_all(frozen_raw_frame)
                outcome = select_from_frozen_frame(
                    frozen_raw_frame,
                    frozen_faces,
                    workflow,
                )
                if outcome.action == "confirm":
                    notice = ""
                    print(
                        "Live area active: "
                        f"revision {workflow.selection_revision}; "
                        "identity reprojection error "
                        f"{workflow.identity_reprojection_max_error:.3g}"
                    )
                elif outcome.action == "cancel":
                    notice = (
                        "Selection cancelled; previous area restored."
                        if had_active_selection
                        else "Selection cancelled; tracking is not configured."
                    )
            except LiveAreaSelectionError as exc:
                notice = str(exc)
                print(notice)
            continue

        if active is None:
            continue
        if key in (ord("d"), ord("D")):
            debug_enabled = not debug_enabled
        elif key in (ord("p"), ord("P")):
            guidance_visible = not guidance_visible
        elif key in (ord("s"), ord("S")):
            paths = save_live_area_selection(output_dir, workflow)
            print("Saved JSON metadata only:")
            for path in paths:
                print(f"  {path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera-index", type=int, default=0)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    capture = cv2.VideoCapture(args.camera_index)
    if not capture.isOpened():
        capture.release()
        print(
            "Live Area Selection failed: could not open the camera. Check macOS "
            "Camera permission for Terminal/Python.",
            file=sys.stderr,
        )
        return 1
    try:
        with FaceLandmarkerDetector(model_path=args.model, max_faces=2) as detector:
            print("LIVE AREA SELECTION - F freeze/select | Q quit")
            run_demo(capture, detector, output_dir=args.output)
    except KeyboardInterrupt:
        print("Live Area Selection canceled.")
        return 0
    except (
        OSError,
        ValueError,
        FaceLandmarkerError,
        LiveAreaSelectionError,
        LiveAreaSelectionRuntimeError,
        SpecialAreaProfileError,
        SpecialAreaSelectionError,
        SpecialAreaTrackingError,
        SpecialAreaLiveSessionError,
        SpecialAreaWebcamRuntimeError,
    ) as exc:
        print(f"Live Area Selection failed: {exc}", file=sys.stderr)
        return 1
    finally:
        capture.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
