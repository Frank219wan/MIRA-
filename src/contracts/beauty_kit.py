"""Beauty Kit and structured product-capability contracts."""

from typing import Literal

from pydantic import Field

from .common import ContractModel


class ProductCapability(ContractModel):
    schema_version: str = "1.0"
    capability_id: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    supported_areas: list[str] = Field(min_length=1)
    supported_goals: list[str] = Field(min_length=1)
    color_families: list[str] = Field(default_factory=list)
    finishes: list[str] = Field(default_factory=list)
    depths: list[str] = Field(default_factory=list)
    pigmentations: list[str] = Field(default_factory=list)
    textures: list[str] = Field(default_factory=list)
    functions: list[str] = Field(default_factory=list)
    verification_status: Literal["verified", "unverified"] = "unverified"


class BeautyKitProduct(ContractModel):
    product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    capability_ids: list[str] = Field(min_length=1)


class BeautyKit(ContractModel):
    schema_version: str = "1.0"
    kit_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    products: list[BeautyKitProduct] = Field(default_factory=list)
