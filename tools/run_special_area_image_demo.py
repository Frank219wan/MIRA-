"""Run the MIRA Special Area Preference MVP on one local image."""

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

from src.special_area_profile import (  # noqa: E402
    VALID_LOCATIONS,
    VALID_PREFERENCES,
    SpecialAreaProfileError,
    build_special_area,
    build_special_area_profile,
    normalize_pixel_polygon,
    save_strict_json,
)
from src.special_area_selector import (  # noqa: E402
    SpecialAreaSelectionError,
    render_debug_regions,
    select_polygon,
)
from src.special_area_tutorial_adapter import adapt_special_area_tutorial  # noqa: E402


LOCATION_DISPLAY_LABELS = {
    "subject_left_cheek": "subject_left_cheek  — your left cheek",
    "subject_right_cheek": "subject_right_cheek — your right cheek",
}


def _choose(
    prompt: str,
    choices: Sequence[str],
    input_fn: Callable[[str], str] = input,
    display_labels: Mapping[str, str] | None = None,
) -> str:
    while True:
        print(prompt)
        for index, choice in enumerate(choices, start=1):
            display_label = (
                display_labels.get(choice, choice) if display_labels else choice
            )
            print(f"{index}. {display_label}")
        answer = input_fn("> ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(choices):
            return choices[int(answer) - 1]
        upper_answer = answer.upper()
        for choice in choices:
            if answer == choice or upper_answer == choice.upper():
                return choice
        print("Please enter a listed number or value.")


def build_session_summary(
    profile: dict[str, Any], image_basename: str
) -> dict[str, Any]:
    """Build a path-free summary suitable for strict JSON output."""

    if Path(image_basename).name != image_basename:
        raise SpecialAreaProfileError("image_basename must not contain a path.")
    return {
        "schema_version": profile["schema_version"],
        "image_sample_id": profile["image_sample_id"],
        "image_basename": image_basename,
        "selected_area_count": len(profile["areas"]),
        "area_ids": [area["area_id"] for area in profile["areas"]],
        "outputs": {
            "profile": "special_area_profile.json",
            "tutorial": "adapted_tutorial.json",
            "debug_image": "debug_region.jpg",
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if not args.image.is_file():
            raise SpecialAreaSelectionError(f"Image does not exist: {args.image}")
        image = cv2.imread(str(args.image), cv2.IMREAD_COLOR)
        if image is None or image.size == 0:
            raise SpecialAreaSelectionError(f"Could not read image: {args.image}")

        pixel_polygon = select_polygon(image)
        if pixel_polygon is None:
            print("Selection cancelled. No output was written.")
            return 0
        height, width = image.shape[:2]
        polygon = normalize_pixel_polygon(pixel_polygon, width, height)

        user_label = input("Optional label for this area:\n> ").strip()
        location = _choose(
            "Where is this area?",
            VALID_LOCATIONS,
            display_labels=LOCATION_DISPLAY_LABELS,
        )
        preference = _choose(
            "How would you like MIRA to treat this area?", VALID_PREFERENCES
        )
        area = build_special_area(
            area_id="area_01",
            user_label=user_label,
            location=location,
            preference=preference,
            polygon=polygon,
        )
        profile = build_special_area_profile(args.image.stem, [area])
        tutorial = adapt_special_area_tutorial(profile)
        summary = build_session_summary(profile, args.image.name)
        debug_image = render_debug_regions(image, profile["areas"])

        args.output.mkdir(parents=True, exist_ok=True)
        save_strict_json(args.output / "special_area_profile.json", profile)
        save_strict_json(args.output / "adapted_tutorial.json", tutorial)
        save_strict_json(args.output / "session_summary.json", summary)
        if not cv2.imwrite(str(args.output / "debug_region.jpg"), debug_image):
            raise SpecialAreaSelectionError("Could not write debug_region.jpg.")
    except (OSError, SpecialAreaProfileError, SpecialAreaSelectionError) as exc:
        print(f"Special Area demo failed: {exc}", file=sys.stderr)
        return 1

    print(f"Special Area profile: {args.output / 'special_area_profile.json'}")
    print(f"Adapted tutorial: {args.output / 'adapted_tutorial.json'}")
    print(f"Session summary: {args.output / 'session_summary.json'}")
    print(f"Debug image: {args.output / 'debug_region.jpg'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
