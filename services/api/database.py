"""TinyDB storage for the supplier directory, separate from incident analysis."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from tinydb import TinyDB
from tinydb.table import Table

DATABASE_PATH = Path(__file__).resolve().with_name("suppliers.json")
INCIDENTS_DATABASE_PATH = Path(__file__).resolve().with_name("incidents.json")


@contextmanager
def get_suppliers_table() -> Iterator[Table]:
    """Open the suppliers table and close its JSON storage after use."""
    with TinyDB(DATABASE_PATH) as database:
        yield database.table("suppliers")


@contextmanager
def get_incidents_tables() -> Iterator[tuple[Table, Table]]:
    """Open incident records and their separate CSV-seed idempotency keys."""
    with TinyDB(INCIDENTS_DATABASE_PATH) as database:
        yield (
            database.table("incidents"),
            database.table("incident_seed_keys"),
        )
