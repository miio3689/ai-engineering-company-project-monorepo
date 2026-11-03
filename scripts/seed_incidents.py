#!/usr/bin/env python3
"""Import validated legacy incident CSV rows into the shared TinyDB store."""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from services.api.shared_paths import ensure_shared_python_path  # noqa: E402

ensure_shared_python_path(REPOSITORY_ROOT)

from brasaland_shared.incidents import (  # noqa: E402
    INCIDENT_CATEGORIES,
    INCIDENT_STATUSES,
    transform_csv_record,
    validate_record,
)
from services.api import database  # noqa: E402
from tinydb import Query  # noqa: E402

DEFAULT_CSV_PATH = REPOSITORY_ROOT / "scripts" / "incidents-brasaland.csv"
REQUIRED_CSV_COLUMNS = (
    "incident_id",
    "date",
    "location_id",
    "category",
    "description",
    "status",
    "customer_id",
    "satisfaction_score",
    "reporter_id",
)

VALIDATION_REASON_LABELS = {
    "missing_or_invalid_location_id": "sede ausente o no válida",
    "missing_or_invalid_category": "categoría ausente o no válida",
    "empty_or_short_description": "descripción vacía o demasiado corta",
    "missing_reporter_id": "falta el identificador del informante",
    "closed_without_satisfaction_score": "incidencia cerrada sin puntuación",
    "satisfaction_score_out_of_range": "puntuación de satisfacción fuera de rango",
}
TRANSFORM_REASON_LABELS = {
    "unmapped_status": "estado sin mapa",
    "invalid_date": "fecha no parseable",
    "empty_title": "título vacío",
    "invalid_transform": "fila no transformable",
}


class CsvReadError(Exception):
    """A user-facing, safe-to-print error while reading the input CSV."""


class DatabaseAccessError(Exception):
    """A safe-to-display error while accessing the incidents database."""


@dataclass
class SeedResult:
    rows_read: int = 0
    valid_rows: int = 0
    inserted: int = 0
    duplicates: int = 0
    discarded: int = 0
    discarded_by_reason: Counter[str] = field(default_factory=Counter)
    status_totals: dict[str, int] = field(default_factory=dict)
    category_totals: dict[str, int] = field(default_factory=dict)


def _read_csv(csv_path: Path) -> list[tuple[int, dict[str, Any]]]:
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            reader = csv.DictReader(csv_file, strict=True)
            if not reader.fieldnames:
                raise CsvReadError("El CSV está vacío o no contiene cabecera.")
            if not set(REQUIRED_CSV_COLUMNS).issubset(reader.fieldnames):
                raise CsvReadError("Al CSV le faltan columnas requeridas.")
            return [
                (row_number, row)
                for row_number, row in enumerate(reader, start=2)
            ]
    except FileNotFoundError as exc:
        raise CsvReadError("No se encontró el archivo CSV.") from exc
    except PermissionError as exc:
        raise CsvReadError("No hay permisos para leer el archivo CSV.") from exc
    except UnicodeDecodeError as exc:
        raise CsvReadError("El CSV debe estar codificado en UTF-8.") from exc
    except csv.Error as exc:
        raise CsvReadError("El archivo CSV tiene un formato no válido.") from exc
    except OSError as exc:
        raise CsvReadError("No se pudo leer el archivo CSV.") from exc


def _incident_id_for_report(record: dict[str, Any]) -> str:
    value = record.get("incident_id")
    if value is None or not str(value).strip():
        return "<sin incident_id>"
    return str(value).strip()


def _print_discarded(
    row_number: int,
    record: dict[str, Any],
    reason_codes: list[str],
) -> None:
    incident_id = json.dumps(
        _incident_id_for_report(record),
        ensure_ascii=False,
    )
    labels = [
        VALIDATION_REASON_LABELS.get(
            reason_code,
            TRANSFORM_REASON_LABELS.get(reason_code, "fila no válida"),
        )
        for reason_code in reason_codes
    ]
    print(
        f"Fila {row_number}, incident_id={incident_id}: "
        f"descartada ({'; '.join(labels)})."
    )


