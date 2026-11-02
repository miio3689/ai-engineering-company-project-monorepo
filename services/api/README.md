# Brasaland Incidents API

FastAPI service exposing the shared Brasaland incident validation and metrics functions from `scripts/analyze.py`.

## Run locally

From the repository root:

```bash
uv sync
python3 -c 'import secrets; print(secrets.token_urlsafe(48))'
# Copy the output into services/api/.env as JWT_SECRET_KEY=<generated value>
uv run --env-file services/api/.env uvicorn services.api.app.main:app --reload --host 0.0.0.0 --port 8000
```

At startup, the API loads `services/api/.env` before initializing authentication
configuration. Existing process environment variables take precedence. Standalone
scripts such as `promote_admin` do not start the API, so run them with `--env-file`
as shown below.

`POST /api/incidents/analyze` accepts a CSV upload under the multipart field `file`. `GET /api/incidents/results/export` downloads the most recent analysis as `results.csv`. The most recent metrics are held in process memory and are reset when the service restarts.

## Gestión de incidencias

Los cinco endpoints de gestión y resumen requieren autenticación Bearer. La
validación de estas rutas devuelve `400` con este formato, identificando cada
campo y explicando el error en español:

```json
{
  "detail": "Datos no válidos.",
  "errors": [
    { "field": "status", "message": "Selecciona uno de los valores permitidos." }
  ]
}
```

| Endpoint | Respuestas |
| --- | --- |
| `POST /api/incidents` | `201` creada; `400` datos no válidos; `401` sin autenticación; `500` error interno genérico. |
| `GET /api/incidents` | `200` lista (vacía si no hay incidencias); `400` filtros no válidos; `401` sin autenticación; `500` error interno genérico. Filtros opcionales combinables: `status`, `origin`, `branch` y `category`. |
| `GET /api/incidents/summary` | `200` resumen; `401` sin autenticación; `500` error interno genérico. |
| `GET /api/incidents/{id}` | `200` incidencia; `401` sin autenticación; `404` si no existe; `500` error interno genérico. |
| `PATCH /api/incidents/{id}/status` | `200` incidencia actualizada; `400` datos o transición no válidos; `401` sin autenticación; `404` si no existe; `500` error interno genérico. |

El resumen tiene esta forma; cada desglose contiene todos los valores permitidos
de su grupo, incluso cuando su contador es cero:

```text
{
  "total": entero,
  "by_status": { "open": entero, "in_progress": entero, "resolved": entero, "discarded": entero },
  "by_category": { ... },
  "by_origin": { ... },
  "by_branch": { ... }
}
```

Con la base vacía, `total` y todos los contadores son cero. El almacenamiento
TinyDB de incidencias está en `services/api/incidents.json`, separado de los
almacenes de proveedores y autenticación, y excluido de Git. Los errores
inesperados responden con un mensaje genérico sin exponer el stack trace. La
conversión de errores de validación de FastAPI a `400` se limita al router de
incidencias; login y registro conservan sus respuestas `422`.

Browser access is allowed from `http://localhost:3000` and the configured Codespaces backoffice origin by default. Set `CORS_ALLOWED_ORIGINS` to a comma-separated list of exact origins to override this default, for example `CORS_ALLOWED_ORIGINS="http://localhost:3000,https://backoffice.example.com"`.

## AUTH-01: configuration and authorization

`JWT_SECRET_KEY` is mandatory: the application refuses to start if it is
missing, empty or shorter than 32 characters (excluding surrounding whitespace).
There is no built-in signing key. The command above generates a random key;
configure a stable secret through the deployment environment/secret manager
and never commit it. Changing the key invalidates existing tokens.
JWTs also bind to the account's stored `created_at`; a missing or mismatched
claim is rejected, preventing a deleted account's token from authenticating
as a new account if TinyDB reuses its ID.
`ACCESS_TOKEN_EXPIRE_MINUTES` remains optional and defaults to 30.
The service loads `services/api/.env` at startup; existing process environment variables take precedence.

