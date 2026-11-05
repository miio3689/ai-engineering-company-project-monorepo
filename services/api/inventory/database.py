"""Optional SQLModel database connection for inventory operations."""

import logging
import os
from collections.abc import Iterator

from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from . import models  # noqa: F401

logger = logging.getLogger(__name__)
_engine = None


def get_engine():
    """Create the shared engine on first use without connecting at import time."""
    global _engine

    database_url = os.environ.get("DATABASE_URL")
    if not database_url or not database_url.strip():
        raise HTTPException(
            status_code=503,
            detail="Servicio de inventario no disponible.",
        )

    if _engine is None:
        _engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=0,
        )
    return _engine


def get_db() -> Iterator[Session]:
    """Yield one SQLModel session per request and close it afterward."""
    with Session(get_engine()) as session:
        yield session


def init_inventory_db() -> None:
    """Create registered inventory tables when a database URL is configured."""
    database_url = os.environ.get("DATABASE_URL")
    if not database_url or not database_url.strip():
        return

    try:
        SQLModel.metadata.create_all(get_engine())
    except Exception as exc:
        logger.error(
            "Inventory database initialization failed (type: %s).",
            type(exc).__name__,
        )