# Phase Progress & Verification Log

## Phase 0 — Scaffolding & infra ✅
- Backend FastAPI clean-arch skeleton, frontend Next.js feature-based skeleton,
  root docker-compose (db/backend/frontend/mailpit + healthchecks), `.env.example`,
  Makefile, READMEs, docs.
- **Verified:** Python files compile; `enums.py` loads 24 enums with correct
  `@@map` names; design system ported verbatim from BRAND.md.

## Phase 1 — Data layer ✅
- **46 SQLAlchemy 2 models** across `app/models/*` (organization, auth, master,
  funding, allocation, transaction, booking_rule, mittelabruf, payroll, finanzplan,
  audit) + **24 enums**.
- Faithful to Prisma: preserved `@@map` table/column names, native PG enum types,
  FK `onDelete` (RESTRICT/CASCADE/SET NULL), unique constraints, all `@@index`,
  cuid PKs, `Decimal(p,s)` → `Numeric(p,s)`, denormalized `org_id` columns that have
  **no** Prisma relation are kept FK-less (FundingRule, TransactionSplit,
  FundAllocation, AuditLog, etc.).
- Baseline Alembic migration `0001_initial` (builds schema from validated metadata).
- Pydantic v2 schema foundation (`schemas/base.py`) with the Decimal→string wire
  contract from PLANNING.md. Idempotent demo seed (`app/seeds/demo.py`).
- **Verified:**
  - `configure_mappers()` passes (no relationship errors).
  - All 46 table names match the Prisma `@@map` set exactly (set diff = ∅).
  - `CREATE TABLE` DDL compiles for PostgreSQL for all 46 tables.
  - `pytest` green (6 passed): health endpoints + model-layer suite.

## Phase 2 — Auth, tenancy, RBAC 🟡 (foundation done)
- `core/security.py` — JWT issue/verify + magic-link tokens (passwordless, per decision).
- `permissions/rbac.py` — OrgRole policy + super-admin axis (mirrors lib/session.ts).
- `dependencies/auth.py` — `get_current_user`, `get_org_context` (port of
  `requireOrgSession`, org resolved via `X-Org-Id` header), `require_roles`,
  `require_super_admin`.
- `core/errors.py` — `{error, code}` envelope (matches monolith) + validation mapping.
- `services/email_service.py` — magic-link delivery (dev logs link, prod SMTP).
- Routers: `/api/auth/{magic-link,verify,signout}`, `/api/protected/me` (GET/PUT,
  faithful `{data}`/`{error,code}` envelopes, name-composition + validation).
- **Verified:** app boots; `/api/health` 200; OpenAPI served; `/api/protected/me`
  without token → 401 `{error,code}`.
- **Remaining:** org invites, `/api/setup/organisation`, `/api/admin/*` (super-admin
  org/user/member/invite management), magic-link rate limiting (5/IP/h).

## Phase 3 — Domain services & endpoints 🟡 (master-data slice done)
Built as full repository → service → route → test verticals, faithful to the
monolith (custom validation codes/messages, `{data}`/`{error,code}` envelopes,
org-scoping, exact authorization = org session only):
- **Kostenstellen** — CRUD + soft-delete with active-child cascade + warnings,
  1-level hierarchy, code uniqueness/format.
- **Funder** — CRUD; hard-delete only if no measures (HAS_MEASURES); create/update
  accept only 5 of 7 FunderTyp values (KIRCHE/PRIVAT rejected — parity).
- **Kostenbereiche** — read-only taxonomy (no org filter, `nur_obergruppen`, kinder).
- **Haushaltsjahre** — CRUD + irreversible close (confirmation token, sets
  geschlossen_am/von), closed-year immutability, open-year warning, year uniqueness.
- **Bank-Accounts** — CRUD + saldo view (opening balance + Σ transactions),
  IBAN normalize/validate/global-unique, hard-delete only if no dependents.
- **Fördermassnahmen** (domain core) — full CRUD: list (filters, expiry, `_count`,
  `cost_center_ids`), get/create/update with all validation codes, Durchführungs-
  zeitraum validation, rule + cost-center replacement, status-lock (ABGESCHLOSSEN →
  only WIDERRUFEN), soft-delete (→WIDERRUFEN) + hard-delete (blocker check on
  allocations/Mittelabrufe, DB cascade). Funder existence + cost-center org checks.
