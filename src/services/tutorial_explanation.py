"""Convert authoritative CV output into deterministic facts and safe wording."""

from __future__ import annotations

import copy
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import uuid4

from src.contracts.cv_actions import PersonalizedActionWrapper
from src.contracts.makeup import MakeupActionUnit
from src.contracts.matching import MatchingItem
from src.contracts.my_tutorial import (
    FaceProfileReference,
    MyTutorialStep,
    TutorialStepProvenance,
)
from src.contracts.tutorial_explanation import (
    ExplanationFacts,
    GeneratedTutorialText,
    ParameterChange,
    ReasonEvidence,
)
from src.services.tutorial_explanation_prompt import (
    TUTORIAL_EXPLANATION_PROMPT,
    TUTORIAL_EXPLANATION_PROMPT_VERSION,
)


EXPLANATION_GENERATOR_VERSION = "1.0"

REFERENCE_PARAMETER_ALIASES = {
    "personalized_direction_deg": ("reference_direction_deg", "direction_relative_to_eye_axis_deg"),
    "personalized_extension_ratio": ("reference_extension_ratio",),
    "personalized_range_factor": ("reference_range_factor", "range_factor"),
    "personalized_intensity_factor": ("reference_intensity_factor", "intensity_factor"),
}


class TutorialExplanationError(ValueError):
    """Raised when authoritative CV data is absent or internally inconsistent."""


class ExplanationProvider(Protocol):
    provider_name: str
    model_name: str | None

    def generate(
        self,
        *,
        prompt: str,
        standard_action: dict[str, Any],
        facts: dict[str, Any],
        cv_personalized_action: dict[str, Any],
        product_match: dict[str, Any] | None,
    ) -> GeneratedTutorialText | Mapping[str, Any]: ...


@dataclass(frozen=True)
class TutorialExplanationRun:
    run_id: str
    request_id: str | None
    recipe_id: str
    step_index: int
    action_id: str
    source_standard_action: dict[str, Any]
    face_profile_id: str
    face_profile_version: str
    cv_personalized_action: dict[str, Any]
    deterministic_facts: dict[str, Any]
    applied_rules: list[str]
    explanation_generator_version: str
    prompt_version: str
    provider_name: str
    model_name: str | None
    fallback_used: bool
    response: dict[str, Any]


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TutorialExplanationError(f"Required CV numeric field is missing: {label}.")
    number = float(value)
    if not math.isfinite(number):
        raise TutorialExplanationError(f"Required CV numeric field is not finite: {label}.")
    return number


def build_explanation_facts(wrapper: PersonalizedActionWrapper) -> ExplanationFacts:
    """Derive facts only; never execute or reinterpret personalization rules."""

    action = wrapper.personalized_action
    adjustments_by_parameter = {item.parameter: item for item in action.adjustments}
    changes: list[ParameterChange] = []
    reasons: list[ReasonEvidence] = []

    for parameter, personalized_raw in action.personalized_parameters.items():
        reference_parameter = parameter
        if reference_parameter not in action.original_parameters:
            reference_parameter = next(
                (
                    candidate
                    for candidate in REFERENCE_PARAMETER_ALIASES.get(parameter, ())
                    if candidate in action.original_parameters
                ),
                "",
            )
        if not reference_parameter:
            continue
        reference_raw = action.original_parameters[reference_parameter]
        if isinstance(reference_raw, bool) or isinstance(personalized_raw, bool):
            continue
        if not isinstance(reference_raw, (int, float)) or not isinstance(
            personalized_raw, (int, float)
        ):
            continue
        reference = _number(reference_raw, f"original_parameters.{parameter}")
        personalized = _number(
            personalized_raw, f"personalized_parameters.{parameter}"
        )
        delta = round(personalized - reference, 12)
        adjustment = adjustments_by_parameter.get(parameter)
        rule_ids = list(adjustment.rule_ids) if adjustment else []
        changes.append(
            ParameterChange(
                parameter=parameter,
                reference_value=reference,
                personalized_value=personalized,
                delta=delta,
                direction=(
                    "increased" if delta > 0 else "decreased" if delta < 0 else "unchanged"
                ),
                rule_ids=rule_ids,
                feature_path=adjustment.feature_path if adjustment else None,
                feature_value=adjustment.feature_value if adjustment else None,
                operation=adjustment.operation if adjustment else None,
                adjustment_value=adjustment.adjustment_value if adjustment else None,
            )
        )
        if adjustment is not None:
            reasons.append(
                ReasonEvidence(
                    parameter=parameter,
                    feature_path=adjustment.feature_path,
                    feature_value=adjustment.feature_value,
                    rule_ids=list(adjustment.rule_ids),
                )
            )

    if not changes:
        raise TutorialExplanationError(
            f"CV PersonalizedAction {action.action_id} has no comparable numeric parameters."
        )
    return ExplanationFacts(
        action_id=action.action_id,
        changes=changes,
        applied_rules=list(action.applied_rules),
        reasons=reasons,
    )


