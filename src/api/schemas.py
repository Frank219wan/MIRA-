"""Request envelopes used only by the Week 1 HTTP boundary."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from src.contracts.beauty_kit import BeautyKit, ProductCapability
from src.contracts.common import ContractModel
from src.contracts.cv_adaptation import CVAdaptation, validate_cv_face_profile
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult


class MatchingRequest(ContractModel):
    recipe: StandardRecipe | None = None
    recipe_id: str | None = Field(default=None, min_length=1)
    beauty_kit: BeautyKit
    capabilities: list[ProductCapability] | None = None

    @model_validator(mode="after")
    def require_one_recipe_source(self) -> "MatchingRequest":
        if (self.recipe is None) == (self.recipe_id is None):
            raise ValueError("provide exactly one of recipe or recipe_id")
        return self


class CVAdaptationRequest(ContractModel):
    recipe: StandardRecipe
    face_profile: dict


class ExplanationRequest(ContractModel):
    recipe: StandardRecipe
    matching: MatchingResult
    adaptation: CVAdaptation


class MyTutorialOrchestrationRequest(ContractModel):
    tutorial_id: str | None = Field(default=None, min_length=1)
    recipe: StandardRecipe | None = None
    recipe_id: str | None = Field(default=None, min_length=1)
    beauty_kit: BeautyKit | None = None
    beauty_kit_id: str | None = Field(default=None, min_length=1)
    face_profile: dict[str, Any]
    face_profile_id: str = Field(min_length=1)
    target_effect: Literal["cat_eye"] = "cat_eye"
    capabilities: list[ProductCapability] | None = None

    @field_validator("face_profile")
    @classmethod
    def validate_profile(cls, value: dict[str, Any]) -> dict[str, Any]:
        return validate_cv_face_profile(value)

    @model_validator(mode="after")
    def require_input_or_reference(self) -> "MyTutorialOrchestrationRequest":
        if (self.recipe is None) == (self.recipe_id is None):
            raise ValueError("provide exactly one of recipe or recipe_id")
        if (self.beauty_kit is None) == (self.beauty_kit_id is None):
            raise ValueError("provide exactly one of beauty_kit or beauty_kit_id")
        return self
