"""Backend-owned end-to-end My Tutorial orchestration."""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from pathlib import Path
from uuid import uuid4

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.cv_actions import (
    CVPersonalizedAction,
    DecodedActionMappingConfig,
    PersonalizedActionWrapper,
)
from src.contracts.cv_adaptation import validate_cv_face_profile
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult
from src.contracts.my_tutorial import FaceProfileReference, MyTutorialResponse, MyTutorialStep
from src.observability import log_event
from src.personalization_engine import PersonalizationEngineError, personalize_action
from src.services.decoded_action_adapter import (
    DecodedActionMappingError,
    adapt_decoded_action,
)
from src.services.product_matching import ProductMatchingService
from src.services.tutorial_explanation import (
    TutorialExplanationError,
    TutorialExplanationRun,
    TutorialExplanationService,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MAPPING_PATH = (
    PROJECT_ROOT / "data" / "fixtures" / "decoded_cv_action_mapping_demo_v1.json"
)
ORCHESTRATOR_VERSION = "1.0"


class MyTutorialOrchestrationError(ValueError):
    """Raised when a validated orchestration input cannot be processed safely."""


class MyTutorialOrchestrator:
    def __init__(
        self,
        *,
        matcher: ProductMatchingService | None = None,
        explanation: TutorialExplanationService | None = None,
        mapping_config: DecodedActionMappingConfig | None = None,
    ) -> None:
        self.matcher = matcher or ProductMatchingService()
        self.explanation = explanation or TutorialExplanationService()
        self.mapping_config = mapping_config or self._load_mapping(DEFAULT_MAPPING_PATH)

    @staticmethod
    def _load_mapping(path: Path) -> DecodedActionMappingConfig:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return DecodedActionMappingConfig.model_validate(payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise MyTutorialOrchestrationError(
                f"Unable to load decoded-action mapping: {path}"
            ) from exc

    def generate(
        self,
        *,
        recipe: StandardRecipe,
        beauty_kit: BeautyKit,
        face_profile: dict,
        face_profile_id: str,
        capabilities: list[ProductCapability],
        target_effect: str = "cat_eye",
        tutorial_id: str | None = None,
        request_id: str | None = None,
        explanation_run_observer: Callable[[TutorialExplanationRun], None] | None = None,
    ) -> MyTutorialResponse:
        recipe_before = copy.deepcopy(recipe.model_dump(mode="json"))
        kit_before = copy.deepcopy(beauty_kit.model_dump(mode="json"))
        profile_before = copy.deepcopy(face_profile)
        capabilities_before = copy.deepcopy(
            [item.model_dump(mode="json") for item in capabilities]
        )
        try:
            validated_profile = validate_cv_face_profile(copy.deepcopy(face_profile))
        except ValueError as exc:
            raise MyTutorialOrchestrationError(str(exc)) from exc
        if target_effect != "cat_eye":
            raise MyTutorialOrchestrationError(
                f"Unsupported target_effect: {target_effect!r}; expected 'cat_eye'."
            )
        face_reference = FaceProfileReference(
            profile_id=face_profile_id, version=validated_profile["version"]
        )
        log_event(
            "my_tutorial_orchestration_start",
            module="my_tutorial_orchestrator",
            request_id=request_id,
            orchestrator_version=ORCHESTRATOR_VERSION,
            recipe_id=recipe.recipe_id,
            beauty_kit_id=beauty_kit.kit_id,
            face_profile_version=validated_profile["version"],
            target_effect=target_effect,
        )
        matching = self.matcher.match(
            recipe, beauty_kit, capabilities, request_id=request_id
        )
        log_event(
            "my_tutorial_matching_complete",
            module="my_tutorial_orchestrator",
            request_id=request_id,
            recipe_id=recipe.recipe_id,
            matching_id=matching.matching_id,
            decisions=[item.decision for item in matching.items],
        )
        matches = {item.step_index: item for item in matching.items}
        steps: list[MyTutorialStep] = []
        for action in recipe.action_units:
            match_item = matches[action.step_index]
            mappings = [
                item for item in self.mapping_config.mappings
                if item.source.area == action.area
                and item.source.goal == action.goal
                and item.source.product_requirement == action.product_requirement
            ]
            if not mappings:
                steps.append(
                    self.explanation.generate_standard_fallback_step(
                        standard_action=action,
                        recipe_id=recipe.recipe_id,
                        face_profile=face_reference,
                        personalization_status="not_applicable",
                        action_id=None,
                        mapping_version=self.mapping_config.mapping_version,
                        matching_id=matching.matching_id,
                        match_result=match_item,
                        request_id=request_id,
                    )
                )
                self._log_step(request_id, action.step_index, "not_applicable", match_item.decision)
                continue
            if len(mappings) != 1 or mappings[0].status != "approved":
                steps.append(
                    self.explanation.generate_standard_fallback_step(
                        standard_action=action,
                        recipe_id=recipe.recipe_id,
                        face_profile=face_reference,
                        personalization_status="unsupported",
                        action_id=mappings[0].action_id if len(mappings) == 1 else None,
                        mapping_version=self.mapping_config.mapping_version,
                        matching_id=matching.matching_id,
                        match_result=match_item,
                        request_id=request_id,
                    )
                )
                self._log_step(request_id, action.step_index, "unsupported", match_item.decision)
                continue
            try:
                adapted = adapt_decoded_action(action, self.mapping_config)
                raw_cv_result = personalize_action(
                    validated_profile,
                    adapted.standard_makeup_action.model_dump(),
                    target_effect,
                )
                cv_result = CVPersonalizedAction.model_validate(raw_cv_result)
                if cv_result.model_dump(mode="json") != raw_cv_result:
                    raise MyTutorialOrchestrationError(
                        "CV PersonalizedAction validation changed authoritative output."
                    )
                wrapper = PersonalizedActionWrapper(
                    recipe_id=recipe.recipe_id,
                    step_index=action.step_index,
                    face_profile_version=validated_profile["version"],
                    personalized_action=cv_result,
                    provenance=adapted,
                )
                step = self.explanation.generate_step(
                    standard_action=action,
                    personalized=wrapper,
                    face_profile=face_reference,
                    request_id=request_id,
                    product_match=match_item.model_dump(mode="json"),
                    matching_id=matching.matching_id,
                    run_observer=explanation_run_observer,
                )
                step = MyTutorialStep.model_validate(
                    {**step.model_dump(mode="json"), "match_result": match_item.model_dump(mode="json")}
                )
            except (DecodedActionMappingError, PersonalizationEngineError, TutorialExplanationError) as exc:
                raise MyTutorialOrchestrationError(
                    f"Step {action.step_index} personalization failed: {exc}"
                ) from exc
            steps.append(step)
            self._log_step(
                request_id,
                action.step_index,
                "personalized",
                match_item.decision,
                action_id=cv_result.action_id,
                mapping_version=adapted.mapping_version,
                applied_rules=cv_result.applied_rules,
            )

        if recipe.model_dump(mode="json") != recipe_before:
            raise MyTutorialOrchestrationError("Orchestration mutated StandardRecipe input.")
        if beauty_kit.model_dump(mode="json") != kit_before:
            raise MyTutorialOrchestrationError("Orchestration mutated BeautyKit input.")
        if face_profile != profile_before:
            raise MyTutorialOrchestrationError("Orchestration mutated Face Profile input.")
        if [item.model_dump(mode="json") for item in capabilities] != capabilities_before:
            raise MyTutorialOrchestrationError("Orchestration mutated capability input.")
        response = MyTutorialResponse(
            tutorial_id=tutorial_id or f"my-tutorial-{uuid4()}",
            recipe_id=recipe.recipe_id,
            steps=steps,
        )
        log_event(
            "my_tutorial_orchestration_complete",
            module="my_tutorial_orchestrator",
            request_id=request_id,
            tutorial_id=response.tutorial_id,
            recipe_id=recipe.recipe_id,
            matching_id=matching.matching_id,
            step_count=len(steps),
        )
        return response

    @staticmethod
    def _log_step(
        request_id: str | None,
        step_index: int,
        personalization_status: str,
        match_decision: str | None,
        **fields: object,
    ) -> None:
        log_event(
            "my_tutorial_step_assembled",
            module="my_tutorial_orchestrator",
            request_id=request_id,
            step_index=step_index,
            personalization_status=personalization_status,
            match_decision=match_decision,
            **fields,
        )
