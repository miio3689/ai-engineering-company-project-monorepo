"""SQLModel tables for inventory ingredients and stock movements."""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint
from sqlmodel import Field, SQLModel


class Ingredient(SQLModel, table=True):
    __tablename__ = "ingredient"
    __table_args__ = (
        CheckConstraint(
            "unit IN ('kg', 'litro', 'unidad')",
            name="ck_ingredient_unit",
        ),
        CheckConstraint(
            "category IN ('meat', 'produce', 'sauce', 'beverage', 'packaging', 'cleaning')",
            name="ck_ingredient_category",
        ),
        CheckConstraint("country IN ('CO', 'US')", name="ck_ingredient_country"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str
    sku: str = Field(index=True, unique=True)
    unit: str
    category: str
    country: str


class IngredientEntry(SQLModel, table=True):
    __tablename__ = "ingredient_entry"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_ingredient_entry_quantity"),
        CheckConstraint(
            "location_id BETWEEN 1 AND 14",
            name="ck_ingredient_entry_location",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredient.id", index=True)
    quantity: float
    supplier_name: str
    location_id: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user_uuid: str


class IngredientExit(SQLModel, table=True):
    __tablename__ = "ingredient_exit"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_ingredient_exit_quantity"),
        CheckConstraint(
            "reason IN ('consumption', 'waste')",
            name="ck_ingredient_exit_reason",
        ),
        CheckConstraint(
            "location_id BETWEEN 1 AND 14",
            name="ck_ingredient_exit_location",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    ingredient_id: int = Field(foreign_key="ingredient.id", index=True)
    quantity: float
    reason: str
    location_id: int
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    user_uuid: str