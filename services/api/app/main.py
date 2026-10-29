"""FastAPI endpoints for Brasaland incident analysis."""

from __future__ import annotations

import csv
import io
import os
import sys
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from scripts.analyze import calculate_metrics, results_rows, validate_record  # noqa: E402,F401
from services.api.routes.auth import router as auth_router  # noqa: E402
from services.api.routes.profiles import router as profiles_router  # noqa: E402
from services.api.routes.suppliers import router as suppliers_router  # noqa: E402
from services.api.routes.users import router as users_router  # noqa: E402
from services.api.auth_security import get_current_user  # noqa: E402
from services.api.models import UserResponse  # noqa: E402

EXPECTED_COLUMNS = (
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

app = FastAPI(title="Brasaland Incidents API", version="1.0.0")
app.include_router(suppliers_router)
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(profiles_router)
allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,https://cautious-meme-q7w9qr9ppxqqhx5rr-3000.app.github.dev",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS", "PATCH", "PUT", "DELETE"],
    allow_headers=["Accept", "Authorization", "Content-Type"],
)
_latest_metrics: dict[str, Any] | None = None
_metrics_lock = Lock()


def parse_incident_csv(content: bytes) -> list[dict[str, str]]:
    """Decode and validate CSV structure before passing records to shared logic."""
    if not content or not content.strip():
        raise HTTPException(status_code=400, detail="El fichero CSV está vacío.")

    try:
        text = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
        headers = reader.fieldnames
        if not headers:
            raise HTTPException(status_code=400, detail="El fichero está vacío o no contiene una cabecera CSV.")

        normalized_headers = [header.strip() if header else "" for header in headers]
        if len(normalized_headers) != len(EXPECTED_COLUMNS) or set(normalized_headers) != set(EXPECTED_COLUMNS):
            missing_columns = [column for column in EXPECTED_COLUMNS if column not in normalized_headers]
            if missing_columns:
                detail = (
                    "CSV con columnas no válidas. Faltan: "
                    + ", ".join(missing_columns)
                    + ". Se esperaban las 9 columnas de incidencias del formato Brasaland."
                )
            else:
                detail = "CSV con columnas no válidas. Se esperaban exactamente las 9 columnas del formato Brasaland."
            raise HTTPException(status_code=400, detail=detail)
        if len(set(normalized_headers)) != len(normalized_headers):
            raise HTTPException(status_code=400, detail="El CSV contiene nombres de columna duplicados.")

        # DictReader uses the original header strings as dictionary keys; normalize
        # whitespace so harmless spaces around header labels do not break records.
        records: list[dict[str, str]] = []
        for row_number, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                raise HTTPException(
                    status_code=400,
                    detail=f"Formato CSV inválido en la fila {row_number}: número de campos incorrecto.",
                )
            records.append(
                {
                    normalized_headers[index]: value
                    for index, value in enumerate(row.values())
                }
            )
        if not records:
            raise HTTPException(status_code=400, detail="El CSV no contiene filas de incidencias.")
        return records
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="El fichero debe ser CSV codificado en UTF-8.") from exc
    except csv.Error as exc:
        raise HTTPException(status_code=400, detail="El fichero no tiene un formato CSV válido.") from exc


@app.post("/api/incidents/analyze")
async def analyze_incidents(
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
) -> dict[str, Any]:
    """Analyze uploaded incident CSV records with the shared script functions."""
    global _latest_metrics

    try:
        if file.filename and Path(file.filename).suffix.lower() != ".csv":
            raise HTTPException(status_code=400, detail="El fichero debe tener extensión .csv.")
        content = await file.read()
        records = parse_incident_csv(content)
        metrics = calculate_metrics(records)

        invalid_by_rule = {
            rule: count
            for rule, count in metrics["invalid_by_rule"].items()
            if count > 0
        }
        result = {
            "total_records": metrics["total_records"],
            "valid_records": metrics["valid_records"],
            "invalid_records": metrics["invalid_records"],
            "invalid_by_rule": invalid_by_rule,
            "category_counts": {
                category: {
                    "count": count,
                    "percentage": round(metrics["category_percentages"][category], 1),
                }
                for category, count in metrics["category_counts"].items()
            },
            "status_counts": {
                status: {
                    "count": count,
                    "percentage": round(metrics["status_percentages"][status], 1),
                }
                for status, count in metrics["status_counts"].items()
            },
            "satisfaction": {
                "average": metrics["average_satisfaction"],
                "scored_cases": metrics["scored_closed_cases"],
                "counts": {
                    str(score): count
                    for score, count in metrics["satisfaction_counts"].items()
                },
            },
        }
        with _metrics_lock:
            _latest_metrics = metrics
        return result
    except HTTPException:
        raise
    except Exception as exc:
        # Keep implementation details out of the public response.
        raise HTTPException(status_code=500, detail="Error interno al analizar el fichero.") from exc
    finally:
        await file.close()


@app.get("/api/incidents/results/export")
def export_latest_results(
    current_user: UserResponse = Depends(get_current_user),
) -> Response:
    """Download the last analysis using the script's CSV metric row format."""
    with _metrics_lock:
        metrics = _latest_metrics
        if metrics is None:
            raise HTTPException(
                status_code=404,
                detail="No hay ningún análisis disponible, ejecuta /api/incidents/analyze primero",
            )
        csv_rows = results_rows(metrics)

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("metric", "value", "percentage"))
    writer.writerows(csv_rows)
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="results.csv"'},
    )