- Public `POST /users` accepts `email`, `password`, and optional `name`, `phone`
  and `address`. It always assigns `user`; any supplied `role` returns 422.
- Registration always creates a linked profile. Missing or blank names default
  to the email portion before `@`, including when phone/address are provided.
- An admin can `PUT /users/{id}` to update any user's email and role.
  Non-admins can update only their own email; another ID or any `role` field
  (even unchanged, null or invalid) returns 403.
- `DELETE /users/{id}` allows only an admin or the user themselves, and also
  deletes the linked profile. Non-admin requests for other IDs return 403
  before checking existence. An authorized request for a missing ID returns 404.
- `GET /profiles/me` and `PUT /profiles/me` repair legacy accounts without a
  profile using the email-based default. Repeated requests reuse the same
  profile and preserve its saved fields. Invalid updates still return 422.

### Promote an existing user to admin

Register the user normally, then run this trusted terminal command from the
repository root (not an API endpoint):

```bash
uv run --env-file services/api/.env python -m services.api.promote_admin registered@example.com
```

The email lookup is case-insensitive. A missing/invalid email fails with a
nonzero exit code; repeated promotion is safe. This updates the existing
`services/api/auth.json` store without changing the password or profile.
Restrict terminal/database access to administrators. Stop the API while running
this command: TinyDB requires a single writer, and the service's lock only
coordinates threads within one process. Run the API with one worker.

### Verification

Run the complete backend suite from the repository root:

```bash
uv run python -m unittest discover -s services/api/tests -t . -v
```

Tests define their own fake signing key and use temporary databases. The JWT
startup subprocess disables dotenv loading, so the missing-key case is isolated
from `services/api/.env`; tests do not modify the real user store.
Install the project's `test` dependency group if `httpx` is missing.
The registration grep in the backoffice found no submitted `role`: its input
contains email/password plus optional name/phone/address. No frontend was changed.

```bash
grep -nE 'role|RegistrationInput|JSON.stringify|/users|input\[field\]|\["name", "phone", "address"\]' \
  uis/backoffice/services/auth.ts uis/backoffice/types/auth.ts \
  uis/backoffice/hooks/use-auth-form.ts
```

## Seed del gestor de incidencias

Desde la raíz del monorepo, importa el CSV histórico por defecto:

```bash
uv run python scripts/seed_incidents.py
```

También se puede indicar otra ruta:

```bash
uv run python scripts/seed_incidents.py ruta/al/archivo.csv
```

El seed valida las filas con la lógica compartida, transforma estados,
categorías y sedes, y reporta descartes sin imprimir la descripción. La clave
de origen se guarda en la tabla auxiliar `incident_seed_keys`, no en el
documento `Incident`; volver a ejecutar el seed omite las claves ya
registradas.

TinyDB no coordina escrituras entre procesos: **detén la API antes de ejecutar
el seed y configura la API con un solo worker**. El incidente se inserta antes
que su clave de idempotencia. Si el proceso se interrumpe entre ambas
escrituras, una segunda ejecución podría insertar de nuevo esa incidencia.

AUTH-01 regression coverage in `tests/test_auth.py`:

| Failure | Rejected case | Allowed case |
| --- | --- | --- |
| 1 | `test_public_registration_rejects_every_role_and_assigns_user` | Same test: registration without role and successful login; terminal promotion tests |
| 2 | `test_non_admin_cannot_submit_role_even_unchanged_or_invalid`, `test_non_admin_cannot_update_other_existing_or_missing_user` | Own email update in the first test; `test_admin_can_update_email_and_role_of_any_user` |
| 3 | `test_delete_other_user_is_forbidden_before_existence_check` | `test_self_delete_removes_user_profile_and_invalidates_token`, `test_admin_can_delete_other_user_and_get_404_for_missing_user` |
| 4 | `test_invalid_profile_updates_do_not_create_or_change_profiles` | `test_registration_always_creates_profile_with_default_or_given_name`, `test_get_profile_repairs_legacy_account_idempotently`, `test_put_profile_repairs_legacy_account_and_preserves_changes` and concurrent repair test |
| 5 | `test_startup_rejects_missing_empty_and_short_jwt_secret` | `test_startup_accepts_jwt_secret_at_minimum_length_and_above` plus real signed login tokens in endpoint tests |

