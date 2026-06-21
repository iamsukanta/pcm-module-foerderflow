# Phase 5 — Hardening & Parity Sign-off

Status of the monolith (`foerderflow/`) → decoupled (`foerderflow-backend/` +
`foerderflow-frontend/`) migration. Goal: 100 % functional parity.

## Verification status (green)

| Check | Command | Result |
|---|---|---|
| Backend unit/integration | `cd foerderflow-backend && pytest -q` | **179 passed** |
| Backend boots + OpenAPI | `python -c "from app.main import app; app.openapi()"` | **~102 paths** |
| Frontend types | `cd foerderflow-frontend && npx tsc --noEmit` | **clean** |
| Frontend production build | `npx next build` | **green, 52 routes** |
| Frontend unit (vitest) | `npx vitest run` | **13 passed** |

## Architecture (decoupled)

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + PostgreSQL. Table
  names preserve the Prisma `@@map` schema (same DB shape as the monolith).
- **Auth:** passwordless magic-link → JWT in an httpOnly `ff_token` cookie
  (replaces NextAuth). Active org via `selected_org_id` cookie → `X-Org-Id` header.
- **Frontend:** Next.js 15 (App Router). Server Components read via a BFF
  `serverFetch` helper; client components call the backend through catch-all
  proxies `/api/protected/[...path]` and `/api/admin/[...path]` that inject the
  Bearer token + `X-Org-Id`. This let the bulk of monolith client components be
  ported verbatim.

## Pages ported (all build-green)

Auth/shell: landing, login (+verify/error), org-select, dashboard layout +
sidebar, admin layout + sidebar.
Dashboard modules: **dashboard cockpit**, kostenstellen, haushaltsjahre, konten,
profil, fristen, umlage-source-scopes, verteilungsschluessel, buchungsregeln,
mittelabrufe, verwendungsnachweise/[id], personal (6 pages), foerdermassnahmen
(list/new/[id]/edit/import-bescheid), transaktionen (list/[id]/import), review.
Admin: overview, organisations (list/[id]/neu), users.

## Backend endpoints added for the BFF (beyond the monolith API surface)

These are faithful equivalents of monolith server-side helpers that the BFF needs
as HTTP endpoints (the monolith called Prisma directly inside Server Components):

- `GET /protected/fristen/kritische-count` — sidebar badge count.
- `GET /protected/foerdermassnahmen/{id}/compliance-status` — full
  `FehlbedarfStatusResult` for the detail banner + cross-financing widget.
- `GET /protected/foerdermassnahmen/{id}/bescheid/meta` — Bescheid metadata
  (no bytes) for the Bescheid tab.
- `GET /protected/dashboard/cockpit` — landing-page aggregation (KPIs, top
  measures, deadline lists, onboarding counts, Fehlbedarf widget items).
- Foerdermassnahme **list** serializer now includes `betrag_ist` (batch sum) for
  the list-page Ampel; admin **list_users** now includes `memberships[]`.

## Known parity deviations (minor, intentional)

1. **Verwendungsnachweis detail** — the "eingereicht von <email>" line is omitted
   (the backend get endpoint doesn't return the submitting user's email). Date +
   snapshot render identically.
2. **Compliance banner dismissal** — SSR starts undismissed each load; dismissal
   is recorded via the existing `/compliance/dismiss` endpoint but the
   "already dismissed?" pre-check (monolith queried the audit log) is not re-run
   server-side.
3. **import-bescheid OCR** requires `MISTRAL_API_KEY`; empty key → graceful
   `EXTRACTION_FAILED` (502), matching the monolith's behavior without a key.

## Live end-to-end smoke — PASSED

`docker compose up --build` brought up all 4 services (db, mailpit, backend,
frontend) healthy. Backend entrypoint ran `alembic upgrade head` (0001_initial)
and seeded the demo org. Verified against the running stack:

- **Auth chain:** `POST /auth/magic-link` → dev-logged token → `POST /auth/verify`
  → JWT → `GET /protected/me` (memberships, super-admin flag). ✓
- **BFF:** `/api/auth/callback` exchanges the token, sets the httpOnly `ff_token`
  cookie, and 307-redirects to `/org-select` (host-relative). `/api/org/select`
  sets `selected_org_id`. ✓
- **Pages render (200) with the cookie jar:** dashboard cockpit (greeting + KPIs +
  getting-started), all 13 dashboard modules, `/admin` + organisations + users.
  Detail routes (`kostenstellen/[id]`) render. ✓
- **Write path through the catch-all proxy:** `POST /api/protected/kostenstellen`
  → 201 with the German success message; `DELETE` → 200. ✓
- **Encoding:** Postgres stores correct UTF-8 (org name `Zukunft für Kinder`,
  hex `…66c3bc72…`). ✓
- **No runtime errors** in the frontend container logs.

### Issues found & fixed during the live smoke

1. `FinanzplanTab.tsx` used a raw `<a>` for an internal route → replaced with
   `next/link` (`@next/next/no-html-link-for-pages` — a clean-build lint error the
   local stale `.next` cache had masked).
2. BFF redirects used `req.nextUrl.origin`, which inside the container resolved to
   `http://0.0.0.0:3000` (unfollowable by a browser). Added `requestOrigin(req)`
   (derives from the forwarded Host header); applied to the callback + signout
   redirects.

### To run

```bash
cp .env.example .env   # set AUTH_SECRET (openssl rand -hex 32); MISTRAL_API_KEY optional
docker compose up --build          # RUN_SEED=1 in .env seeds demo data
# frontend → http://localhost:3000 · backend → http://localhost:8000/docs · mail → http://localhost:8025
```