- **Verified:** `pytest` green — **22 passed**; app boots; **18 OpenAPI paths**.
- Added canonical `utils/serialization.decimal_str` (Prisma decimal.js `toString`
  parity: drops trailing zeros) used across services.
- **Fördermassnahme sub-resources** — funding rules (GET/POST `[id]/regeln`,
  DELETE `[id]/regeln/[ruleId]`) and cost-center links (POST/DELETE
  `[id]/kostenstellen`): WIDERRUFEN guard (MEASURE_REVOKED), validation codes,
  duplicate-link conflict, nested cost_center serialization, + **audit logging**.
- Added `services/audit_service.log_audit(db, …)` — fire-and-forget port of
  lib/audit.ts; writes AuditLog inside a SAVEPOINT on the request session after
  the main commit, so failures never poison the transaction or open an external
  connection (testable, offline-safe).
- **Verified:** `pytest` green — **25 passed**; app boots; **21 OpenAPI paths**.
- **Finanzplan-Positionen** — full CRUD (`finanzplan-positionen` + `[id]` +
  `[id]/deckungsfaehigkeit`): money fields serialize as **numbers** (monolith uses
  Number()); Verwaltungspauschale validation (FIXER_BETRAG / PROZENT_GESAMT (with
  recursion guard) / PROZENT_PERSONAL (measure-default fallback) / UMLAGE_KOSTENSTELLEN
  with full FK consistency + ziel-in-key checks); kostenbereich resolve (code→id) +
  replace; **Doppelförderung soft-check** (ANBest-P) on UMLAGE create/update;
  Deckungsfähigkeit pool view (bewilligt × (1+limit%); IST via fund-allocation
  weighting — measure-level resolver fallback wired with the transactions module).
- Helpers: `services/finanzplan_kostenbereich.resolve_kostenbereiche`,
  `services/pauschale_doppelfoerderung.{check,format}`.
- **Verified:** `pytest` green — **34 passed**; app boots; **24 OpenAPI paths**.
- **Allocation subsystem** — Verteilungsschlüssel (`verteilungsschluessel` + `[id]` +
  `[id]/neue-version`) and Umlage-Pools (`umlage-source-scopes` + `[id]`):
  100%-sum invariant (400 INVARIANT_SUM_NOT_100 incl. `summe_prozent`), position
  dup/range checks, active-cost-center validation, overlap warnings, version
  families (close prior key gueltig_bis = neue_von−1, ist_aktiv=false, parent_key_id
  chaining), in-place name/gueltig_bis patch, soft-delete; Umlage-Pool CRUD with
  unique-name (DUPLICATE_NAME), cost-center replace, delete-blocked-if-referenced.
  `APIError` extended with `extra` for the invariant's `summe_prozent` field.
- **Verified:** `pytest` green — **39 passed**; app boots; **29 OpenAPI paths**.

### Transactions engine (built in tested sub-slices)
- **Slice 1 — core:** `GET /transaktionen` (full cockpit filter set via
  `transaction_filter.build_conditions`: status/KB/KST/measure/bank/IBAN/search/
  date/amount/confidence/has_massnahme with split+allocation EXISTS subqueries),
  pagination, cockpit KPIs (einnahmen/ausgaben/cashflow/zugeordnet/fortschritt);
  `GET /transaktionen/[id]` (full details: splits→cost_center+fund_allocations→
  measure, active belege, import_batch, latest rule_application+rule); `PATCH
  /transaktionen/[id]` (kostenbereich/notiz/auftraggeber, KB existence check).
  Money→string, dates→YYYY-MM-DD.
- **Verified:** `pytest` green — **46 passed**; app boots; **31 OpenAPI paths**.
- **Slice 2 — splits + Förderzuordnung:** `PUT /[id]/splits` (100%-rule, cent-exact
  rounding correction, status transitions, optional save_as_rule→BookingRule);
  `GET/POST/PATCH/DELETE /[id]/fund-allocation` with the full validation chain
  (fiscal-year-open, ownership, **Doppelfinanzierung**, **Förderfähigkeit**,
  **Overhead-Limit**, **Bridge position decision**, **Position-Überziehung**) and
  the balancing-invariant amount calc. Ported the **canonical allocation→position
  resolver** (Override ∪ Bridge, cross-dialect SQLAlchemy Core) and wired it back
  into Finanzplan `_pool_ist` (Deckungsfähigkeit now uses the real IST path).
  New: `allocation_betraege`, `allocation_position_resolver`,
  `foerderfahigkeit_service` (4 checks + de-DE EUR formatting). Audit on
  create/update/delete.
