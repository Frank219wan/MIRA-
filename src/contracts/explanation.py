"""Typed LLM explanation handoff envelope; no provider call is included."""

from __future__ import annotations

from typing import Optional

from pydantic import Field

from .common import ContractModel


class LLMExplanation(ContractModel):
    schema_version: str = "1.0"
    recipe_id: str = Field(min_length=1)
    matching_id: Optional[str] = None
    adaptation_id: Optional[str] = None
    explanation: str = Field(min_length=1)
