"""TinyDB storage for the supplier directory, separate from incident analysis."""

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from tinydb import TinyDB
from tinydb.table import Table

DATABASE_PATH = Path(__file__).resolve().with_name("suppliers.json")


@contextmanager
def get_suppliers_table() -> Iterator[Table]:
    """Open the suppliers table and close its JSON storage after use."""
    with TinyDB(DATABASE_PATH) as database:
        yield database.table("suppliers")
