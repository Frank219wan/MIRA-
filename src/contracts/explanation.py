"""Typed LLM explanation handoff envelope; no provider call is included."""

from pydantic import Field

from .common import ContractModel


class LLMExplanation(ContractModel):
    schema_version: str = "1.0"
    recipe_id: str = Field(min_length=1)
    matching_id: str | None = None
    adaptation_id: str | None = None
    explanation: str = Field(min_length=1)
