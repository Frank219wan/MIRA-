"""Run Reference Package -> personalization -> normalized AR guidance."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ar_guidance import build_a02_guidance, build_a04_guidance  # noqa: E402
from src.personalization_engine import load_json_object, save_json_output  # noqa: E402
from src.reference_package import (  # noqa: E402
    package_existing_reference,
    personalize_reference_package,
    reference_a04_parameters,
)


FIXTURE_DIR = PROJECT_ROOT / "data" / "fixtures" / "main_demo"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "main_demo_pipeline"


class MainDemoPipelineError(ValueError):
    """Raised when the CLI inputs cannot form a complete demo output."""


def run_demo(
    *,
    reference_package: Mapping[str, Any],
    user_profile: Mapping[str, Any],
    landmarks: Mapping[str, Any],
    sample_id: str,
) -> dict[str, Any]:
    side = landmarks.get("side")
    if not isinstance(side, str):
        raise MainDemoPipelineError("Landmarks JSON must include side.")
    personalization = personalize_reference_package(
        reference_package, user_profile, sample_id=sample_id
    )
    reference_a04 = reference_a04_parameters(reference_package)
    reference_a02 = {
        "range_factor": personalization["A02"]["reference_range_factor"],
        "intensity_factor": personalization["A02"][
            "reference_intensity_factor"
        ],
    }
    guidance = {
        "schema_version": "0.1",
        "sample_id": sample_id,
        "reference": {
            "A04": build_a04_guidance(
                landmarks,
                reference_a04,
                side,
                source="reference_action",
            ),
            "A02": build_a02_guidance(
                landmarks,
                reference_a02,
                side,
                source="reference_action",
            ),
        },
        "personalized": {
            "A04": build_a04_guidance(
                landmarks,
                personalization["A04"],
                side,
                source="personalized_action",
            ),
            "A02": build_a02_guidance(
                landmarks,
                personalization["A02"],
                side,
                source="personalized_action",
            ),
        },
    }
    return {
        "reference_package": dict(reference_package),
        "personalization": personalization,
        "ar_guidance": guidance,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=("existing_reference", "video_reference"),
        default="existing_reference",
    )
    parser.add_argument(
        "--reference-package",
        type=Path,
        help="Required for video_reference; ignored for existing_reference.",
    )
    parser.add_argument("--sample", choices=("face_06", "face_11"))
    parser.add_argument("--user-profile", type=Path)
    parser.add_argument("--landmarks", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if (args.sample is None) == (args.user_profile is None):
            raise MainDemoPipelineError(
                "Provide exactly one of --sample or --user-profile."
            )
        if args.mode == "existing_reference":
            package = package_existing_reference(
                load_json_object(FIXTURE_DIR / "main_demo_reference.json")
            )
        else:
            if args.reference_package is None:
                raise MainDemoPipelineError(
                    "--reference-package is required for video_reference."
                )
            package = load_json_object(args.reference_package)
            if package.get("mode") != "video_reference":
                raise MainDemoPipelineError(
                    "Expected a video_reference Reference Package."
                )
        if args.sample is not None:
            sample_id = args.sample
            user_profile = load_json_object(
                FIXTURE_DIR / f"{args.sample}_face_profile.json"
            )
        else:
            assert args.user_profile is not None
            sample_id = args.user_profile.stem
            user_profile = load_json_object(args.user_profile)
        outputs = run_demo(
            reference_package=package,
            user_profile=user_profile,
            landmarks=load_json_object(args.landmarks),
            sample_id=sample_id,
        )
        args.output.mkdir(parents=True, exist_ok=True)
        save_json_output(
            args.output / "reference_package.json",
            outputs["reference_package"],
        )
        save_json_output(
            args.output / "personalization.json", outputs["personalization"]
        )
        save_json_output(
            args.output / "ar_guidance.json", outputs["ar_guidance"]
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Main Demo pipeline failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "output_dir": str(args.output),
                "sample_id": sample_id,
                "triggered_rules": outputs["personalization"][
                    "triggered_rules"
                ],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
