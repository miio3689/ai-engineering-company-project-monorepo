"""Database access for the data pipelines (it does not depend on services/).

The connection string comes from the DATABASE_URL environment variable
(services/api/.env is loaded for local runs) or, when the variable is missing,
from the Prefect Secret block "supabase-database-url".
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
SECRET_BLOCK_NAME = "supabase-database-url"

_engine: Engine | None = None


def _database_url() -> str:
    load_dotenv(REPOSITORY_ROOT / "services" / "api" / ".env")
    url = (os.environ.get("DATABASE_URL") or "").strip()
    if url:
        return url
    try:
        from prefect.blocks.system import Secret

        return Secret.load(SECRET_BLOCK_NAME).get().strip()
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL no está configurada y no existe el bloque Secret "
            f"'{SECRET_BLOCK_NAME}'."
        ) from exc


def get_engine() -> Engine:
    """Create the shared engine on first use."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            _database_url(), pool_pre_ping=True, pool_size=2, max_overflow=0
        )
    return _engine
