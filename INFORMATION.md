# Claude Code Rules — structured-foerderflow

## Architecture

Two services, zero shared code:

- `foerderflow-backend/` — Python 3.12, FastAPI, async SQLAlchemy 2.0, Alembic, Pydantic v2
- `foerderflow-frontend/` — Next.js 15, TypeScript, TanStack Query, Zustand, openapi-fetch

The **only** contract between them is the REST API. Never import Python from JS or vice versa.

### Docker stack

| Service | Image / Build | Dev port | Notes |
|---------|---------------|----------|-------|
| `db` | postgres:16-alpine | 5432 | Credentials from `.env.local` |
| `mailpit` | axllent/mailpit | 8025 | All dev emails land here |
| `backend` | `./foerderflow-backend/Dockerfile` | 8000 | Hot-reload via override |
| `frontend` | `./foerderflow-frontend/Dockerfile` | 3001 | Hot-reload via override (`npm run dev`) |
| `nginx` | nginx:1.27-alpine | 80 | `/api/*` → backend:8000, `/*` → frontend |

`docker-compose.override.yml` activates automatically in dev — mounts source as volumes for hot-reload and exposes backend on 8000, frontend on 3001.

`next.config.ts` rewrites `/api/:path*` → `http://backend:8000/api/:path*` (client-side calls). Server Components use `serverFetch()` from `lib/server-fetch.ts` which hits `BACKEND_URL` directly.

### .env.local (never commit)

```
DATABASE_URL=postgresql+asyncpg://foerderflow:foerderflow@db:5432/foerderflow
POSTGRES_USER=foerderflow
POSTGRES_PASSWORD=foerderflow
POSTGRES_DB=foerderflow
SECRET_KEY=<random>
BACKEND_URL=http://backend:8000
EMAIL_HOST=mailpit
EMAIL_PORT=1025
DEMO_USER_EMAIL=anikpalace37@gmail.com
DEMO_ORG_NAME=Zukunft für Kinder
ENVIRONMENT=development
```

---

## Make targets

```
make up              # start dev stack (foreground, hot-reload)
make up-d            # start dev stack (detached)
make down            # stop stack
make logs            # tail all container logs
make build           # rebuild images

make migrate         # alembic upgrade head
make migrate-down    # alembic downgrade -1
make makemigration   # alembic revision --autogenerate (prompts for message)

make seed            # seed system data: Kostenbereiche (33) + TVöD 2025 (84) — idempotent
make seed-demo       # seed demo org (reads DEMO_USER_EMAIL from .env.local — user must exist first)
make seed-reset      # wipe org data + reseed demo org
make seed-pilot-fam  # seed pilot org "Freunde alter Menschen e.V." (reads PILOT_USER_EMAIL)
make seed-pilot-fam-reset  # wipe pilot org data + reseed

make test            # pytest with coverage (gate: 80%)
make test-fast       # pytest -x -q (no coverage)
make lint            # ruff + mypy
make fe-lint         # ESLint
make fe-tsc          # tsc --noEmit
make check           # full CI gate: lint + test + fe-lint + fe-tsc

make types           # regenerate foerderflow-frontend/types/api.d.ts from /api/openapi.json
```

### Fresh-start sequence

```bash
make build           # build images
make up-d            # start stack
make migrate         # create all DB tables
make seed            # seed Kostenbereiche + TVöD (no user needed)
# → login via magic link at http://localhost:80 to create your user
# → mailpit at http://localhost:8025 to get the link
make seed-demo       # seed demo org data
```

---

## Backend rules

### IDs
Always use `new_id()` from `app/utils/ids.py` (cuid2). Never use `uuid4()` or auto-increment integers.

### DB sessions
All DB access goes through the `get_db` dependency. Never create engines or sessions outside `app/database.py`. Scripts use `AsyncSessionLocal` from `app.database` directly.

### Multi-tenancy
Every query that touches tenant data **must** filter by `org_id`. Use `require_org_session` to get a validated `OrgSession`. There are no exceptions.

### Role-based access
Use `require_role(*roles)` (dependency factory in `app/dependencies.py`) when an endpoint is restricted to specific `OrgRole` values (`ADMIN`, `FINANCE`, `READONLY`). Chain it after `require_org_session`.

