"""Request envelopes used only by the Week 1 HTTP boundary."""

from __future__ import annotations

from pydantic import Field, model_validator

from src.contracts.beauty_kit import BeautyKit
from src.contracts.common import ContractModel
from src.contracts.cv_adaptation import CVAdaptation
from src.contracts.makeup import StandardRecipe
from src.contracts.matching import MatchingResult


class MatchingRequest(ContractModel):
    recipe: StandardRecipe | None = None
    recipe_id: str | None = Field(default=None, min_length=1)
    beauty_kit: BeautyKit

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