- **Verified:** `pytest` green — **52 passed**; app boots; **33 OpenAPI paths**.
- **Slice 3 — massnahme + confirm + batch:** `POST /[id]/massnahme` (assign measure
  to all splits: Laufzeit + KST-whitelist checks, one VORLAEUFIG allocation/split);
  `PATCH /[id]/confirm` (raise last rule's match_count → recompute confidence
  ORANGE→GELB→GRÜN, status KATEGORISIERT); `POST /batch-confirm` + `/batch-massnahme`
  (Mode A ids / Mode B filter+excluded via `resolve_batch_input`, MAX 20000,
  per-item skip collection). New: `booking_rules.calculate_confidence`,
  `transaction_confirm`, `massnahme_zuordnung`, `transaction_batch`.
- **Verified:** `pytest` green — **58 passed**; app boots; **37 OpenAPI paths**.
- **Slice 4 — booking-rule engine:** `buchungsregeln` CRUD (POST/GET, PUT full-replace,
  PATCH toggle, DELETE), `preview` (matched count + 5 sample + total, NO_CONDITIONS
  guard), `suggest` (rule inference from selection — common auftraggeber pattern +
  frequent KB), `[id]/backfill` (GET count / POST apply, status-scope guard, MAX
  20000), `transaktionen/batch-regeln`. Match engine `build_rule_match_conditions`
  (AND logic, |betrag| range) + `apply_rule_to_transaction` (set_kostenbereich
  override, split replace w/ rounding, **confidence learning** match_count→ORANGE/
  GELB/GRÜN, audit application, auto FundAllocation per split incl. per-split measure
  mapping, status transitions). New: `rule_inference`, `buchungsregel_service`,
  engine in `booking_rules`. `decimal_str` now tolerates float/int.
- **Verified:** `pytest` green — **64 passed**; app boots; **43 OpenAPI paths**.
- **Slice 5 — belege:** `[id]/belege` (list/upload), `[id]/belege/[belegId]`
  (download/soft-delete). PDF/JPEG/PNG/WEBP ≤10MB to disk OR external reference;
  retention 1–10y; list omits datei_pfad; download streams file or returns ref;
  soft-delete (geloescht_am) + retention warning. `beleg_service` + `settings.upload_dir`.
