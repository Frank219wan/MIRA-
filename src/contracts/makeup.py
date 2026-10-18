"""Reusable makeup recipe contracts."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator, model_validator

from .common import ContractModel


class ProductCapabilityRequirement(ContractModel):
    """Structured requirement used by matching; omitted when tutorial evidence is insufficient."""

    product_category: str = Field(min_length=1)
    color_families: list[str] = Field(min_length=1)
    finishes: list[str] = Field(min_length=1)
    depths: list[str] = Field(min_length=1)
    pigmentations: list[str] = Field(min_length=1)
    textures: list[str] = Field(min_length=1)
    functions: list[str] = Field(min_length=1)


class MakeupActionUnit(ContractModel):
    """One observable makeup action extracted from a tutorial."""

    step_index: int = Field(ge=1)
    area: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    product_requirement: str = Field(min_length=1)
    tool: str = Field(min_length=1)
    motion: str = Field(min_length=1)
    intensity: str = Field(min_length=1)
    target_result: str = Field(min_length=1)
    product_capability_requirement: ProductCapabilityRequirement | None = None
    time_range_seconds: tuple[float, float] | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)

    @field_validator(
        "area", "goal", "product_requirement", "tool", "motion",
        "intensity", "target_result", mode="before",
    )
    @classmethod
    def reject_blank_text(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "MakeupActionUnit":
        if self.time_range_seconds is not None:
            start, end = self.time_range_seconds
            if start < 0 or end < start:
                raise ValueError("time_range_seconds must be non-negative and ordered")
        return self


class StandardRecipe(ContractModel):
    """Canonical ordered recipe, reusable beyond the Week 1 demo."""

    schema_version: Literal["1.0"] = "1.0"
    recipe_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    source_media_path: str = Field(min_length=1)
    action_units: list[MakeupActionUnit] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_ordered_steps(self) -> "StandardRecipe":
        expected = list(range(1, len(self.action_units) + 1))
        actual = [unit.step_index for unit in self.action_units]
        if actual != expected:
            raise ValueError("action_units must be ordered with consecutive step_index values starting at 1")
        return self
