"""Pydantic request and response schemas for inventory endpoints."""

from datetime import datetime
from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator

IngredientUnit: TypeAlias = Literal["kg", "litro", "unidad"]
IngredientCategory: TypeAlias = Literal[
    "meat", "produce", "sauce", "beverage", "packaging", "cleaning"
]
IngredientCountry: TypeAlias = Literal["CO", "US"]
ExitReason: TypeAlias = Literal["consumption", "waste"]


class IngredientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    sku: str = Field(min_length=1)
    unit: IngredientUnit
    category: IngredientCategory
    country: IngredientCountry

    @field_validator("name", "sku")
    @classmethod
    def require_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Este campo no puede estar vacío.")
        return value


class LocationStockRead(BaseModel):
    location_id: int
    quantity: float


class IngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    name: str
    sku: str
    unit: IngredientUnit
    category: IngredientCategory
    country: IngredientCountry
    current_stock: float
    stock_by_location: list[LocationStockRead] = Field(default_factory=list)


class EntryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: int = Field(gt=0)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    supplier_name: str = Field(min_length=1)
    unit_cost: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    location_id: int = Field(ge=1, le=14)

    @field_validator("supplier_name")
    @classmethod
    def require_nonblank_supplier(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El proveedor no puede estar vacío.")
        return value


class ExitCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredient_id: int = Field(gt=0)
    quantity: float = Field(gt=0, allow_inf_nan=False)
    reason: ExitReason
    location_id: int = Field(ge=1, le=14)


class InventoryMovementRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    ingredient_id: int
    name: str
    sku: str
    quantity: float
    location_id: int
    created_at: datetime
    user_uuid: str


class PriceVarianceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline_unit_cost: float
    variance_pct: float
    threshold_pct: float


class InboundOrderRead(InventoryMovementRead):
    type: Literal["inbound"]
    supplier_name: str
    unit_cost: float | None = None
    price_variance: PriceVarianceRead | None = None


class OutboundOrderRead(InventoryMovementRead):
    type: Literal["outbound"]
    reason: ExitReason


InventoryOrderRead: TypeAlias = Annotated[
    InboundOrderRead | OutboundOrderRead,
    Field(discriminator="type"),
]


class StockEditAttempt(BaseModel):
    """Body of a direct stock edit attempt. The API always rejects it."""

    model_config = ConfigDict(extra="forbid")

    location_id: int = Field(ge=1, le=14)
    quantity: float = Field(ge=0, allow_inf_nan=False)


class StockEditRejection(BaseModel):
    """Error body returned when a direct stock edit is rejected."""

    detail: str