### Fiscal year guard
Before any write to fiscal-year-scoped data, call `_check_fiscal_year_open(fiscal_year_id, db)`. A `GESCHLOSSEN` year is immutable.

### Allocation splits
Whenever positions/splits are created or updated, validate with:
```python
from app.utils.decimal import assert_sums_to_100
assert_sums_to_100(values)  # raises HTTPException 422 if sum ≠ 100 % (± 0.01)
```

### Services layer
Complex business logic lives in `app/services/`, not inline in routers:

| Service | Responsibility |
|---------|---------------|
| `FundingService` | Ampel (traffic light) and Soll-Ist calculations |
| `PayrollService` | Payroll creation with salary-component expansion |
| `ImportService` | Bank-export parsing (Finom CSV, CAMT-053, etc.) |
| `BescheidService` | Funding decision / Bescheid processing |
| `BookingRuleService` | Suggest / backfill / preview booking rules |
| `AllocationService` | M:N fund allocations across transaction splits |
| `NachweisService` | Aggregates VerwNachweis data, generates Excel + ZIP export |

Instantiate with `service = FooService(db)` inside the route handler.

### Alembic migrations — known gotcha
When adding a **new enum type** to an *existing* table via `op.add_column()`, Alembic autogenerate does **not** emit a `CREATE TYPE` statement. You must add it manually before the `add_column`:

```python
sa.Enum('VALUE_A', 'VALUE_B', name='myenum').create(op.get_bind(), checkfirst=True)
op.add_column('my_table', sa.Column('col', sa.Enum(..., name='myenum'), nullable=True))
```

And in `downgrade()`, drop it after removing the column:
```python
sa.Enum(name='myenum').drop(op.get_bind(), checkfirst=True)
```

Migration `dd8089dc4bd1` had this fix applied for `pauschaletyp`.

### Enums
All Python enums live in `app/models/base.py`. **Never inline string literals for status fields.**

| Enum | Members |
|------|---------|
| `OrgRole` | ADMIN, FINANCE, READONLY |
| `Rechtsform` | EV, GGMBH, STIFTUNG, ANDERE |
| `CostCenterTyp` | PROJECT, OVERHEAD |
| `FunderTyp` | STIFTUNG, KOMMUNE, MINISTERIUM, EU, KIRCHE, PRIVAT, ANDERE |
| `FinanzierungsartTyp` | ANTEIL, FEHLBEDARF, FESTBETRAG |
| `EigenanteilTyp` | KOFINANZIERUNG, NICHT_FOERDERFAHIGER_OVERHEAD |
| `FundingMeasureStatus` | AKTIV, ABGESCHLOSSEN, WIDERRUFEN |
| `FundingRuleTyp` | KOSTENKATEGORIE_ERLAUBT, KOSTENKATEGORIE_VERBOTEN, BELEGPFLICHT_SPEZIAL, EIGENANTEIL_MIN, VERWENDUNGSFRIST_TAGE, ZWISCHENNACHWEIS_PFLICHT, PERSONALKOSTEN_HOECHSTSATZ |
| `MittelabrufVerfahren` | ANFORDERUNG, ABRUF, ABSCHLAG |
| `MittelabrufStatus` | ABGERUFEN, VERWENDET, ABGELAUFEN, ZURUECKGEZAHLT |
| `AllocationBasis` | MITARBEITERZAHL, QUADRATMETER, BUDGET_ANTEIL, MANUELL |
| `FiscalYearStatus` | OFFEN, GESCHLOSSEN |
| `FristBezug` | HHJ_ENDE, DURCHFUEHRUNG_ENDE, BEWILLIGUNG_ENDE |
| `TransactionTyp` | AUSGABE, EINNAHME, INTERNE_UMBUCHUNG |
| `TransactionStatus` | IMPORTIERT, KATEGORISIERT, ZUGEORDNET, ABGESCHLOSSEN |
| `ImportFormat` | FINOM_CSV, SPARKASSE_CSV, CAMT_053, DATEV_CSV, MANUELL |
| `VerwendungsnachweisTyp` | ZWISCHENNACHWEIS, VERWENDUNGSNACHWEIS, SACHBERICHT_ONLY |
| `VerwendungsnachweisStatus` | OFFEN, IN_BEARBEITUNG, EINGEREICHT, ANERKANNT, ABGELEHNT |
| `Vertragsart` | FESTANSTELLUNG, MINIJOB, WERKVERTRAG, EHRENAMT |
| `Tarifwerk` | TVOEDD, TVOEL, AVR_CARITAS, AVR_DD, INDIVIDUELL |
| `SalaryComponentTyp` | FESTBEZUG, VWL_AG_ZUSCHUSS, JOBTICKET_SACHBEZUG, SALARY_ADJUSTMENT, SONSTIGES |
| `PauschaleTyp` | FIXER_BETRAG, PROZENT_GESAMT, PROZENT_PERSONAL, UMLAGE_KOSTENSTELLEN |
| `AccountTyp` | BANK, KASSE, ONLINE_WALLET |
| `BescheidQuelle` | OCR_IMPORT, MANUAL_UPLOAD |

