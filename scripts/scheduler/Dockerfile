# Dedicated scheduler for the nightly jobs. It runs the OS cron in its own
# container, so the nightly script never shares a process or thread with the
# FastAPI API. Built from docker-compose.yml (service "scheduler").
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

RUN apt-get update \
    && apt-get install -y --no-install-recommends cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Same dependencies as the API (SQLAlchemy, psycopg2, pandas, Prefect).
COPY --from=services api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -r /tmp/requirements.txt

COPY --from=services job_runner /app/services/job_runner
COPY --from=data pipelines /app/data/pipelines
COPY --from=data process /app/data/process
COPY nightly_export.py /app/scripts/nightly_export.py
COPY scheduler/crontab /etc/cron.d/nightly-export
COPY scheduler/entrypoint.sh /usr/local/bin/scheduler-entrypoint

RUN chmod 0644 /etc/cron.d/nightly-export \
    && chmod 0755 /usr/local/bin/scheduler-entrypoint \
    && mkdir -p /app/data/raw /app/data/eval

ENTRYPOINT ["scheduler-entrypoint"]
CMD ["cron", "-f"]
