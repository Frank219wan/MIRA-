"""Aggregate single-frame Face Profile v0.3 measurements into a stable scan.

No landmarks, geometry, or makeup rules are recalculated here. A camera can
feed profiles with add_profile() and request a result with finalize().
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from statistics import fmean, median, quantiles, stdev
from typing import Any, Mapping, Sequence

if __package__:
    from .eye_landmarks import process_eye_geometry
    from .face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError
    from .face_profile import FACE_PROFILE_VERSION, FaceProfileError
    from .personalization_engine import (
        PersonalizationEngineError,
        load_json_object,
        personalize_recipe,
        save_json_output,
    )
    from .reference_action_adapter import (
        ReferenceActionAdapterError,
        build_standard_recipe,
        personalize_reference_recipe,
    )
else:
    from eye_landmarks import process_eye_geometry  # type: ignore
    from face_landmarker import DEFAULT_MODEL_PATH, PROJECT_ROOT, FaceLandmarkerError  # type: ignore
    from face_profile import FACE_PROFILE_VERSION, FaceProfileError  # type: ignore
    from personalization_engine import (  # type: ignore
        PersonalizationEngineError, load_json_object, personalize_recipe, save_json_output,
    )
    from reference_action_adapter import (  # type: ignore
        ReferenceActionAdapterError, build_standard_recipe, personalize_reference_recipe,
    )


DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "stable_face_scan_validation"
DEFAULT_RECIPE_PATH = PROJECT_ROOT / "examples" / "cat_eye_standard_recipe.json"
MIN_VALID_FRAMES = 3
SCAN_VERSION = "0.1"

EYE_FIELDS: dict[str, tuple[str, ...]] = {
    "eye_tail_angle": ("left", "right", "mean"),
    "relative_eye_length": ("left", "right", "mean"),
    "eye_width_height_ratio": ("left", "right", "mean"),
    "brow_eye_ratio": ("left", "right", "mean"),
    "lower_lid_space_ratio": ("left", "right", "mean"),
    "inner_corner_angle": ("left_deg", "right_deg", "mean_deg"),
}
SYMMETRY_FIELDS = (
    "eye_width", "eye_height", "eye_aspect_ratio", "eye_tail_angle_difference",
)
NUMERIC_PATHS = (
    ("eye_geometry", "eye_spacing_ratio"),
    *(
        ("eye_geometry", group, field)
        for group, fields in EYE_FIELDS.items()
        for field in fields
    ),
    *(("symmetry", field) for field in SYMMETRY_FIELDS),
)
FEATURE_PATHS = {
    "eye_tail_angle.mean": ("eye_geometry", "eye_tail_angle", "mean"),
    "relative_eye_length.mean": ("eye_geometry", "relative_eye_length", "mean"),
    "lower_lid_space_ratio.mean": ("eye_geometry", "lower_lid_space_ratio", "mean"),
    "inner_corner_angle.mean_deg": ("eye_geometry", "inner_corner_angle", "mean_deg"),
    "brow_eye_ratio.mean": ("eye_geometry", "brow_eye_ratio", "mean"),
}


class FaceScanAggregationError(ValueError):
    """Raised when a stable scan cannot be formed from valid profiles."""


def _get(data: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            raise FaceScanAggregationError("Missing Face Profile field: " + ".".join(path))
        current = current[key]
    return current


def _finite(value: Any, path: tuple[str, ...]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FaceScanAggregationError("Non-numeric Face Profile field: " + ".".join(path))
    result = float(value)
    if not math.isfinite(result):
        raise FaceScanAggregationError("Non-finite Face Profile field: " + ".".join(path))
    return result


def _reject_nonfinite_json(value: Any, path: str = "profile") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            _reject_nonfinite_json(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_nonfinite_json(child, f"{path}[{index}]")
    elif isinstance(value, float) and not math.isfinite(value):
        raise FaceScanAggregationError(f"Non-finite Face Profile field: {path}")


def validate_face_profile(profile: Mapping[str, Any]) -> dict[tuple[str, ...], float]:
    """Require the full existing v0.3 numeric contract and usable pose result."""

    if not isinstance(profile, Mapping) or profile.get("version") != FACE_PROFILE_VERSION:
        raise FaceScanAggregationError("Expected Face Profile v0.3.")
    _reject_nonfinite_json(profile)
    confidence = _get(profile, ("confidence",))
    if not isinstance(confidence, Mapping):
        raise FaceScanAggregationError("Face Profile confidence must be an object.")
    if confidence.get("pose_normalized") is not True:
        raise FaceScanAggregationError("Pose normalization unavailable for this frame.")
    if not isinstance(confidence.get("expression_controlled"), bool):
        raise FaceScanAggregationError("Missing expression_controlled confidence flag.")
    source = _get(profile, ("raw_geometry_reference", "source"))
    if not isinstance(source, str) or not source:
        raise FaceScanAggregationError("Missing raw_geometry_reference.source.")

    numbers = {path: _finite(_get(profile, path), path) for path in NUMERIC_PATHS}
    for path, value in numbers.items():
        if path[0] == "symmetry" and value < 0:
            raise FaceScanAggregationError("Negative asymmetry is invalid: " + ".".join(path))
        if path[-1] == "eye_spacing_ratio" or (
            len(path) == 3 and path[1] in {
                "relative_eye_length", "eye_width_height_ratio", "brow_eye_ratio",
                "lower_lid_space_ratio",
            }
        ):
            if value <= 0:
                raise FaceScanAggregationError("Degenerate geometry: " + ".".join(path))
        if len(path) == 3 and path[1] == "inner_corner_angle" and not 0 < value < 180:
            raise FaceScanAggregationError("Degenerate inner corner angle: " + ".".join(path))
    return numbers


def feature_dispersion(values: Sequence[float]) -> dict[str, float | int]:
    """Report every observation; Q1/Q3 use inclusive linear quartiles."""

    if len(values) < 2 or not all(math.isfinite(value) for value in values):
        raise FaceScanAggregationError("Dispersion requires at least two finite values.")
    center = median(values)
    q1, _, q3 = quantiles(values, n=4, method="inclusive")
    return {
        "n": len(values),
        "median": center,
        "mean": fmean(values),
        "std": stdev(values),
        "min": min(values),
        "max": max(values),
        "range": max(values) - min(values),
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "mad": median(abs(value - center) for value in values),
    }


class FaceScanAggregator:
    """Incremental profile collector for photo batches or future camera frames."""

    def __init__(self, min_valid_frames: int = MIN_VALID_FRAMES) -> None:
        if isinstance(min_valid_frames, bool) or not isinstance(min_valid_frames, int) or min_valid_frames < 2:
            raise FaceScanAggregationError("min_valid_frames must be an integer >= 2.")
        self.min_valid_frames = min_valid_frames
        self._valid: list[tuple[str, dict[tuple[str, ...], float], dict[str, Any]]] = []
        self._frames: list[dict[str, Any]] = []

    def add_profile(self, profile: Mapping[str, Any], *, frame_id: str | None = None) -> bool:
        """Record a valid frame, or retain its reason for exclusion; return validity."""

        if frame_id is None:
            try:
                encoded = json.dumps(profile, sort_keys=True, allow_nan=False).encode("utf-8")
                frame_id = "profile_" + hashlib.sha256(encoded).hexdigest()[:16]
            except (TypeError, ValueError):
                frame_id = f"invalid_frame_{len(self._frames) + 1}"
        if not isinstance(frame_id, str) or not frame_id:
            raise FaceScanAggregationError("frame_id must be non-empty.")
        try:
            numbers = validate_face_profile(profile)
        except FaceScanAggregationError as exc:
            self._frames.append({"frame_id": frame_id, "valid": False, "reason": str(exc)})
            return False
        self._valid.append((frame_id, numbers, copy.deepcopy(dict(profile))))
        self._frames.append({"frame_id": frame_id, "valid": True, "reason": None})
        return True

    def add_failure(self, *, frame_id: str, reason: str) -> None:
        """Record an image/landmarker failure without fabricating a profile."""

        if not frame_id or not reason:
            raise FaceScanAggregationError("frame_id and failure reason are required.")
        self._frames.append({"frame_id": frame_id, "valid": False, "reason": reason})

    def finalize(self) -> dict[str, Any]:
        """Return a StableFaceScan wrapper with a full median v0.3 profile."""

        count = len(self._valid)
        if count < self.min_valid_frames:
            raise FaceScanAggregationError(
                f"Stable Face Scan requires at least {self.min_valid_frames} valid profiles; got {count}."
            )

        aggregated = copy.deepcopy(min(self._valid, key=lambda item: item[0])[2])
        for path in NUMERIC_PATHS:
            values = [numbers[path] for _, numbers, _ in self._valid]
            target = aggregated
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = median(values)
        # A median of per-frame means need not equal the mean of separate
        # left/right medians. Preserve the v0.3 mean-path relationship using
        # the median signed side difference, without changing the core median.
        for group, fields in EYE_FIELDS.items():
            left_key, right_key, mean_key = fields
            group_value = aggregated["eye_geometry"][group]
            center = group_value[mean_key]
            half_difference = median(
                (numbers[("eye_geometry", group, left_key)]
                 - numbers[("eye_geometry", group, right_key)]) / 2
                for _, numbers, _ in self._valid
            )
            group_value[left_key] = center + half_difference
            group_value[right_key] = center - half_difference
        tail = aggregated["eye_geometry"]["eye_tail_angle"]
        aggregated["symmetry"]["eye_tail_angle_difference"] = abs(
            tail["left"] - tail["right"]
        )
        aggregated["raw_geometry_reference"] = {"source": "stable_face_scan"}
        aggregated["confidence"] = {
            "pose_normalized": True,
            "expression_controlled": all(
                profile["confidence"]["expression_controlled"]
                for _, _, profile in self._valid
            ),
        }
        validate_face_profile(aggregated)
        features = {
            name: feature_dispersion([numbers[path] for _, numbers, _ in self._valid])
            for name, path in FEATURE_PATHS.items()
        }
        result = {
            "version": SCAN_VERSION,
            "frame_count": len(self._frames),
            "valid_frame_count": count,
            "aggregated_face_profile": aggregated,
            "aggregation": {
                "method": "median",
                "quantile_method": "inclusive linear interpolation at (n-1)*p",
                "mad_definition": "median(abs(x_i - median(x)))",
                "numeric_profile_fields": "all v0.3 eye_geometry and symmetry numeric fields",
                "side_value_method": "group mean is median of frame means; sides use median signed half-difference so their average equals that mean",
                "outliers_removed": False,
                "features": features,
            },
            "quality_information": {
                "min_valid_frames": self.min_valid_frames,
                "invalid_frame_count": len(self._frames) - count,
                "frames": sorted(self._frames, key=lambda item: (item["frame_id"], item["valid"])),
                "no_good_bad_threshold_applied": True,
            },
        }
        json.dumps(result, allow_nan=False)
        return result


def _action_values(result: Mapping[str, Any]) -> dict[str, float | None]:
    actions = {action["action_id"]: action for action in result["personalized_actions"]}
    a04 = actions["A04"]["personalized_parameters"]
    a02 = actions["A02"]["personalized_parameters"]
    return {
        "direction_angle_deg": a04["direction_angle_deg"],
        "extension_factor": a04["extension_factor"],
        "personalized_extension_ratio": a04.get("personalized_extension_ratio"),
        "lower_lid_range_factor": a02["range_factor"],
        "lower_lid_intensity_factor": a02["intensity_factor"],
    }


def run_stable_face_scan(
    *,
    profile_paths: Sequence[Path] | None = None,
    image_paths: Sequence[Path] | None = None,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    recipe_path: Path = DEFAULT_RECIPE_PATH,
    reference_geometry_path: Path | None = None,
    model_path: Path = DEFAULT_MODEL_PATH,
    min_valid_frames: int = MIN_VALID_FRAMES,
) -> dict[str, Any]:
    """Use existing image pipeline or saved profiles, then compare actions."""

    if (profile_paths is None) == (image_paths is None):
        raise FaceScanAggregationError("Provide exactly one of profile_paths or image_paths.")
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    aggregator = FaceScanAggregator(min_valid_frames=min_valid_frames)
    accepted: list[tuple[str, dict[str, Any]]] = []
    paths = profile_paths if profile_paths is not None else image_paths
    assert paths is not None
    for path_value in paths:
        path = Path(path_value)
        frame_id = path.stem
        try:
            if profile_paths is not None:
                profile = load_json_object(path)
            else:
                geometry_path = output_dir / f"{frame_id}_geometry.json"
                profile_path = output_dir / f"{frame_id}_profile.json"
                process_eye_geometry(
                    image_path=path,
                    model_path=model_path,
                    debug_output_path=output_dir / f"{frame_id}_debug.jpg",
                    json_output_path=geometry_path,
                    profile_output_path=profile_path,
                )
                profile = load_json_object(profile_path)
        except (FaceLandmarkerError, FaceProfileError, PersonalizationEngineError, OSError, ValueError) as exc:
            aggregator.add_failure(frame_id=frame_id, reason=str(exc))
            continue
        if aggregator.add_profile(profile, frame_id=frame_id):
            accepted.append((frame_id, profile))

    scan = aggregator.finalize()
    manual_recipe = load_json_object(recipe_path)
    reference_geometry = load_json_object(reference_geometry_path) if reference_geometry_path else None
    recipe = build_standard_recipe(manual_recipe, reference_geometry)
    personalize = personalize_reference_recipe if reference_geometry else personalize_recipe
    stable_action = personalize(scan["aggregated_face_profile"], recipe, "cat_eye")
    rows = []
    for frame_id, profile in accepted:
        action = personalize(profile, recipe, "cat_eye")
        rows.append({"source": frame_id, "profile_type": "single_frame", **_action_values(action)})
    rows.append({"source": "stable_face_scan", "profile_type": "median_aggregate", **_action_values(stable_action)})
    fields = (
        "source", "profile_type", "direction_angle_deg", "extension_factor",
        "personalized_extension_ratio", "lower_lid_range_factor", "lower_lid_intensity_factor",
    )
    with (output_dir / "single_vs_stable_personalization.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    save_json_output(output_dir / "stable_face_scan.json", scan)
    save_json_output(output_dir / "stable_face_profile.json", scan["aggregated_face_profile"])
    save_json_output(output_dir / "stable_personalization.json", stable_action)
    return scan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--profiles", nargs="+", type=Path)
    source.add_argument("--images", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--recipe", type=Path, default=DEFAULT_RECIPE_PATH)
    parser.add_argument("--reference-geometry", type=Path)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL_PATH)
    parser.add_argument("--min-valid-frames", type=int, default=MIN_VALID_FRAMES)
    args = parser.parse_args()
    try:
        scan = run_stable_face_scan(
            profile_paths=args.profiles,
            image_paths=args.images,
            output_dir=args.output_dir,
            recipe_path=args.recipe,
            reference_geometry_path=args.reference_geometry,
            model_path=args.model,
            min_valid_frames=args.min_valid_frames,
        )
    except (FaceScanAggregationError, PersonalizationEngineError, ReferenceActionAdapterError, OSError, ValueError) as exc:
        print(f"Stable Face Scan failed: {exc}", file=sys.stderr)
        return 1
    print(f"Stable Face Scan: {scan['valid_frame_count']}/{scan['frame_count']} valid; {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
