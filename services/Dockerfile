FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # services/ and data/ are imported from /app: Celery only adds the working
    # directory to sys.path while it loads the app, not inside the tasks.
    PYTHONPATH=/app

WORKDIR /app

COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -r requirements.txt

COPY . /app/services
COPY --from=packages /shared/python /app/packages/shared/python
COPY --from=scripts *.py /app/scripts/
# services/reporting and the Celery worker run the pipeline code of data/.
COPY --from=data pipelines /app/data/pipelines
COPY --from=data process /app/data/process

EXPOSE 8000

CMD ["uvicorn", "services.api.app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000", "--reload-dir", "/app/services", "--reload-dir", "/app/packages", "--reload-dir", "/app/scripts"]