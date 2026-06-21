# FörderFlow — Current Architecture Analysis (Single Source of Truth)

> Produced during the analysis phase of the monolith → separated full-stack migration.
> All figures below were verified directly against the `foerderflow/` source tree.

## 1. Scope at a glance (verified counts)

| Dimension | Count | Notes |
|-----------|-------|-------|
| Prisma models | **46** | `foerderflow/prisma/schema.prisma` (1740 lines) |
| Prisma enums | **24** | German domain enums (Rechtsform, OrgRole, FunderTyp, …) |
| API route files (`route.ts`) | **96** | `app/api/**` — App Router route handlers |
| App pages (`page.tsx`) | **45** | `app/**` |
| React components | **46** | `components/ui` (15), `components/forms` (21), `components/dashboard` (5), `components/admin` (5) |
| Business-logic lib files | **55** | `lib/**` — ~7,900 LOC of pure domain logic |
| Seed scripts | **10+** | `scripts/seed-*.ts` + recipes/lib |
| Test files | **21** | Jest (`__tests__/`) — calc, VZÄ, parsers |

This is a large, domain-dense application (German non-profit funding/grant management). A faithful, 100%-parity rewrite into FastAPI + a fresh Next.js frontend is a **multi-phase effort**, not a single pass. The roadmap (doc 02) phases it.

## 2. Tech stack (current)

```
Frontend:  Next.js 15.3.9 (App Router, React 19) + TypeScript + Tailwind 3.4
Backend:   Next.js API Routes (same process)
DB:        PostgreSQL (Docker, port 5432)
ORM:       Prisma 5.22 (snake_case via @@map)
Auth:      NextAuth v5 (Auth.js) magic-link + custom Prisma adapter, DB sessions
Reports:   docxtemplater + pizzip (Word), exceljs (Excel), jszip
OCR:       Mistral OCR for Bescheid import (lib/bescheid)
Money:     decimal.js + Prisma Decimal
Email:     nodemailer (magic link)
Icons:     lucide-react only (no emojis)
```

## 3. Authentication & authorization (critical)

- **Mechanism:** NextAuth v5 **magic link (passwordless email)**, session strategy = **`database`** (sessions stored in `Session` table). Custom adapter in `lib/auth-adapter.ts` (PrismaAdapter was incompatible with snake_case).
- **Middleware** (`middleware.ts`): Edge-runtime, **no Prisma**. Does cookie presence check, in-memory rate limiting (5 magic-link requests / IP / hour), open-redirect protection on `callbackUrl`. Protects `/dashboard/*` and `/api/protected/*`.
- **Server-side gate** (`lib/session.ts`):
  - `requireOrgSession({ orgId?, requireRole? })` — resolves active org membership from `selected_org_id` cookie (fallback: first membership), enforces `OrgRole` if `requireRole` set. Redirects: no session → `/login`, no memberships → `/org-select`, wrong role → `/dashboard?error=INSUFFICIENT_ROLE`.
  - `requireSuperAdmin()` — checks `User.is_super_admin` (distinct from org `ADMIN` role); silently redirects non-admins to `/dashboard` (no 403, to avoid leaking `/admin` existence).
- **Multi-tenancy:** every domain table carries `org_id`; every query is filtered by the session's org (row-level isolation enforced at query level, not just UI).
- **Roles:** `OrgRole` enum (org-scoped) + `User.is_super_admin` boolean (cross-org platform admin).

> ⚠️ **Migration conflict to resolve (see doc 02 / decision):** the target spec asks for **JWT + bcrypt/passlib**. The current system is **passwordless magic-link with DB sessions**. These are fundamentally different auth models. "100% parity" and "JWT/bcrypt" cannot both hold literally — a decision is required.

## 4. Domain model (entity groups)

From `prisma/schema.prisma` (46 models). Grouped by bounded context:

- **Identity & tenancy:** Organization, User, Account, Session, VerificationToken, OrganizationMembership, OrgInvite
- **Org master data:** CostCenter (Kostenstelle), Funder (Fördergeber), FunderNachweisFrist, FiscalYear (Haushaltsjahr), Kostenbereich (SKR42)
- **Funding measures:** FundingMeasure (Fördermassnahme), BescheidDokument, FundingRule, FundingMeasureCostCenter, BudgetPosition*, HaushaltsPlanPosten
- **Allocation / distribution:** AllocationKey + AllocationKeyPosition (Verteilungsschlüssel), UmlageSourceScope + UmlageSourceScopeCostCenter (Umlage-Pools)
- **Banking & transactions:** ImportBatch, Transaction, TransactionSplit, FundAllocation, TransactionBeleg, BankAccount, OpeningBalance, CsvImportProfile
- **Booking-rule engine:** BookingRule, BookingRuleSplit, BookingRuleApplication (audit trail + confidence learning)
- **Calls for funds / reporting:** Mittelabruf, NachweisTemplate, VerwNachweis, FinanzplanPosition, FinanzplanPositionKostenbereich
- **Payroll / HR:** Employee, EmployeeContract, SalaryComponent, EmployerGrossFactor, TarifTabelle (TVöD), MonthlyPayroll, PayrollComponent, PayrollAllocation
- **Cross-cutting:** AuditLog

