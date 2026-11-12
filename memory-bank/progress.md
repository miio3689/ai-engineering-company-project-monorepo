# Brasaland - Project Progress

## Current status

Hito 4 is being implemented on top of the existing Brasaland monorepo.

The Hito 3 Talent Pipeline Tracker now lives under `uis/backoffice/`, separate from root-level backend services.

The initial directory structure for Hito 4 is being prepared.

Target directories:

```text
.agents/rules/
.agents/skills/
memory-bank/
uis/website/
uis/backoffice/
services/
```

The existing Hito 3 application remains at:

```text
uis/backoffice/
```

and should not be replaced.

## Completed before Hito 4

### Hito 1

The project contains the initial public web work, including the existing HTML/CSS/JavaScript files.

### Hito 2

The TypeScript/Vite Data Lab is working under `uis/backoffice/data-lab/`.

Validated operations include:

- `npm install`
- `npm run build`
- `npm run dev`

### Hito 3

The Talent Pipeline Tracker Next.js application is working under:

```text
uis/backoffice/
```

Validated operations include:

- typecheck
- lint
- build
- development server
- candidate listing and filters
- candidate detail
- candidate editing
- status and stage updates
- candidate notes

## Hito 4 next steps

1. Ensure the Hito 4 directory structure exists.
2. Create `CONTEXT.md` at the repository root from `CONTEXT-brasaland-briefing.md`.
3. Review the existing repository structure and relevant README files before implementing new applications.
4. Complete and verify the memory bank.
5. Create root `AGENTS.md`.
6. Add at least one scoped rule under `.agents/rules/`.
7. Add at least one reusable skill under `.agents/skills/` with explicit acceptance criteria.
8. Initialize and implement `uis/website`.
9. Continue validating the existing Talent Pipeline Tracker under `uis/backoffice`.
10. Add backend services under `services` according to the repository/template conventions.
11. Run the required validation checks.
12. Review the Git diff and repository status.
13. Commit and push the completed Hito 4 work.
14. Open the required pull request and notify the tech lead.

## Working principle

Hito 4 should extend the current monorepo. Existing milestones should be preserved unless a change is explicitly required by the new milestone.

## AUTH-02 - Account profile and logout

- Added protected `/account/profile`, using the existing unchanged guard.
  `GET /auth/me` loads read-only email and linked name/phone/address through the
  shared Bearer API client. `PUT /profiles/me` sends only editable fields and
  displays the returned profile immediately, with saving/success/error states.
- Added client-side name validation, optional-field clearing as `null`, reset
  to the last saved values, abortable account loading and load retry.
  Accounts with `profile: null` explicitly explain that the API only updates
  existing profiles; no unsupported creation request is made.
- Added shared internal navigation with profile access and logout. Logout
  removes the token, notifies the existing guard via its storage subscription
  and replaces the document with `/login`, discarding the in-memory router
  cache. Storage failures are explicit and do not claim successful logout.
- Chromium against the real API and production build verified profile/email
  loading, authenticated PUT payload/header, immediate name update, persistence
  after reload, clearing optional fields, validation/reset, readable simulated
  load/save failures and retry, missing profile, and centralized PUT 401 logout.
- Verified direct anonymous profile access redirects without requesting account
  data. Logout removes localStorage token and navigates to login; browser Back
  re-enters the unchanged guard and returns to login, with frame-level checks
  confirming no visible cached profile field without a token.
- Responsive layouts pass at 375/768/1280px. Authenticated mobile Lighthouse:
  performance 99, accessibility 100. Fifteen automated authentication/account
  regression tests, typecheck, targeted ESLint, production build and diff checks
  pass. Tests used isolated users; existing user storage was not modified.
- Guard, Website, Data Lab, backend and business pages remain unchanged.
  No commit made.

## AUTH-02 - Client-side route protection

- Added a single client guard in the existing root layout, without moving or
  changing business pages. Only `/login` and `/register` are public; `/`,
  `/incidents`, `/suppliers`, candidate details and other internal paths require
  a non-empty localStorage token.
