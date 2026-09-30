"""Build privacy-safe Main Demo fixtures from validated pipeline outputs.

The generator intentionally reads the ignored ``data/output`` artifacts.  It
never reads or copies source images, and it replaces the Face Profile raw
geometry provenance with a non-path marker before writing tracked fixtures.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Mapping

from .main_demo_personalization_cases import (
    DEFAULT_BLOGGER_PROFILE,
    DEFAULT_FACE06_PROFILE,
    DEFAULT_FACE11_PROFILE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_REFERENCE_RECIPE,
    FEATURE_PATHS,
    MainDemoValidationError,
    _assert_strict_finite,
    _profile_number,
    _reference_parameters,
    calculate_case,
)
from .personalization_engine import load_json_object, save_json_output


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_DIR = PROJECT_ROOT / "data" / "fixtures" / "main_demo"

SAMPLES = {
    "face_06": {
        "profile": DEFAULT_FACE06_PROFILE,
        "generated_result": DEFAULT_OUTPUT_DIR / "face06_personalization.json",
    },
    "face_11": {
        "profile": DEFAULT_FACE11_PROFILE,
        "generated_result": DEFAULT_OUTPUT_DIR / "face11_personalization.json",
    },
}

FORBIDDEN_FIXTURE_TEXT = (
    "/users/",
    "wansiyu",
    ".jpg",
    ".jpeg",
    ".png",
    "data:image",
    ";base64,",
)


def _reference_action(recipe: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    actions = recipe.get("actions")
    if not isinstance(actions, list):
        raise MainDemoValidationError("Reference recipe actions must be an array.")
    by_id = {
        action.get("action_id"): action
        for action in actions
        if isinstance(action, Mapping)
    }
    a04 = by_id.get("A04")
    a02 = by_id.get("A02")
    if not isinstance(a04, Mapping) or not isinstance(a02, Mapping):
        raise MainDemoValidationError("Reference recipe must contain A04 and A02.")
    source = a04.get("source")
    if not isinstance(source, Mapping) or not isinstance(
        source.get("reference_id"), str
    ):
        raise MainDemoValidationError("Reference A04 must contain source.reference_id.")
    a02_parameters = a02.get("parameters")
    if not isinstance(a02_parameters, Mapping):
        raise MainDemoValidationError("Reference A02 parameters are missing.")
    a04_parameters = _reference_parameters(recipe)
    return source["reference_id"], {
        "A04": {
            "direction_relative_to_eye_axis_deg": a04_parameters[
                "direction_relative_to_eye_axis_deg"
            ],
            "reference_extension_ratio": a04_parameters[
                "reference_extension_ratio"
            ],
            "start_position_ratio": a04_parameters["start_position_ratio"],
        },
        "A02": {
            "range_factor": float(a02_parameters["range_factor"]),
            "intensity_factor": float(a02_parameters["intensity_factor"]),
        },
    }


def safe_face_profile(
    profile: Mapping[str, Any], *, sample_id: str
) -> dict[str, Any]:
    """Copy a complete v0.3 profile while removing local provenance."""

    if profile.get("version") != "0.3":
        raise MainDemoValidationError("Face Profile v0.3 is required.")
    for feature in FEATURE_PATHS:
        _profile_number(profile, feature)
    safe = copy.deepcopy(dict(profile))
    safe["sample_id"] = sample_id
    safe["source_type"] = "safe_fixture"
    safe["raw_geometry_reference"] = {"source": "safe_fixture"}
    _assert_strict_finite(safe)
    return safe


def _fixture_decisions(result: Mapping[str, Any]) -> list[dict[str, Any]]:
    effects = {
        "eye_tail_angle.mean": "A04.direction",
        "relative_eye_length.mean": "A04.extension",
        "lower_lid_space_ratio.mean": "A02.range_and_intensity",
    }
    decisions = []
    for feature, effect in effects.items():
        source = result["feature_decisions"][feature]
        decisions.append(
            {
                "feature": feature,
                "blogger_value": source["blogger"],
                "user_value": source["user"],
                "signed_difference": source["difference"],
                "threshold": source["threshold"],
                "inside_dead_zone": source["inside_dead_zone"],
                "triggered_rule": source["triggered_rule"],
                "decision": source["decision"],
                "effect": effect,
            }
        )
    return decisions


def safe_personalization(
    result: Mapping[str, Any], *, sample_id: str, reference_id: str
) -> dict[str, Any]:
    """Convert a validated case output to the Product-facing fixture shape."""

    direction = result["A04"]["direction"]
    extension = result["A04"]["extension"]
    a02 = result["A02"]
    config = result["dead_zone_config"]
    decisions = _fixture_decisions(result)
    all_keep_reference = all(
        decision["decision"] == "KEEP_REFERENCE" for decision in decisions
    )
    fixture = {
        "mode": "reference_relative",
        "sample_id": sample_id,
        "reference_id": reference_id,
        "triggered_rules": list(result["triggered_rules"]),
        "decision": (
            "KEEP_REFERENCE"
            if all_keep_reference
            else "APPLY_RELATIVE_ADJUSTMENT"
        ),
        "dead_zone": {
            "enabled": bool(result["dead_zone_enabled"]),
            "status": config["status"],
            "scope": config["scope"],
            "thresholds": {
                "eye_tail_angle_deg": config["eye_tail_angle_deg"],
                "relative_eye_length": config["relative_eye_length"],
                "lower_lid_space_ratio": config["lower_lid_space_ratio"],
            },
        },
        # Preserve the complete validated pipeline payload for future Product
        # consumers while exposing stable, concise fields above.
        "source_validation_result": copy.deepcopy(dict(result)),
        "feature_decisions": decisions,
        "A04": {
            "reference_direction": direction["reference_direction_deg"],
            "blogger_correction": direction["blogger_correction_deg"],
            "user_correction": direction["user_correction_deg"],
            "raw_relative_direction_adjustment": direction[
                "raw_relative_adjustment_deg"
            ],
            "relative_direction_adjustment": direction[
                "relative_adjustment_deg"
            ],
            "personalized_direction": direction["personalized_direction_deg"],
            "reference_extension_ratio": extension[
                "reference_extension_ratio"
            ],
            "blogger_extension_factor": extension[
                "blogger_adaptation_factor"
            ],
            "user_extension_factor": extension["user_adaptation_factor"],
            "raw_relative_extension_factor": extension[
                "raw_relative_adaptation_factor"
            ],
            "relative_extension_factor": extension[
                "relative_adaptation_factor"
            ],
            "personalized_extension_ratio": extension[
                "personalized_extension_ratio"
            ],
            "start_position_ratio": result["A04"]["start_position_ratio"],
        },
        "A02": {
            "reference_range_factor": a02["reference_range_factor"],
            "blogger_range_factor": a02["blogger_range_mapping_factor"],
            "user_range_factor": a02["user_range_mapping_factor"],
            "raw_relative_range_factor": a02["raw_relative_range_factor"],
            "personalized_range_factor": a02["personalized_range_factor"],
            "reference_intensity_factor": a02["reference_intensity_factor"],
            "blogger_intensity_factor": a02[
                "blogger_intensity_mapping_factor"
            ],
            "user_intensity_factor": a02["user_intensity_mapping_factor"],
            "raw_relative_intensity_factor": a02[
                "raw_relative_intensity_factor"
            ],
            "personalized_intensity_factor": a02[
                "personalized_intensity_factor"
            ],
        },
    }
    _assert_strict_finite(fixture)
    return fixture


def _assert_private_text_absent(value: Mapping[str, Any]) -> None:
    serialized = json.dumps(value, ensure_ascii=False, allow_nan=False).lower()
    matches = [token for token in FORBIDDEN_FIXTURE_TEXT if token in serialized]
    if matches:
        raise MainDemoValidationError(
            "Unsafe fixture content found: " + ", ".join(matches)
        )


def generate_safe_fixtures(
    *,
    blogger_profile: Mapping[str, Any],
    profiles: Mapping[str, Mapping[str, Any]],
    reference_recipe: Mapping[str, Any],
    generated_results: Mapping[str, Mapping[str, Any]],
    output_dir: Path = DEFAULT_FIXTURE_DIR,
) -> dict[str, dict[str, Any]]:
    """Validate source results, sanitize them, and write five strict JSON files."""

    reference_id, reference_action = _reference_action(reference_recipe)
    reference_parameters = _reference_parameters(reference_recipe)
    fixtures: dict[str, dict[str, Any]] = {}
    for sample_id, profile in profiles.items():
        case = sample_id.replace("_", "")
        calculated = calculate_case(
            blogger_profile,
            profile,
            reference_parameters,
            case=case,
            dead_zone_enabled=True,
        )
        if calculated != generated_results[sample_id]:
            raise MainDemoValidationError(
                f"{sample_id} no longer matches the generated validation result."
            )
        fixtures[f"{sample_id}_face_profile.json"] = safe_face_profile(
            profile, sample_id=sample_id
        )
        fixtures[f"{sample_id}_personalization.json"] = safe_personalization(
            calculated, sample_id=sample_id, reference_id=reference_id
        )

    reference_fixture = {
        "reference_id": reference_id,
        "source_type": "safe_fixture",
        "blogger_face_profile_p0": {
            "eye_tail_angle_mean": _profile_number(
                blogger_profile, "eye_tail_angle.mean"
            ),
            "relative_eye_length_mean": _profile_number(
                blogger_profile, "relative_eye_length.mean"
            ),
            "lower_lid_space_ratio_mean": _profile_number(
                blogger_profile, "lower_lid_space_ratio.mean"
            ),
        },
        "reference_action": reference_action,
    }
    _assert_strict_finite(reference_fixture)
    fixtures["main_demo_reference.json"] = reference_fixture

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, fixture in fixtures.items():
        _assert_private_text_absent(fixture)
        save_json_output(output_dir / filename, fixture)
    return fixtures


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate privacy-safe Face06/Face11 Main Demo fixtures."
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        profiles = {
            sample_id: load_json_object(config["profile"])
            for sample_id, config in SAMPLES.items()
        }
        results = {
            sample_id: load_json_object(config["generated_result"])
            for sample_id, config in SAMPLES.items()
        }
        fixtures = generate_safe_fixtures(
            blogger_profile=load_json_object(DEFAULT_BLOGGER_PROFILE),
            profiles=profiles,
            reference_recipe=load_json_object(DEFAULT_REFERENCE_RECIPE),
            generated_results=results,
            output_dir=args.output_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}")
        return 1
    print(
        json.dumps(
            {"output_dir": str(args.output_dir), "files": sorted(fixtures)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
