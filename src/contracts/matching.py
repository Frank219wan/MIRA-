"""Deterministic Product Matching v1 contracts."""

from typing import Literal

from pydantic import Field

from .beauty_kit import BeautyKitProduct
from .common import ContractModel


class HardConstraintEvidence(ContractModel):
    constraint: str = Field(min_length=1)
    expected: list[str] = Field(default_factory=list)
    actual: list[str] = Field(default_factory=list)
    passed: bool


class ScoreComponent(ContractModel):
    component: str = Field(min_length=1)
    points_awarded: float = Field(ge=0)
    points_possible: float = Field(gt=0)
    evidence: str = Field(min_length=1)


class SubstitutionCandidate(ContractModel):
    product_id: str = Field(min_length=1)
    match_score: float = Field(ge=0, le=100)
    hard_constraint_failures: list[str] = Field(default_factory=list)
    difference: str = Field(min_length=1)


class MatchingProvenance(ContractModel):
    matcher_version: str = Field(min_length=1)
    rules_version: str = Field(min_length=1)
    source_step_index: int = Field(ge=1)
    product_requirement: str = Field(min_length=1)
    evaluated_product_ids: list[str] = Field(default_factory=list)
    pre_cap_score: float = Field(default=0, ge=0, le=100)
    hard_constraint_score_cap: float = Field(default=0, ge=0, le=100)
    hard_constraints: list[HardConstraintEvidence] = Field(default_factory=list)
    score_components: list[ScoreComponent] = Field(default_factory=list)


class MatchingItem(ContractModel):
    step_index: int = Field(ge=1)
    status: Literal["matched", "unmatched", "substitution_candidate"]
    product_id: str | None = None
    capability_id: str | None = None
    note: str | None = None
    decision: Literal[
        "strong_match", "low_match", "missing_capability", "functional_conflict"
    ] | None = None
    best_match: BeautyKitProduct | None = None
    match_score: float = Field(default=0, ge=0, le=100)
    reason: str | None = None
    difference: str | None = None
    impact: str | None = None
    satisfied_capabilities: list[str] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)
    functional_conflict: str | None = None
    substitution_candidates: list[SubstitutionCandidate] = Field(default_factory=list)
    provenance: MatchingProvenance | None = None


class MatchingResult(ContractModel):
    schema_version: str = "1.0"
    matching_id: str = Field(min_length=1)
    recipe_id: str = Field(min_length=1)
    beauty_kit_id: str = Field(min_length=1)
    items: list[MatchingItem] = Field(default_factory=list)
