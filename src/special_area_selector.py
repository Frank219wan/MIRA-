"""OpenCV UI and debug renderer for user-selected special areas."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


WINDOW_TITLE = "MIRA — Select Your Area"
INSTRUCTION_LINES = (
    "Click to mark an area you care about",
    "ENTER confirm   U undo   C clear   Q quit",
)


class SpecialAreaSelectionError(ValueError):
    """Raised when an image or selected polygon cannot be rendered."""


@dataclass(frozen=True)
class PolygonSelectionOutcome:
    """Explicit result so live selection can distinguish cancel from quit."""

    action: str
    points: list[tuple[int, int]]


@dataclass(frozen=True)
class PolygonPreviewGeometry:
    """Marker and path geometry for one draft selection frame."""

    marker_points: list[tuple[int, int]]
    path_points: list[tuple[int, int]]
    closed: bool


def build_polygon_preview_geometry(
    points: Sequence[tuple[int, int]],
    *,
    normalize_for_preview: Callable[
        [Sequence[tuple[int, int]]], Sequence[tuple[int, int]]
    ]
    | None = None,
) -> PolygonPreviewGeometry:
    """Build a safe draft path while always retaining the click markers."""

    markers = list(points)
    if len(markers) < 2:
        return PolygonPreviewGeometry(markers, [], False)
    if len(markers) == 2:
        return PolygonPreviewGeometry(markers, markers, False)
    if normalize_for_preview is None:
        return PolygonPreviewGeometry(markers, markers, True)
    try:
        normalized = list(normalize_for_preview(markers))
    except (ValueError, RuntimeError):
        return PolygonPreviewGeometry(markers, [], False)
    if len(normalized) < 3:
        return PolygonPreviewGeometry(markers, [], False)
    return PolygonPreviewGeometry(markers, normalized, True)


def polygon_key_action(
    key: int, point_count: int, *, allow_space: bool = True
) -> str | None:
    """Map an OpenCV key code to one deterministic polygon-editor action."""

    if key in (ord("q"), ord("Q")):
        return "quit"
    if key == 27:
        return "cancel"
    if key in (8, 127, ord("u"), ord("U")):
        return "undo"
    if key in (ord("c"), ord("C")):
        return "clear"
    if key in ((10, 13, 32) if allow_space else (10, 13)) and point_count >= 3:
        return "confirm"
    return None


def _display_scale(image: Any, max_width: int = 1100, max_height: int = 800) -> float:
    height, width = image.shape[:2]
    return min(1.0, max_width / width, max_height / height)


def _selection_frame(
    image: Any,
    preview: PolygonPreviewGeometry,
    instruction_lines: Sequence[str] = INSTRUCTION_LINES,
) -> Any:
    canvas = image.copy()
    if preview.path_points:
        polygon = np.asarray(preview.path_points, dtype=np.int32)
        cv2.polylines(
            canvas,
            [polygon],
            preview.closed,
            (80, 220, 255),
            2,
            cv2.LINE_AA,
        )
    for point in preview.marker_points:
        cv2.circle(canvas, point, 4, (80, 220, 255), -1, cv2.LINE_AA)
    banner_height = max(64, 10 + len(instruction_lines) * 27)
    cv2.rectangle(
        canvas,
        (0, 0),
        (canvas.shape[1], banner_height),
        (28, 28, 28),
        -1,
    )
    for line_index, line in enumerate(instruction_lines):
        cv2.putText(
            canvas,
            line,
            (12, 25 + line_index * 27),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
    status = f"Selecting area: {len(preview.marker_points)} points"
    if 0 < len(preview.marker_points) < 3:
        status += " (at least 3 required)"
    cv2.putText(
        canvas,
        status,
        (12, canvas.shape[0] - 14),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (80, 220, 255),
        1,
        cv2.LINE_AA,
    )
    return canvas


def select_polygon(image: Any, window_title: str = WINDOW_TITLE) -> list[tuple[int, int]] | None:
    """Collect a polygon in a scaled preview and return original-image pixels.

    Returning ``None`` means the user quit without confirming.
    """

    outcome = select_polygon_with_outcome(
        image,
        window_title=window_title,
        allow_space=False,
    )
    if outcome.action != "confirm":
        return None
    return outcome.points


def select_polygon_with_outcome(
    image: Any,
    *,
    window_title: str = WINDOW_TITLE,
    instruction_lines: Sequence[str] = INSTRUCTION_LINES,
    allow_space: bool = True,
    normalize_for_preview: Callable[
        [Sequence[tuple[int, int]]], Sequence[tuple[int, int]]
    ]
    | None = None,
) -> PolygonSelectionOutcome:
    """Collect a polygon and distinguish confirm, cancel, and app quit."""

    if image is None or not hasattr(image, "size") or image.size == 0:
        raise SpecialAreaSelectionError("Input image is empty.")
    original_height, original_width = image.shape[:2]
    scale = _display_scale(image)
    if scale < 1.0:
        display_image = cv2.resize(
            image,
            (round(original_width * scale), round(original_height * scale)),
            interpolation=cv2.INTER_AREA,
        )
    else:
        display_image = image.copy()

    points: list[tuple[int, int]] = []

    def on_mouse(event: int, x: int, y: int, _flags: int, _parameter: Any) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            points.append((x, y))

    cv2.namedWindow(window_title, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_title, on_mouse)
    try:
        while True:
            preview = build_polygon_preview_geometry(
                points,
                normalize_for_preview=normalize_for_preview,
            )
            cv2.imshow(
                window_title,
                _selection_frame(display_image, preview, instruction_lines),
            )
            key = cv2.waitKey(20) & 0xFF
            action = polygon_key_action(key, len(points), allow_space=allow_space)
            if action in {"quit", "cancel"}:
                return PolygonSelectionOutcome(action, [])
            if action == "undo":
                if points:
                    points.pop()
            elif action == "clear":
                points.clear()
            elif action == "confirm":
                break
            try:
                if cv2.getWindowProperty(window_title, cv2.WND_PROP_VISIBLE) < 1:
                    return PolygonSelectionOutcome("cancel", [])
            except cv2.error:
                return PolygonSelectionOutcome("cancel", [])
    finally:
        cv2.destroyWindow(window_title)

    return PolygonSelectionOutcome(
        "confirm",
        [
            (
                min(original_width - 1, max(0, round(x / scale))),
                min(original_height - 1, max(0, round(y / scale))),
            )
            for x, y in points
        ],
    )


def render_polygon_selection_preview(
    image: Any,
    points: Sequence[tuple[int, int]],
    *,
    status: str,
) -> Any:
    """Render the validated point order before metadata collection."""

    if image is None or not hasattr(image, "size") or image.size == 0:
        raise SpecialAreaSelectionError("Preview image is empty.")
    if len(points) < 3:
        raise SpecialAreaSelectionError(
            "Validated preview polygon needs at least 3 points."
        )
    return _selection_frame(
        image,
        PolygonPreviewGeometry(list(points), list(points), True),
        (
            "MIRA - SELECT AREA",
            status,
            "Enter label, location, and preference in Terminal",
        ),
    )


def _pixel(point: Mapping[str, Any], width: int, height: int) -> tuple[int, int]:
    return (
        min(width - 1, max(0, round(float(point["x_norm"]) * width))),
        min(height - 1, max(0, round(float(point["y_norm"]) * height))),
    )


def render_debug_regions(image: Any, areas: Sequence[Mapping[str, Any]]) -> Any:
    """Return a copy with all selected polygons and user preferences overlaid."""

    if image is None or not hasattr(image, "size") or image.size == 0:
        raise SpecialAreaSelectionError("Debug image is empty.")
    canvas = image.copy()
    overlay = image.copy()
    height, width = image.shape[:2]
    colors = ((70, 210, 255), (255, 120, 100), (150, 230, 100), (220, 120, 230))
    prepared: list[tuple[np.ndarray, Mapping[str, Any], tuple[int, int, int]]] = []
    for index, area in enumerate(areas):
        polygon = area.get("polygon")
        if not isinstance(polygon, list) or len(polygon) < 3:
            raise SpecialAreaSelectionError("Each debug area needs at least 3 points.")
        pixels = np.asarray([_pixel(point, width, height) for point in polygon], dtype=np.int32)
        color = colors[index % len(colors)]
        cv2.fillPoly(overlay, [pixels], color)
        prepared.append((pixels, area, color))
    canvas = cv2.addWeighted(overlay, 0.20, canvas, 0.80, 0.0)
    for pixels, area, color in prepared:
        cv2.polylines(canvas, [pixels], True, color, 3, cv2.LINE_AA)
        label_parts = [str(area["area_id"]), str(area["preference"])]
        if area.get("user_label"):
            label_parts.append(str(area["user_label"]))
        label = " | ".join(label_parts)
        x = int(pixels[:, 0].min())
        y = max(24, int(pixels[:, 1].min()) - 8)
        cv2.putText(
            canvas,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    return canvas
