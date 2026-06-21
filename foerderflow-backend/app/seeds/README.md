# Seed data — FörderFlow backend

Python/SQLAlchemy port of the monolith's `scripts/seed-*.ts`. Four modules under
`app/seeds/`, all idempotent and runnable as `python -m app.seeds.<module>`.

| Module | Purpose | Run as |
|---|---|---|
| `system_data` | System reference data (`org_id IS NULL`): **Kostenbereiche** (SKR42, 34 rows) + **TVöD-D 2025** tariff table (102 rows). Prerequisite for `demo`. | `python -m app.seeds.system_data` |
| `demo` | Demo org **"Zukunft für Kinder"** — full dataset (measures, employees, payrolls, transactions, Mittelabrufe, Verwendungsnachweise, booking rules). Auto-seeds system data if missing. | `python -m app.seeds.demo` |
| `pilot_fam` | Pilot org **"Freunde alter Menschen e.V."** — 9 bank accounts, 31 cost centers, umlage scopes, allocation key, funding measure, 26 booking rules. CLI flags incl. resets. | `python -m app.seeds.pilot_fam [flags]` |
| `reset` | FK-aware reset helpers (`reset_org_data`, `reset_transactions`, `reset_rules`). Library only — imported by the seeds. | — |

> **Windows console note:** the seeds print box-drawing chars and umlauts. On a
> Windows shell run with `PYTHONIOENCODING=utf-8` (the Docker/Linux runtime is
> already UTF-8). Example: `PYTHONIOENCODING=utf-8 python -m app.seeds.demo`.

---

## Prerequisites

1. **Database** reachable via `DATABASE_URL`
   (default `postgresql+psycopg://foerderflow:password@localhost:5432/foerderflow`).
2. **Schema migrated**: `alembic upgrade head` (the Docker entrypoint does this
   automatically on startup).

That's it — unlike the monolith, the demo/pilot seeds **create** their user/org/
membership if missing, so no magic-link login or admin-UI step is required first.

---

## Demo seed

```bash
# 1. system reference data (Kostenbereiche + TVöD) — also auto-run by demo if missing
python -m app.seeds.system_data

# 2. demo org + full dataset
python -m app.seeds.demo
```

### Environment overrides

| Var | Default | Effect |
|---|---|---|
| `DEMO_USER_EMAIL` | `jade.dyett@gmail.com` | account email (created if absent) |
| `DEMO_ORG_NAME` | `Zukunft für Kinder` | organization name (created if absent) |
| `DEMO_TODAY` | `2026-05-20` | anchor date for relative deadlines (`YYYY-MM-DD`) |
| `DEMO_RESET` | unset | `1` → wipe **all** org data, then re-seed (see below) |
| `DEMO_BESCHEID_PDF` | `public/demo-assets/zuwendungsbescheid-demo.pdf` | optional demo Bescheid PDF; skipped silently if the file is absent |

```bash
# different account
DEMO_USER_EMAIL=paulelektro2024@gmail.com python -m app.seeds.demo

# DEMO_RESET — wipe demo-org data and re-seed (user + org + membership are kept)
DEMO_RESET=1 python -m app.seeds.demo
```

`DEMO_RESET=1` calls `reset_org_data(..., keep_audit_log=False)` — it deletes every
org-scoped row (measures, personnel, transactions, …) **except** the Organization
record and its memberships, then re-seeds from scratch.

---

## Pilot seed (`pilot_fam`) — flags

```bash
python -m app.seeds.pilot_fam [flags]
```

| Flag | Effect |
|---|---|
| `--org-name "<name>"` | target org by name (default `Freunde alter Menschen e.V.`); created if absent |
| `--org-id <cuid>` | target org by id (must exist) |
| `--no-create-org` | error instead of auto-creating a missing org |
| `--skip-measure` | omit the placeholder FundingMeasure + Funder |
| `--dry-run` | run everything, then **roll back** — validate without writing |
| `--reset-rules` | back up (JSON → `backups/`) + delete this org's BookingRules, then re-seed |
| `--reset-transactions` | delete Transactions + Splits + FundAllocations + Belege + ImportBatches + BookingRuleApplications (master data untouched); writes a count manifest to `backups/` |
| `--reset-all` | wipe **all** org data via `reset_org_data` (keeps Org + Memberships + AuditLog), then re-seed. Makes `--reset-rules`/`--reset-transactions` redundant — they are skipped |
| `--berlin-measure-id <id>` / `--berlin-measure-name "<n>"` | override the measure that `link_berlin` booking-rule splits attach to (default: auto-lookup via cost center `B-GGE`) |

```bash
# first run (creates the org + all master data)
python -m app.seeds.pilot_fam

# re-import just the booking rules (old ones backed up to backups/)
python -m app.seeds.pilot_fam --reset-rules

# clear bookings before re-importing CSVs, keep master data
python -m app.seeds.pilot_fam --reset-transactions

# nuke everything for this org and rebuild master data
python -m app.seeds.pilot_fam --reset-all

# safe preview
python -m app.seeds.pilot_fam --reset-all --dry-run
```

---

## Docker workflow

`docker-compose.yml` wires the backend entrypoint to seed on startup:

```bash
# bring up DB + backend, run migrations, then seed system data + demo org
RUN_SEED=1 docker compose up -d --build

# also seed the pilot org
RUN_SEED=1 SEED_PILOT=1 docker compose up -d --build
```

Or run a one-off inside the running container:

```bash
docker compose exec backend python -m app.seeds.system_data
docker compose exec -e DEMO_USER_EMAIL=paulelektro2024@gmail.com backend python -m app.seeds.demo
docker compose exec -e DEMO_RESET=1 backend python -m app.seeds.demo
docker compose exec backend python -m app.seeds.pilot_fam --reset-all
```

---

## Constraints & invariants enforced by the seeds

- **Idempotency** — every insert is existence-checked (upsert on the natural key:
  `org_id+code`, `org_id+name`, `org_id+jahr`, etc.). Re-running creates no duplicates.
- **Org isolation** — all resets are scoped by `org_id`; resetting one org never
  touches another (verified: pilot `--reset-all` leaves the demo org intact).
- **FK-safe delete order** — `reset_org_data` deletes leaves → roots, with cost
  centers deleted children-first (self-referential `RESTRICT` on `parent_id`), and
  umlage scopes before cost centers.
- **Split sums = 100 %** — booking-rule splits and allocation-key positions are
  validated to total 100 %; a non-conforming entry is skipped with a `⚠`.
- **Cross-reference integrity** — every `set_kostenbereich_code` and split cost-center
  code resolves against the seeded catalogues.
- **IBAN global uniqueness** — pilot bank accounts skip an IBAN already owned by
  another org (`⚠`) rather than colliding on the global unique constraint.
- **Fehlbedarf rule** — demo measure `HAUSAUFGABEN` uses `FINANZIERUNGSART=FEHLBEDARF`
  with `eigenmittel_betrag`/`drittmittel_betrag` set; other measures stay `ANTEIL`.
- **Amount-sign convention** — `AUSGABE` transactions are stored negative,
  `EINNAHME` positive; split/allocation amounts are positive absolutes.
- **Atomic reset + re-seed** — a `--reset-*` run and the following re-seed commit as
  one unit (rollback on any error), so the DB is never left half-wiped.
```