def _exact(value: float) -> str:
    return repr(value)


def _change_instruction(change: ParameterChange) -> str:
    old = _exact(change.reference_value)
    new = _exact(change.personalized_value)
    delta = _exact(change.delta)
    suffix = f"（{old} → {new}，Δ {delta}）"
    if change.direction == "unchanged":
        return f"保持 {change.parameter} 不变{suffix}"
    if change.parameter in {"direction_angle_deg", "personalized_direction_deg"}:
        motion = "让线条更平一些" if change.direction == "decreased" else "让线条更上扬一些"
    elif "extension" in change.parameter:
        motion = "向外延伸得更远一些" if change.direction == "increased" else "缩短向外延伸"
    elif "range" in change.parameter:
        motion = "扩大覆盖范围" if change.direction == "increased" else "收窄覆盖范围"
    elif "intensity" in change.parameter:
        motion = "增强用量或显色" if change.direction == "increased" else "减轻用量或显色"
    else:
        motion = "增加该参数" if change.direction == "increased" else "减少该参数"
    return f"{motion}{suffix}"


def template_explanation(
    standard_action: MakeupActionUnit,
    facts: ExplanationFacts,
    cv_personalized_action: Mapping[str, Any],
) -> GeneratedTutorialText:
    how = "；".join(_change_instruction(change) for change in facts.changes)
    evidence = "；".join(
        f"{reason.feature_path}={_exact(reason.feature_value)}，规则 {','.join(reason.rule_ids)}"
        for reason in facts.reasons
    )
    rules = ",".join(facts.applied_rules) or "无触发规则"
    why = (
        f"依据 CV 证据：{evidence}。触发规则：{rules}。"
        if evidence
        else f"触发规则：{rules}。"
    )
    parameters = cv_personalized_action.get("personalized_parameters", {})
    region = (
        parameters.get("region") or parameters.get("target_region")
        if isinstance(parameters, Mapping)
        else None
    )
    return GeneratedTutorialText(
        where=str(region) if region is not None else standard_action.area,
        how=how,
        why=why,
        stop_when=standard_action.target_result,
    )


def _validate_provider_numbers(
    text: GeneratedTutorialText, facts: ExplanationFacts
) -> None:
    allowed = {
        _exact(value)
        for change in facts.changes
        for value in (
            change.reference_value,
            change.personalized_value,
            change.delta,
            change.feature_value,
            change.adjustment_value,
        )
        if value is not None
    }
    supplied = " ".join((text.where, text.how, text.why, text.stop_when))
    mentioned = set(re.findall(r"[-+]?\d+(?:\.\d+)?", supplied))
    unsupported = sorted(mentioned - allowed)
    if unsupported:
        raise ValueError(
            "Explanation provider introduced unsupported numeric text: "
            + ", ".join(unsupported)
        )


