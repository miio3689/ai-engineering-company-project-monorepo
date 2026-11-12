"""Authenticated inventory endpoints backed by SQLModel."""

from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session, select

from ..auth_security import get_current_user
from ..inventory.database import get_db
from ..inventory.models import Ingredient, IngredientEntry, IngredientExit
from ..inventory.schemas import (
    EntryCreate,
    ExitCreate,
    InboundOrderRead,
    IngredientCreate,
    IngredientRead,
    InventoryOrderRead,
    LocationStockRead,
    OutboundOrderRead,
)
from ..models import UserResponse

router = APIRouter(prefix="/inventory", tags=["inventory"])
logger = logging.getLogger(__name__)


def _database_error(session: Session, exc: SQLAlchemyError) -> HTTPException:
    session.rollback()
    logger.error("Inventory database error (type: %s).", type(exc).__name__)
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflicto de datos de inventario.",
        )
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Servicio de inventario no disponible.",
    )


def _product_stock_statement(ingredient_id: int | None = None):
    entry_totals = (
        select(
            IngredientEntry.ingredient_id.label("ingredient_id"),
            func.sum(IngredientEntry.quantity).label("total"),
        )
        .group_by(IngredientEntry.ingredient_id)
        .subquery()
    )
    exit_totals = (
        select(
            IngredientExit.ingredient_id.label("ingredient_id"),
            func.sum(IngredientExit.quantity).label("total"),
        )
        .group_by(IngredientExit.ingredient_id)
        .subquery()
    )
    stock = (
        func.coalesce(entry_totals.c.total, 0)
        - func.coalesce(exit_totals.c.total, 0)
    ).label("current_stock")
    statement = (
        select(Ingredient, stock)
        .outerjoin(
            entry_totals,
            entry_totals.c.ingredient_id == Ingredient.id,
        )
        .outerjoin(
            exit_totals,
            exit_totals.c.ingredient_id == Ingredient.id,
        )
    )
    if ingredient_id is not None:
        statement = statement.where(Ingredient.id == ingredient_id)
    return statement


def _stock_by_location(
    session: Session,
    ingredient_ids: list[int],
) -> dict[int, list[LocationStockRead]]:
    if not ingredient_ids:
        return {}

    stock: dict[int, dict[int, float]] = {}
    entry_totals = session.exec(
        select(
            IngredientEntry.ingredient_id,
            IngredientEntry.location_id,
            func.sum(IngredientEntry.quantity),
        )
        .where(IngredientEntry.ingredient_id.in_(ingredient_ids))
        .group_by(IngredientEntry.ingredient_id, IngredientEntry.location_id)
    ).all()
    for ingredient_id, location_id, quantity in entry_totals:
        stock.setdefault(ingredient_id, {})[location_id] = float(quantity)

    exit_totals = session.exec(
        select(
            IngredientExit.ingredient_id,
            IngredientExit.location_id,
            func.sum(IngredientExit.quantity),
        )
        .where(IngredientExit.ingredient_id.in_(ingredient_ids))
        .group_by(IngredientExit.ingredient_id, IngredientExit.location_id)
    ).all()
    for ingredient_id, location_id, quantity in exit_totals:
        location_stock = stock.setdefault(ingredient_id, {})
        location_stock[location_id] = location_stock.get(location_id, 0.0) - float(
            quantity
        )

    return {
        ingredient_id: [
            LocationStockRead(
                location_id=location_id,
                quantity=round(quantity, 3),
            )
            for location_id, quantity in sorted(location_totals.items())
        ]
        for ingredient_id, location_totals in stock.items()
    }


def _ingredient_response(
    ingredient: Ingredient,
    current_stock: float,
    stock_by_location: list[LocationStockRead] | None = None,
) -> IngredientRead:
    return IngredientRead(
        **ingredient.model_dump(),
        current_stock=round(float(current_stock), 3),
        stock_by_location=stock_by_location or [],
    )


def _require_ingredient(session: Session, ingredient_id: int) -> Ingredient:
    ingredient = session.get(Ingredient, ingredient_id)
    if ingredient is None:
        session.rollback()
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado.")
    return ingredient


def _sort_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@router.get("/products", response_model=list[IngredientRead])
def list_products(
    session: Session = Depends(get_db),
    _current_user: UserResponse = Depends(get_current_user),
) -> list[IngredientRead]:
    try:
        rows = session.exec(_product_stock_statement()).all()
        stock_by_ingredient = _stock_by_location(
            session,
            [ingredient.id for ingredient, _ in rows if ingredient.id is not None],
        )
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    return [
        _ingredient_response(
            ingredient,
            stock,
            stock_by_ingredient.get(ingredient.id, []),
        )
        for ingredient, stock in rows
    ]