def _transform_failure_reason(error: ValueError) -> str:
    message = str(error)
    if message.startswith("unsupported CSV status:"):
        return "unmapped_status"
    if message == "date must use YYYY-MM-DD format":
        return "invalid_date"
    if message == "description cannot produce an empty incident title":
        return "empty_title"
    return "invalid_transform"


def _source_key(record: dict[str, Any], transformed: dict[str, str]) -> str:
    incident_id = record.get("incident_id")
    if incident_id is not None and str(incident_id).strip():
        return f"incident_id:{str(incident_id).strip()}"
    fallback = json.dumps(
        [transformed["title"], transformed["created_at"]],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return f"title_created_at:{fallback}"


def _count_totals(records: list[dict[str, Any]], values: tuple[str, ...], field: str) -> dict[str, int]:
    return {
        value: sum(1 for record in records if record.get(field) == value)
        for value in values
    }


def _print_report(result: SeedResult) -> None:
    print("\nInforme del seed de incidencias")
    print(f"Filas leídas: {result.rows_read}")
    print(f"Filas válidas: {result.valid_rows}")
    print(f"Incidencias insertadas: {result.inserted}")
    print(f"Omitidas por duplicado: {result.duplicates}")
    print(f"Filas descartadas: {result.discarded}")
    print("Descartadas por motivo:")
    if result.discarded_by_reason:
        for reason, count in sorted(result.discarded_by_reason.items()):
            label = VALIDATION_REASON_LABELS.get(
                reason,
                TRANSFORM_REASON_LABELS.get(reason, "fila no válida"),
            )
            print(f"  - {label}: {count}")
    else:
        print("  - Ninguna")
    print("Totales actuales por status:")
    for status, count in result.status_totals.items():
        print(f"  - {status}: {count}")
    print("Totales actuales por category:")
    for category, count in result.category_totals.items():
        print(f"  - {category}: {count}")


def seed_csv(csv_path: Path) -> SeedResult:
    """Validate, transform and import a CSV into the API's incidents database."""
    rows = _read_csv(csv_path)
    result = SeedResult(rows_read=len(rows))
    query = Query()

    try:
        with database.get_incidents_tables() as (incidents, seed_keys):
            for row_number, record in rows:
                is_valid, validation_failures = validate_record(record)
                if not is_valid:
                    result.discarded += 1
                    result.discarded_by_reason.update(validation_failures)
                    _print_discarded(row_number, record, validation_failures)
                    continue

                try:
                    transformed = transform_csv_record(record)
                except ValueError as exc:
                    reason = _transform_failure_reason(exc)
                    result.discarded += 1
                    result.discarded_by_reason[reason] += 1
                    _print_discarded(row_number, record, [reason])
                    continue

                result.valid_rows += 1
                source_key = _source_key(record, transformed)
                if seed_keys.contains(query.source_key == source_key):
                    result.duplicates += 1
                    continue

                inserted_at = datetime_now_utc()
                incident_record = transformed | {"updated_at": inserted_at}
                incident_document_id = incidents.insert(incident_record)
                seed_keys.insert(
                    {
                        "source_key": source_key,
                        "incident_document_id": incident_document_id,
                    }
                )
                result.inserted += 1

            stored_records = [dict(record) for record in incidents.all()]
            result.status_totals = _count_totals(
                stored_records,
                INCIDENT_STATUSES,
                "status",
            )
            result.category_totals = _count_totals(
                stored_records,
                INCIDENT_CATEGORIES,
                "category",
            )
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise DatabaseAccessError(
            "No se pudo acceder a la base de datos de incidencias."
        ) from exc
    _print_report(result)
    return result


def datetime_now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Importa incidencias históricas validadas desde un CSV."
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Ruta al CSV (por defecto scripts/incidents-brasaland.csv)",
    )
    args = parser.parse_args(argv)

    try:
        seed_csv(args.csv_path)
    except CsvReadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except DatabaseAccessError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
