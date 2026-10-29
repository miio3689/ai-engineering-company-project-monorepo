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