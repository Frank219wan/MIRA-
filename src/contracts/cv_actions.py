"""Frozen boundaries around CV-owned standard and personalized actions."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import Field, field_validator

from .common import ContractModel


def _finite_parameters(value: dict[str, Any]) -> dict[str, Any]:
    for name, item in value.items():
        if isinstance(item, bool):
            continue
        if isinstance(item, (int, float)) and not math.isfinite(float(item)):
            raise ValueError(f"CV action parameter must be finite: {name}")
    return value


class CVStandardMakeupAction(ContractModel):
    """CV engine-owned input shape; the backend does not reinterpret it."""

    action_id: str = Field(pattern=r"^A\d{2}$")
    parameters: dict[str, Any]

    _validate_parameters = field_validator("parameters")(_finite_parameters)


class DecodedActionSelector(ContractModel):
    area: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    product_requirement: str = Field(min_length=1)


class DecodedActionMapping(ContractModel):
    mapping_id: str = Field(min_length=1)
    action_id: str = Field(pattern=r"^A\d{2}$")
    source: DecodedActionSelector
    parameters: dict[str, Any] | None = None
    required_product_inputs: list[str] = Field(default_factory=list)
    status: Literal["approved", "placeholder_requires_product_input"]

    @field_validator("parameters")
    @classmethod
    def validate_parameters(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return None if value is None else _finite_parameters(value)


class DecodedActionMappingConfig(ContractModel):
    mapping_version: Literal["1.0"] = "1.0"
    mappings: list[DecodedActionMapping]
    unresolved_inputs: list[str] = Field(default_factory=list)


class AdaptedCVAction(ContractModel):
    """Backend-owned link from a decoded step to an unchanged CV action."""

    mapping_version: Literal["1.0"] = "1.0"
    mapping_id: str = Field(min_length=1)
    source_step_index: int = Field(ge=1)
    standard_makeup_action: CVStandardMakeupAction


class CVAdjustment(ContractModel):
    rule_ids: list[str]
    feature_path: str
    feature_value: float
    parameter: str
    operation: Literal["add", "multiply"]
    adjustment_value: float
    original_value: float
    personalized_value: float


class CVPersonalizedAction(ContractModel):
    """Exact validated representation of Personalization Engine v0 output."""

    action_id: str = Field(pattern=r"^A\d{2}$")
    original_parameters: dict[str, Any]
    personalized_parameters: dict[str, Any]
    applied_rules: list[str]
    adjustments: list[CVAdjustment]


class PersonalizedActionWrapper(ContractModel):
    schema_version: Literal["0.2"] = "0.2"
    recipe_id: str = Field(min_length=1)
    step_index: int = Field(ge=1)
    face_profile_version: Literal["0.3"] = "0.3"
    personalized_action: CVPersonalizedAction
    provenance: AdaptedCVAction
