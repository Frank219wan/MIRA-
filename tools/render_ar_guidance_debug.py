"""Render reference and personalized A04 guidance over a local image."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import cv2


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ar_guidance import ARGuidanceError, build_a04_guidance  # noqa: E402
from src.personalization_engine import load_json_object  # noqa: E402


FIXTURE_DIR = PROJECT_ROOT / "data" / "fixtures" / "main_demo"


class ARGuidanceRenderError(ValueError):
    """Raised when a debug input cannot be rendered."""


def _pixel(point: Mapping[str, Any], width: int, height: int) -> tuple[int, int]:
    return (
        round(float(point["x_norm"]) * (width - 1)),
        round(float(point["y_norm"]) * (height - 1)),
    )


def render_debug(
    image: Any,
    reference_guidance: Mapping[str, Any],
    personalized_guidance: Mapping[str, Any],
) -> Any:
    """Draw reference in yellow and personalized guidance in magenta."""

    if image is None or image.size == 0:
        raise ARGuidanceRenderError("Debug image is empty.")
    canvas = image.copy()
    height, width = canvas.shape[:2]
    specs = (
        (reference_guidance, (0, 220, 255), "reference"),
        (personalized_guidance, (255, 80, 220), "personalized"),
    )
    for guidance, color, label in specs:
        anchor = _pixel(guidance["anchor"], width, height)
        endpoint = _pixel(guidance["endpoint"], width, height)
        cv2.arrowedLine(canvas, anchor, endpoint, color, 2, tipLength=0.18)
        cv2.circle(canvas, anchor, 4, color, -1)
        cv2.putText(
            canvas,
            label,
            (endpoint[0] + 4, endpoint[1] - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument(
        "--landmarks",
        type=Path,
        required=True,
        help="JSON with side, eye_inner, and eye_outer normalized points.",
    )
    parser.add_argument("--sample", choices=("face_06", "face_11"), required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data" / "output" / "ar_guidance_debug.jpg",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
        if image is None:
            raise ARGuidanceRenderError(f"Could not read image: {args.image}")
        landmarks_payload = load_json_object(args.landmarks)
        side = landmarks_payload.get("side")
        if not isinstance(side, str):
            raise ARGuidanceRenderError("Landmarks JSON must include side.")
        reference = load_json_object(
            FIXTURE_DIR / "main_demo_reference.json"
        )["reference_action"]["A04"]
        personalization = load_json_object(
            FIXTURE_DIR / f"{args.sample}_personalization.json"
        )
        reference_guidance = build_a04_guidance(
            landmarks_payload, reference, side, source="reference_action"
        )
        personalized_guidance = build_a04_guidance(
            landmarks_payload,
            personalization["A04"],
            side,
            source="personalized_action",
        )
        rendered = render_debug(
            image, reference_guidance, personalized_guidance
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        if not cv2.imwrite(str(args.output), rendered):
            raise ARGuidanceRenderError(
                f"Could not write debug image: {args.output}"
            )
    except (OSError, ValueError, json.JSONDecodeError, ARGuidanceError) as exc:
        print(f"AR guidance debug render failed: {exc}", file=sys.stderr)
        return 1
    print(f"AR guidance debug: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