- SSR/hydration display a checking state rather than protected UI. Missing
  tokens trigger `router.replace("/login")`; blocked storage shows an explicit
  error. Route changes, storage events, focus and page restoration recheck the
  session. No Next.js middleware or backend changes.
- Chromium checks against the production build passed: direct anonymous access
  to the three main routes, candidate detail and an unknown internal path
  redirects without displaying protected content; login/register remain public
  with and without tokens; JavaScript-disabled pages show only the checking
  state; blocked storage, cross-tab logout and same-tab logout followed by
  focus/navigation are handled.
- Real API registration/login produced a valid token verified by `/auth/me`.
  Incidents rendered normally and suppliers loaded all 15 existing rows.
  The root still encounters the existing `/records` 404 from the real API.
  Separate read-only candidate fixtures, added only to the test process,
  confirmed normal authenticated Tracker listing/detail and no visible
  candidate data before anonymous redirects. No repository backend was changed.
- Verified the unchanged public website `/` and `/application.html`: HTTP 200,
  visible content without a token, no guard and no redirect.
- Eleven existing authentication regression tests, typecheck, targeted ESLint,
  production build and diff checks pass. Website, Data Lab and business page
  files remain unchanged. Test servers stopped and isolated test data removed.
- This is a browser UI guard, not server-side authorization: existing Next.js
  server components still execute/serialize normally and API authentication
  remains responsible for protecting data.
- No commit made.

## AUTH-02 - Backoffice authentication flows

- Added `/login` and `/register` following the existing page/component/hook/
  service/types structure. Login uses OAuth form data (`username=email`);
  registration uses public JSON and automatically logs in after creation.
- Successful authentication stores the returned token under `access_token` in
  browser localStorage and navigates to `/`. Registration errors appear beside
  their fields, including duplicate email (409), FastAPI validation (422), and
  the name required when phone/address are supplied.
- Centralized existing candidate, supplier and incident requests through
  `services/api-client.ts`: reads the browser token per request, sends Bearer
  authorization, and clears storage/navigates to `/login` on protected 401.
  Public authentication failures stay on the form.
- Chromium verification against the real API and production frontend passed:
  registration with/without optional profile, automatic login and exact stored
  token, `/auth/me` profile confirmation, manual storage logout and subsequent
  login, incorrect credentials, duplicate email field error, existing 15-row
  supplier listing with Bearer header, and a genuinely expired signed JWT
  clearing the token and redirecting. Also checked simulated 422 field errors
  and automatic-login failure after successful registration.
- Verified validation focus, reset, and 375/768/1280px layouts without overflow.
  Eleven automated regression tests, typecheck, targeted ESLint and production
  build pass. Isolated mobile Lighthouse scores: login 99 performance/100
  accessibility; register 98 performance/100 accessibility.
- Existing limitation remains: `services/api` has no `/records` endpoint.
  Navigation to `/` succeeds, but the Tracker cannot load its candidate data
  from this API. Existing server components cannot read browser localStorage;
  their loading model was not changed.
- Used an isolated authentication test database, not the existing user store.
  No route guards, website/Data Lab changes, backend changes, or commit.

## AUTH-03 - Restablecimiento y cambio de contraseña

- Backend: restablecimiento por email con tokens aleatorios almacenados como
  hash SHA-256, caducidad configurable, un solo uso e invalidación de tokens
  previos. `POST /auth/forgot-password` siempre responde `200`; los endpoints
  de reset y cambio de contraseña responden `400` ante token inválido/usado o
  contraseña actual incorrecta, respectivamente.
- Frontend: vistas `/forgot-password`, `/reset-password` y
  `/account/change-password`; enlace de recuperación en login y rutas públicas
  incluidas en el guard. Un `400` al cambiar la contraseña muestra el error y
  conserva la sesión.
- Validaciones reportadas: 41 pruebas de backend y 18 de frontend, build, lint
  y typecheck superados.
- La desarrolladora completó y verificó la prueba real de extremo a extremo
  con Resend: email recibido con enlace correcto, cambio de contraseña,
  rechazo al reutilizar el enlace y respuesta `400` al cambiar la contraseña
  desde la cuenta sin cerrar la sesión.
