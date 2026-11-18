"""Validate telemetry events against the approved contract.

The contract is docs/telemetry/event-schemas.json. A copy lives next to this
module because the API container only ships the services/ folder; a test keeps
both copies identical. Messages only name the property path and the broken
rule, never the received value (it could be personal data).
"""

import json
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from .telemetry_models import TelemetryEvent

CONTRACT_PATH = Path(__file__).with_name("telemetry_schemas") / "event-schemas.json"


@lru_cache(maxsize=1)
def load_contract() -> dict[str, Any]:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _resolve(schema: dict[str, Any], definitions: dict[str, Any]) -> dict[str, Any]:
    reference = schema.get("$ref")
    if reference is None:
        return schema
    return definitions[reference.rsplit("/", 1)[-1]]


def _is_type(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    return False


def _is_date_time(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def _check_value(
    path: str,
    value: Any,
    schema: dict[str, Any],
    definitions: dict[str, Any],
) -> list[str]:
    schema = _resolve(schema, definitions)
    expected = schema.get("type")
    if expected and not _is_type(value, expected):
        return [f"{path}: wrong type (expected {expected})"]

    problems: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: value not in the allowed list")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value != value or value in (float("inf"), float("-inf")):
            problems.append(f"{path}: not a finite number")
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: below the minimum")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: above the maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            problems.append(f"{path}: not above the exclusive minimum")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{path}: too short")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{path}: too long")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            problems.append(f"{path}: does not match the expected pattern")
        if schema.get("format") == "date-time" and not _is_date_time(value):
            problems.append(f"{path}: not an ISO 8601 date-time with time zone")
    return problems


def validate_event_contract(event: TelemetryEvent) -> list[str]:
    """Return the list of contract violations (empty when the event is valid)."""
    contract = load_contract()
    problems: list[str] = []

    if event.schemaVersion.split(".")[0] != contract["schemaVersion"].split(".")[0]:
        problems.append("schemaVersion: unsupported major version")
    if event.timestamp.tzinfo is None:
        problems.append("timestamp: must include a time zone")

    definition = contract["events"].get(event.event_type)
    if definition is None:
        problems.append("event_type: not in the approved catalog")
        return problems

    properties_schema = definition["schema"]["properties"]["properties"]
    allowed = properties_schema["properties"]
    definitions = contract["definitions"]

    for key in event.properties:
        if key not in allowed:
            problems.append("properties: unexpected property")
    for key in properties_schema.get("required", []):
        if key not in event.properties:
            problems.append(f"properties.{key}: required")
    for key, value in event.properties.items():
        if key in allowed:
            problems.extend(
                _check_value(f"properties.{key}", value, allowed[key], definitions)
            )
    return problems
