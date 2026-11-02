"""Shared Brasaland incident validation and CSV transformation rules."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

Record = Mapping[str, Any]

CSV_LOCATIONS = tuple(
    [f"COL-{number:02d}" for number in range(1, 11)]
    + [f"FLA-{number:02d}" for number in range(1, 5)]
)
CSV_CATEGORIES = (
    "CUSTOMER_COMPLAINT",
    "EQUIPMENT",
    "SUPPLY",
    "FOOD_QUALITY",
    "STAFF",
)
CSV_STATUSES = ("OPEN", "CLOSED", "DISCARDED")
SATISFACTION_SCORES = (1, 2, 3, 4, 5)
VALIDATION_ERROR_NAMES = (
    "missing_or_invalid_location_id",
    "missing_or_invalid_category",
    "empty_or_short_description",
    "missing_reporter_id",
    "closed_without_satisfaction_score",
    "satisfaction_score_out_of_range",
)


class IncidentStatus(str, Enum):
    open = "open"
    in_progress = "in_progress"
    resolved = "resolved"
    discarded = "discarded"


class Category(str, Enum):
    equipment_failure = "equipment_failure"
    supply_issue = "supply_issue"
    customer_complaint = "customer_complaint"
    staff_issue = "staff_issue"
    facility_issue = "facility_issue"
    pos_system = "pos_system"
    delivery_issue = "delivery_issue"
    other = "other"


class IncidentOrigin(str, Enum):
    customer = "customer"
    branch = "branch"
    internal = "internal"


class Branch(str, Enum):
    central = "central"
    medellin_centro = "medellin_centro"
    medellin_laureles = "medellin_laureles"
    medellin_envigado = "medellin_envigado"
    medellin_bello = "medellin_bello"
    medellin_itagui = "medellin_itagui"
    bogota_chapinero = "bogota_chapinero"
    bogota_usaquen = "bogota_usaquen"
    cali_granada = "cali_granada"
    barranquilla_norte = "barranquilla_norte"
    miami_doral = "miami_doral"
    miami_hialeah = "miami_hialeah"
    miami_kendall = "miami_kendall"
    orlando_international = "orlando_international"
    fort_lauderdale = "fort_lauderdale"


INCIDENT_STATUSES = tuple(status.value for status in IncidentStatus)
INCIDENT_CATEGORIES = tuple(category.value for category in Category)
INCIDENT_ORIGINS = tuple(origin.value for origin in IncidentOrigin)

STATUS_LABELS = {
    IncidentStatus.open.value: "Abierta",
    IncidentStatus.in_progress.value: "En progreso",
    IncidentStatus.resolved.value: "Resuelta",
    IncidentStatus.discarded.value: "Descartada",
}
CATEGORY_LABELS = {
    Category.equipment_failure.value: "Fallo de equipamiento",
    Category.supply_issue.value: "Problema de insumos",
    Category.customer_complaint.value: "Queja de cliente",
    Category.staff_issue.value: "Incidencia de personal",
    Category.facility_issue.value: "Problema de instalaciones",
    Category.pos_system.value: "Sistema de caja (TPV)",
    Category.delivery_issue.value: "Problema de domicilios",
    Category.other.value: "Otra",
}
ORIGIN_LABELS = {
    IncidentOrigin.customer.value: "Cliente",
    IncidentOrigin.branch.value: "Sede",
    IncidentOrigin.internal.value: "Interno",
}
BRANCH_LABELS = {
    Branch.central.value: "Central (Medellín / Miami)",
    Branch.medellin_centro.value: "Medellín Centro",
    Branch.medellin_laureles.value: "Medellín Laureles",
    Branch.medellin_envigado.value: "Medellín Envigado",
    Branch.medellin_bello.value: "Medellín Bello",
    Branch.medellin_itagui.value: "Medellín Itagüí",
    Branch.bogota_chapinero.value: "Bogotá Chapinero",
    Branch.bogota_usaquen.value: "Bogotá Usaquén",
    Branch.cali_granada.value: "Cali Granada",
    Branch.barranquilla_norte.value: "Barranquilla Norte",
    Branch.miami_doral.value: "Miami Doral",
    Branch.miami_hialeah.value: "Miami Hialeah",
    Branch.miami_kendall.value: "Miami Kendall",
    Branch.orlando_international.value: "Orlando International Drive",
    Branch.fort_lauderdale.value: "Fort Lauderdale",
}
BRANCHES = tuple(BRANCH_LABELS.items())

STATUS_TRANSITIONS = {
    IncidentStatus.open.value: frozenset(
        (IncidentStatus.in_progress.value, IncidentStatus.discarded.value)
    ),
    IncidentStatus.in_progress.value: frozenset(
        (IncidentStatus.resolved.value, IncidentStatus.discarded.value)
    ),
    IncidentStatus.resolved.value: frozenset(),
    IncidentStatus.discarded.value: frozenset(),
}

CSV_STATUS_MAP = {
    "OPEN": IncidentStatus.open.value,
    "CLOSED": IncidentStatus.resolved.value,
    "DISCARDED": IncidentStatus.discarded.value,
}
CSV_CATEGORY_MAP = {
    "CUSTOMER_COMPLAINT": Category.customer_complaint.value,
    "EQUIPMENT": Category.equipment_failure.value,
    "SUPPLY": Category.supply_issue.value,
    "FOOD_QUALITY": Category.customer_complaint.value,
    "STAFF": Category.staff_issue.value,
}
CSV_LOCATION_MAP = {
    "COL-01": Branch.medellin_centro.value,
    "COL-02": Branch.medellin_laureles.value,
    "COL-03": Branch.medellin_envigado.value,
    "COL-04": Branch.medellin_bello.value,
    "COL-05": Branch.medellin_itagui.value,
    "COL-06": Branch.bogota_chapinero.value,
    "COL-07": Branch.bogota_usaquen.value,
    "COL-08": Branch.cali_granada.value,
    "COL-09": Branch.barranquilla_norte.value,
    "COL-10": Branch.central.value,
    "FLA-01": Branch.miami_doral.value,
    "FLA-02": Branch.miami_hialeah.value,
    "FLA-03": Branch.miami_kendall.value,
    "FLA-04": Branch.orlando_international.value,
}
DEFAULT_BRANCH = Branch.central.value


def validate_record(record: Record) -> tuple[bool, list[str]]:
    """Return whether one legacy CSV row is valid and its failed rule IDs."""
    allowed_locations = set(CSV_LOCATIONS)
    allowed_categories = set(CSV_CATEGORIES)

    def value(field: str) -> str:
        raw = record.get(field, "")
        return "" if raw is None else str(raw).strip()

    failures: list[str] = []

    location_id = value("location_id")
    if not location_id or location_id not in allowed_locations:
        failures.append("missing_or_invalid_location_id")

    category = value("category")
    if not category or category not in allowed_categories:
        failures.append("missing_or_invalid_category")

    description = value("description")
    if len(description) < 5:
        failures.append("empty_or_short_description")

    if not value("reporter_id"):
        failures.append("missing_reporter_id")

    status = value("status")
    score_text = value("satisfaction_score")
    if status == "CLOSED" and not score_text:
        failures.append("closed_without_satisfaction_score")

    if score_text:
        try:
            score = int(score_text)
        except ValueError:
            score = None
        if score is None or str(score) != score_text or not 1 <= score <= 5:
            failures.append("satisfaction_score_out_of_range")

    return not failures, failures


def transform_csv_record(record: Record) -> dict[str, str]:
    """Transform a validated legacy CSV row into a model-ready incident."""
    source_status = str(record.get("status", "")).strip()
    source_category = str(record.get("category", "")).strip()
    source_location = str(record.get("location_id", "")).strip()
    description_value = record.get("description")
    if description_value is None:
        raise ValueError("description is required to create an incident title")
    description = str(description_value)
    title = description[:120].strip()
    if not title:
        raise ValueError("description cannot produce an empty incident title")

    try:
        status = CSV_STATUS_MAP[source_status]
    except KeyError as exc:
        raise ValueError(f"unsupported CSV status: {source_status}") from exc
    try:
        category = CSV_CATEGORY_MAP[source_category]
    except KeyError as exc:
        raise ValueError(f"unsupported CSV category: {source_category}") from exc

    date_value = str(record.get("date", "")).strip()
    try:
        created_at = datetime.strptime(date_value, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc

    return {
        "title": title,
        "description": description,
        "category": category,
        "status": status,
        "origin": IncidentOrigin.customer.value,
        "branch": CSV_LOCATION_MAP.get(source_location, DEFAULT_BRANCH),
        "created_at": created_at.isoformat(),
    }