- Limitaciones conocidas: la API todavía devuelve `404` en `/records`, previo
  a este trabajo; el token de reset viaja en la URL y puede quedar en el
  historial del navegador; Resend en modo de pruebas solo entrega al email de
  la cuenta propietaria.

## Gestor de Incidencias Centralizado

- Modelo `Incident` con ID, campos de incidencia y timestamps automáticos.
  Cinco endpoints autenticados: `POST /api/incidents`, `GET /api/incidents`,
  `GET /api/incidents/summary`, `GET /api/incidents/{id}` y
  `PATCH /api/incidents/{id}/status`. La
  conversión de validación a `400` está acotada al router de incidencias;
  login y registro mantienen sus respuestas `422`.
- `packages/shared/python/brasaland_shared` contiene la validación compartida
  y las reglas de transformación. `scripts/analyze.py` conserva su interfaz
  pública como fachada compatible.
- `scripts/seed_incidents.py` carga el CSV en TinyDB e implementa idempotencia
  con `incident_id` en una tabla auxiliar, sin añadir esa clave al modelo.
- El seed fue verificado por la desarrolladora con el CSV real: 96 registros
  (open 32, resolved 50, discarded 14; customer_complaint 48, supply_issue 22,
  equipment_failure 17, staff_issue 9). La segunda ejecución no duplicó
  registros.
- Backoffice: formulario en `/incidents/register`, listado y cambio de estado
  en `/incidents/list`, y métricas en `/incidents/summary`. La desarrolladora
  verificó manualmente el frontend en el navegador de Codespaces; en esta
  sesión no fue posible ejecutar Chromium.
- Validaciones registradas: 70 pruebas de backend en total (41 previas más las
  nuevas), 18 pruebas de `test:auth`, typecheck, lint sin avisos y build.
- Limitaciones conocidas: la página `/` sigue recibiendo el `404` preexistente
  de `/records`; TinyDB no coordina escrituras entre procesos, por lo que el
  seed debe ejecutarse con la API parada y la API debe usar un solo worker. La
  alerta para quejas abiertas durante más de 48 horas no está implementada;
  solo se dejó el modelo preparado.

## Milestone 09 - Supplier write actions

- Added supplier creation with multiple categories, optional contact/notes,
  client validation, reset, pending/success states and readable API 422 errors.
- Added per-row rate editing and one-click suspend/activate; updates use returned
  API records without page reloads and preserve existing filters.
- No DELETE UI; no backend or incident page changes.
- Chromium verification passed: creation with all fields, invalid country/currency
  rejection, readable simulated 422 response, rate update from 12.50 to 19.75 USD,
  client rejection of zero/negative rates without PATCH, suspend/activate badge
  changes, existing filters, reset and responsive layouts.
- Removed the test supplier via direct API DELETE (204) and compared all 15
  original documents including IDs, rates, statuses and timestamps unchanged.
- Typecheck, targeted ESLint and production build pass; the same browser write
  checks also pass against the production build. Lighthouse mobile performance:
  96/100. No commit made.

## Milestone 09 - Supplier listing frontend

- Added the read-only `/suppliers` page, linked from the main backoffice listing,
  following the incident page's page/component/service/types structure.
- Uses `NEXT_PUBLIC_API_BASE_URL` and the existing supplier response fields;
  country and category filters trigger API requests with combined AND filters.
- Displays currency-qualified rates, category labels and active/suspended badges,
  plus loading, empty and error states with retry. Stale requests are aborted.
- Verified with backend and frontend running together in Chromium: frontend HTTP
  200, 15 seed suppliers, USA = 6, carne = 3, USA + carne = 1 (Miami Meat
  Distributors LLC), all eight category filters and no document reloads.
- Verified empty results, HTTP 503 error/retry, keyboard filter navigation and
  layouts at 375, 768 and 1280 pixels without page horizontal overflow.
