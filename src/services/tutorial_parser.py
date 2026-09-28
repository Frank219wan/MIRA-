"""Provider-agnostic Week 1 tutorial-video parsing boundary."""

from __future__ import annotations

import logging
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.contracts.makeup import StandardRecipe
from src.observability import log_event

from .tutorial_prompt import TUTORIAL_PARSER_PROMPT, TUTORIAL_PROMPT_VERSION


class TutorialParserError(ValueError):
    """Base error returned when a tutorial cannot become a valid recipe."""


class TutorialModelOutputError(TutorialParserError):
    """A multimodal provider returned output outside the shared contract."""


class TutorialProviderError(TutorialParserError):
    """A provider failed before producing model output."""


class TutorialMediaInput(BaseModel):
    """Reference to a video file or an ordered directory of extracted frames."""

    model_config = ConfigDict(extra="forbid")

    media_path: Path
    media_kind: str = Field(pattern="^(video|frame_directory)$")
    recipe_id: str = Field(min_length=1)
    title: str = Field(min_length=1)


class TutorialVisionProvider(Protocol):
    """Adapter implemented by an eventual multimodal model integration."""

    def extract_action_units(
        self, media: TutorialMediaInput, prompt: str
    ) -> object: ...


@dataclass
class TutorialParserRun:
    """Debug metadata only; stores a media reference, never media bytes."""

    run_id: str
    request_id: str | None
    provider_name: str
    model_name: str | None
    prompt_version: str
    input_media_path: str
    input_media_kind: str
    recipe_id: str
    tutorial_title: str
    raw_provider_output: object | None = None
    validated_recipe: dict[str, Any] | None = None
    validation_error: str | None = None
    error_traceback: str | None = None
    schema_version: str | None = None
    duration_ms: int | None = None


class MockTutorialVisionProvider:
    """Offline deterministic provider for tests and contract demonstrations."""

    def __init__(self, output: object | None = None) -> None:
        self.output = output if output is not None else {"action_units": _mock_steps()}
        self.provider_name = "mock"
        self.model_name = None

    def extract_action_units(
        self, media: TutorialMediaInput, prompt: str
    ) -> object:
        return self.output


