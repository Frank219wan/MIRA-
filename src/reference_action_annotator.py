"""Click A04 landmarks on a local-eye tutorial image and inspect the overlay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

import cv2

if __package__:
    from .reference_action_geometry import (
        OPTIONAL_POINTS,
        REQUIRED_POINTS,
        ReferenceActionGeometryError,
        build_reference_action_geometry,
        save_reference_action_geometry,
    )
else:
    from reference_action_geometry import (  # type: ignore
        OPTIONAL_POINTS,
        REQUIRED_POINTS,
        ReferenceActionGeometryError,
        build_reference_action_geometry,
        save_reference_action_geometry,
    )


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_IMAGE = PROJECT_ROOT / "examples" / "reference" / "cat_eye_reference.jpg"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "reference_action"


class AnnotationError(ValueError):
    """Raised for unreadable images, invalid cropping, or canceled annotation."""


def crop_image(
    image: Any,
    *,
    crop: str | None = None,
    split: float = 0.5,
    roi: tuple[int, int, int, int] | None = None,
) -> tuple[Any, dict[str, int]]:
    """Return an explicit ROI and its location in the original image."""

    height, width = image.shape[:2]
    if height <= 1 or width <= 1:
        raise AnnotationError("Image is too small to annotate.")
    if crop is not None and roi is not None:
        raise AnnotationError("Use either --crop or --roi, not both.")
    if not 0 < split < 1:
        raise AnnotationError("--split must be strictly between 0 and 1.")
    if roi is not None:
        x, y, selected_width, selected_height = roi
    elif crop is not None:
        boundary = round(height * split)
        if not 0 < boundary < height:
            raise AnnotationError("Split produces an empty crop.")
        x = 0
        selected_width = width
        if crop == "top":
            y, selected_height = 0, boundary
        elif crop == "bottom":
            y, selected_height = boundary, height - boundary
        else:
            raise AnnotationError("--crop must be top or bottom.")
    else:
        x, y, selected_width, selected_height = 0, 0, width, height
    if (
        x < 0 or y < 0 or selected_width <= 1 or selected_height <= 1
        or x + selected_width > width or y + selected_height > height
    ):
        raise AnnotationError("ROI is outside the image or too small.")
    return (
        image[y : y + selected_height, x : x + selected_width].copy(),
        {"x": x, "y": y, "width": selected_width, "height": selected_height},
    )


def _read_image(path: Path) -> Any:
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        raise AnnotationError(f"Could not read image: {path}")
    return image


def select_roi(image: Any) -> tuple[int, int, int, int]:
    try:
        bounds = cv2.selectROI("Select tutorial ROI; Enter confirms", image, False, False)
        cv2.destroyWindow("Select tutorial ROI; Enter confirms")
    except cv2.error as exc:
        raise AnnotationError(f"Could not open ROI selector: {exc}") from exc
    result = tuple(int(value) for value in bounds)
    if result[2] <= 1 or result[3] <= 1:
        raise AnnotationError("ROI selection was canceled or is too small.")
    return result


def draw_annotation_overlay(
    image: Any,
    annotation: Mapping[str, Any],
    geometry: Mapping[str, Any] | None = None,
) -> Any:
    """Draw clicked points, eye axis, liner vector, and normalized measures."""

    canvas = image.copy()
    colors = {
        "eye_inner": (255, 200, 0),
        "eye_outer": (255, 200, 0),
        "eyeliner_tip": (0, 80, 255),
        "eyeliner_start": (0, 200, 0),
        "upper_lash_outer_reference": (200, 80, 200),
    }
    points = {
        name: (int(round(value["x"])), int(round(value["y"])))
        for name, value in annotation.items()
        if name in colors and isinstance(value, Mapping)
    }
    if "eye_inner" in points and "eye_outer" in points:
        cv2.line(canvas, points["eye_inner"], points["eye_outer"], (255, 200, 0), 2)
    if "eye_outer" in points and "eyeliner_tip" in points:
        cv2.arrowedLine(
            canvas, points["eye_outer"], points["eyeliner_tip"],
            (0, 80, 255), 2, tipLength=0.15,
        )
    for name, point in points.items():
        cv2.circle(canvas, point, 5, colors[name], -1)
        cv2.putText(
            canvas, name, (point[0] + 7, point[1] - 7),
            cv2.FONT_HERSHEY_SIMPLEX, 0.48, colors[name], 1, cv2.LINE_AA,
        )
    if geometry is not None:
        direction = geometry["direction_relative_to_eye_axis_deg"]
        extension = geometry["eyeliner_extension_ratio"]
        height, width = canvas.shape[:2]
        label_width = min(width, 560)
        cv2.rectangle(canvas, (0, 0), (label_width, min(height, 69)), (20, 20, 20), -1)
        cv2.putText(
            canvas, f"direction relative to eye axis: {direction:+.2f} deg",
            (8, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            cv2.LINE_AA,
        )
        cv2.putText(
            canvas, f"extension distance / eye width: {extension:.3f}",
            (8, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            cv2.LINE_AA,
        )
    return canvas


def click_annotation(image: Any) -> dict[str, dict[str, int]]:
    """Collect required points, then optional points; Enter finishes after 3."""

    labels = REQUIRED_POINTS + OPTIONAL_POINTS[:2]
    annotation: dict[str, dict[str, int]] = {}
    state = {"index": 0}
    window = "A04 annotation: click point; u undo; s skip optional; Enter finish; Esc cancel"

    def on_mouse(event: int, x: int, y: int, flags: int, userdata: Any) -> None:
        del flags, userdata
        if event == cv2.EVENT_LBUTTONDOWN and state["index"] < len(labels):
            annotation[labels[state["index"]]] = {"x": x, "y": y}
            state["index"] += 1

    try:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window, on_mouse)
        while True:
            canvas = draw_annotation_overlay(image, annotation)
            instruction = (
                f"Click: {labels[state['index']]}"
                if state["index"] < len(labels)
                else "All points selected; Enter to save"
            )
            cv2.putText(
                canvas, instruction, (8, max(22, image.shape[0] - 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 255), 2, cv2.LINE_AA,
            )
            cv2.imshow(window, canvas)
            key = cv2.waitKey(30) & 0xFF
            if key == 27:
                raise AnnotationError("Annotation canceled.")
            if key in (10, 13) and state["index"] >= len(REQUIRED_POINTS):
                return annotation
            if key in (ord("s"), ord("S")) and state["index"] >= len(REQUIRED_POINTS):
                state["index"] = min(len(labels), state["index"] + 1)
            if key in (ord("u"), ord("U")) and state["index"] > 0:
                state["index"] -= 1
                annotation.pop(labels[state["index"]], None)
    except cv2.error as exc:
        raise AnnotationError(f"Could not open annotation window: {exc}") from exc
    finally:
        try:
            cv2.destroyWindow(window)
        except cv2.error:
            pass


def annotate_image(
    image_path: Path | str,
    *,
    output_json: Path | str,
    debug_output: Path | str,
    reference_id: str = "cat_eye_main_demo",
    crop: str | None = None,
    split: float = 0.5,
    roi: tuple[int, int, int, int] | None = None,
    select_roi_interactively: bool = False,
    points_json: Path | str | None = None,
) -> dict[str, Any]:
    image_file = Path(image_path)
    original = _read_image(image_file)
    if select_roi_interactively:
        if crop is not None or roi is not None:
            raise AnnotationError("--select-roi cannot be combined with --crop or --roi.")
        roi = select_roi(original)
    cropped, crop_bounds = crop_image(original, crop=crop, split=split, roi=roi)

    if points_json is None:
        annotation = click_annotation(cropped)
    else:
        try:
            with Path(points_json).open(encoding="utf-8") as handle:
                annotation = json.load(
                    handle,
                    parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)),
                )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise AnnotationError(f"Could not read points JSON: {exc}") from exc
    if not isinstance(annotation, Mapping):
        raise AnnotationError("Points JSON must contain an object.")
    crop_height, crop_width = cropped.shape[:2]
    for name, value in annotation.items():
        if isinstance(value, Mapping):
            x, y = value.get("x"), value.get("y")
            if (
                isinstance(x, (int, float)) and not isinstance(x, bool)
                and isinstance(y, (int, float)) and not isinstance(y, bool)
                and not (0 <= x < crop_width and 0 <= y < crop_height)
            ):
                raise AnnotationError(
                    f"{name} is outside the selected crop ({crop_width}x{crop_height})."
                )
    result = build_reference_action_geometry(
        annotation,
        reference_id=reference_id,
        source_image=str(image_file),
        crop_roi=crop_bounds,
    )
    overlay = draw_annotation_overlay(cropped, result["annotation"], result["geometry"])
    debug_path = Path(debug_output)
    debug_path.parent.mkdir(parents=True, exist_ok=True)
    if not cv2.imwrite(str(debug_path), overlay):
        raise AnnotationError(f"Could not write debug overlay: {debug_path}")
    save_reference_action_geometry(output_json, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, default=DEFAULT_IMAGE)
    parser.add_argument(
        "--output-json", type=Path,
        default=DEFAULT_OUTPUT_DIR / "cat_eye_reference_annotation.json",
    )
    parser.add_argument(
        "--debug-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / "cat_eye_reference_debug.jpg",
    )
    parser.add_argument("--reference-id", default="cat_eye_main_demo")
    parser.add_argument("--crop", choices=("top", "bottom"))
    parser.add_argument("--split", type=float, default=0.5)
    parser.add_argument("--roi", type=int, nargs=4, metavar=("X", "Y", "W", "H"))
    parser.add_argument("--select-roi", action="store_true")
    parser.add_argument(
        "--points-json", type=Path,
        help="Existing manual points in the cropped image's pixel coordinates; skips GUI.",
    )
    args = parser.parse_args()
    try:
        result = annotate_image(
            args.image,
            output_json=args.output_json,
            debug_output=args.debug_output,
            reference_id=args.reference_id,
            crop=args.crop,
            split=args.split,
            roi=tuple(args.roi) if args.roi else None,
            select_roi_interactively=args.select_roi,
            points_json=args.points_json,
        )
    except (AnnotationError, ReferenceActionGeometryError, OSError) as exc:
        print(f"Reference annotation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Reference geometry: {args.output_json}")
    print(f"Debug overlay: {args.debug_output}")
    print(json.dumps(result["geometry"], ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
