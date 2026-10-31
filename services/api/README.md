# Brasaland Incidents API

FastAPI service exposing the shared Brasaland incident validation and metrics functions from `scripts/analyze.py`.

## Run locally

From the repository root:

```bash
uv sync
uv run uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000
```

At startup, the API loads `services/api/.env` before initializing authentication
configuration. Existing process environment variables take precedence.

### Password reset email configuration

- `RESEND_API_KEY`: Resend API key; required to deliver password reset emails
	and has no default. It is read only from the process environment or the
	service's local environment file.
- `EMAIL_FROM`: sender address for reset emails. Defaults to
	`onboarding@resend.dev` for development.
- `FRONTEND_BASE_URL`: frontend base URL used to construct the reset link. It
	defaults to `http://localhost:3000`.
- `PASSWORD_RESET_EXPIRE_MINUTES`: reset-token lifetime in minutes. Defaults to
	`30`; accepted values are from `15` to `60`.

`POST /api/incidents/analyze` accepts a CSV upload under the multipart field `file`. `GET /api/incidents/results/export` downloads the most recent analysis as `results.csv`. The most recent metrics are held in process memory and are reset when the service restarts.

Browser access is allowed from `http://localhost:3000` and the configured Codespaces backoffice origin by default. Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of exact origins to override this default, for example `CORS_ALLOWED_ORIGINS="http://localhost:3000,https://backoffice.example.com"`.