### Models (files in `app/models/`)

| File | Key models |
|------|-----------|
| `base.py` | All enums + `TimestampMixin` |
| `auth.py` | `User`, `Account`, `Session`, `VerificationToken` |
| `organisation.py` | `Organization`, `OrganizationMembership`, `OrgInvite` |
| `fiscal_year.py` | `FiscalYear` |
| `funding.py` | `CostCenter`, `Funder`, `FunderNachweisFrist`, `FundingMeasure`, `FundingRule`, `FundingMeasureCostCenter`, `AllocationKey`, `AllocationKeyPosition`, `BudgetPosition`, `NachweisTemplate`, `Mittelabruf`, `VerwNachweis`, `Kostenbereich`, `FinanzplanPosition`, `FinanzplanPositionKostenbereich`, `HaushaltsPlanPosten`, `UmlageSourceScope`, `UmlageSourceScopeCostCenter`, `BescheidDokument` |
| `transaction.py` | `BankAccount`, `OpeningBalance`, `CsvImportProfile`, `ImportBatch`, `Transaction`, `TransactionSplit`, `FundAllocation`, `TransactionBeleg`, `BookingRule`, `BookingRuleSplit`, `BookingRuleApplication` |
| `personnel.py` | `Employee`, `EmployeeContract`, `SalaryComponent`, `EmployerGrossFactor`, `TarifTabelle`, `MonthlyPayroll`, `PayrollComponent`, `PayrollAllocation` |
| `audit.py` | `AuditLog` |

**`Kostenbereich` field note**: Uses `skr49_konto` (single string) — not `skr42_konto_von/bis` like the old Prisma schema.

### Schemas (`app/schemas/`)

```
auth.py  organisation.py  fiscal_year.py  funder.py
funding.py  transaction.py  personnel.py  cost_center.py
kostenbereich.py  verwendungsnachweis.py  common.py
```

- Input: `*Create` / `*Update` — never expose the DB model directly
- Output: `*Response` with `model_config = {"from_attributes": True}`
- Patch endpoints use `Optional` fields only
- Key: `AllocationKeyNeueVersionCreate` (in `funding.py`) — neue-version endpoint

### Routers (22 files → 24 prefixes under `/api/v1/`)

