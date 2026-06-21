# FörderFlow — Complete API Endpoint Inventory

> Extracted directly from `foerderflow/app/api/**/route.ts` (96 route files).
> Each row = one Next.js route handler and the HTTP methods it exports.
> This is the contract the FastAPI backend must reproduce 1:1 (paths, methods,
> request/response shapes, validation, and authorization). `[param]` = path param.

## Public / auth (not under `/api/protected`)

| Methods | Path | Notes |
|---------|------|-------|
| (NextAuth) | `/api/auth/[...nextauth]` | Magic-link sign-in/callback (Auth.js) |
| GET | `/api/auth/signout` | Sign out |
| POST | `/api/setup/organisation` | First-run org setup |

## Super-Admin (`/api/admin/*`, gated by `requireSuperAdmin`)

| Methods | Path |
|---------|------|
| GET, POST | `/api/admin/organisations` |
| GET, PUT, DELETE | `/api/admin/organisations/[id]` |
| POST | `/api/admin/organisations/[id]/members` |
| PUT, DELETE | `/api/admin/organisations/[id]/members/[user_id]` |
| POST | `/api/admin/organisations/[id]/invite` |
| DELETE | `/api/admin/organisations/[id]/invites/[invite_id]` |
| GET | `/api/admin/users` |
| GET, PUT | `/api/admin/users/[id]` |

## Identity / org context (`/api/protected/*`)

| Methods | Path |
|---------|------|
| GET, PUT | `/api/protected/me` |
| GET, POST | `/api/protected/org/invite` |
| DELETE | `/api/protected/org/invite/[id]` |

## Master data

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/kostenstellen` |
| GET, PATCH, DELETE | `/api/protected/kostenstellen/[id]` |
| GET | `/api/protected/kostenbereiche` |
| GET, POST | `/api/protected/funder` |
| GET, PATCH, DELETE | `/api/protected/funder/[id]` |
| GET, POST | `/api/protected/haushaltsjahre` |
| GET, PATCH | `/api/protected/haushaltsjahre/[id]` |
| POST | `/api/protected/haushaltsjahre/[id]/close` |
| GET, POST | `/api/protected/bank-accounts` |
| PATCH, DELETE | `/api/protected/bank-accounts/[id]` |
| GET, POST | `/api/protected/opening-balances` |
| GET, POST | `/api/protected/csv-profiles` |

## Funding measures (Fördermassnahmen)

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/foerdermassnahmen` |
| GET, PATCH, DELETE | `/api/protected/foerdermassnahmen/[id]` |
| POST | `/api/protected/foerdermassnahmen/import-bescheid` |
| GET, POST, DELETE | `/api/protected/foerdermassnahmen/[id]/bescheid` |
| GET | `/api/protected/foerdermassnahmen/[id]/ampel` |
| GET | `/api/protected/foerdermassnahmen/[id]/fehlbedarf-status` |
| GET, POST, DELETE | `/api/protected/foerdermassnahmen/[id]/finanzplan` |
| POST | `/api/protected/foerdermassnahmen/[id]/finanzplan/personalmodul` |
| GET | `/api/protected/foerdermassnahmen/[id]/finanzplan-positionen` |
| GET | `/api/protected/foerdermassnahmen/[id]/finanzplan-positionen/[pos_id]/umlage-preview` |
| POST, DELETE | `/api/protected/foerdermassnahmen/[id]/kostenstellen` |
| GET | `/api/protected/foerdermassnahmen/[id]/preflight` |
| GET | `/api/protected/foerdermassnahmen/[id]/prognose` |
| GET, POST | `/api/protected/foerdermassnahmen/[id]/regeln` |
| DELETE | `/api/protected/foerdermassnahmen/[id]/regeln/[ruleId]` |
| GET | `/api/protected/foerdermassnahmen/[id]/soll-ist-position` |
| GET | `/api/protected/foerdermassnahmen/[id]/stundennachweis` |
| GET, POST | `/api/protected/foerdermassnahmen/[id]/verwendungsnachweis` |
| GET | `/api/protected/foerdermassnahmen/[id]/verwendungsnachweis/preview` |