class TutorialExplanationService:
    def __init__(self, provider: ExplanationProvider | None = None) -> None:
        self.provider = provider

    def generate_step(
        self,
        *,
        standard_action: MakeupActionUnit,
        personalized: PersonalizedActionWrapper,
        face_profile: FaceProfileReference,
        request_id: str | None = None,
        product_match: dict[str, Any] | None = None,
        matching_id: str | None = None,
        run_observer: Callable[[TutorialExplanationRun], None] | None = None,
    ) -> MyTutorialStep:
        cv_action = personalized.personalized_action
        if personalized.step_index != standard_action.step_index:
            raise TutorialExplanationError("CV result step_index does not match source action.")
        if personalized.provenance.source_step_index != standard_action.step_index:
            raise TutorialExplanationError("CV provenance does not match source action.")
        if personalized.face_profile_version != face_profile.version:
            raise TutorialExplanationError("Face Profile version does not match CV result.")
        if personalized.provenance.standard_makeup_action.action_id != cv_action.action_id:
            raise TutorialExplanationError("CV action_id does not match mapping provenance.")

        cv_before = copy.deepcopy(cv_action.model_dump())
        facts = build_explanation_facts(personalized)
        fallback_used = self.provider is None
        provider_name = "deterministic-template"
        model_name: str | None = None
        text: GeneratedTutorialText
        if self.provider is None:
            text = template_explanation(standard_action, facts, cv_before)
        else:
            provider_name = self.provider.provider_name
            model_name = self.provider.model_name
            try:
                generated = self.provider.generate(
                    prompt=TUTORIAL_EXPLANATION_PROMPT,
                    standard_action=standard_action.model_dump(),
                    facts=facts.model_dump(),
                    cv_personalized_action=cv_before,
                    product_match=copy.deepcopy(product_match),
                )
                text = (
                    generated
                    if isinstance(generated, GeneratedTutorialText)
                    else GeneratedTutorialText.model_validate(generated)
                )
                _validate_provider_numbers(text, facts)
            except Exception:
                fallback_used = True
                text = template_explanation(standard_action, facts, cv_before)

        if cv_action.model_dump() != cv_before:
            raise TutorialExplanationError("Explanation provider modified authoritative CV output.")

        run_id = f"tutorial-explanation-{uuid4()}"
        provenance = TutorialStepProvenance(
            request_id=request_id,
            run_id=run_id,
            source_recipe_id=personalized.recipe_id,
            source_step_index=standard_action.step_index,
            face_profile_version=face_profile.version,
            face_profile_id=face_profile.profile_id,
            matching_id=matching_id,
            product_id=(product_match or {}).get("product_id"),
            mapping_version=personalized.provenance.mapping_version,
            applied_rules=list(cv_action.applied_rules),
            cv_adjustments=list(cv_action.adjustments),
            explanation_generator_version=EXPLANATION_GENERATOR_VERSION,
            prompt_version=TUTORIAL_EXPLANATION_PROMPT_VERSION,
            provider_name=provider_name,
            model_name=model_name,
            fallback_used=fallback_used,
        )
        step = MyTutorialStep(
            action_id=cv_action.action_id,
            step_index=standard_action.step_index,
            personalization_status="personalized",
            standard_action=standard_action,
            cv_standard_action=personalized.provenance,
            face_profile=face_profile,
            cv_personalized_action=personalized,
            where=text.where,
            how=text.how,
            why=text.why,
            stop_when=text.stop_when,
            reference_parameters=copy.deepcopy(cv_action.original_parameters),
            personalized_parameters=copy.deepcopy(cv_action.personalized_parameters),
            applied_rules=list(cv_action.applied_rules),
            provenance=provenance,
            fallback_status="template_fallback" if fallback_used else "none",
        )
        if run_observer is not None:
            run_observer(
                TutorialExplanationRun(
                    run_id=run_id,
                    request_id=request_id,
                    recipe_id=personalized.recipe_id,
                    step_index=standard_action.step_index,
                    action_id=cv_action.action_id,
                    source_standard_action=standard_action.model_dump(),
                    face_profile_id=face_profile.profile_id,
                    face_profile_version=face_profile.version,
                    cv_personalized_action=cv_before,
                    deterministic_facts=facts.model_dump(),
                    applied_rules=list(cv_action.applied_rules),
                    explanation_generator_version=EXPLANATION_GENERATOR_VERSION,
                    prompt_version=TUTORIAL_EXPLANATION_PROMPT_VERSION,
                    provider_name=provider_name,
                    model_name=model_name,
                    fallback_used=fallback_used,
                    response=step.model_dump(),
                )
            )
        return step

    def generate_standard_fallback_step(
        self,
        *,
        standard_action: MakeupActionUnit,
        recipe_id: str,
        face_profile: FaceProfileReference,
        personalization_status: str,
        action_id: str | None,
        mapping_version: str,
        matching_id: str,
        match_result: MatchingItem,
        request_id: str | None = None,
    ) -> MyTutorialStep:
        """Render an unmapped action without inventing CV parameters or rules."""

        if personalization_status not in {"unsupported", "not_applicable"}:
            raise TutorialExplanationError("Invalid standard fallback personalization status.")
        match_context = {
            "missing_capability": "当前 Beauty Kit 缺少此步骤所需能力",
            "functional_conflict": "当前候选产品存在功能冲突，未自动替换",
            "low_match": "当前产品仅为低匹配，请留意妆效差异",
        }.get(match_result.decision or "", "此步骤暂不支持 CV 个性化")
        run_id = f"tutorial-explanation-{uuid4()}"
        return MyTutorialStep(
            action_id=action_id,
            step_index=standard_action.step_index,
            personalization_status=personalization_status,
            standard_action=standard_action,
            match_result=match_result,
            face_profile=face_profile,
            where=standard_action.area,
            how=(
                f"使用 {standard_action.tool}，以 {standard_action.intensity} 强度"
                f"进行 {standard_action.motion}。"
            ),
            why=f"{match_context}；保留原教程确定性步骤。",
            stop_when=standard_action.target_result,
            reference_parameters={},
            personalized_parameters={},
            applied_rules=[],
            provenance=TutorialStepProvenance(
                request_id=request_id,
                run_id=run_id,
                source_recipe_id=recipe_id,
                source_step_index=standard_action.step_index,
                face_profile_version=face_profile.version,
                face_profile_id=face_profile.profile_id,
                matching_id=matching_id,
                product_id=match_result.product_id,
                mapping_version=mapping_version,
                applied_rules=[],
                cv_adjustments=[],
                explanation_generator_version=EXPLANATION_GENERATOR_VERSION,
                prompt_version="standard-action-fallback-v1",
                provider_name="deterministic-template",
                fallback_used=True,
            ),
            fallback_status="standard_action_fallback",
        )