The original eight supplier/incident regression tests and their assertions
remain unchanged. Admin fixtures are created through `services_auth.crear_usuario`,
never through public registration.

## AUTH-03: password reset email configuration

- `RESEND_API_KEY`: Resend API key; required to deliver password reset emails
  and has no default. It must be configured to send email through Resend.
- `EMAIL_FROM`: sender address for reset emails; defaults to
  `onboarding@resend.dev`.
- `FRONTEND_BASE_URL`: public frontend base URL used to construct the reset
  link, without a trailing slash. In Codespaces, use the public URL for port
  3000. It defaults to `http://localhost:3000` for local development.
- `PASSWORD_RESET_EXPIRE_MINUTES`: reset-token lifetime in minutes. Defaults to
  `30`; accepted values are from `15` to `60`.

In Resend test mode, email is delivered only to the address of the Resend
account owner.

### Password reset endpoints

| Endpoint | Authentication | Responses |
| --- | --- | --- |
| `POST /auth/forgot-password` | Public | `200` with the same generic response whether or not the email exists; request validation errors return `422`. |
| `POST /auth/reset-password` | Public | `200` when the password is reset; `400` for an invalid, expired or already-used token; request validation errors return `422`. |
| `POST /auth/change-password` | Con sesión autenticada | `200` when the password is changed; `400` when the current password is incorrect; `401` when unauthenticated; request validation errors return `422`. |

`forgot-password` schedules email delivery and always returns `200`, including
when the account does not exist or email delivery fails, so the endpoint does
not disclose account existence or mail-provider status. Reset tokens are
single-use; a successful reset invalidates the token.

### Verification

Run the complete backend suite from the repository root:

```bash
uv run python -m unittest discover -s services/api/tests -t . -v
```

Tests define their own fake signing key and use temporary databases. The JWT
startup subprocess disables dotenv loading, so the missing-key case is isolated
from `services/api/.env`; tests do not modify the real user store.
Install the project's `test` dependency group if `httpx` is missing.
The registration grep in the backoffice found no submitted `role`: its input
contains email/password plus optional name/phone/address. No frontend was changed.

```bash
grep -nE 'role|RegistrationInput|JSON.stringify|/users|input\[field\]|\["name", "phone", "address"\]' \
  uis/backoffice/services/auth.ts uis/backoffice/types/auth.ts \
  uis/backoffice/hooks/use-auth-form.ts
```

AUTH-01 regression coverage in `tests/test_auth.py`:

| Failure | Rejected case | Allowed case |
| --- | --- | --- |
| 1 | `test_public_registration_rejects_every_role_and_assigns_user` | Same test: registration without role and successful login; terminal promotion tests |
| 2 | `test_non_admin_cannot_submit_role_even_unchanged_or_invalid`, `test_non_admin_cannot_update_other_existing_or_missing_user` | Own email update in the first test; `test_admin_can_update_email_and_role_of_any_user` |
| 3 | `test_delete_other_user_is_forbidden_before_existence_check` | `test_self_delete_removes_user_profile_and_invalidates_token`, `test_admin_can_delete_other_user_and_get_404_for_missing_user` |
| 4 | `test_invalid_profile_updates_do_not_create_or_change_profiles` | `test_registration_always_creates_profile_with_default_or_given_name`, `test_get_profile_repairs_legacy_account_idempotently`, `test_put_profile_repairs_legacy_account_and_preserves_changes` and concurrent repair test |
| 5 | `test_startup_rejects_missing_empty_and_short_jwt_secret` | `test_startup_accepts_jwt_secret_at_minimum_length_and_above` plus real signed login tokens in endpoint tests |

The original eight supplier/incident regression tests and their assertions
remain unchanged. Admin fixtures are created through `services_auth.crear_usuario`,
never through public registration.