| Router file | Prefix |
|-------------|--------|
| `auth.py` | `/auth` |
| `organisations.py` | `/organisations` |
| `cost_centers.py` | `/organisations/{org_id}/cost-centers` |
| `fiscal_years.py` | `/organisations/{org_id}/fiscal-years` |
| `funders.py` | `/organisations/{org_id}/funders` |
| `funding.py` | `/organisations/{org_id}/funding-measures` |
| `transactions.py` | `/organisations/{org_id}/transactions` |
| `allocation_keys.py` | `/organisations/{org_id}/allocation-keys` |
| `mittelabrufe.py` | `/organisations/{org_id}/mittelabrufe` |
| `payroll.py` | `/organisations/{org_id}/payroll` |
| `personnel.py` | `/organisations/{org_id}/employees` |
| `personnel.py` → `vzae_router` | `/organisations/{org_id}/personal` (VZÄ) |
| `employer_gross_factors.py` | `/organisations/{org_id}/employer-gross-factors` |
| `verwendungsnachweise.py` | `/organisations/{org_id}/verwendungsnachweise` |
| `booking_rules.py` | `/organisations/{org_id}/booking-rules` |
| `kostenbereiche.py` | `/organisations/{org_id}/kostenbereiche` |
| `bank_accounts.py` | `/organisations/{org_id}/bank-accounts` |
| `bank_accounts.py` → `ob_router` | `/organisations/{org_id}/opening-balances` |
| `csv_profiles.py` | `/organisations/{org_id}/csv-profiles` |
| `umlage_source_scopes.py` | `/organisations/{org_id}/umlage-source-scopes` |
| `fristen.py` | `/organisations/{org_id}/fristen` |
| `review.py` | `/organisations/{org_id}/review` + `GET /ytd-stats` (YTD fund-allocation aggregation) |
| `compliance.py` | `/organisations/{org_id}/compliance` + `GET /fehlbedarf` (WARNUNG/HINWEIS/OK per measure) |
| `tarif.py` | `/organisations/{org_id}/tarif` |

### Seed scripts (`scripts/`)

| Script | Purpose | Requires |
|--------|---------|---------|
| `scripts/seed.py` | System seed: 33 Kostenbereiche + 102 TVöD 2025 entries (17 Gruppen E1–E15 × 6 Stufen). Idempotent. | Nothing |
| `scripts/seed_demo.py` | Demo org "Zukunft für Kinder": FY2025(GESCHLOSSEN)+FY2026, 1 BankAccount, 8 KSTs, 5 Fördergeber (3 with VN-Fristen), 3 AG-Brutto-Faktoren, 2 AllocationKeys, 3 measures (HAUSAUFGABEN/SPRACHFOERDERUNG/FERIEN)+finanzplan+regeln, 4 employees+payrolls (Jan–Mär 2026), 17 transactions+FundAllocations, 6 Mittelabrufe, 3 VerwNachweise, 4 BookingRules | User must exist (login first) |
| `scripts/seed_pilot_fam.py` | Pilot org "Freunde alter Menschen e.V.": FY2025, 9 BankAccounts (BFS-SozialBank) + Eröffnungsbestände, 31 KSTs (6 Parents + 24 Children + 1 Standalone), 1 Funder (LAGeSo) + 1 FundingMeasure (Berlin 2025), 1 UmlageSourceScope, 1 AllocationKey, 26 BookingRules. Env: `PILOT_USER_EMAIL`, `PILOT_ORG_NAME`, `PILOT_RESET=1` | User must exist (login first) |

Run via `make seed` / `make seed-demo` / `make seed-reset` / `make seed-pilot-fam` / `make seed-pilot-fam-reset`. Scripts use `AsyncSessionLocal` from `app.database` and `new_id()` from `app.utils.ids`.

`DEMO_USER_EMAIL` and `DEMO_ORG_NAME` are read from environment (set in `.env.local`). `DEMO_RESET=1` wipes org data before reseeding.

### Tests
- Test file per router: `tests/test_<domain>.py`
- Fixtures from `conftest.py`: `db`, `client`, `test_org`, `test_fiscal_year`, `auth_headers`
- aiosqlite in-memory — no real DB in unit tests
- Coverage gate: **80% minimum** (enforced in CI)

### Linting
```
ruff check app/ tests/
mypy app/
```

---

## Frontend rules

### Design system — Tailwind v4 + Soft Depth theme

**Theme is defined in `app/globals.css` via `@theme {}`** — NOT in `tailwind.config.ts`.
`tailwind.config.ts` only provides `content` paths in this project.