@router.post(
    "/products",
    response_model=IngredientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_product(
    product: IngredientCreate,
    session: Session = Depends(get_db),
    _current_user: UserResponse = Depends(get_current_user),
) -> IngredientRead:
    ingredient = Ingredient(**product.model_dump())
    session.add(ingredient)
    try:
        session.commit()
        session.refresh(ingredient)
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    return _ingredient_response(ingredient, 0.0)


@router.get("/products/{ingredient_id}", response_model=IngredientRead)
def get_product(
    ingredient_id: int,
    session: Session = Depends(get_db),
    _current_user: UserResponse = Depends(get_current_user),
) -> IngredientRead:
    try:
        row = session.exec(
            _product_stock_statement(ingredient_id=ingredient_id)
        ).first()
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Ingrediente no encontrado.")
    ingredient, current_stock = row
    try:
        stock_by_location = _stock_by_location(session, [ingredient_id]).get(
            ingredient_id,
            [],
        )
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    return _ingredient_response(ingredient, current_stock, stock_by_location)


@router.post(
    "/orders/inbound",
    response_model=InboundOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_inbound_order(
    order: EntryCreate,
    session: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
) -> InboundOrderRead:
    try:
        ingredient = _require_ingredient(session, order.ingredient_id)
        entry = IngredientEntry(
            **order.model_dump(),
            user_uuid=str(current_user.id),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    return InboundOrderRead(
        id=entry.id,
        type="inbound",
        ingredient_id=entry.ingredient_id,
        name=ingredient.name,
        sku=ingredient.sku,
        quantity=entry.quantity,
        location_id=entry.location_id,
        created_at=entry.created_at,
        user_uuid=entry.user_uuid,
        supplier_name=entry.supplier_name,
    )


@router.post(
    "/orders/outbound",
    response_model=OutboundOrderRead,
    status_code=status.HTTP_201_CREATED,
)
def create_outbound_order(
    order: ExitCreate,
    session: Session = Depends(get_db),
    current_user: UserResponse = Depends(get_current_user),
) -> OutboundOrderRead:
    try:
        ingredient = session.exec(
            select(Ingredient)
            .where(Ingredient.id == order.ingredient_id)
            .with_for_update()
        ).first()
        if ingredient is None:
            session.rollback()
            raise HTTPException(
                status_code=404,
                detail="Ingrediente no encontrado.",
            )

        inbound = session.exec(
            select(func.coalesce(func.sum(IngredientEntry.quantity), 0)).where(
                IngredientEntry.ingredient_id == ingredient.id,
                IngredientEntry.location_id == order.location_id,
            )
        ).one()
        outbound = session.exec(
            select(func.coalesce(func.sum(IngredientExit.quantity), 0)).where(
                IngredientExit.ingredient_id == ingredient.id,
                IngredientExit.location_id == order.location_id,
            )
        ).one()
        raw_available = float(inbound) - float(outbound)
        available = round(raw_available, 3)
        requested = round(order.quantity, 3)
        if requested > available or order.quantity > raw_available:
            session.rollback()
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Insufficient stock for ingredient '{ingredient.name}' "
                    f"at location {order.location_id}. "
                    f"Available: {available:.3f}, requested: {requested:.3f}."
                ),
            )

        exit_record = IngredientExit(
            **order.model_dump(),
            user_uuid=str(current_user.id),
        )
        session.add(exit_record)
        session.commit()
        session.refresh(exit_record)
    except HTTPException:
        raise
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc
    return OutboundOrderRead(
        id=exit_record.id,
        type="outbound",
        ingredient_id=exit_record.ingredient_id,
        name=ingredient.name,
        sku=ingredient.sku,
        quantity=exit_record.quantity,
        location_id=exit_record.location_id,
        created_at=exit_record.created_at,
        user_uuid=exit_record.user_uuid,
        reason=exit_record.reason,
    )


@router.get("/orders", response_model=list[InventoryOrderRead])
def list_orders(
    session: Session = Depends(get_db),
    _current_user: UserResponse = Depends(get_current_user),
) -> list[InventoryOrderRead]:
    try:
        entries = session.exec(
            select(IngredientEntry, Ingredient.name, Ingredient.sku).join(
                Ingredient,
                Ingredient.id == IngredientEntry.ingredient_id,
            )
        ).all()
        exits = session.exec(
            select(IngredientExit, Ingredient.name, Ingredient.sku).join(
                Ingredient,
                Ingredient.id == IngredientExit.ingredient_id,
            )
        ).all()
    except SQLAlchemyError as exc:
        raise _database_error(session, exc) from exc

    orders: list[InventoryOrderRead] = [
        InboundOrderRead(
            id=entry.id,
            type="inbound",
            ingredient_id=entry.ingredient_id,
            name=name,
            sku=sku,
            quantity=entry.quantity,
            location_id=entry.location_id,
            created_at=entry.created_at,
            user_uuid=entry.user_uuid,
            supplier_name=entry.supplier_name,
        )
        for entry, name, sku in entries
    ]
    orders.extend(
        OutboundOrderRead(
            id=exit_record.id,
            type="outbound",
            ingredient_id=exit_record.ingredient_id,
            name=name,
            sku=sku,
            quantity=exit_record.quantity,
            location_id=exit_record.location_id,
            created_at=exit_record.created_at,
            user_uuid=exit_record.user_uuid,
            reason=exit_record.reason,
        )
        for exit_record, name, sku in exits
    )
    return sorted(orders, key=lambda order: _sort_timestamp(order.created_at), reverse=True)