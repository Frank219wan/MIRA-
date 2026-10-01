"""My Tutorial v0.2 response and provenance contracts."""

from typing import Any, Literal

from pydantic import Field, model_validator

from .common import ContractModel
from .cv_actions import AdaptedCVAction, CVAdjustment, PersonalizedActionWrapper
from .makeup import MakeupActionUnit
from .matching import MatchingItem


class FaceProfileReference(ContractModel):
    profile_id: str = Field(min_length=1)
    version: Literal["0.3"] = "0.3"


class TutorialStepProvenance(ContractModel):
    request_id: str | None = None
    run_id: str = Field(min_length=1)
    source_recipe_id: str = Field(min_length=1)
    source_step_index: int = Field(ge=1)
    face_profile_version: Literal["0.3"] = "0.3"
    face_profile_id: str = Field(min_length=1)
    matching_id: str | None = None
    product_id: str | None = None
    mapping_version: str | None = None
    applied_rules: list[str] = Field(default_factory=list)
    cv_adjustments: list[CVAdjustment] = Field(default_factory=list)
    explanation_generator_version: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    provider_name: str = Field(min_length=1)
    model_name: str | None = None
    fallback_used: bool


class MyTutorialStep(ContractModel):
    action_id: str | None = Field(default=None, pattern=r"^A\d{2}$")
    step_index: int = Field(ge=1)
    personalization_status: Literal[
        "personalized", "unsupported", "not_applicable"
    ] = "personalized"
    standard_action: MakeupActionUnit
    cv_standard_action: AdaptedCVAction | None = None
    match_result: MatchingItem | None = None
    face_profile: FaceProfileReference | None = None
    cv_personalized_action: PersonalizedActionWrapper | None = None
    where: str = Field(min_length=1)
    how: str = Field(min_length=1)
    why: str = Field(min_length=1)
    stop_when: str = Field(min_length=1)
    reference_parameters: dict[str, Any]
    personalized_parameters: dict[str, Any]
    applied_rules: list[str]
    provenance: TutorialStepProvenance
    fallback_status: Literal["none", "template_fallback", "standard_action_fallback"]

    @model_validator(mode="after")
    def require_consistent_links(self) -> "MyTutorialStep":
        if self.standard_action.step_index != self.step_index:
            raise ValueError("standard_action.step_index must match step_index")
        if self.cv_standard_action is not None:
            if self.cv_standard_action.source_step_index != self.step_index:
                raise ValueError("cv_standard_action source step must match step_index")
            if self.cv_standard_action.standard_makeup_action.action_id != self.action_id:
                raise ValueError("cv_standard_action action_id must match action_id")
        if self.cv_personalized_action is not None:
            if self.cv_personalized_action.step_index != self.step_index:
                raise ValueError("cv_personalized_action step must match step_index")
            if self.cv_personalized_action.personalized_action.action_id != self.action_id:
                raise ValueError("cv_personalized_action action_id must match action_id")
        if self.match_result is not None and self.match_result.step_index != self.step_index:
            raise ValueError("match_result step must match step_index")
        if self.personalization_status == "personalized":
            if self.action_id is None or self.cv_personalized_action is None:
                raise ValueError("personalized steps require an action_id and CV result")
        elif self.cv_standard_action is not None or self.cv_personalized_action is not None:
            raise ValueError("unsupported/not_applicable steps cannot contain CV actions")
        return self


class MyTutorialResponse(ContractModel):
    schema_version: Literal["0.2"] = "0.2"
    tutorial_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    steps: list[MyTutorialStep] = Field(min_length=1)
