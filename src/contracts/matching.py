"""Structural matching result contract; no matching algorithm is included."""

from typing import Literal

from pydantic import Field

from .common import ContractModel


class MatchingItem(ContractModel):
    step_index: int = Field(ge=1)
    status: Literal["matched", "unmatched", "substitution_candidate"]
    product_id: str | None = None
    capability_id: str | None = None
    note: str | None = None


class MatchingResult(ContractModel):
    schema_version: str = "1.0"
    matching_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    beauty_kit_id: str = Field(min_length=1)
    items: list[MatchingItem] = Field(default_factory=list)