| Token | Value | Usage |
|-------|-------|-------|
| `soft-bg` | `#fafaf9` | Page background |
| `soft-sidebarBg` | `#f3f1ee` | Sidebar background |
| `soft-surface` | `#ffffff` | Cards, modals |
| `soft-ink` | `#1b1a22` | Primary text |
| `soft-ink2` | `#4a4753` | Secondary text |
| `soft-ink3` | `#7a7684` | Tertiary text / icons |
| `soft-accent` | `#6b5ce0` | Active state, links, primary buttons |
| `soft-accentDark` | `#4b3fb3` | Hover state |
| `soft-line` | `#ebe8e3` | Card borders |
| `soft-ok` / `soft-okSoft` | `#4a8064` / `#e4efe7` | Success |
| `soft-warn` / `soft-warnSoft` | `#b47a2c` / `#fbf2e0` | Warning |
| `soft-crit` / `soft-critSoft` | `#b5453d` / `#fbe4e1` | Error / critical |

Custom utilities: `rounded-soft` (14px), `rounded-soft-sm` (10px), `rounded-soft-xs` (8px), `shadow-soft`, `shadow-soft-lg`.

Font: IBM Plex Sans (body) + IBM Plex Mono (numbers). Use class `.numeric` on any currency/number element.

**Never use default Tailwind colors** (`bg-blue-*`, `bg-slate-*`, etc.) — all colors must come from the `soft-*` palette.

### API calls

- **Server Components / RSC**: `serverFetch<T>(path, init?)` from `lib/server-fetch.ts` — reads `access_token` cookie, hits `BACKEND_URL` directly
- `getSelectedOrgId()` from `lib/server-fetch.ts` — reads `selected_org_id` cookie server-side
- **Client Components** (common): raw `fetch()` with typed response casts
- **Client Components** (preferred when types exist): `apiClient` from `lib/api/client.ts` (openapi-fetch typed against `/api/openapi.json`)

Reading `orgId` client-side:
```typescript
const match = document.cookie.match(/selected_org_id=([^;]+)/);
if (match?.[1]) setOrgId(decodeURIComponent(match[1]));
```

### Type generation
After adding/changing a backend endpoint, regenerate types:
```
make types
```
Never edit `types/api.d.ts` by hand.

### State
- **Server state** (API data): TanStack Query
- **Client state** (UI, local preferences): Zustand
- Never put server state in Zustand

### Auth flow
1. `/login` → `POST /api/v1/auth/magic-link` → backend emails link → check Mailpit at `:8025`
2. `/auth/verify?token=xxx` → `POST /api/v1/auth/verify` → backend sets `access_token` cookie → redirect `/org-select`
3. `/org-select` → `GET /api/v1/auth/memberships` → pick/create org → frontend sets `selected_org_id` cookie → redirect `/dashboard`
4. `middleware.ts` guards `/dashboard/*` (requires both cookies) and `/org-select` (requires `access_token`)

### Components
- Default to Server Components (no `"use client"`)
- Add `"use client"` only when hooks or browser APIs are required
- `useSearchParams` requires a `<Suspense>` wrapper — use an inner client component pattern

---

## Frontend structure

### Dashboard layout (`app/dashboard/layout.tsx`)

Fetches org info, user info, and fristen count in parallel on every render. Passes `kritischeFristen` (count of ROT items) to `<SidebarNav>` for the badge.

### Sidebar sections (`components/dashboard/SidebarNav.tsx`)

| Section | Items |
|---------|-------|
| **Täglich** | Übersicht, Transaktionen, Review-Inbox, Fristen (red badge) |
| **Monatlich** | Gehaltserfassung, Mittelabrufe, Buchungsregeln |
| **Verwaltung** (collapsible) | Fördermassnahmen, Kostenstellen, Verteilungsschlüssel, Haushaltsjahre, Personal, Bankkonten, Umlage-Pools, Administration |

### Dashboard pages (`app/dashboard/`)

