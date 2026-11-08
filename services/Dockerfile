FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY api/requirements.txt requirements.txt
RUN pip install --no-cache-dir uv \
    && uv pip install --system --no-cache -r requirements.txt

COPY . /app/services
COPY --from=packages /shared/python /app/packages/shared/python
COPY --from=scripts *.py /app/scripts/

EXPOSE 8000

CMD ["uvicorn", "services.api.app.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000", "--reload-dir", "/app/services", "--reload-dir", "/app/packages", "--reload-dir", "/app/scripts"]