- **Slice 6 — CSV import + digest (engine complete):** `transaktionen/import`
  (POST: profile/custom-mapping → builtin-autodetect → UNKNOWN_FORMAT; PUT: preview);
  `csv-profiles` (list systemwide+own / create); `transaktionen/digest` (24h
  rule-application confidence rollup). Full port of lib/import/*: detector/tokenizer
  (delimiter/decimal/date/header autodetect), profile parser (date/amount, Soll/Haben,
  truncation), duplicate hashing (sha256), Kostenbereich heuristics (~50 rules), 5
  builtin bank profiles, field-hint mapping suggestion, persist pipeline (bank-account
  auto-create, typ classify, EREF extract, de-dupe, booking-rule auto-apply,
  saldo-consistency). `csv_import/*` package + `csv_profile_service`,
  `transaction_digest`.
- **JSONB cross-dialect:** `_types.JSONBType = JSONB().with_variant(JSON, "sqlite")`
  applied to all 5 JSONB columns — PostgreSQL keeps real JSONB; SQLite test harness
  now builds the **full metadata** (conftest simplified, no table cherry-picking).
- **Verified:** `pytest` green — **80 passed**; app boots; **48 OpenAPI paths**;
  PG DDL still emits JSONB.

**✅ Transactions engine COMPLETE** (core · splits/fund-allocation · massnahme/
confirm/batch · booking-rule engine · belege · import/digest).

## Mittelabruf + Fristen + Fehlbedarf-compliance ✅
- **Mittelabrufe** (`mittelabrufe` + `[id]` + `[id]/frist` + `kalender`): CRUD with
  measure-AKTIV + not-ABRUF-Verfahren guards, fiscal-year-open, verwendungsfrist
  derivation (body→FundingRule→42), server-computed frist_bis, status-transition
  validation (VERWENDET needs betrag_verwendet≥betrag, ZURUECKGEZAHLT needs
  betrag_zurueck), frist recompute (ABGERUFEN-only), Python-aggregated kalender
  (month/quarter × funder), audit on update. Money→string, dates→YYYY-MM-DD.
- **Fehlbedarf compliance** (ANBest-P §2.2): full port — `compute_fehlbedarf_status`
  (pure), `get_fehlbedarf_status` (eigenmittel-ist via Einnahmen-KB allocations,
  zuwendung-abgerufen, overlap heuristic for drittmittel-ist), `check_mittelabruf_allowed`
  (hard block on POST → MITTELABRUF_LIMIT_UEBERSCHRITTEN), `recompute_cross_finanzierung_alerts`
  (audit), `berechne_zuwendung`. Wired into Mittelabruf POST + measure
  `[id]/fehlbedarf-status`.
- **Fristen** (`fristen`): consolidated deadline list (Mittelabruf/VerwNachweis/
  Massnahme-Laufzeit/Haushaltsjahr), days_until + dringlichkeit, days_ahead 1–365.
  `count_kritische_fristen` for the sidebar badge.
- **Compliance** (`compliance/dismiss`): audit-logged banner dismissal.
- **Verified:** `pytest` green — **93 passed**; app boots; **55 OpenAPI paths**.

## Verwendungsnachweis + reporting ✅
- **Verwendungsnachweise** (`verwendungsnachweise` + `[id]` + `[id]/einreichen`):
  CRUD with the status-transition matrix (OFFEN→IN_BEARBEITUNG→EINGEREICHT→
  ANERKANNT/ABGELEHNT), snapshot immutability after EINGEREICHT, delete-only-OFFEN,
  fiscal-year-closed guards, **Frist auto-fill** from FunderNachweisFrist (HHJ_ENDE/
  DURCHFUEHRUNG_ENDE/BEWILLIGUNG_ENDE + offset). Einreichen builds the immutable
  snapshot via the aggregator + audit.
- **Aggregator** (`build_nachweis_data`): Einnahmen (zuwendung/eigenmittel, prozent-
  weighted), Ausgaben grouped by Kostenbereich (personal/sach), dedup transactions,
  Soll-Ist via the canonical IST aggregator.
- **IST core** (`aggregate_ist_by_finanzplan_position`): two-phase — direct
  allocations via the resolver + pauschale (FIXER_BETRAG/PROZENT_GESAMT/
  PROZENT_PERSONAL/UMLAGE_KOSTENSTELLEN) capped at bewilligt.
- **Excel report** (openpyxl): 3 sheets (Einnahmen&Ausgaben, Belegliste, Soll-Ist)
  with full styling/number formats — `foerdermassnahmen/[id]/verwendungsnachweis`.
- **Stundennachweis** (openpyxl): per-employee VZÄ sheets —
  `foerdermassnahmen/[id]/stundennachweis`.
- **Preview** (`foerdermassnahmen/[id]/verwendungsnachweis/preview`): ampel +
  soll-ist + unmapped-ist + belege coverage + Mittelabrufe.
- **Soll-Ist** (`foerdermassnahmen/[id]/soll-ist-position`), **ampel**,
  **berechne_zuwendung**, **VZÄ** helpers ported.
- **Verified:** `pytest` green — **103 passed**; app boots; **62 OpenAPI paths**.

## Payroll ✅
- **Employees** (`employees` + `[id]`): CRUD with first-contract creation,
  code-uniqueness, austrittsdatum/ist_aktiv. **Contracts** (`[id]/contracts`):
  versioned — new contract closes the prior (gueltig_bis = neu−1), order check.
  **Salary components** (`[id]/contracts/[contractId]/components`): monthly/one-off
  + deactivate (`?action=deactivate&componentId=`).
- **Salary calc** (`personal/berechnung`): berechne_gehalt (actual_salary, an_brutto,
  ag_brutto), get_ag_faktor (default 1.2121), get_aktiver_vertrag. **Payroll builder**
  (`personal/payroll_builder`): active contract + active components → MonthlyPayroll,
  manual overrides, duplicate-month/no-contract errors.
- **Payroll** (`payroll` + `[id]` + `[id]/allocations` + `monat-uebersicht`): CRUD
  (import-readonly guard, delete-if-no-allocations), allocations replace (100%-sum
  invariant, allocation_key expansion, betrag_anteil = ag_brutto × %), monthly grid.
- **Gross factors** (`employer-gross-factors`): versioned create. **Tarif**
  (`tarif`): TVöD lookup. **Personal soll-ist** (`personal/soll-ist`): payroll-ist
  vs. finanzplan personal positions.
- Money/hours serialize via `decimal_str` (Prisma decimal.js parity).
- **Verified:** `pytest` green — **114 passed**; app boots; **73 OpenAPI paths**.

## Super-admin + org invites + setup ✅
- **`/admin/*`** (super-admin gated): organisations (list/create/detail+members+
  invites/update/delete-if-empty), members (add by email/user_id, role change,
  remove — with **last-admin guard** + `?force=true`), invites (revoke), users
  (list/detail/update super-admin flag + profile, **self-revoke protection**).
- **`org/invite`** (org-admin): list (any member) + create/delete (role ADMIN only).
  **`setup/organisation`**: super-admin (or `ALLOW_SELF_SERVICE`) creates org +
  ADMIN membership.
- **`org_invite_service.create_org_invite`** (shared): email validation,
  already-member block, expire-old-invites, 7-day invite, magic-link email (dev-logged).
- **Verified:** `pytest` green — **124 passed**; app boots; **84 OpenAPI paths**.
- conftest now persists a real super-admin User + overrides `get_current_user` /
  `require_super_admin` (FK-safe for `created_by`).

### Remaining Phase 3 modules (smaller / lower-traffic)
foerdermassnahmen misc: ampel, prognose, preflight, finanzplan (+personalmodul),
bescheid CRUD + bescheid OCR import (Mistral — likely stub), finanzplan-positionen
umlage-preview → allocations position-wahl-ausstehend, fund-allocations/summary,
opening-balances → payroll import (Lohnjournal) + lohnbuero-export + vzae-uebersicht
→ auth signout (done) / [...nextauth] (magic-link done). Then Phase 4 (frontend),
Phase 5.

Layers added: `repositories/{base,cost_center,funder,fiscal_year,bank_account}`,
`services/{kostenstelle,funder,kostenbereich,haushaltsjahr,bank_account}`,
`api/routes/{kostenstellen,kostenbereiche,funder,haushaltsjahre,bank_accounts}`,
tests `test_kostenstellen.py` + `test_master_data.py` + `conftest.py` (SQLite harness).

### Wire-format contract decisions (documented for the new frontend)
- `Decimal` → JSON **string** (matches Prisma); explicit `Number()` views (bank-account
  saldo) → **number**, exactly as the monolith does.
- `Date` → `YYYY-MM-DD`; `DateTime` → ISO-8601. (Minor: the monolith's list endpoints
  sometimes emit full-ISO for date columns; we standardize on `YYYY-MM-DD` since the
  consuming frontend is also rewritten.)

## Remaining Phase 3 + Phases 4–5 — Not started
- **Phase 3:** ~160 REST ops porting ~7,900 LOC of domain logic (allocation math,
  TVöD payroll, Fehlbedarf/ANBest-P compliance, booking-rule confidence engine,
  CSV/CAMT/DATEV importers, Word/Excel generators, Mistral OCR). Build order +
  golden-file parity tests per `docs/02-migration-roadmap.md` §2.
- **Phase 4:** 45 pages + 46 components on the Next.js scaffold.
- **Phase 5:** full test suites + parity sign-off + prod deploy docs.

## How to run what exists
```bash
cd foerderflow-backend
pip install -e ".[dev]"
pytest                     # 6 passing
uvicorn app.main:app --reload      # http://localhost:8000/docs
# With a Postgres DB + .env: alembic upgrade head && python -m app.seeds.demo
```
