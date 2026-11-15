"""Temporary telemetry receiver (Phase 1 stub).

It only validates the batch format, logs how many events arrived and their
event_type, and answers 200. It does not store anything: the real storage
replaces the body of receive_events in a later phase.

It requires no authentication on purpose: navigator.sendBeacon cannot send an
Authorization header. The body is read as text so it accepts both
application/json and text/plain (the content type used to avoid a CORS
preflight). Properties and userId are never written to the log.
"""

import logging
import os

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import ValidationError

from ..telemetry_models import TelemetryBatch, TelemetryReceipt

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# URL del endpoint de telemetría. Aún no se usa para redirigir tráfico: fija el
# patrón de configuración por entorno desde el inicio.
TELEMETRY_ENDPOINT = os.getenv("TELEMETRY_ENDPOINT", "")

MAX_BODY_BYTES = 256 * 1024

telemetry_logger = logging.getLogger("api.telemetry")
if not telemetry_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    telemetry_logger.addHandler(_handler)
    telemetry_logger.setLevel(logging.INFO)
    telemetry_logger.propagate = False


@router.post("/events", response_model=TelemetryReceipt)
async def receive_events(request: Request) -> TelemetryReceipt:
    raw_body = await request.body()
    if len(raw_body) > MAX_BODY_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="El lote de telemetría es demasiado grande.",
        )

    try:
        batch = TelemetryBatch.model_validate_json(raw_body)
    except ValidationError as exc:
        # Solo ubicación y mensaje: nunca el valor recibido (podría ser un dato personal).
        issues = [
            {"loc": [str(part) for part in error["loc"]], "msg": error["msg"]}
            for error in exc.errors()[:20]
        ]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=issues,
        ) from exc

    telemetry_logger.info("telemetry batch received: count=%d", len(batch.events))
    for event in batch.events:
        telemetry_logger.info("telemetry event: %s", event.event_type)
    return TelemetryReceipt(received=len(batch.events))