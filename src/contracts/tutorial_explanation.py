"""Deterministic facts and provider-neutral tutorial wording contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .common import ContractModel


class ParameterChange(ContractModel):
    parameter: str = Field(min_length=1)
    reference_value: float
    personalized_value: float
    delta: float
    direction: Literal["increased", "decreased", "unchanged"]
    rule_ids: list[str]
    feature_path: str | None = None
    feature_value: float | None = None
    operation: Literal["add", "multiply"] | None = None
    adjustment_value: float | None = None


class ReasonEvidence(ContractModel):
    parameter: str = Field(min_length=1)
    feature_path: str = Field(min_length=1)
    feature_value: float
    rule_ids: list[str]


class ExplanationFacts(ContractModel):
    facts_version: Literal["1.0"] = "1.0"
    action_id: str = Field(pattern=r"^A\d{2}$")
    changes: list[ParameterChange]
    applied_rules: list[str]
    reasons: list[ReasonEvidence]


class GeneratedTutorialText(ContractModel):
    """The only fields an explanation provider is allowed to produce."""

    where: str = Field(min_length=1)
    how: str = Field(min_length=1)
    why: str = Field(min_length=1)
    stop_when: str = Field(min_length=1)
