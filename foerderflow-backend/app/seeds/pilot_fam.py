"""Idempotent master-data seed for the pilot customer "Freunde alter Menschen e.V."

Full port of monolith `scripts/seed-pilot-fam.ts`. Maintains:
  - FiscalYear 2025
  - 9 BankAccounts (BFS-SozialBank) + opening balances
  - 6 parent cost centers + 24 children + 1 standalone (Demenz-WGs) = 31 KSTs
  - 1 Funder (Land Berlin / LAGeSo) + 1 FundingMeasure (Öff. Zuwendungen Berlin 2025)
  - 1 UmlageSourceScope "Geschäftsstelle 2025" (7 source KSTs)
  - 1 AllocationKey "Verwaltungs-Standortverteilung 2025" (5×20%)
  - 26 BookingRules + their splits

All operations are upserts on natural keys (org_id+code / org_id+name).

Run:
  python -m app.seeds.pilot_fam
  python -m app.seeds.pilot_fam --org-name "Anderer Name"
  python -m app.seeds.pilot_fam --org-id <cuid>
  python -m app.seeds.pilot_fam --dry-run             # validate only, write nothing
  python -m app.seeds.pilot_fam --skip-measure        # omit the FundingMeasure
  python -m app.seeds.pilot_fam --reset-rules         # delete BookingRules before re-seed
  python -m app.seeds.pilot_fam --reset-transactions  # delete Tx+Splits+Allocations+ImportBatches
  python -m app.seeds.pilot_fam --reset-all           # wipe ALL org data (keep Memberships+AuditLog)

Status markers:  +  created    ↻  updated    ·  unchanged    ⚠  warning    —  note
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.allocation import (
    AllocationKey,
    AllocationKeyPosition,
    UmlageSourceScope,
    UmlageSourceScopeCostCenter,
)
from app.models.booking_rule import BookingRule, BookingRuleSplit
from app.models.enums import (
    AccountTyp,
    AllocationBasis,
    CostCenterTyp,
    FinanzierungsartTyp,
    FiscalYearStatus,
    FunderTyp,
    FundingMeasureStatus,
    MittelabrufVerfahren,
    Rechtsform,
)
from app.models.funding import FundingMeasure, FundingMeasureCostCenter
from app.models.master import CostCenter, FiscalYear, Funder, Kostenbereich
from app.models.organization import Organization
from app.models.transaction import BankAccount, OpeningBalance
from app.seeds.reset import (
    ResetOptions,
    reset_org_data,
    reset_rules as do_reset_rules,
    reset_transactions as do_reset_transactions,
)

# ─────────────────────────────────────────────
# Master data
# ─────────────────────────────────────────────
BANK_ACCOUNTS = [
    ("BFS-600", "GiroPlus (Hauptkonto)", "DE06370205000003143600", "BFSWDE33XXX", "SozialBank AG", "67875.34"),
    ("BFS-601", "Spendenkonto (Haupt)", "DE76370205000003143601", "BFSWDE33XXX", "SozialBank AG", "97236.03"),
    ("BFS-602", "GiroKomfort 602", "DE49370205000003143602", "BFSWDE33XXX", "SozialBank AG", "27210.09"),
    ("BFS-603", "Spendenkonto (klein)", "DE22370205000003143603", "BFSWDE33XXX", "SozialBank AG", "826.76"),
    ("BFS-604", "GiroKomfort 604", "DE92370205000003143604", "BFSWDE33XXX", "SozialBank AG", "60228.04"),
    ("BFS-605", "GiroKomfort 605", "DE65370205000003143605", "BFSWDE33XXX", "SozialBank AG", "7892.65"),
    ("BFS-606", "GiroKomfort 606", "DE38370205000003143606", "BFSWDE33XXX", "SozialBank AG", "7836.70"),
    ("BFS-607", "GiroKomfort 607", "DE11370205000003143607", "BFSWDE33XXX", "SozialBank AG", "8580.78"),
    ("BFS-608", "GiroKomfort 608", "DE81370205000003143608", "BFSWDE33XXX", "SozialBank AG", "6533.74"),
]

# (code, name, typ, parent)
COST_CENTERS = [
    ("BERLIN", "Berlin (Standort)", CostCenterTyp.PROJECT, None),
    ("HAMBURG", "Hamburg (Standort)", CostCenterTyp.PROJECT, None),
    ("KOELN", "Köln (Standort)", CostCenterTyp.PROJECT, None),
    ("MUENCHEN", "München (Standort)", CostCenterTyp.PROJECT, None),
    ("FRANKFURT", "Frankfurt (Standort)", CostCenterTyp.PROJECT, None),
    ("ZENTRALE", "Zentrale Verwaltung", CostCenterTyp.OVERHEAD, None),
    ("B-GGE", "Berlin Gemeinsam gegen Einsamkeit", CostCenterTyp.PROJECT, "BERLIN"),
    ("B-GN", "Berlin Generation Nachbarschaft", CostCenterTyp.PROJECT, "BERLIN"),
    ("B-FR", "Berlin Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "BERLIN"),
    ("HH-GGE", "Hamburg Gemeinsam gegen Einsamkeit", CostCenterTyp.PROJECT, "HAMBURG"),
    ("HH-GN", "Hamburg Generation Nachbarschaft", CostCenterTyp.PROJECT, "HAMBURG"),
    ("HH-CC", "Hamburg Community Care", CostCenterTyp.PROJECT, "HAMBURG"),
    ("HH-GS", "Hamburg Gemeinsamkeitsscouts", CostCenterTyp.PROJECT, "HAMBURG"),
    ("HH-FR", "Hamburg Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "HAMBURG"),
    ("K-GGE", "Köln Gemeinsam gegen Einsamkeit", CostCenterTyp.PROJECT, "KOELN"),
    ("K-FR", "Köln Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "KOELN"),
    ("M-GGE", "München Gemeinsam gegen Einsamkeit", CostCenterTyp.PROJECT, "MUENCHEN"),
    ("M-FR", "München Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "MUENCHEN"),
    ("F-GGE", "Frankfurt Gemeinsam gegen Einsamkeit", CostCenterTyp.PROJECT, "FRANKFURT"),
    ("F-FR", "Frankfurt Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "FRANKFURT"),
    ("Z-VS", "Vorstand", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-GF", "Geschäftsführung", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-HR", "Human Resources", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-BH", "Buchhaltung", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-IT", "IT", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-LK", "Leitung Koordination", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-DS", "Datenschutz", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-FR-AUS", "Fundraising und Kommunikation (Ausgaben)", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-FR-EIN", "Gesamtverein Fundraising (Einnahmen)", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("Z-KS", "Krankenkassen und Steuern", CostCenterTyp.OVERHEAD, "ZENTRALE"),
    ("DWG", "Demenz-WGs", CostCenterTyp.PROJECT, None),
]

UMLAGE_SOURCE_SCOPES = [
    {
        "name": "Geschäftsstelle 2025",
        "beschreibung": (
            "Verwaltungs-Kostenstellen der Geschäftsstelle (Z-GF, Z-HR, Z-LK, Z-FR-AUS, "
            "Z-FR-EIN, Z-IT, Z-DS). Aufteilung nach Standort-Anteilen gemäß FamEV-Excel-Schema 2025."
        ),
        "cost_center_codes": ["Z-GF", "Z-HR", "Z-LK", "Z-FR-AUS", "Z-FR-EIN", "Z-IT", "Z-DS"],
    },
]

ALLOCATION_KEYS = [
    {
        "name": "Verwaltungs-Standortverteilung 2025",
        "basis": AllocationBasis.MANUELL,
        "gueltig_von": date(2025, 1, 1),
        "gueltig_bis": None,
        "positions": [
            ("B-GGE", 20), ("HH-GGE", 20), ("M-GGE", 20), ("F-GGE", 20), ("K-GGE", 20),
        ],
    },
]

# (name, match_auftraggeber, match_verwendungszweck, set_kostenbereich_code,
#  splits=[(cc_code, prozent, link_berlin)])
BOOKING_RULES = [
    ("Winheller (Anwaltskanzlei)", "Winheller", None, "RECHTSBERATUNG", [("Z-BH", 100, False)]),
    ("Haus des Stiftens (IT-Services)", "Haus des Stiftens", None, "IT_SOFTWARE", [("Z-IT", 100, False)]),
    ("BAGSO (Bundesarbeitsgemeinschaft Senioren-Organisationen)", "BAGSO", None, "MITGLIEDSBEITRAEGE",
     [("F-GGE", 20, False), ("B-GGE", 20, True), ("M-GGE", 20, False), ("K-GGE", 20, False),
      ("HH-GGE", 8, False), ("HH-GN", 8, False), ("HH-CC", 4, False)]),
    ("Domainfactory", "Domainfactory", None, "IT_INFRASTRUKTUR", [("Z-IT", 100, False)]),
    ("PARI-Personal", "PariPersonal", None, "PERSONAL_HONORARE", [("Z-HR", 100, False)]),
    ("Petits Frères des Pauvres (Dachverband Frankreich, gleich BAGSO-Splits)", "Petits Frères des Pauvres", None, "MITGLIEDSBEITRAEGE",
     [("F-GGE", 20, False), ("B-GGE", 20, True), ("M-GGE", 20, False), ("K-GGE", 20, False),
      ("HH-GGE", 8, False), ("HH-GN", 8, False), ("HH-CC", 4, False)]),
    ("Stephan Pirron (Datenschutz)", "Stephan Pirron", None, "RECHTSBERATUNG", [("Z-DS", 100, False)]),
    ("Fundraisingbox", "Fundraisingbox", None, "SACH_DIENSTLEISTUNGEN", [("Z-FR-AUS", 100, False)]),
    ("Dr. G. Lachnit", "Lachnit", None, "RECHTSBERATUNG",
     [("F-GGE", 20, False), ("B-GGE", 20, True), ("M-GGE", 20, False), ("K-GGE", 20, False), ("HH-GGE", 20, False)]),
    ("Paritätischer Hamburg (Landesverband Wohlfahrt)", "Paritätischer Hamburg", None, "MITGLIEDSBEITRAEGE",
     [("HH-GGE", 40, False), ("HH-GN", 40, False), ("HH-CC", 10, False), ("HH-GS", 10, False)]),
    ("Vattenfall Tieckstraße (Berliner Büro)", "Vattenfall", "Tieckstr", "ENERGIE",
     [("Z-GF", 10, False), ("Z-HR", 10, False), ("Z-LK", 10, False), ("B-GGE", 70, True)]),
    ("Vattenfall Bismarckstraße (Hamburger Büro)", "Vattenfall", "Bismarckstr", "ENERGIE",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("Vattenfall Eppendorfer Weg (Hamburger Büro)", "Vattenfall", "Eppendorfer", "ENERGIE",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("Vattenfall Bismarckstraße + Hamburger Büro (eprimo)", "eprimo", None, "ENERGIE",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("ASC Alsterservice (Hinrichsenstraße)", "ASC", None, "REINIGUNG",
     [("HH-GGE", 50, False), ("HH-CC", 50, False)]),
    ("Telekom Deutschland (Bismarck/Hamburg)", "Telekom Deutschland", None, "KOMMUNIKATION",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("Vodafone GmbH (Bismarck/Hamburg)", "Vodafone GmbH", None, "KOMMUNIKATION",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("Drillisch Online (Bismarck/Hamburg)", "Drillisch Online", None, "KOMMUNIKATION",
     [("Z-FR-AUS", 10, False), ("HH-GN", 90, False)]),
    ("Wolf-Dieter Schellig (Hausgeld Berlin)", "Wolf-Dieter Schellig", None, "MIETE", [("B-GGE", 100, True)]),
    ("Schomerus & Partner (Buchhaltung)", "Schomerus", None, "SACH_DIENSTLEISTUNGEN", [("Z-BH", 100, False)]),
    ("Microsoft (Software-Lizenzen)", "Microsoft", None, "IT_SOFTWARE", [("Z-IT", 100, False)]),
    ("Personio (HR-Software)", "Personio", None, "IT_SOFTWARE", [("Z-HR", 100, False)]),
    ("LinkedIn (Marketing)", "LinkedIn", None, "SACH_MARKETING", [("Z-FR-AUS", 100, False)]),
    ("Meta / Facebook (Marketing)", "Meta Platforms", None, "SACH_MARKETING", [("Z-FR-AUS", 100, False)]),
    ("Deutsche Bahn (Reisekosten)", "DB Vertrieb", None, "SACH_REISE", [("Z-GF", 100, False)]),
    ("UNION Versicherung", "UNION Versicherung", None, "VERSICHERUNG", [("Z-GF", 100, False)]),
]

PILOT_MEASURE = {
    "funder_name": "Land Berlin / Landesamt für Gesundheit und Soziales (LAGeSo)",
    "funder_typ": FunderTyp.MINISTERIUM,
    "measure_name": "Öffentliche Zuwendungen Berlin 2025",
    "budget_gesamt": Decimal("31937.73"),
    "foerderquote": Decimal("100"),
    "laufzeit_von": date(2025, 1, 1),
    "laufzeit_bis": date(2025, 12, 31),
    "antragsnummer": None,
}


# ─────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────
def _log(prefix: str, msg: str) -> None:
    print(f"  {prefix} {msg}")


def _get(db: Session, model, **filters):
    return db.execute(select(model).filter_by(**filters)).scalar_one_or_none()


def _backup_dir() -> Path:
    p = Path.cwd() / "backups"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _ts() -> str:
    # Deterministic-enough filename; uses wall clock (CLI context, not a workflow).
    return datetime.now().strftime("%Y-%m-%dT%H-%M-%S")


# ─────────────────────────────────────────────
# Org resolution
# ─────────────────────────────────────────────
def find_org(db: Session, args) -> Organization:
    if args.org_id:
        org = _get(db, Organization, id=args.org_id)
        if not org:
            raise SystemExit(f"Org mit id={args.org_id} nicht gefunden.")
        return org
    org = _get(db, Organization, name=args.org_name)
    if org:
        return org
    if args.no_create_org:
        existing = db.execute(select(Organization.id, Organization.name)).all()
        listing = "\n".join(f"  {i}  {n}" for i, n in existing)
        raise SystemExit(
            f'Org "{args.org_name}" nicht gefunden. Existierende Orgs:\n{listing}'
        )
    org = Organization(
        name=args.org_name, rechtsform=Rechtsform.EV, regelarbeitszeit_stunden=Decimal("39")
    )
    db.add(org)
    db.flush()
    print(f'\n+ Org neu angelegt: "{org.name}" (id: {org.id})')
    print("  Rechtsform = EV, regelarbeitszeit_stunden = 39 — bei Bedarf anpassen.")
    return org


# ─────────────────────────────────────────────
# Sections
# ─────────────────────────────────────────────
def seed_fiscal_year(db: Session, org_id: str) -> str:
    print("\n# FiscalYear 2025")
    fy = _get(db, FiscalYear, org_id=org_id, jahr=2025)
    if fy:
        _log("·", f"2025 existiert (Status: {fy.status})")
        return fy.id
    fy = FiscalYear(
        org_id=org_id, jahr=2025, beginn=date(2025, 1, 1), ende=date(2025, 12, 31),
        status=FiscalYearStatus.OFFEN,
    )
    db.add(fy)
    db.flush()
    _log("+", "FiscalYear 2025 angelegt")
    return fy.id


def seed_bank_accounts(db: Session, org_id: str, fiscal_year_id: str) -> None:
    print("\n# BankAccounts (9 × BFS-SozialBank)")
    for code, bez, iban, bic, bankname, saldo in BANK_ACCOUNTS:
        collision = _get(db, BankAccount, iban=iban)
        if collision and collision.org_id != org_id:
            _log("⚠", f"IBAN {iban} gehört bereits einer anderen Org — überspringe {code}")
            continue
        acc = _get(db, BankAccount, org_id=org_id, code=code)
        if acc:
            acc.bezeichnung, acc.iban, acc.bic = bez, iban, bic
            acc.bankname, acc.typ = bankname, AccountTyp.BANK
            _log("↻", f"{code}  {bez}  {iban}")
        else:
            acc = BankAccount(
                org_id=org_id, code=code, bezeichnung=bez, typ=AccountTyp.BANK,
                iban=iban, bic=bic, bankname=bankname,
            )
            db.add(acc)
            db.flush()
            _log("+", f"{code}  {bez}  {iban}")
        target = Decimal(saldo)
        ob = _get(db, OpeningBalance, bank_account_id=acc.id, fiscal_year_id=fiscal_year_id)
        if ob:
            if ob.saldo_eroeffnung != target:
                ob.saldo_eroeffnung, ob.datum = target, date(2025, 1, 1)
                _log("↻", f"    Eröffnung 2025: {target} €")
        else:
            db.add(OpeningBalance(
                bank_account_id=acc.id, fiscal_year_id=fiscal_year_id,
                saldo_eroeffnung=target, datum=date(2025, 1, 1),
            ))
            _log("+", f"    Eröffnung 2025: {target} €")
    db.flush()


def seed_cost_centers(db: Session, org_id: str) -> dict[str, str]:
    print("\n# CostCenters (6 Parents + 24 Children + 1 Standalone = 31)")
    code_to_id: dict[str, str] = {}

    def upsert(code, name, typ, parent_id):
        existing = _get(db, CostCenter, org_id=org_id, code=code)
        if existing:
            existing.name, existing.typ, existing.parent_id = name, typ, parent_id
            _log("↻" if False else "·", f"{code:<10} {name}")
            return existing.id
        row = CostCenter(org_id=org_id, code=code, name=name, typ=typ, parent_id=parent_id)
        db.add(row)
        db.flush()
        _log("+", f"{code:<10} {name}")
        return row.id

    for code, name, typ, parent in COST_CENTERS:
        if parent is None:
            code_to_id[code] = upsert(code, name, typ, None)
    for code, name, typ, parent in COST_CENTERS:
        if parent is not None:
            pid = code_to_id.get(parent)
            if not pid:
                _log("⚠", f'Parent "{parent}" für {code} nicht gefunden — überspringe')
                continue
            code_to_id[code] = upsert(code, name, typ, pid)
    db.flush()
    return code_to_id


def seed_umlage_source_scopes(db: Session, org_id: str, cc: dict[str, str]) -> None:
    print(f"\n# UmlageSourceScopes ({len(UMLAGE_SOURCE_SCOPES)})")
    for spec in UMLAGE_SOURCE_SCOPES:
        missing = [c for c in spec["cost_center_codes"] if c not in cc]
        if missing:
            _log("⚠", f'Scope "{spec["name"]}" unbekannte KSTs: {", ".join(missing)} — überspringe')
            continue
        scope = _get(db, UmlageSourceScope, org_id=org_id, name=spec["name"])
        expected = {cc[c] for c in spec["cost_center_codes"]}
        if scope:
            scope.beschreibung = spec["beschreibung"]
            db.execute(
                UmlageSourceScopeCostCenter.__table__.delete().where(
                    UmlageSourceScopeCostCenter.umlage_source_scope_id == scope.id
                )
            )
            for ccid in expected:
                db.add(UmlageSourceScopeCostCenter(
                    org_id=org_id, umlage_source_scope_id=scope.id, cost_center_id=ccid
                ))
            _log("↻", f'{spec["name"]}  ({len(expected)} KSTs, Bridge ersetzt)')
        else:
            scope = UmlageSourceScope(org_id=org_id, name=spec["name"], beschreibung=spec["beschreibung"])
            db.add(scope)
            db.flush()
            for ccid in expected:
                db.add(UmlageSourceScopeCostCenter(
                    org_id=org_id, umlage_source_scope_id=scope.id, cost_center_id=ccid
                ))
            _log("+", f'{spec["name"]}  ({len(expected)} KSTs)')
    db.flush()


def seed_allocation_keys(db: Session, org_id: str, cc: dict[str, str]) -> None:
    print(f"\n# AllocationKeys ({len(ALLOCATION_KEYS)})")
    for spec in ALLOCATION_KEYS:
        total = sum(p[1] for p in spec["positions"])
        if abs(total - 100) > 0.001:
            _log("⚠", f'Schlüssel "{spec["name"]}" Summe {total} ≠ 100 — überspringe')
            continue
        missing = [c for c, _ in spec["positions"] if c not in cc]
        if missing:
            _log("⚠", f'Schlüssel "{spec["name"]}" unbekannte KSTs: {", ".join(missing)} — überspringe')
            continue
        existing = db.execute(
            select(AllocationKey).where(
                AllocationKey.org_id == org_id, AllocationKey.name == spec["name"],
                AllocationKey.parent_key_id.is_(None), AllocationKey.ist_aktiv.is_(True),
            )
        ).scalar_one_or_none()
        if existing:
            existing.basis = spec["basis"]
            existing.gueltig_von = spec["gueltig_von"]
            existing.gueltig_bis = spec["gueltig_bis"]
            db.execute(
                AllocationKeyPosition.__table__.delete().where(
                    AllocationKeyPosition.allocation_key_id == existing.id
                )
            )
            for code, prozent in spec["positions"]:
                db.add(AllocationKeyPosition(
                    org_id=org_id, allocation_key_id=existing.id,
                    cost_center_id=cc[code], prozent=Decimal(str(prozent)),
                ))
            _log("↻", f'{spec["name"]}  ({len(spec["positions"])} Positionen ersetzt)')
        else:
            ak = AllocationKey(
                org_id=org_id, name=spec["name"], basis=spec["basis"],
                gueltig_von=spec["gueltig_von"], gueltig_bis=spec["gueltig_bis"],
                ist_aktiv=True, parent_key_id=None,
            )
            db.add(ak)
            db.flush()
            for code, prozent in spec["positions"]:
                db.add(AllocationKeyPosition(
                    org_id=org_id, allocation_key_id=ak.id,
                    cost_center_id=cc[code], prozent=Decimal(str(prozent)),
                ))
            _log("+", f'{spec["name"]}  ({len(spec["positions"])} Positionen)')
    db.flush()


def seed_funding_measure(db: Session, org_id: str, skip: bool) -> str | None:
    if skip:
        return None
    print("\n# Funder + FundingMeasure")
    funder = _get(db, Funder, org_id=org_id, name=PILOT_MEASURE["funder_name"])
    if not funder:
        funder = Funder(org_id=org_id, name=PILOT_MEASURE["funder_name"], typ=PILOT_MEASURE["funder_typ"])
        db.add(funder)
        db.flush()
        _log("+", f"Funder: {PILOT_MEASURE['funder_name']}")
    else:
        _log("·", f"Funder: {PILOT_MEASURE['funder_name']}")

    existing = _get(db, FundingMeasure, org_id=org_id, name=PILOT_MEASURE["measure_name"])
    if existing:
        _log("·", f"FundingMeasure: {PILOT_MEASURE['measure_name']}  (vorhanden, Edits bleiben)")
        return existing.id
    measure = FundingMeasure(
        org_id=org_id, funder_id=funder.id, name=PILOT_MEASURE["measure_name"],
        budget_gesamt=PILOT_MEASURE["budget_gesamt"], foerderquote=PILOT_MEASURE["foerderquote"],
        laufzeit_von=PILOT_MEASURE["laufzeit_von"], laufzeit_bis=PILOT_MEASURE["laufzeit_bis"],
        antragsnummer=PILOT_MEASURE["antragsnummer"],
        mittelabruf_verfahren=MittelabrufVerfahren.ABRUF, status=FundingMeasureStatus.AKTIV,
        finanzierungsart=FinanzierungsartTyp.FESTBETRAG,
    )
    db.add(measure)
    db.flush()
    _log("+", f"FundingMeasure: {PILOT_MEASURE['measure_name']}")
    _log("—", "   Werte sind Platzhalter — Bescheid-Import oder Edit-UI nutzen.")
    return measure.id


def find_berlin_measure_id(db: Session, org_id: str, args) -> str | None:
    if args.berlin_measure_id:
        m = _get(db, FundingMeasure, id=args.berlin_measure_id)
        if not m or m.org_id != org_id:
            _log("⚠", f'--berlin-measure-id "{args.berlin_measure_id}" nicht gefunden/andere Org — ignoriere')
            return None
        return m.id
    if args.berlin_measure_name:
        m = _get(db, FundingMeasure, org_id=org_id, name=args.berlin_measure_name)
        if not m:
            _log("⚠", f'--berlin-measure-name "{args.berlin_measure_name}" nicht gefunden — ignoriere')
            return None
        return m.id
    bgge = _get(db, CostCenter, org_id=org_id, code="B-GGE")
    if not bgge:
        return None
    rows = db.execute(
        select(FundingMeasure.id).join(
            FundingMeasureCostCenter,
            FundingMeasureCostCenter.funding_measure_id == FundingMeasure.id,
        ).where(
            FundingMeasure.org_id == org_id,
            FundingMeasureCostCenter.cost_center_id == bgge.id,
        )
    ).scalars().all()
    if len(rows) == 1:
        return rows[0]
    if len(rows) > 1:
        _log("⚠", f"{len(rows)} Maßnahmen mit KST B-GGE — Berlin-Verknüpfung übersprungen.")
    return None


def seed_booking_rules(db: Session, org_id: str, cc: dict[str, str], args) -> None:
    print(f"\n# BookingRules ({len(BOOKING_RULES)} Rules)")
    kb_rows = db.execute(
        select(Kostenbereich.id, Kostenbereich.code).where(Kostenbereich.org_id.is_(None))
    ).all()
    kb_code_to_id = {code: id_ for id_, code in kb_rows}

    berlin_measure_id = find_berlin_measure_id(db, org_id, args)
    if berlin_measure_id:
        _log("·", f"Berlin-Maßnahme gefunden ({berlin_measure_id}) — link_berlin Splits werden verknüpft")
    else:
        _log("·", "Keine Berlin-Maßnahme — link_berlin Splits bleiben unverknüpft")

    # Optional pre-reset with JSON backup (skipped under --reset-all: rules already gone)
    if args.reset_rules and not args.reset_all:
        existing = db.execute(
            select(BookingRule).where(BookingRule.org_id == org_id)
        ).scalars().all()
        if existing:
            backup = [
                {"id": r.id, "name": r.name, "match_auftraggeber": r.match_auftraggeber,
                 "match_verwendungszweck": r.match_verwendungszweck,
                 "set_kostenbereich_id": r.set_kostenbereich_id, "prioritaet": r.prioritaet,
                 "splits": [{"cost_center_id": s.cost_center_id, "prozent": str(s.prozent),
                             "funding_measure_id": s.funding_measure_id,
                             "allocation_prozent": str(s.allocation_prozent) if s.allocation_prozent else None}
                            for s in r.splits]}
                for r in existing
            ]
            path = _backup_dir() / f"booking-rules-{org_id}-{_ts()}.json"
            path.write_text(json.dumps(backup, indent=2, ensure_ascii=False), encoding="utf-8")
            _log("·", f"Backup geschrieben: {path.name} ({len(existing)} Rules)")
            do_reset_rules(db, org_id, _log)

    for i, (name, match_ag, match_vz, set_kb_code, splits) in enumerate(BOOKING_RULES):
        total = sum(s[1] for s in splits)
        if abs(total - 100) > 0.001:
            _log("⚠", f'Regel "{name}" Split-Summe {total} ≠ 100 — überspringe')
            continue
        missing = [s[0] for s in splits if s[0] not in cc]
        if missing:
            _log("⚠", f'Regel "{name}" unbekannte KSTs: {", ".join(missing)} — überspringe')
            continue
        set_kb_id = kb_code_to_id.get(set_kb_code) if set_kb_code else None
        if set_kb_code and not set_kb_id:
            _log("⚠", f'Regel "{name}": unbekannter Kostenbereich "{set_kb_code}" — set_kostenbereich_id leer')

        def build_splits(rule_id):
            for cc_code, prozent, link_berlin in splits:
                db.add(BookingRuleSplit(
                    rule_id=rule_id, cost_center_id=cc[cc_code], prozent=Decimal(str(prozent)),
                    funding_measure_id=berlin_measure_id if link_berlin else None,
                    allocation_prozent=Decimal("100") if (link_berlin and berlin_measure_id) else None,
                ))

        existing = _get(db, BookingRule, org_id=org_id, name=name)
        prioritaet = 100 - i
        if existing:
            existing.match_auftraggeber = match_ag
            existing.match_verwendungszweck = match_vz
            existing.set_kostenbereich_id = set_kb_id
            existing.prioritaet = prioritaet
            existing.aktiv = True
            db.execute(
                BookingRuleSplit.__table__.delete().where(BookingRuleSplit.rule_id == existing.id)
            )
            build_splits(existing.id)
            _log("↻", f"Regel {name}  ({len(splits)} Splits aktualisiert)")
        else:
            rule = BookingRule(
                org_id=org_id, name=name, match_auftraggeber=match_ag,
                match_verwendungszweck=match_vz, set_kostenbereich_id=set_kb_id,
                prioritaet=prioritaet, aktiv=True,
            )
            db.add(rule)
            db.flush()
            build_splits(rule.id)
            _log("+", f"Regel {name}  ({len(splits)} Splits)")
    db.flush()


# ─────────────────────────────────────────────
# Resets
# ─────────────────────────────────────────────
def run_reset_all(db: Session, org_id: str) -> None:
    print("\n# Full-Reset: ALLE Org-Daten löschen (außer Memberships + AuditLog)")
    reset_org_data(db, org_id, ResetOptions(log=_log))
    _log("·", "Reset abgeschlossen — Seed legt Stammdaten neu an")


def run_reset_transactions(db: Session, org_id: str) -> None:
    print("\n# Reset Transaktionen + Allocations + Imports")
    summary = do_reset_transactions(db, org_id, _log)
    if summary.total() > 0:
        path = _backup_dir() / f"transactions-reset-manifest-{org_id}-{_ts()}.json"
        path.write_text(
            json.dumps({"org_id": org_id, "deleted": summary.counts}, indent=2),
            encoding="utf-8",
        )
        _log("·", f"Manifest geschrieben: {path.name}")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="FörderFlow pilot master-data seed (Freunde alter Menschen e.V.)")
    p.add_argument("--org-name", default="Freunde alter Menschen e.V.")
    p.add_argument("--org-id", default=None)
    p.add_argument("--dry-run", action="store_true", help="Validate only — rolls back at the end")
    p.add_argument("--skip-measure", action="store_true")
    p.add_argument("--no-create-org", action="store_true")
    p.add_argument("--reset-rules", action="store_true")
    p.add_argument("--reset-transactions", action="store_true")
    p.add_argument("--reset-all", action="store_true")
    p.add_argument("--berlin-measure-id", default=None)
    p.add_argument("--berlin-measure-name", default=None)
    return p.parse_args(argv)


def run(db: Session, args: argparse.Namespace) -> None:
    print("\n════════════════════════════════════════════════════════")
    print(f"  Stammdaten-Seed Pilotkunde: {args.org_name}")
    if args.dry_run:
        print("  ⚠ DRY-RUN — keine Änderungen werden geschrieben (Rollback am Ende)")
    if args.skip_measure:
        print("  → FundingMeasure wird übersprungen")
    if args.reset_all:
        print("  → ALLE Org-Daten werden gelöscht (Memberships + AuditLog bleiben)")
    elif args.reset_transactions:
        print("  → Transaktionen + Allocations + Imports werden gelöscht")
    print("════════════════════════════════════════════════════════")

    org = find_org(db, args)
    print(f"\n→ Org: {org.name}  (id: {org.id})")

    if args.reset_all:
        run_reset_all(db, org.id)
    elif args.reset_transactions:
        run_reset_transactions(db, org.id)

    fy_id = seed_fiscal_year(db, org.id)
    seed_bank_accounts(db, org.id, fy_id)
    cc = seed_cost_centers(db, org.id)
    seed_umlage_source_scopes(db, org.id, cc)
    seed_allocation_keys(db, org.id, cc)
    seed_funding_measure(db, org.id, args.skip_measure)
    seed_booking_rules(db, org.id, cc, args)

    if args.dry_run:
        db.rollback()
        print("\n(DRY-RUN — Transaktion zurückgerollt, nichts geschrieben)")
    else:
        db.commit()

    print("\n════════════════════════════════════════════════════════")
    print("  Seed abgeschlossen.")
    print("════════════════════════════════════════════════════════\n")


def main(argv=None) -> None:
    args = parse_args(argv)
    db = SessionLocal()
    try:
        run(db, args)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
