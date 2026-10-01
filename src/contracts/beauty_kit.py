"""Personal Beauty Kit and product-capability contracts."""

from pydantic import Field, model_validator

from .common import ContractModel


class ProductCapability(ContractModel):
    schema_version: str = "1.0"
    capability_id: str = Field(min_length=1)
    product_category: str = Field(min_length=1)
    supported_areas: list[str] = Field(min_length=1)
    supported_goals: list[str] = Field(min_length=1)
    supported_product_requirements: list[str] = Field(default_factory=list)
    compatible_finishes: list[str] = Field(default_factory=list)


class BeautyKitProduct(ContractModel):
    product_id: str = Field(min_length=1)
    # ``name`` is retained for Week 1 clients; product_name is the explicit v1 field.
    name: str = Field(min_length=1)
    product_name: str | None = Field(default=None, min_length=1)
    brand: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    shade_name: str | None = Field(default=None, min_length=1)
    color_attributes: dict[str, str] = Field(default_factory=dict)
    finish: str | None = Field(default=None, min_length=1)
    depth: str | None = Field(default=None, min_length=1)
    reflectivity: str | None = Field(default=None, min_length=1)
    capability_ids: list[str] = Field(default_factory=list)


class BeautyKit(ContractModel):
    schema_version: str = "1.0"
    kit_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    products: list[BeautyKitProduct] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_unique_products(self) -> "BeautyKit":
        product_ids = [product.product_id for product in self.products]
        if len(product_ids) != len(set(product_ids)):
            raise ValueError("Beauty Kit product_id values must be unique")
        return self
