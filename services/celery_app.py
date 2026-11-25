"""Celery application of Brasaland (ticket DEV-55).

Producer / consumer: the API only enqueues a light message (ids and dates,
never data) in Redis and answers 202 with the task id; a separate worker
process consumes the queue. Redis is both the broker and the result backend,
and both sides read its URL from REDIS_URL.

    celery -A services.celery_app worker --loglevel=INFO            # worker
    celery -A services.celery_app worker --loglevel=INFO --pool=solo  # worker on Windows
    celery -A services.celery_app flower --port=5555                # monitoring

Importing this module never connects to Redis nor to the database.
"""

from __future__ import annotations

import os

from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# The pipeline takes ~15 s; a run that has not finished in 15 minutes is stuck.
TASK_SOFT_TIME_LIMIT = int(os.environ.get("TASK_SOFT_TIME_LIMIT", "900"))
TASK_TIME_LIMIT = TASK_SOFT_TIME_LIMIT + 60

celery_app = Celery(
    "brasaland",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["services.async_tasks.pipeline_tasks"],
)

celery_app.conf.update(
    # Messages are JSON: only ids, dates and small numbers travel through Redis.
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # ACK only after the task finishes: if the worker dies mid-task the message
    # goes back to the queue instead of being lost.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    # Report STARTED, so GET /tasks/{task_id} can tell queued from running.
    task_track_started=True,
    # Every task has a timeout: the soft limit raises inside the task (and is
    # retried), the hard limit kills the child so it never blocks the pool.
    task_soft_time_limit=TASK_SOFT_TIME_LIMIT,
    task_time_limit=TASK_TIME_LIMIT,
    result_expires=60 * 60 * 24,
    # Unacked messages are redelivered after this; longer than any task.
    broker_transport_options={"visibility_timeout": 60 * 60, "socket_connect_timeout": 3},
    redis_socket_connect_timeout=3,
    broker_connection_retry_on_startup=True,
    # Flower and the worker logs need task events.
    worker_send_task_events=True,
    task_send_sent_event=True,
)

app = celery_app  # `celery -A services.celery_app` finds either name
