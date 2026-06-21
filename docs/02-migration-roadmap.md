# FörderFlow — Migration Roadmap (Monolith → Separated Full-Stack)

> Target layout (from the brief):
> `new-structured-foerderflow/{foerderflow-frontend, foerderflow-backend, docker-compose.yml, .env.example, Makefile, README.md, docs/}`
> Backend: FastAPI + SQLAlchemy 2 + Alembic + Pydantic v2 + Postgres.
> Frontend: Next.js + TS + Tailwind + TanStack Query + Axios + RHF + Zod.

## 0. Reality check on "100% parity in one pass"

The monolith is **46 models, ~160 API operations, 45 pages, 55 domain-logic files (~7,900 LOC), plus Word/Excel report generation, multi-format importers (CSV/CAMT/DATEV/Lohnjournal) and Mistral OCR**. Reproducing every calculation byte-for-byte in a *different language* (TS→Python) and re-architecting SSR→REST is a large, multi-phase program. This roadmap sequences it so each phase is independently verifiable against the monolith. It is built to be executed iteratively (many sessions), not as a single generation.

## 1. Two decisions that block faithful work (need your call)

1. **Auth model.** Monolith = passwordless **magic-link + database sessions** (NextAuth v5). Brief asks FastAPI **JWT + bcrypt/passlib**. These are incompatible models. Options:
   - (A) Keep magic-link semantics, issue **JWT after email verification** (closest to parity; no passwords — matches GDPR rationale in PLANNING.md).
   - (B) Introduce password login + JWT (changes the auth UX — violates "do not change authentication").
   - (C) JWT + keep server-side session table for revocation (hybrid).
   *Recommendation: A.*
2. **Frontend data-fetching architecture.** Monolith Server Components query Prisma directly. With a separate API:
   - (A) Keep Next.js SSR but have Server Components/route handlers call the FastAPI REST API (BFF-style), preserving SSR + SEO + the current page flow most faithfully.
   - (B) Client-first: thin Next.js shell, all data via TanStack Query in Client Components (matches "TanStack Query/Axios" emphasis, but changes loading/SSR behavior).
   *Recommendation: A for parity, with TanStack Query for client-side mutations/lists.*

## 2. Phase plan

### Phase 0 — Scaffolding & infra (foundation)
- Create `foerderflow-backend/` (FastAPI clean-architecture skeleton: `app/{api,core,models,schemas,repositories,services,use_cases,dependencies,middleware,permissions,utils,seeds,tests}`), `foerderflow-frontend/` (Next.js feature-based skeleton).
- Root `docker-compose.yml` (postgres + backend + frontend + healthchecks), `.env.example`, `Makefile`, `README.md`.
- CI scaffolding, linting, formatting (ruff/black/mypy; eslint/prettier).
- **Verify:** containers boot, `/health` green, empty OpenAPI served.

### Phase 1 — Data layer (the spine)
- Port all **46 models + 24 enums** from `schema.prisma` → SQLAlchemy 2 models, **preserving** `@@map` table/column names, relations, unique constraints, indexes, and snake_case so the DB is byte-compatible.
- Generate the **initial Alembic migration**; validate it produces a schema diff-equal to the Prisma-managed DB.
- Pydantic v2 schemas (request/response) per entity.
- Port seed system (`scripts/seed-*.ts`) → `app/seeds/` (demo, pilot orgs from PLANNING.md: Treffpunkt, Famev, FTZ).
- **Verify:** migrate + seed into a fresh Postgres; row counts and key records match a monolith seed run.

### Phase 2 — Auth, tenancy, RBAC (per decision §1.1)
- Implement chosen auth, `requireOrgSession`/`requireSuperAdmin` equivalents as FastAPI dependencies, org-scoping middleware, role enforcement, rate limiting, open-redirect protections.
- `/me`, org-switch, invites, setup/organisation.
- **Verify:** auth/permission integration tests mirror monolith redirects/403 semantics.

### Phase 3 — Domain services & endpoints (the bulk; sub-phased by context)
Port `lib/**` logic into `services/` + `use_cases/`, expose via routers. Order by dependency:
1. Master data: Kostenstellen, Kostenbereiche, Funder, Haushaltsjahre, Bank accounts, Opening balances, CSV profiles.
2. Funding measures + rules + Finanzplan + Kostenstellen-Zuordnung + Bescheid import (OCR).
3. Allocation: Verteilungsschlüssel (+ versioning), Umlage-Pools, allocation resolver, position-wahl.
4. Transactions & banking: import pipeline (CSV/CAMT/DATEV), splits, fund-allocation, belege, batch ops, confirm, digest.
5. Booking-rule engine: match/confidence/backfill/preview/suggest + application audit.
6. Mittelabruf, Fristen, compliance (Fehlbedarf ANBest-P §2.2).
7. Verwendungsnachweis + Stundennachweis + Excel/Word generation, einreichen.
8. Payroll: employees, contracts, components, TVöD tarif, gross factors, monthly payroll + allocations, import, Lohnbüro export, VZÄ, soll-ist.
9. Ampel, prognose, fund-allocation summary, dashboard digest.
- **Verify per sub-phase:** golden-file tests comparing endpoint output to monolith for the same seeded inputs; the 21 existing Jest tests get Python equivalents.

### Phase 4 — Frontend
- Port design system (BRAND.md tokens → tailwind config + globals), `components/ui` (15), forms (21), dashboard/admin components.
- Reproduce all **45 pages** + navigation (`SidebarNav` grouping, AdminSidebar) with identical labels/German terms.
- API client layer (Axios + typed services from OpenAPI), TanStack Query hooks, RHF+Zod forms, error boundaries, loading/empty states.
- **Verify:** page-by-page visual/functional comparison against monolith; E2E plan covering core workflows.

### Phase 5 — Hardening & parity sign-off
- Full test suites (backend unit/integration/API; frontend component/integration + E2E).
- Parity checklist against the brief's Success Criteria (every page/form/report/allocation/permission).
- Production docker profile, deployment + env + CI/CD docs.

## 3. Highest-risk parity areas (extra scrutiny)
- **Report generators** (Excel/Word) — output structure must match exactly (python-docx/openpyxl vs docxtemplater/exceljs).
- **Money math** — TS `decimal.js`/Prisma Decimal → Python `Decimal`; rounding modes and the 100%-rule must match to the cent.
- **Importers** — CSV profile heuristics, CAMT.053, DATEV, Lohnjournal parsing edge cases.
- **Booking-rule confidence learning** — ORANGE/GELB/GRÜN thresholds + match_count side effects.
- **Date/Decimal JSON serialization** — pin the contract so the frontend parses identically (PLANNING.md notes Prisma serializes Decimal→string).
- **Auth semantics** — exact redirect targets and silent-redirect behavior for super-admin.

## 4. Working agreement / verification discipline
- Monolith is the **single source of truth**; when behavior is ambiguous, read the TS source, don't invent.
- Each phase ends with a concrete verification step + a parity note in `docs/`.
- No business logic, labels, field names, or workflows change (per brief's DO-NOT list).

## 5. Status
- [x] Analysis phase (docs 01–03 produced and verified against source).
- [ ] Decisions §1.1 & §1.2 confirmed by stakeholder.
- [ ] Phase 0 scaffolding.
- [ ] Phases 1–5.
