"""Week 1 Beauty Kit and product-capability contracts."""

from pydantic import Field

from .common import ContractModel


class ProductCapability(ContractModel):
    schema_version: str = "1.0"
    capability_id: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    supported_areas: list[str] = Field(min_length=1)
    supported_goals: list[str] = Field(min_length=1)


class BeautyKitProduct(ContractModel):
    product_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    capability_ids: list[str] = Field(min_length=1)


class BeautyKit(ContractModel):
    schema_version: str = "1.0"
    kit_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    products: list[BeautyKitProduct] = Field(default_factory=list)
