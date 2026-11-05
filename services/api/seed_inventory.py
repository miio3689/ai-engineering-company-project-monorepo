"""Idempotent all-or-nothing seed for Brasaland inventory data."""

from collections.abc import Callable
from dataclasses import dataclass
import os
from pathlib import Path
import sys

from dotenv import load_dotenv
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from . import services_auth
from .inventory.database import get_engine
from .inventory.models import Ingredient, IngredientEntry, IngredientExit

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]

INGREDIENTS_SEED = (
    {
        "name": "Falda de ternera",
        "sku": "BRS-BEEF-001",
        "unit": "kg",
        "category": "meat",
        "country": "CO",
    },
    {
        "name": "Costilla de cerdo",
        "sku": "BRS-PORK-001",
        "unit": "kg",
        "category": "meat",
        "country": "US",
    },
    {
        "name": "Chimichurri",
        "sku": "BRS-SAUCE-001",
        "unit": "litro",
        "category": "sauce",
        "country": "CO",
    },
    {
        "name": "Salsa BBQ de la casa",
        "sku": "BRS-SAUCE-002",
        "unit": "litro",
        "category": "sauce",
        "country": "US",
    },
    {
        "name": "Yuca",
        "sku": "BRS-PROD-001",
        "unit": "kg",
        "category": "produce",
        "country": "CO",
    },
    {
        "name": "Caja para llevar (M)",
        "sku": "BRS-PKG-001",
        "unit": "unidad",
        "category": "packaging",
        "country": "CO",
    },
)

ENTRIES_SEED = (
    ("BRS-BEEF-001", 50, "Carnes del Valle S.A.", 1),
    ("BRS-BEEF-001", 30, "Carnes del Valle S.A.", 1),
    ("BRS-PORK-001", 40, "MiamiMeat Co.", 2),
    ("BRS-SAUCE-001", 20, "Salsas Artesanales Ltda.", 3),
    ("BRS-SAUCE-002", 15, "Salsas Artesanales Ltda.", 2),
    ("BRS-PROD-001", 60, "Carnes del Valle S.A.", 1),
    ("BRS-PKG-001", 200, "Salsas Artesanales Ltda.", 3),
)

EXITS_SEED = (
    ("BRS-BEEF-001", 12.5, "consumption", 1),
    ("BRS-PORK-001", 5, "waste", 2),
    ("BRS-SAUCE-001", 4, "consumption", 3),
)


class SeedInventoryError(RuntimeError):
    """Expected seed failures with safe, user-facing messages."""


@dataclass(frozen=True)
class SeedResult:
    already_seeded: bool
    ingredients_inserted: int = 0
    entries_inserted: int = 0
    exits_inserted: int = 0
    stock_by_sku: dict[str, float] | None = None


def _active_user_uuid() -> str:
    active_users = [user for user in services_auth.listar_usuarios() if user.is_active]
    if not active_users:
        raise SeedInventoryError(
            "No hay usuarios activos en TinyDB; no se insertó ningún dato."
        )
    return str(active_users[0].id)


def _seed_stock_by_sku() -> dict[str, float]:
    stock = {ingredient["sku"]: 0.0 for ingredient in INGREDIENTS_SEED}
    for sku, quantity, _, _ in ENTRIES_SEED:
        stock[sku] += float(quantity)
    for sku, quantity, _, _ in EXITS_SEED:
        stock[sku] -= float(quantity)
    return stock


def seed_inventory(
    session_factory: Callable[[], Session] | None = None,
) -> SeedResult:
    """Insert all seed data in one transaction, or do nothing if already seeded."""
    user_uuid = _active_user_uuid()
    if session_factory is None:
        engine = get_engine()
        session_factory = lambda: Session(engine)

    seed_skus = [ingredient["sku"] for ingredient in INGREDIENTS_SEED]
    with session_factory() as session:
        with session.begin():
            existing_skus = session.exec(
                select(Ingredient.sku).where(Ingredient.sku.in_(seed_skus))
            ).all()
            if existing_skus:
                return SeedResult(already_seeded=True)

            ingredients = [Ingredient(**record) for record in INGREDIENTS_SEED]
            session.add_all(ingredients)
            session.flush()
            ingredient_ids = {
                ingredient.sku: ingredient.id for ingredient in ingredients
            }

            entries = [
                IngredientEntry(
                    ingredient_id=ingredient_ids[sku],
                    quantity=quantity,
                    supplier_name=supplier_name,
                    location_id=location_id,
                    user_uuid=user_uuid,
                )
                for sku, quantity, supplier_name, location_id in ENTRIES_SEED
            ]
            exits = [
                IngredientExit(
                    ingredient_id=ingredient_ids[sku],
                    quantity=quantity,
                    reason=reason,
                    location_id=location_id,
                    user_uuid=user_uuid,
                )
                for sku, quantity, reason, location_id in EXITS_SEED
            ]
            session.add_all(entries + exits)
            session.flush()

    return SeedResult(
        already_seeded=False,
        ingredients_inserted=len(INGREDIENTS_SEED),
        entries_inserted=len(ENTRIES_SEED),
        exits_inserted=len(EXITS_SEED),
        stock_by_sku=_seed_stock_by_sku(),
    )


def _print_result(result: SeedResult) -> None:
    if result.already_seeded:
        print("La semilla de inventario ya estaba sembrada; no se insertó nada.")
        return

    print(f"Ingredientes insertados: {result.ingredients_inserted}")
    print(f"Entradas insertadas: {result.entries_inserted}")
    print(f"Salidas insertadas: {result.exits_inserted}")
    print("Stock neto por SKU:")
    for sku, stock in (result.stock_by_sku or {}).items():
        print(f"- {sku}: {stock:g}")


def main(session_factory: Callable[[], Session] | None = None) -> None:
    """Load the service environment and run the inventory seed command."""
    load_dotenv(REPOSITORY_ROOT / "services" / "api" / ".env")
    if not os.environ.get("DATABASE_URL", "").strip():
        print(
            "Error: DATABASE_URL no está configurada; no se sembró el inventario.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        result = seed_inventory(session_factory)
    except SeedInventoryError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    except Exception as exc:
        if isinstance(exc, SQLAlchemyError):
            message = "Error: no se pudo acceder a la base de datos de inventario."
        else:
            message = "Error: no se pudo completar la semilla de inventario."
        print(message, file=sys.stderr)
        raise SystemExit(1) from exc

    _print_result(result)


if __name__ == "__main__":
    main()