"""Supplier directory endpoints backed by the shared TinyDB storage."""

from datetime import datetime, timezone
from threading import Lock

from fastapi import APIRouter, HTTPException, Response, status

from ..database import get_suppliers_table
from ..models import (
    Supplier,
    SupplierRateUpdate,
    SupplierResponse,
    SupplierStatusUpdate,
)

router = APIRouter(prefix="/suppliers", tags=["suppliers"])
_database_lock = Lock()


@router.post("", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED)
def create_supplier(supplier: Supplier) -> SupplierResponse:
    record = supplier.model_dump(mode="json")
    record["updated_at"] = datetime.now(timezone.utc).isoformat()
    with _database_lock, get_suppliers_table() as table:
        supplier_id = table.insert(record)
    return SupplierResponse(id=supplier_id, **record)


@router.get("", response_model=list[SupplierResponse])
def list_suppliers(
    country: str | None = None, category: str | None = None
) -> list[SupplierResponse]:
    with _database_lock, get_suppliers_table() as table:
        records = table.all()
    return [
        SupplierResponse(id=record.doc_id, **record)
        for record in records
        if (country is None or record["country"] == country)
        and (category is None or category in record["categories"])
    ]


@router.get("/{id}", response_model=SupplierResponse)
def get_supplier(id: int) -> SupplierResponse:
    with _database_lock, get_suppliers_table() as table:
        record = table.get(doc_id=id)
    if record is None:
        raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
    return SupplierResponse(id=record.doc_id, **record)


@router.patch("/{id}/rate", response_model=SupplierResponse)
def update_supplier_rate(id: int, update: SupplierRateUpdate) -> SupplierResponse:
    with _database_lock, get_suppliers_table() as table:
        record = table.get(doc_id=id)
        if record is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
        changes = {
            "rate_per_unit": update.rate_per_unit,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        table.update(changes, doc_ids=[id])
    return SupplierResponse(id=record.doc_id, **(dict(record) | changes))


@router.patch("/{id}/status", response_model=SupplierResponse)
def update_supplier_status(id: int, update: SupplierStatusUpdate) -> SupplierResponse:
    with _database_lock, get_suppliers_table() as table:
        record = table.get(doc_id=id)
        if record is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
        changes = update.model_dump(mode="json")
        table.update(changes, doc_ids=[id])
    return SupplierResponse(id=record.doc_id, **(dict(record) | changes))


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(id: int) -> Response:
    """Correct erroneous records; normal procurement operations suspend suppliers."""
    with _database_lock, get_suppliers_table() as table:
        if table.get(doc_id=id) is None:
            raise HTTPException(status_code=404, detail="Proveedor no encontrado.")
        table.remove(doc_ids=[id])
    return Response(status_code=status.HTTP_204_NO_CONTENT)