| Folder | Feature |
|--------|---------|
| `page.tsx` | KPI cards (Gesamtvolumen, Offene Transaktionen, Reserviert, Dringende Abrufe) + Aktive Massnahmen + Nächste Fristen |
| `personal/` | Employee list |
| `personal/[id]/` | Employee detail: Stammdaten + Verträge |
| `personal/gehaltserfassung/` | Payroll entry |
| `personal/gehaltserfassung/export/` | Lohnbüro CSV export |
| `personal/vzae/` | VZÄ (FTE) overview |
| `foerdermassnahmen/` | Funding measures list |
| `foerdermassnahmen/new/` | Create measure (wizard) |
| `foerdermassnahmen/[id]/` | Detail: tabs Übersicht \| Finanzplan \| Ampel \| Nachweise \| Prognose |
| `foerdermassnahmen/[id]/edit/` | Edit measure |
| `foerdermassnahmen/import-bescheid/` | Import grant decision PDF |
| `verteilungsschluessel/` | Allocation keys list |
| `verteilungsschluessel/new/` | Create allocation key |
| `verteilungsschluessel/[id]/` | Detail + edit + neue-version |
| `haushaltsjahre/` | Fiscal years list |
| `haushaltsjahre/new/` | Create fiscal year |
| `haushaltsjahre/[id]/` | Detail + close |
| `kostenstellen/` | Cost centers |
| `kostenstellen/new/` | Create cost center |
| `kostenstellen/[id]/` | Detail + deactivate |
| `transaktionen/` | Transaction list with filters |
| `transaktionen/[id]/` | Detail: categorize + SplitEditor + FundAllocationForm |
| `transaktionen/import/` | CSV import |
| `mittelabrufe/` | Fund requests + calendar |
| `mittelabrufe/[id]/` | Drawdown detail |
| `buchungsregeln/` | Booking rules + suggest + backfill |
| `fristen/` | Deadline monitor |
| `review/` | Review inbox (pending items) |
| `konten/` | Bank accounts + opening balances |
| `umlage-source-scopes/` | Overhead allocation pools (Phase K) |
| `verwendungsnachweise/[id]/` | VerwNachweis detail + einreichen |
| `profil/` | User profile |

### Admin pages (`app/admin/`)

`app/admin/` → overview, `organisations/` → org list, `users/` → user list.

### Dashboard widgets (`components/dashboard/`)

| Component | Purpose |
|-----------|---------|
| `SidebarNav` | Left nav with Täglich/Monatlich/Verwaltung sections + Mein Profil + conditional VoluLink Super-Admin. Props: `kritischeFristen`, `isSuperAdmin`. |
| `GettingStartedWidget` | Onboarding checklist (shows until org has baseline data) |
| `FehlbedarfWidget` | Server Component — calls `/compliance/fehlbedarf`; renders WARNUNG/HINWEIS/OK per FEHLBEDARF/Vollfinanzierungs-measure; hidden if no relevant measures |
| `LogoutButton` | Client button that clears cookies and redirects to `/login` |

### UI components (`components/ui/`)

| Component | Purpose |
|-----------|---------|
| `PageShell` | Page wrapper with consistent padding |
| `Badge` | Status pills: `default`, `success`, `warning`, `danger`, `muted` |
| `AmpelBadge` | Traffic-light badge: `GRUEN` / `GELB` / `ROT` with dot + label |
| `Button` | Primary / secondary / ghost / danger variants |
| `SearchInput` | Search field for list pages |
| `EmptyState` | Empty list placeholder |
| `ConfirmDialog` | Destructive action confirmation modal |
| `SkeletonCard` | Loading skeleton — also exports `SkeletonList` |
| `Toast` + `ToastProvider` | Toast notifications via `useToast()` hook |

### Form components (`components/forms/`)

`FoerdermassnahmeForm`, `FoerdermassnahmeWizard`, `FoerderregelEditor`, `FinanzplanPositionenStep`, `FiscalYearCloseForm`, `HaushaltjahrForm`, `KostenstelleForm`, `TransaktionImportForm`, `FoerdermassnahmeDeleteButton`, `SplitEditor`, `FundAllocationForm`, `KostenbereichSelect`, `BelegUploadForm`

### Hooks (`lib/hooks/`)

`useAuth.ts` → `useCurrentUser()`, `useDebounce.ts`, `useKostenbereiche.ts`

---

## UI patterns

### `inputCls` — always a function
```typescript
const inputCls = (error?: string) =>
  `w-full rounded-soft-xs border px-3 py-2.5 text-sm outline-none transition-colors
   focus:ring-2 focus:ring-soft-accent focus:border-soft-accent ${
     error
       ? "border-soft-crit bg-soft-critSoft text-soft-crit"
       : "border-soft-line bg-white"
   }`;
```
Never define `inputCls` as a plain string.

