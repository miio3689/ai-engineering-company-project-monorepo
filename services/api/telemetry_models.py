"""Pydantic models for the telemetry event envelope.

The envelope is defined in docs/telemetry/telemetry-plan.md (section 6) and
docs/telemetry/event-schemas.json. These models are reused unchanged when the
real storage replaces the Phase 1 stub.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"


class TelemetryEvent(BaseModel):
    """One telemetry event with the standard envelope."""

    model_config = ConfigDict(extra="forbid")

    eventId: str = Field(pattern="^" + _UUID + "$")
    timestamp: datetime
    sessionId: str = Field(pattern="^" + _UUID + "$")
    userId: str = Field(pattern=r"^(anonymous|[0-9]+)$")
    event_type: str = Field(pattern=r"^[a-z]+(_[a-z]+)+$")
    schemaVersion: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    requestId: str = Field(pattern="^(none|" + _UUID + ")$")
    properties: dict[str, Any]


class TelemetryReceipt(BaseModel):
    """Response of the receiver for one batch: received = stored + rejected."""

    received: int
    stored: int
    rejected: int