- Typecheck, targeted ESLint and production build pass.
- Production Lighthouse mobile performance: 94/100.
- The main candidate page cannot render against the incident/supplier-only API:
  its existing candidate request receives 404. The menu link is added using the
  existing pattern; end-to-end navigation from that page requires the candidate
  backend. No candidate API integration changes were made.
- No supplier mutation UI added; API and incident page remain unchanged.
- No commit made.

## Milestone 09 - Supplier directory API

- Added the supplier router with create, list, detail, rate update, status
  update and delete endpoints, backed by the existing TinyDB storage.
- Mounted the router in the existing API; incident handlers remain unchanged.
- Rate and status updates use dedicated input models that reject extra fields.
- Validated all requested HTTP cases against the seeded local database with
  FastAPI TestClient. Removed the test supplier and verified that all 15
  original documents, IDs and timestamps were preserved.
- Eight isolated integration tests pass, including combined filters, 404
  responses, rejection before opening TinyDB, field-level update isolation and
  incident analysis/export regression checks.
- Existing CORS remains unchanged and does not permit cross-origin PATCH or
  DELETE. TinyDB writes require a single API worker and no concurrent seeder.
- No commit made for this task.

## Auditoría de gestión de errores

  HTTP ni respuestas crudas; `response.json()` está protegido. Las páginas de
  servidor muestran error local con reintento en vez de caer al error genérico.
  Las cargas usan `try/catch/finally`, estados de carga/éxito/error y fallbacks
  con optional chaining. `app/error.tsx` no muestra `error.message` y ofrece
  reintento, enlace al inicio y contacto de soporte. No cambiaron el logout
  ante 401, los errores 422 por campo de autenticación ni el mensaje fijo de
  forgot-password.
  recuperación de contraseña y el análisis CSV manejan errores en ámbitos
  acotados; el registro revierte el usuario si falla el perfil y responde con
  500 genérico. Un manejador global devuelve JSON limpio para errores no
  controlados. Los logs no incluyen tracebacks ni datos sensibles. Se conservan
  el 422 de autenticación, el 400 de incidencias, `{detail}` en analyze y el
  200 genérico de forgot-password.
  CSV; `analyze.py` también controla la escritura. Los errores críticos se
  comunican por `stderr` y terminan con código distinto de cero; se validan
  argumentos, cabeceras y columnas. El seed de proveedores (`services/api/seed.py`)
  y `promote_admin.py` también controlan fallos de validación y persistencia.
  las 18 pruebas de `test:auth`, typecheck, lint y build.
  terminal se probaron errores de carga/reintento, backend detenido, login
  incorrecto, registro con email repetido, sesión caducada, analizador con
  archivo no CSV y recuperación de contraseña; errores por campo de registro,
  recepción de correo real de recuperación, análisis del CSV real y creación
  de incidencia; archivo inexistente con salida no cero, CSV real y seed
  idempotente. Esta sesión no ejecutó el navegador ni una entrega real con
  Resend.
  backend de `/records`) sigue mostrando un panel de error legible con
  reintento. No se pudo comprobar si Resend permite fijar un timeout y no se
  añadió. Algunos detalles 409/422 ahora son genéricos. La denegación de
  permisos de archivos se simuló; no se probó el camino exitoso de
  `pandas_clean.py` porque Pandas no está instalado. TinyDB puede dejar una
  escritura parcial si falla a mitad de una importación.

## Hito 5 - Inventario con SQLModel y doble base de datos

- Según lo informado por el desarrollador, las fases 1 a 4 fueron aprobadas y
  commiteadas. La fase 1 añadió la conexión SQLModel opcional sin reemplazar
  TinyDB; la fase 2 separó modelos ORM y schemas; la fase 3 añadió rutas
  autenticadas y reglas de stock; la fase 4 añadió la semilla transaccional e
  idempotente.
- El desarrollador ejecutó manualmente desde la raíz
  `uv run python -m services.api.seed_inventory` contra Supabase y confirmó
  que funciona. Esta sesión no realizó esa conexión.
- Las pruebas locales usan SQLite en memoria y TinyDB temporal. La última suite
  completa de backend registrada pasó 113 pruebas. La semilla crea 6
  ingredientes, 7 entradas y 3 salidas; el segundo intento no duplica datos y
  el endpoint de productos devuelve los stocks netos esperados.
