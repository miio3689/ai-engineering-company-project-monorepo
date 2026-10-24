# Brasaland Incidents API

FastAPI service exposing the shared Brasaland incident validation and metrics functions from `scripts/analyze.py`.

## Run locally

From the repository root:

```bash
python -m pip install -r services/api/requirements.txt
uvicorn services.api.app.main:app --reload
```

`POST /api/incidents/analyze` accepts a CSV upload under the multipart field `file`. `GET /api/incidents/results/export` downloads the most recent analysis as `results.csv`. The most recent metrics are held in process memory and are reset when the service restarts.

Browser access is allowed from `http://localhost:3000` by default (the backoffice Next.js development origin). Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of exact origins to override this default, for example `CORS_ALLOWED_ORIGINS="http://localhost:3000,https://backoffice.example.com"`.
