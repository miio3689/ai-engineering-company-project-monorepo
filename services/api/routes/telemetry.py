"""Telemetry receiver: validates every event on its own and stores the valid
ones with a single bulk insert.

The body is parsed loosely ({"events": [...]}) and each item goes through
TelemetryEvent.model_validate plus the approved event contract, so one bad
event never cancels the rest of the batch. It requires no authentication on
purpose: navigator.sendBeacon cannot send an Authorization header. Properties
and user ids are never written to the log. Telemetry rows are immutable.
"""

import json
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from ..inventory.database import get_db
from ..telemetry_contract import validate_event_contract
from ..telemetry_models import TelemetryEvent, TelemetryReceipt
from ..telemetry_storage import event_to_row, store_events

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# URL del endpoint de telemetría: fija el patrón de configuración por entorno.
TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "")

MAX_BODY_BYTES = 256 * 1024
MAX_EVENTS_PER_BATCH = 100

telemetry_logger = logging.getLogger("api.telemetry")
if not telemetry_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    telemetry_logger.addHandler(_handler)
    telemetry_logger.setLevel(logging.INFO)
    telemetry_logger.propagate = False


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail=detail,
    )


@router.post("/events", response_model=TelemetryReceipt)
async def receive_events(
    request: Request,
    session: Session = Depends(get_db),
) -> TelemetryReceipt:
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="El lote de telemetría es demasiado grande.",
        )

    try:
        payload = json.loads(raw_body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise _unprocessable("El cuerpo debe ser JSON.") from exc
    raw_events = payload.get("events") if isinstance(payload, dict) else None
    if not isinstance(raw_events, list):
        raise _unprocessable("El cuerpo debe ser un objeto con una lista 'events'.")
    if len(raw_events) > MAX_EVENTS_PER_BATCH:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="El lote tiene demasiados eventos.",
        )

    rows = []
    stored_types = []
    rejected = 0
    for index, raw_event in enumerate(raw_events):
        try:
            event = TelemetryEvent.model_validate(raw_event)
        except ValidationError:
            rejected += 1
            telemetry_logger.warning(
                "telemetry event rejected: index=%d reason=invalid_envelope", index
            )
            continue
        problems = validate_event_contract(event)
        if problems:
            rejected += 1
            telemetry_logger.warning(
                "telemetry event rejected: index=%d type=%s reason=%s",
                index,
                event.event_type,
                "; ".join(problems[:5]),
            )
            continue
        rows.append(event_to_row(event))
        stored_types.append(event.event_type)

    try:
        await run_in_threadpool(store_events, session, rows)
    except SQLAlchemyError as exc:
        session.rollback()
        telemetry_logger.error(
            "Telemetry storage error (type: %s).", type(exc).__name__
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Servicio de telemetría no disponible.",
        ) from exc

    telemetry_logger.info(
        "telemetry batch received: received=%d stored=%d rejected=%d",
        len(raw_events),
        len(rows),
        rejected,
    )
    for event_type in stored_types:
        telemetry_logger.info("telemetry event stored: %s", event_type)
    return TelemetryReceipt(
        received=len(raw_events),
        stored=len(rows),
        rejected=rejected,
    )