"""Authenticated CRUD and summary endpoints for operational incidents."""

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.exceptions import HTTPException as StarletteHTTPException

from ..auth_security import get_current_user
from ..database import get_incidents_tables
from ..models import Incident, IncidentCreate, IncidentStatusUpdate
from ..shared_paths import ensure_shared_python_path

ensure_shared_python_path()

from brasaland_shared.incidents import (  # noqa: E402
    BRANCHES,
    INCIDENT_CATEGORIES,
    INCIDENT_ORIGINS,
    INCIDENT_STATUSES,
    STATUS_TRANSITIONS,
    Branch,
    Category,
    IncidentOrigin,
    IncidentStatus,
)

logger = logging.getLogger(__name__)


class IncidentValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(message)


def _validation_response(errors: list[dict[str, str]]) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "Datos no válidos.", "errors": errors},
    )


def _field_message(field: str, error_type: str) -> str:
    if error_type == "missing":
        labels = {
            "title": "El título",
            "description": "La descripción",
            "category": "La categoría",
            "status": "El estado",
            "origin": "El origen",
            "branch": "La sede",
        }
        return f"{labels.get(field, 'Este campo')} es obligatorio."
    if error_type == "enum":
        return "Selecciona uno de los valores permitidos."
    if error_type in {"string_type", "string_too_short", "value_error"}:
        labels = {
            "title": "El título es obligatorio y no puede estar vacío.",
            "description": "La descripción es obligatoria y no puede estar vacía.",
        }
        return labels.get(field, "Revisa el valor de este campo.")
    if error_type == "extra_forbidden":
        return "Este campo no está permitido."
    if error_type == "int_parsing":
        return "El identificador debe ser un número entero."
    if error_type == "json_invalid":
        return "Envía un cuerpo JSON válido."
    return "Revisa el valor de este campo."


def _request_validation_errors(exc: RequestValidationError) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for error in exc.errors():
        location = error.get("loc", ())
        field = next(
            (
                str(part)
                for part in reversed(location)
                if part not in {"body", "query", "path"}
            ),
            "body",
        )
        result.append(
            {
                "field": field,
                "message": _field_message(field, str(error.get("type", ""))),
            }
        )
    return result or [{"field": "body", "message": "Revisa los datos enviados."}]


class IncidentRoute(APIRoute):
    def get_route_handler(self) -> Callable[..., Any]:
        original_handler = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original_handler(request)
            except RequestValidationError as exc:
                return _validation_response(_request_validation_errors(exc))
            except IncidentValidationError as exc:
                return _validation_response(
                    [{"field": exc.field, "message": exc.message}]
                )
            except StarletteHTTPException:
                raise
            except Exception as exc:
                logger.error(
                    "Unexpected error in an incident endpoint (type: %s).",
                    type(exc).__name__,
                )
                return JSONResponse(
                    status_code=500,
                    content={"detail": "Error interno del servicio."},
                )

        return handler


router = APIRouter(
    prefix="/api/incidents",
    tags=["incidents"],
    route_class=IncidentRoute,
    dependencies=[Depends(get_current_user)],
)
_database_lock = Lock()


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _record_response(document_id: int, record: dict[str, Any]) -> Incident:
    return Incident(id=document_id, **record)


@router.post("", response_model=Incident, status_code=201)
def create_incident(incident: IncidentCreate) -> Incident:
    now = _now_utc().isoformat()
    record = incident.model_dump(mode="json")
    record["created_at"] = now
    record["updated_at"] = now
    with _database_lock, get_incidents_tables() as (incidents, _):
        document_id = incidents.insert(record)
    return _record_response(document_id, record)


@router.get("", response_model=list[Incident])
def list_incidents(
    status: IncidentStatus | None = None,
    origin: IncidentOrigin | None = None,
    branch: Branch | None = None,
    category: Category | None = None,
) -> list[Incident]:
    filters = {
        key: value.value
        for key, value in {
            "status": status,
            "origin": origin,
            "branch": branch,
            "category": category,
        }.items()
        if value is not None
    }
    with _database_lock, get_incidents_tables() as (incidents, _):
        records = incidents.all()
    return [
        _record_response(record.doc_id, dict(record))
        for record in records
        if all(record.get(field) == value for field, value in filters.items())
    ]


@router.get("/summary")
def incidents_summary() -> dict[str, Any]:
    with _database_lock, get_incidents_tables() as (incidents, _):
        records = incidents.all()

    def count_by(field: str, values: tuple[str, ...]) -> dict[str, int]:
        return {
            value: sum(1 for record in records if record.get(field) == value)
            for value in values
        }

    return {
        "total": len(records),
        "by_status": count_by("status", INCIDENT_STATUSES),
        "by_category": count_by("category", INCIDENT_CATEGORIES),
        "by_origin": count_by("origin", INCIDENT_ORIGINS),
        "by_branch": count_by("branch", tuple(value for value, _ in BRANCHES)),
    }


@router.get("/{id}", response_model=Incident)
def get_incident(id: int) -> Incident:
    with _database_lock, get_incidents_tables() as (incidents, _):
        record = incidents.get(doc_id=id)
    if record is None:
        raise HTTPException(status_code=404, detail="No se encontró la incidencia.")
    return _record_response(record.doc_id, dict(record))


@router.patch("/{id}/status", response_model=Incident)
def update_incident_status(id: int, update: IncidentStatusUpdate) -> Incident:
    with _database_lock, get_incidents_tables() as (incidents, _):
        record = incidents.get(doc_id=id)
        if record is None:
            raise HTTPException(
                status_code=404,
                detail="No se encontró la incidencia.",
            )

        current_status = str(record["status"])
        target_status = update.status.value
        if target_status not in STATUS_TRANSITIONS[current_status]:
            raise IncidentValidationError(
                "status",
                "La transición de estado solicitada no está permitida.",
            )

        changes = {
            "status": target_status,
            "updated_at": _now_utc().isoformat(),
        }
        incidents.update(changes, doc_ids=[id])
    return _record_response(record.doc_id, dict(record) | changes)
