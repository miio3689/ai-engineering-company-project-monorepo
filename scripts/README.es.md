# Carpeta `scripts`

Esta carpeta contiene **scripts auxiliares** del monorepo: automatizaciones de desarrollo, utilidades de mantenimiento, tareas repetitivas (setup, lint, migraciones, generación de datos, etc.) y tooling interno.

- **Propósito principal**: agrupar herramientas de soporte que no pertenecen a una app/agente/pipeline específico, pero facilitan el trabajo del equipo.
- **Recomendación**: documenta cada script (qué hace, parámetros, requisitos, ejemplos de uso) y procura que sean reproducibles (y seguros) en distintos entornos.

## `analyze.py`

Valida y resume un CSV de incidencias de Brasaland, incluyendo desgloses por regla inválida, categoría, estado y satisfacción. No requiere dependencias externas.

```bash
python scripts/analyze.py scripts/incidents-brasaland.csv
```

El script solicita confirmación para exportar las métricas a `results.csv` en el directorio de trabajo actual.


## `nightly_export.py`

Job nocturno (ticket DEV-53). Para el día objetivo, exporta las filas de `telemetry_events` a `data/raw/telemetry_YYYY-MM-DD.csv` (solo si el archivo no existe), lanza el pipeline de desempeño de negocio (`data/pipelines/pipeline.py`) como subproceso y registra la ejecución en `public.job_runs`.

```bash
python scripts/nightly_export.py                          # ayer en UTC
TARGET_DATE=2026-11-20 python scripts/nightly_export.py   # otra fecha, sin tocar código
```

- **Día objetivo**: ayer en UTC, o `TARGET_DATE=YYYY-MM-DD`.
- **El CSV es una copia de respaldo** para auditoría y recuperación. El pipeline lee `telemetry_events` de la base de datos, no el CSV. Los CSV no se suben al repositorio porque contienen ids de usuario y de sesión.
- **Estados** en `job_runs`: `pending` → `processing` → `completed` | `failed`. Los gestiona `services/job_runner`.
  - **Lock**: el propio estado `processing`. Una segunda instancia termina sin error.
  - **Idempotencia**: un `completed` para `(nightly_export, target_date)` hace que una nueva ejecución de ese día no haga nada.
  - **Omisiones**: se registran como `completed` con `skip_reason` (`duplicate` o `locked`).
- **Código de salida**: `0` si completa o se omite; `1` si falla, y en ese caso `error_message` guarda la excepción.
- **Requisitos**: `DATABASE_URL` (o `services/api/.env`) y crear antes la tabla con `services/job_runner/sql/job_runs.sql`.
- **Variable opcional**: `PIPELINE_TIMEOUT_SECONDS` (por defecto 1800).
- **Disparador**: el contenedor `scheduler` de `docker-compose.yml` ejecuta cron con `0 2 * * *` (todos los días a las 02:00 UTC; ver `scheduler/crontab`). Los logs se ven con `docker compose logs scheduler`.