### Form error handling
```typescript
const [errors, setErrors] = useState<Record<string, string>>({});
// errors.general → top-level red alert box
// errors.fieldName → per-field red styling + role="alert" paragraph
```

Per-field error:
```tsx
{errors.fieldName && (
  <p role="alert" className="mt-1 text-xs text-soft-crit">{errors.fieldName}</p>
)}
```

General error box:
```tsx
{errors.general && (
  <div role="alert" className="rounded-soft-xs bg-soft-critSoft border border-soft-crit/30 p-4 text-sm text-soft-crit">
    <strong className="font-medium">Fehler: </strong>{errors.general}
  </div>
)}
```

Every `<input>` / `<select>` must have `id` matching `<label htmlFor>`, `aria-invalid={!!errors.field}`, and `className={inputCls(errors.field)}`.

Add `noValidate` to every `<form>` — browser validation is suppressed, custom validation runs instead.

### Toast notifications
```typescript
const toast = useToast();  // from @/components/ui/ToastProvider
toast.success("Gespeichert.");
toast.error("Fehler beim Speichern.");
```

### Section layout pattern
```tsx
<section>
  <h2 className="text-base font-semibold text-soft-ink mb-4 pb-2 border-b border-soft-line">
    Abschnittstitel
  </h2>
  <div className="space-y-4">{/* fields */}</div>
</section>
```
Use `<h3>` inside modals.

---

## Domain-specific notes

### Personal / Mitarbeiter

Employee creation is **two-step**:
1. `POST /organisations/{orgId}/employees` — creates the person
2. `POST /organisations/{orgId}/employees/{empId}/contracts` — creates the first contract

`employee_code` is always shown as **"Personalnummer"** in the UI (never "Kürzel").

**Tarifwerk = INDIVIDUELL** → hides Entgeltgruppe + Stufe fields; switching away resets them.

### Verteilungsschlüssel / Allocation Keys

Positions are always called **"Kostenstellenanteile"** — never "Positionen".

**Neue Version** flow:
- `POST /organisations/{orgId}/allocation-keys/{keyId}/neue-version` with `{ gueltig_von, positions[] }`
- Old key gets `gueltig_bis = neue_gueltig_von - 1 day`, `ist_aktiv = False`
- New key created with same `name` + `basis`

`SummenBalken` — inline progress bar wherever percentage sums are shown (green=100%, yellow<100%, red>100%).

### Fördermassnahmen detail tabs

`/dashboard/foerdermassnahmen/[id]?tab=X`:
- `uebersicht` — Stammdaten, Fördergeber, Zeitraum, Budget-Fortschrittsbalken, verknüpfte KSTs
- `bescheid` — Zuwendungsbescheid: BescheidDokumente (OCR/manual upload, delete)
- `regeln` — Förderregeln list
- `finanzplan` — Finanzplan-Positionen (Soll-Ist table)
- `nachweise` — Verwendungsnachweise list

### Phase K / Umlage (overhead allocation)

`PauschaleTyp.UMLAGE_KOSTENSTELLEN` on a `FinanzplanPosition` activates Phase K mode:
- `umlage_allocation_key_id` — which key distributes the overhead
- `umlage_ziel_cost_center_id` — target cost center
- `umlage_source_scope_id` — pool of source cost centers (`UmlageSourceScope`)

Managed via `/organisations/{org_id}/umlage-source-scopes`.

### Fristen dringlichkeit

The `/fristen` endpoint returns items with `dringlichkeit`: `ROT` (<7 days), `GELB` (7–14 days), `GRUEN` (>14 days). The sidebar badge shows only `ROT` count.

---

## Common

### Commits
German Conventional Commits:
```
feat: neue Funktion
fix: Fehler behoben
refactor: Umstrukturierung ohne Funktionsänderung
test: Tests hinzugefügt
chore: Build/Config Änderung
```
Always append:
```
Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
```

### Environment
- Commit `.env.example` with placeholder values only
- Never commit `.env.local` or `.env.production`
- All secrets via env vars — no hardcoded credentials