- No se ha comprobado concurrencia real ni el bloqueo `with_for_update()` en
  PostgreSQL desde esta sesión; SQLite no aplica ese bloqueo. Tampoco se
  hicieron mediciones de rendimiento o carga.
- `create_all()` no es un sistema de migraciones. El stock usa `float` con
  redondeo a tres decimales. `user_uuid` es el ID entero de TinyDB convertido a
  texto y TinyDB puede reutilizar IDs de usuarios eliminados. Sin
  `DATABASE_URL`, los endpoints de inventario responden `503`.
- La fase 5 documentó la configuración, uso y limitaciones del inventario.
  La suite completa de esta fase pasó 113 pruebas; `git diff --check` pasó,
  `services/api/.env` está ignorado por Git y la búsqueda de URI PostgreSQL con
  credenciales en archivos rastreados encontró únicamente el ejemplo
  ficticio de `services/api/README.md`.

## Hito 5 - Backoffice de inventario

- Implementadas las vistas de productos (`/inventory/products`), registro de
  entrada (`/inventory/orders/inbound`), registro de salida
  (`/inventory/orders/outbound`) e historial de órdenes (`/inventory/orders`).
  `/inventory` redirige a la vista de productos.
- La lista de productos indica nivel según unidad: `kg`/`litro`, bajo < 20 y
  medio < 50; `unidad`, bajo < 50 y medio < 150. La salida advierte sobre
  stock insuficiente sin bloquear el envío; la API aplica la regla definitiva.
- Las cuatro vistas pasaron lint, typecheck y build; `test:auth` pasó sus 18
  pruebas. El build se validó en una copia temporal que excluyó `.env*`.
- El desarrollador realizó manualmente la comprobación visual del inventario
  contra la API real.

## Ticket #infra-40 - Fase 5: documentación y puertos publicados

- Fases 1 a 4 completadas, según las validaciones anteriores del ticket.
- En el VPS se verificó la construcción de imágenes, la API en estado
  `healthy`, el arranque de `uis` y la comunicación `uis` → `api` por nombre de
  servicio: `wget http://api:8000/openapi.json` devolvió el JSON esperado.
- Los logs del VPS no mostraron errores de inicialización de Supabase.
- La configuración Compose local confirma website `3000→5174`, backoffice
  `3001→3000` y API `8000→8000`. El 2026-11-12 se reverificaron en el VPS los
  puertos `3000`, `3001` y `8000`; se validaron el arranque limpio con
  `.env.example` y el inicio de sesión desde un navegador externo. La fase 5
  queda validada. Queda pendiente abrir o reenviar el PR.

## Ticket #infra-40 - Orígenes de desarrollo del backoffice

- `uis/backoffice/next.config.ts` lee `NEXT_ALLOWED_DEV_ORIGINS` como hosts
  separados por comas, recorta espacios y descarta entradas vacías. La opción
  `allowedDevOrigins` se omite si no quedan hosts configurados.
- La documentación oficial de Next.js describe hosts sin esquema ni puerto,
  permite comodines (`*` para una etiqueta y `**` al inicio para varias) y
  compara el hostname de `Origin`/`Referer`. No menciona IP de forma expresa;
  una IP literal usa ese formato de hostname. El manifiesto del backoffice
  declara Next.js 16.3.0. No se pudo inspeccionar el paquete instalado debido
  a una restricción de acceso.
- La tabla de `infra/DEPLOY.md` documenta `NEXT_ALLOWED_DEV_ORIGINS` con el
  ejemplo `203.0.113.10`.
- Validado en el contenedor `uis`: `npm run typecheck` pasó sin errores y `next dev` arrancó con `NEXT_ALLOWED_DEV_ORIGINS` definida, cargando `next.config.ts` sin errores; el backoffice respondió 200.
- Validado en el VPS el 2026-11-12: con la variable definida con la IP del servidor, el navegador carga `/_next/*` sin errores 403 y el inicio de sesión funciona.