## 5. Business-logic hot spots (must be ported byte-faithfully)

Largest / most calculation-heavy files in `lib/` (LOC):

| File | LOC | Responsibility |
|------|-----|----------------|
| `lib/nachweis/excel-generator.ts` | 485 | Verwendungsnachweis Excel export |
| `lib/fehlbedarf-compliance.ts` | 477 | ANBest-P §2.2 Fehlbedarf compliance |
| `lib/foerderfahigkeit.ts` | 431 | Förderfähigkeit (eligibility) validation at point of entry |
| `lib/import/transaction-import.ts` | 376 | Transaction import pipeline |
| `lib/nachweis/stundennachweis-generator.ts` | 354 | Stundennachweis (timesheet) generation |
| `lib/booking-rules.ts` | 350 | Booking-rule match engine + confidence (ORANGE/GELB/GRÜN) |
| `lib/finanzplan-ist.ts` | 266 | Finanzplan actuals roll-up |
| `lib/import/extraction-prompt.ts`, `lib/bescheid/*` | — | Mistral OCR Bescheid extraction |
| `lib/fristen.ts` | 220 | Deadline computation (Verwendungsfrist 42d, warn 14d, crit 7d) |

Key invariants (from PLANNING.md, to preserve exactly):
- **100%-rule:** cost-center allocations and transaction splits must sum to exactly 100% (server-validated).
- **No double funding:** same cost not assigned to two funders (checked at every FundAllocation).
- **Förderfähigkeit at point of entry**, not retroactive.
- **Belegprinzip:** no booking without a receipt (upload or accounting reference).
- **Soft-delete everywhere** (`deleted_at` / status), except BookingRule (hard-delete allowed).
- **Confidence learning:** each manual confirmation raises `match_count`; ORANGE (0–1) → GELB (2–4) → GRÜN (5+).
- **Decimal handling:** Prisma `Decimal` → serialize before crossing to client.

## 6. Reporting / import-export surface (Python re-implementation required)

- **Exports:** Verwendungsnachweis (Word via docxtemplater, Excel via exceljs), Stundennachweis, Lohnbüro export, scenario/reporting exports.
- **Imports:** universal CSV importer with profile system, CAMT.053, DATEV, Kostenstellen CSV, Lohnjournal, Bescheid (Mistral OCR).
- These rely on JS libs (docxtemplater/exceljs/jszip) → must map to Python equivalents (python-docx/openpyxl) with **identical output structure** (this is the highest-risk parity area).

## 7. Navigation / UX structure (frontend parity reference)

Sidebar (`components/dashboard/SidebarNav.tsx`) is grouped:
- **Täglich:** Übersicht, Transaktionen, Review-Inbox, Fristen (critical-deadline badge)
- **Monatlich:** Gehaltserfassung, Mittelabrufe, Buchungsregeln
- **Verwaltung (collapsible):** Fördermassnahmen, Kostenstellen, Bank- & Kassenkonten, Verteilungsschlüssel, Umlage-Pools, Haushaltsjahre, Personal
- **Footer:** Mein Profil, VoluLink Super-Admin (only if `is_super_admin`)
- Separate **Admin** area (`/admin/*`) with its own `AdminSidebar`.

Design system is fully tokenized (`lib/design-tokens.ts` → `tailwind.config.ts` → `globals.css`); strict `soft-*` palette, IBM Plex Sans/Mono, no default Tailwind colors, no hex. BRAND.md is the design source of truth.

## 8. Architectural implications of frontend/backend separation

The current frontend is **SSR-first**: Server Components read Prisma **directly** (e.g., pages call `requireOrgSession()` then query `db`). Splitting into REST means:
- Every server-side data read must become a REST call (server-side fetch with forwarded auth) or move to client-side TanStack Query.
- Auth context (org membership, super-admin) currently resolved server-side from cookies must be re-expressed as an API contract (`/me`, org-switch endpoint already exists at `app/api/protected/me`).
- Decimal/Date serialization contract must be pinned in OpenAPI so the new frontend parses identically.

See `docs/02-migration-roadmap.md` for the phased plan and `docs/03-endpoint-inventory.md` for the endpoint map.
