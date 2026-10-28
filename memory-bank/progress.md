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