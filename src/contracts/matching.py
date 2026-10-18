"""Explainable product matching result contract."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import Field

from .common import ContractModel


class MatchingItem(ContractModel):
    step_index: int = Field(ge=1)
    status: Literal["matched", "unmatched", "substitution_candidate"]
    product_id: Optional[str] = None
    capability_id: Optional[str] = None
    note: Optional[str] = None
    score: float | None = Field(default=None, ge=0.0, le=100.0)
    verification_status: Literal["verified", "insufficient_data"] = "insufficient_data"
    reason: str = ""
    difference: str = ""
    impact: str = ""
    missing_capabilities: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    required_capabilities: dict[str, object] = Field(default_factory=dict)
    capability_checks: list[dict[str, object]] = Field(default_factory=list)


class MatchingResult(ContractModel):
    schema_version: str = "1.0"
    matching_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    beauty_kit_id: str = Field(min_length=1)
    items: list[MatchingItem] = Field(default_factory=list)
