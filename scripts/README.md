# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

> _Spanish version: [README.es.md](./README.es.md)._


## `nightly_export.py`

Nightly job (ticket DEV-53). For the target day, it exports the `telemetry_events` rows to `data/raw/telemetry_YYYY-MM-DD.csv` (only if the file does not exist), launches the business performance pipeline (`data/pipelines/pipeline.py`) as a subprocess, and records the execution in `public.job_runs`.

```bash
python scripts/nightly_export.py                          # yesterday in UTC
TARGET_DATE=2026-11-20 python scripts/nightly_export.py   # any other day, no code change
```

- **Target day**: yesterday in UTC, or `TARGET_DATE=YYYY-MM-DD`.
- **The CSV is a backup** for audit and recovery. The pipeline reads `telemetry_events` from the database, not the CSV. The CSV files are not committed because they contain user and session ids.
- **States** in `job_runs`: `pending` → `processing` → `completed` | `failed`. They are managed by `services/job_runner`.
  - **Lock**: the `processing` state itself. A second instance exits without an error.
  - **Idempotency**: a `completed` row for `(nightly_export, target_date)` makes a new run of that day do nothing.
  - **Skipped runs**: recorded as `completed` with a `skip_reason` (`duplicate` or `locked`).
- **Exit code**: `0` when it completes or is skipped; `1` when it fails, with the exception stored in `error_message`.
- **Requirements**: `DATABASE_URL` (or `services/api/.env`), and the table created beforehand with `services/job_runner/sql/job_runs.sql`.
- **Optional variable**: `PIPELINE_TIMEOUT_SECONDS` (default 1800).
- **Trigger**: the `scheduler` container in `docker-compose.yml` runs cron with `0 2 * * *` (every day at 02:00 UTC; see `scheduler/crontab`). Logs are available with `docker compose logs scheduler`.