## Finanzplan positions

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/finanzplan-positionen` |
| GET, PATCH, DELETE | `/api/protected/finanzplan-positionen/[id]` |
| GET | `/api/protected/finanzplan-positionen/[id]/deckungsfaehigkeit` |

## Allocation / distribution

| Methods | Path |
|---------|------|
| GET | `/api/protected/allocations/position-wahl-ausstehend` |
| GET, POST | `/api/protected/verteilungsschluessel` |
| GET, PATCH, DELETE | `/api/protected/verteilungsschluessel/[id]` |
| POST | `/api/protected/verteilungsschluessel/[id]/neue-version` |
| GET, POST | `/api/protected/umlage-source-scopes` |
| GET, PATCH, DELETE | `/api/protected/umlage-source-scopes/[id]` |
| GET | `/api/protected/fund-allocations/summary` |

## Booking-rule engine

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/buchungsregeln` |
| PUT, PATCH, DELETE | `/api/protected/buchungsregeln/[id]` |
| GET, POST | `/api/protected/buchungsregeln/[id]/backfill` |
| POST | `/api/protected/buchungsregeln/preview` |
| POST | `/api/protected/buchungsregeln/suggest` |

## Transactions & banking

| Methods | Path |
|---------|------|
| GET | `/api/protected/transaktionen` |
| GET, PATCH | `/api/protected/transaktionen/[id]` |
| PATCH | `/api/protected/transaktionen/[id]/confirm` |
| PUT | `/api/protected/transaktionen/[id]/splits` |
| POST | `/api/protected/transaktionen/[id]/massnahme` |
| GET, POST, PATCH, DELETE | `/api/protected/transaktionen/[id]/fund-allocation` |
| GET, POST | `/api/protected/transaktionen/[id]/belege` |
| GET, DELETE | `/api/protected/transaktionen/[id]/belege/[belegId]` |
| POST, PUT | `/api/protected/transaktionen/import` |
| POST | `/api/protected/transaktionen/batch-confirm` |
| POST | `/api/protected/transaktionen/batch-massnahme` |
| POST | `/api/protected/transaktionen/batch-regeln` |
| GET | `/api/protected/transaktionen/digest` |

## Calls for funds & deadlines (Mittelabruf / Fristen)

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/mittelabrufe` |
| GET, PATCH | `/api/protected/mittelabrufe/[id]` |
| PATCH | `/api/protected/mittelabrufe/[id]/frist` |
| GET | `/api/protected/mittelabrufe/kalender` |
| GET | `/api/protected/fristen` |

## Verwendungsnachweise (proof of use)

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/verwendungsnachweise` |
| GET, PATCH, DELETE | `/api/protected/verwendungsnachweise/[id]` |
| POST | `/api/protected/verwendungsnachweise/[id]/einreichen` |

## Compliance

| Methods | Path |
|---------|------|
| POST | `/api/protected/compliance/dismiss` |

## Payroll / HR

| Methods | Path |
|---------|------|
| GET, POST | `/api/protected/employees` |
| GET, PATCH | `/api/protected/employees/[id]` |
| GET, POST | `/api/protected/employees/[id]/contracts` |
| GET, POST, PATCH | `/api/protected/employees/[id]/contracts/[contractId]/components` |
| GET, POST | `/api/protected/employer-gross-factors` |
| GET, POST | `/api/protected/payroll` |
| GET, PATCH, DELETE | `/api/protected/payroll/[id]` |
| GET, POST | `/api/protected/payroll/[id]/allocations` |
| POST | `/api/protected/payroll/import` |
| GET | `/api/protected/payroll/lohnbuero-export` |
| GET | `/api/protected/payroll/monat-uebersicht` |
| GET | `/api/protected/personal/soll-ist` |
| GET | `/api/protected/personal/vzae-uebersicht` |
| GET | `/api/protected/tarif` |

---

**Total: 96 route files.** Several expose 3–4 methods, so the FastAPI surface will be ~150–170 individual operations. Each must preserve: exact path, method, query/body validation (currently Zod), authorization (`requireOrgSession` / role / `requireSuperAdmin`), org-scoping, response shape, and error semantics.