class TutorialParser:
    """Converts multimodal provider output into one validated StandardRecipe."""

    def __init__(self, provider: TutorialVisionProvider) -> None:
        self.provider = provider

    def parse(
        self,
        input: TutorialMediaInput,
        request_id: str | None = None,
        run_observer: Callable[[TutorialParserRun], None] | None = None,
    ) -> StandardRecipe:
        """Call the provider and validate a Week 1 recipe, optionally observing a run."""
        started = time.perf_counter()
        run = TutorialParserRun(
            run_id=f"parser-{uuid4()}",
            request_id=request_id,
            provider_name=str(getattr(self.provider, "provider_name", type(self.provider).__name__)),
            model_name=getattr(self.provider, "model_name", None),
            prompt_version=TUTORIAL_PROMPT_VERSION,
            input_media_path=str(input.media_path),
            input_media_kind=input.media_kind,
            recipe_id=input.recipe_id,
            tutorial_title=input.title,
        )
        log_event(
            "tutorial_parse_start",
            module="tutorial_parser",
            request_id=request_id,
            run_id=run.run_id,
            provider_name=run.provider_name,
            prompt_version=run.prompt_version,
        )
        try:
            log_event(
                "provider_call_start",
                module="tutorial_parser",
                request_id=request_id,
                run_id=run.run_id,
                provider_name=run.provider_name,
            )
            try:
                raw_output = self.provider.extract_action_units(input, TUTORIAL_PARSER_PROMPT)
            except Exception:
                log_event(
                    "provider_call_end",
                    module="tutorial_parser",
                    request_id=request_id,
                    run_id=run.run_id,
                    provider_name=run.provider_name,
                    error_code="provider_failure",
                )
                raise
            run.raw_provider_output = raw_output
            log_event(
                "provider_call_end",
                module="tutorial_parser",
                request_id=request_id,
                run_id=run.run_id,
                provider_name=run.provider_name,
                error_code=None,
            )
            recipe = self.validate_provider_output(input, raw_output)
            run.validated_recipe = recipe.model_dump(mode="json")
            run.schema_version = recipe.schema_version
            log_event(
                "schema_validation_success",
                module="tutorial_parser",
                request_id=request_id,
                run_id=run.run_id,
                recipe_id=recipe.recipe_id,
                schema_version=recipe.schema_version,
            )
            return recipe
        except TutorialParserError as exc:
            run.validation_error = str(exc)
            run.error_traceback = traceback.format_exc()
            logging.getLogger("mira").exception(
                "tutorial_parser_failure request_id=%s run_id=%s",
                request_id,
                run.run_id,
            )
            log_event(
                "schema_validation_failure",
                module="tutorial_parser",
                request_id=request_id,
                run_id=run.run_id,
                error_code="parser_failure",
            )
            raise
        except Exception as exc:
            run.validation_error = str(exc)
            run.error_traceback = traceback.format_exc()
            logging.getLogger("mira").exception(
                "tutorial_provider_failure request_id=%s run_id=%s",
                request_id,
                run.run_id,
            )
            raise TutorialProviderError("Tutorial provider call failed.") from exc
        finally:
            run.duration_ms = round((time.perf_counter() - started) * 1000)
            log_event(
                "tutorial_parse_end",
                module="tutorial_parser",
                request_id=request_id,
                run_id=run.run_id,
                duration_ms=run.duration_ms,
                error_code="parser_failure" if run.validation_error else None,
            )
            if run_observer is not None:
                try:
                    run_observer(run)
                except Exception:
                    logging.getLogger("mira").exception(
                        "tutorial_run_observer_failure request_id=%s run_id=%s",
                        request_id,
                        run.run_id,
                    )

    def validate_provider_output(
        self, input: TutorialMediaInput, raw_output: object
    ) -> StandardRecipe:
        """Validate stored provider output without making a provider call."""
        if not isinstance(raw_output, dict) or "action_units" not in raw_output:
            raise TutorialModelOutputError(
                "Tutorial model output must be an object containing action_units."
            )
        try:
            recipe = StandardRecipe.model_validate(
                {
                    "recipe_id": input.recipe_id,
                    "title": input.title,
                    "source_media_path": str(input.media_path),
                    "action_units": raw_output["action_units"],
                }
            )
        except ValidationError as exc:
            raise TutorialModelOutputError(
                "Tutorial model output failed StandardRecipe validation: "
                f"{exc.errors(include_url=False)}"
            ) from exc
        if len(recipe.action_units) != 5:
            raise TutorialModelOutputError(
                "Week 1 tutorial parser requires exactly 5 action_units."
            )
        return recipe


def _mock_steps() -> list[dict[str, Any]]:
    return [
        {"step_index": 1, "area": "upper eyelid", "goal": "prime", "product_requirement": "eye primer", "tool": "fingertip", "motion": "pat", "intensity": "light", "target_result": "even base", "time_range_seconds": [0, 8], "confidence": 0.99},
        {"step_index": 2, "area": "crease", "goal": "add depth", "product_requirement": "matte transition shadow", "tool": "blending brush", "motion": "windshield-wiper blend", "intensity": "sheer", "target_result": "soft transition", "time_range_seconds": [8, 20], "confidence": 0.97},
        {"step_index": 3, "area": "outer corner", "goal": "define", "product_requirement": "matte deep shadow", "tool": "detail brush", "motion": "press and blend", "intensity": "medium", "target_result": "defined outer corner", "time_range_seconds": [20, 32], "confidence": 0.96},
        {"step_index": 4, "area": "center lid", "goal": "brighten", "product_requirement": "shimmer shadow", "tool": "flat shader brush", "motion": "pat", "intensity": "medium", "target_result": "reflective lid", "time_range_seconds": [32, 42], "confidence": 0.98},
        {"step_index": 5, "area": "upper lash line", "goal": "define", "product_requirement": "eyeliner", "tool": "liner brush", "motion": "short stroke", "intensity": "light", "target_result": "clean lash-line definition", "time_range_seconds": [42, 55], "confidence": 0.95},
    ]
