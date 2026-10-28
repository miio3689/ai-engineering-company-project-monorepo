"""Supplier directory models from the Milestone 09 Brasaland briefing."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SupplierStatus(str, Enum):
    active = "active"
    suspended = "suspended"


class Supplier(BaseModel):
    """Create/update payload; client-supplied IDs and timestamps are rejected."""

    model_config = ConfigDict(extra="forbid")

    name: str
    country: Literal["Colombia", "USA"]
    categories: list[
        Literal[
            "carne",
            "verduras_y_hortalizas",
            "salsas_y_condimentos",
            "bebidas",
            "packaging",
            "productos_limpieza",
            "lacteos",
            "carbon_y_combustible",
        ]
    ] = Field(min_length=1)
    rate_per_unit: float = Field(gt=0, allow_inf_nan=False)
    currency: Literal["COP", "USD"]
    status: SupplierStatus
    contact_email: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def validate_country_currency(self) -> Supplier:
        expected_currency = "COP" if self.country == "Colombia" else "USD"
        if self.currency != expected_currency:
            raise ValueError(
                f"currency must be {expected_currency} when country is {self.country}"
            )
        return self


class SupplierResponse(Supplier):
    """Persisted supplier with a TinyDB document ID and server-side timestamp."""

    id: int
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
