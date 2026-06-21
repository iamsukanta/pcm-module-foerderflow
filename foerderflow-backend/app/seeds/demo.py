"""Demo-data seed — full port of monolith `scripts/seed-demo.ts`.

Prepares the account jade.dyett@gmail.com / org "Zukunft für Kinder" so every
dashboard/report looks alive. The live demo steps (Bescheid import, CSV import,
Verwendungsnachweis creation) are deliberately left open.

Idempotent: existence-checked before each insert; re-running creates no duplicates.

Run:      python -m app.seeds.demo
Reset:    DEMO_RESET=1 python -m app.seeds.demo        (wipes org data, keeps user+org)
Override: DEMO_USER_EMAIL=... DEMO_ORG_NAME=... DEMO_TODAY=YYYY-MM-DD python -m app.seeds.demo

Unlike the monolith (which requires the user/org/membership to pre-exist), this
port creates them if missing — friendlier for a fresh dev DB.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.allocation import AllocationKey, AllocationKeyPosition
from app.models.auth import OrganizationMembership, User
from app.models.enums import (
    AccountTyp,  # noqa: F401  (kept for parity; bank accounts not seeded in demo)
    AllocationBasis,
    BescheidQuelle,
    CostCenterTyp,
    EigenanteilTyp,
    FinanzierungsartTyp,
    FiscalYearStatus,
    FristBezug,
    FunderTyp,
    FundingMeasureStatus,
    FundingRuleTyp,
    MittelabrufStatus,
    MittelabrufVerfahren,
    OrgRole,
    Rechtsform,
    TransactionStatus,
    TransactionTyp,
    Tarifwerk,
    Vertragsart,
    VerwendungsnachweisStatus,
    VerwendungsnachweisTyp,
)
from app.models.finanzplan import (
    FinanzplanPosition,
    FinanzplanPositionKostenbereich,
    VerwNachweis,
)
from app.models.funding import (
    BescheidDokument,
    FundingMeasure,
    FundingMeasureCostCenter,
    FundingRule,
)
from app.models.master import (
    CostCenter,
    FiscalYear,
    Funder,
    FunderNachweisFrist,
    Kostenbereich,
)
from app.models.mittelabruf import Mittelabruf
from app.models.organization import Organization
from app.models.payroll import (
    Employee,
    EmployeeContract,
    EmployerGrossFactor,
    MonthlyPayroll,
    PayrollAllocation,
    TarifTabelle,
)
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel, SalaryTariff
from app.models.transaction import (
    BankAccount,  # noqa: F401  (parity)
    FundAllocation,
    Transaction,
    TransactionSplit,
)
from app.models.booking_rule import BookingRule, BookingRuleSplit
from app.seeds import system_data
from app.seeds.reset import ResetOptions, reset_org_data
from app.services.personal.berechnung import berechne_gehalt

USER_EMAIL = os.getenv("DEMO_USER_EMAIL", "jade.dyett@gmail.com")
ORG_NAME = os.getenv("DEMO_ORG_NAME", "Zukunft für Kinder")
RESET = os.getenv("DEMO_RESET") == "1"
TODAY = (
    date.fromisoformat(os.environ["DEMO_TODAY"])
    if os.getenv("DEMO_TODAY")
    else date(2026, 5, 20)
)
# Optional demo Bescheid PDF; skipped gracefully if absent (matches monolith).
BESCHEID_PDF = Path(
    os.getenv(
        "DEMO_BESCHEID_PDF",
        str(Path.cwd() / "public" / "demo-assets" / "zuwendungsbescheid-demo.pdf"),
    )
)


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _add_days(base: date, days: int) -> date:
    return base + timedelta(days=days)


def _first_of_month(year: int, month: int) -> date:
    return date(year, month, 1)


def _round2(n: float | Decimal) -> Decimal:
    return Decimal(str(n)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _get(db: Session, model, **filters):
    return db.execute(select(model).filter_by(**filters)).scalar_one_or_none()


# ─────────────────────────────────────────────────────────────────────
# 1. User & Org & Membership
# ─────────────────────────────────────────────────────────────────────
def ensure_identity(db: Session) -> tuple[Organization, User]:
    user = _get(db, User, email=USER_EMAIL)
    if not user:
        user = User(email=USER_EMAIL, name="Jade Dyett", is_super_admin=True)
        db.add(user)
        db.flush()
    org = _get(db, Organization, name=ORG_NAME)
    if not org:
        org = Organization(
            name=ORG_NAME,
            rechtsform=Rechtsform.EV,
            regelarbeitszeit_stunden=Decimal("39.00"),
        )
        db.add(org)
        db.flush()
    if not _get(db, OrganizationMembership, org_id=org.id, user_id=user.id):
        db.add(
            OrganizationMembership(org_id=org.id, user_id=user.id, role=OrgRole.ADMIN)
        )
        db.flush()
    print(f"✓ User {user.id}, Org {org.id}")
    return org, user


# ─────────────────────────────────────────────────────────────────────
# 2. System taxonomies (must exist before the rest)
# ─────────────────────────────────────────────────────────────────────
def ensure_system_data(db: Session) -> None:
    n_kb = db.execute(select(Kostenbereich.id)).scalars().all()
    n_tarif = db.execute(
        select(TarifTabelle.id).where(
            TarifTabelle.tarifwerk == Tarifwerk.TVOEDD, TarifTabelle.jahr == 2025
        )
    ).scalars().all()
    if len(n_kb) < 18:
        system_data.seed_kostenbereiche(db)
    if len(n_tarif) < 90:
        system_data.seed_tvoedd_2025(db)
    db.flush()
    print("✓ System-Taxonomien (Kostenbereiche + TVöD) vorhanden")


# ─────────────────────────────────────────────────────────────────────
# 3. FiscalYear
# ─────────────────────────────────────────────────────────────────────
def ensure_fiscal_year(db: Session, org_id: str, jahr: int, geschlossen: bool) -> FiscalYear:
    fy = _get(db, FiscalYear, org_id=org_id, jahr=jahr)
    if not fy:
        fy = FiscalYear(
            org_id=org_id,
            jahr=jahr,
            beginn=_d(f"{jahr}-01-01"),
            ende=_d(f"{jahr}-12-31"),
            status=FiscalYearStatus.GESCHLOSSEN if geschlossen else FiscalYearStatus.OFFEN,
            geschlossen_am=datetime(jahr + 1, 2, 15) if geschlossen else None,
        )
        db.add(fy)
        db.flush()
    print(f"  ✓ Haushaltsjahr {jahr} ({fy.status})")
    return fy


# ─────────────────────────────────────────────────────────────────────
# 4. CostCenters
# ─────────────────────────────────────────────────────────────────────
def ensure_cost_centers(db: Session, org_id: str) -> dict[str, str]:
    items = [
        ("KST-101", "Hausaufgabenhilfe", CostCenterTyp.PROJECT),
        ("KST-102", "Sommer-Ferienprogramm", CostCenterTyp.PROJECT),
        ("KST-103", "Sprachförderung Grundschule", CostCenterTyp.PROJECT),
        ("KST-104", "Schulmentoring", CostCenterTyp.PROJECT),
        ("KST-105", "Inklusive Spielgruppen", CostCenterTyp.PROJECT),
        ("KST-201", "Verwaltung", CostCenterTyp.OVERHEAD),
        ("KST-202", "Geschäftsstelle", CostCenterTyp.OVERHEAD),
        ("KST-203", "Fundraising", CostCenterTyp.OVERHEAD),
    ]
    out: dict[str, str] = {}
    for code, name, typ in items:
        row = _get(db, CostCenter, org_id=org_id, code=code)
        if not row:
            row = CostCenter(org_id=org_id, code=code, name=name, typ=typ, ist_aktiv=True)
            db.add(row)
        else:
            row.name, row.typ, row.ist_aktiv = name, typ, True
        db.flush()
        out[code] = row.id
    print(f"  ✓ Kostenstellen: {len(items)}")
    return out


# ─────────────────────────────────────────────────────────────────────
# 5. Funders (+ VN default deadline)
# ─────────────────────────────────────────────────────────────────────
def ensure_funders(db: Session, org_id: str) -> dict[str, str]:
    items = [
        ("AKTION_MENSCH", "Aktion Mensch", FunderTyp.STIFTUNG,
         (FristBezug.DURCHFUEHRUNG_ENDE, 90, "Stiftungs-Standard: VN binnen 3 Monaten nach Vorhabensende")),
        ("STADT_BERLIN", "Stadt Berlin Jugendamt", FunderTyp.KOMMUNE,
         (FristBezug.HHJ_ENDE, 120, "Berliner Standard: VN bis 30.04. nach Haushaltsjahr-Ende")),
        ("BMFSFJ", "BMFSFJ", FunderTyp.MINISTERIUM,
         (FristBezug.DURCHFUEHRUNG_ENDE, 180, "Bundesministerium-Standard: VN binnen 6 Monaten nach Vorhabensende (NBest-P 6.1)")),
        ("STIFTUNG_LESEN", "Deutsche Stiftung Lesen", FunderTyp.STIFTUNG, None),
        ("STIFTUNG_KIND", "Stiftung Kinderhilfe", FunderTyp.STIFTUNG, None),
    ]
    out: dict[str, str] = {}
    n_frist = 0
    for key, name, typ, frist in items:
        row = _get(db, Funder, org_id=org_id, name=name)
        if not row:
            row = Funder(org_id=org_id, name=name, typ=typ)
            db.add(row)
            db.flush()
        out[key] = row.id
        if frist:
            bezug, offset, beschreibung = frist
            existing = _get(
                db, FunderNachweisFrist, org_id=org_id, funder_id=row.id,
                nachweis_typ=VerwendungsnachweisTyp.VERWENDUNGSNACHWEIS,
            )
            if existing:
                existing.bezug, existing.tage_offset, existing.beschreibung = bezug, offset, beschreibung
            else:
                db.add(FunderNachweisFrist(
                    org_id=org_id, funder_id=row.id,
                    nachweis_typ=VerwendungsnachweisTyp.VERWENDUNGSNACHWEIS,
                    bezug=bezug, tage_offset=offset, beschreibung=beschreibung,
                ))
            n_frist += 1
    db.flush()
    print(f"  ✓ Fördergeber: {len(items)} ({n_frist} mit VN-Standardfrist)")
    return out


# ─────────────────────────────────────────────────────────────────────
# 6. EmployerGrossFactor
# ─────────────────────────────────────────────────────────────────────
def ensure_employer_gross_factors(db: Session, org_id: str) -> None:
    items = [
        (Vertragsart.FESTANSTELLUNG, Decimal("1.2121")),
        (Vertragsart.MINIJOB, Decimal("1.085")),
        (Vertragsart.WERKVERTRAG, Decimal("1.0")),
    ]
    for va, faktor in items:
        exists = db.execute(
            select(EmployerGrossFactor).where(
                EmployerGrossFactor.org_id == org_id,
                EmployerGrossFactor.vertragsart == va,
                EmployerGrossFactor.gueltig_ab == _d("2025-01-01"),
            )
        ).scalar_one_or_none()
        if exists:
            continue
        db.add(EmployerGrossFactor(
            org_id=org_id, vertragsart=va, faktor=faktor,
            gueltig_ab=_d("2025-01-01"), notiz=f"Demo-Seed: AG-Faktor {va}",
        ))
    db.flush()
    print(f"  ✓ AG-Faktoren: {len(items)}")


# ─────────────────────────────────────────────────────────────────────
# 7. AllocationKeys
# ─────────────────────────────────────────────────────────────────────
def ensure_allocation_keys(db: Session, org_id: str, kst: dict[str, str]) -> None:
    keys = [
        ("Standard Overhead-Verteilung 2026", AllocationBasis.MANUELL,
         [("KST-201", 50.0), ("KST-202", 30.0), ("KST-203", 20.0)]),
        ("Projektmitarbeiter-Verteilung 2026", AllocationBasis.MITARBEITERZAHL,
         [("KST-101", 25.0), ("KST-102", 25.0), ("KST-103", 20.0), ("KST-104", 15.0), ("KST-105", 15.0)]),
    ]
    for name, basis, positions in keys:
        if _get(db, AllocationKey, org_id=org_id, name=name):
            continue
        ak = AllocationKey(
            org_id=org_id, name=name, basis=basis,
            gueltig_von=_d("2026-01-01"), ist_aktiv=True,
        )
        db.add(ak)
        db.flush()
        for code, prozent in positions:
            db.add(AllocationKeyPosition(
                org_id=org_id, allocation_key_id=ak.id,
                cost_center_id=kst[code], prozent=Decimal(str(prozent)),
            ))
    db.flush()
    print(f"  ✓ Verteilungsschlüssel: {len(keys)}")


# ─────────────────────────────────────────────────────────────────────
# 8. FundingMeasures (+ cost centers, rules, finanzplan)
# ─────────────────────────────────────────────────────────────────────
def ensure_funding_measures(
    db: Session, org_id: str, funders: dict[str, str], kst: dict[str, str]
) -> dict[str, dict]:
    kb_rows = db.execute(
        select(Kostenbereich.id, Kostenbereich.code).where(
            Kostenbereich.code.in_(
                ["PERSONAL_FESTANSTELLUNG", "IT_SOFTWARE", "SACH_REISE", "MIETE", "SACH_BUERO"]
            )
        )
    ).all()
    kb = {code: id_ for id_, code in kb_rows}

    specs = [
        dict(
            key="HAUSAUFGABEN", name="Hausaufgabenhilfe Berlin Mitte 2026",
            funder="AKTION_MENSCH", cost_centers=["KST-101"], budget=60000, quote=80,
            von="2026-01-01", bis="2026-12-31", status=FundingMeasureStatus.AKTIV,
            fkz="AM-2026-HAH-0142", finanzierungsart=FinanzierungsartTyp.FEHLBEDARF,
            eigenmittel=12000, drittmittel=0,
            rules=[
                (FundingRuleTyp.KOSTENKATEGORIE_ERLAUBT, "PERSONAL", None, "Personalkosten förderfähig"),
                (FundingRuleTyp.KOSTENKATEGORIE_ERLAUBT, "SACH_BUERO", None, "Bürokosten förderfähig"),
                (FundingRuleTyp.EIGENANTEIL_MIN, "20", "20.00", "Mindesteigenanteil 20%"),
                (FundingRuleTyp.ZWISCHENNACHWEIS_PFLICHT, "true", "true", "Zwischennachweis quartalsweise"),
            ],
            positions=[
                ("1.1", "Personalkosten Projektkoordination", 42000, "PERSONAL_FESTANSTELLUNG"),
                ("2.1", "Sachmittel & Materialien", 12000, "SACH_BUERO"),
                ("3.1", "Anteilige Raumkosten", 6000, "MIETE"),
            ],
        ),
        dict(
            key="SPRACHFOERDERUNG", name="Sprachförderung Grundschule",
            funder="BMFSFJ", cost_centers=["KST-103", "KST-104"], budget=90000, quote=75,
            von="2026-01-01", bis="2026-12-31", status=FundingMeasureStatus.AKTIV,
            fkz="BMFSFJ-2026-SF-0089", finanzierungsart=None, eigenmittel=0, drittmittel=0,
            rules=[
                (FundingRuleTyp.KOSTENKATEGORIE_ERLAUBT, "PERSONAL", None, "Personalkosten förderfähig"),
                (FundingRuleTyp.PERSONALKOSTEN_HOECHSTSATZ, "PERSONAL_FESTANSTELLUNG", "5500", "max 5500 EUR/VZÄ-Monat"),
                (FundingRuleTyp.VERWENDUNGSFRIST_TAGE, "42", "42", "Verwendungsfrist 42 Tage"),
            ],
            positions=[
                ("P-1", "Personalkosten 1,5 VZÄ Sprachförderkraft", 65000, "PERSONAL_FESTANSTELLUNG"),
                ("S-1", "Lernmaterialien & Lizenzen", 15000, "IT_SOFTWARE"),
                ("R-1", "Fortbildungs- und Reisekosten", 6000, "SACH_REISE"),
                ("M-1", "Raumkosten anteilig", 4000, "MIETE"),
            ],
        ),
        dict(
            key="FERIEN", name="Sommer-Ferienprogramm 2025",
            funder="STADT_BERLIN", cost_centers=["KST-102"], budget=35000, quote=100,
            von="2025-06-01", bis="2025-09-30", status=FundingMeasureStatus.ABGESCHLOSSEN,
            fkz="Bln-JA-2025-SOM-014", finanzierungsart=None, eigenmittel=0, drittmittel=0,
            rules=[
                (FundingRuleTyp.KOSTENKATEGORIE_ERLAUBT, "PERSONAL", None, "Honorare Ferienbetreuende förderfähig"),
                (FundingRuleTyp.BELEGPFLICHT_SPEZIAL, "SACH_BESCHAFFUNG", None, "Belegpflicht für Beschaffungen >150€"),
            ],
            positions=[
                ("1", "Honorare Ferienbetreuung", 22000, "PERSONAL_FESTANSTELLUNG"),
                ("2", "Materialkosten Workshops", 9000, "SACH_BUERO"),
                ("3", "Reise- und Ausflugskosten", 4000, "SACH_REISE"),
            ],
        ),
    ]

    out: dict[str, dict] = {}
    for s in specs:
        measure = _get(db, FundingMeasure, org_id=org_id, name=s["name"])
        if not measure:
            art = s["finanzierungsart"] or FinanzierungsartTyp.ANTEIL
            is_fb = art == FinanzierungsartTyp.FEHLBEDARF
            measure = FundingMeasure(
                org_id=org_id, funder_id=funders[s["funder"]], name=s["name"],
                budget_gesamt=Decimal(str(s["budget"])), foerderquote=Decimal(str(s["quote"])),
                laufzeit_von=_d(s["von"]), laufzeit_bis=_d(s["bis"]),
                mittelabruf_verfahren=MittelabrufVerfahren.ANFORDERUNG, status=s["status"],
                foerderkennzeichen=s["fkz"], finanzierungsart=art,
                eigenanteil_typ=EigenanteilTyp.KOFINANZIERUNG,
                eigenmittel_betrag=Decimal(str(s["eigenmittel"])) if is_fb else None,
                drittmittel_betrag=Decimal(str(s["drittmittel"])) if is_fb else None,
                mwst_foerderfahig=True, mwst_satz_prozent=Decimal("19"),
                verwaltungspauschale_erlaubt=False, budget_flexibilitaet_prozent=Decimal("20"),
            )
            db.add(measure)
            db.flush()

        for cc_code in s["cost_centers"]:
            if not db.execute(
                select(FundingMeasureCostCenter).where(
                    FundingMeasureCostCenter.funding_measure_id == measure.id,
                    FundingMeasureCostCenter.cost_center_id == kst[cc_code],
                )
            ).scalar_one_or_none():
                db.add(FundingMeasureCostCenter(
                    org_id=org_id, funding_measure_id=measure.id, cost_center_id=kst[cc_code]
                ))

        existing_rules = db.execute(
            select(FundingRule).where(FundingRule.funding_measure_id == measure.id)
        ).scalars().all()
        if not existing_rules:
            for typ, schluessel, wert, beschreibung in s["rules"]:
                db.add(FundingRule(
                    org_id=org_id, funding_measure_id=measure.id, typ=typ,
                    schluessel=schluessel, wert=wert, beschreibung=beschreibung,
                ))

        fp_pos: dict[str, str] = {}
        for code, bez, betrag, kb_code in s["positions"]:
            pos = db.execute(
                select(FinanzplanPosition).where(
                    FinanzplanPosition.funding_measure_id == measure.id,
                    FinanzplanPosition.positionscode == code,
                )
            ).scalar_one_or_none()
            if not pos:
                pos = FinanzplanPosition(
                    org_id=org_id, funding_measure_id=measure.id, positionscode=code,
                    bezeichnung=bez, betrag_bewilligt=Decimal(str(betrag)),
                    ueberziehung_limit_pct=Decimal("20"), sort_order=0,
                )
                db.add(pos)
                db.flush()
                if kb.get(kb_code):
                    db.add(FinanzplanPositionKostenbereich(
                        org_id=org_id, finanzplan_position_id=pos.id,
                        kostenbereich_id=kb[kb_code], foerderfahig_anteil=Decimal("1.0"),
                    ))
            fp_pos[code] = pos.id

        out[s["key"]] = {"id": measure.id, "name": measure.name, "fp": fp_pos}
    db.flush()
    print(f"  ✓ Fördermaßnahmen: {len(specs)} (mit Finanzplan & Regeln)")
    return out


# ─────────────────────────────────────────────────────────────────────
# 9. Bescheid documents (optional demo PDF)
# ─────────────────────────────────────────────────────────────────────
def ensure_bescheid_dokumente(db: Session, org_id: str, measures: dict[str, dict]) -> None:
    if not BESCHEID_PDF.is_file():
        print(f"  ⚠ Demo-Bescheid-PDF nicht gefunden unter {BESCHEID_PDF} — überspringe")
        return
    data = BESCHEID_PDF.read_bytes()
    count = 0
    for key in measures:
        m = measures[key]
        safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in m["name"])
        filename = f"Zuwendungsbescheid_{safe}.pdf"
        existing = _get(db, BescheidDokument, funding_measure_id=m["id"])
        if existing:
            existing.filename, existing.size_bytes = filename, len(data)
            existing.bytes, existing.quelle = data, BescheidQuelle.OCR_IMPORT
        else:
            db.add(BescheidDokument(
                org_id=org_id, funding_measure_id=m["id"], filename=filename,
                mime_type="application/pdf", size_bytes=len(data), bytes=data,
                quelle=BescheidQuelle.OCR_IMPORT,
            ))
        count += 1
    db.flush()
    print(f"  ✓ Bescheid-PDFs hinterlegt: {count}")


# ─────────────────────────────────────────────────────────────────────
# 10. Employees + Contracts
# ─────────────────────────────────────────────────────────────────────
def ensure_employees(db: Session, org_id: str) -> list[dict]:
    tarif_rows = db.execute(
        select(TarifTabelle.entgeltgruppe, TarifTabelle.stufe, TarifTabelle.betrag).where(
            TarifTabelle.tarifwerk == Tarifwerk.TVOEDD, TarifTabelle.jahr == 2025
        )
    ).all()
    tarif = {f"{eg}-{st}": float(b) for eg, st, b in tarif_rows}

    items = [
        dict(code="MA-001", vorname="Sandra", nachname="Becker",
             email="sandra.becker@zukunft-fuer-kinder.example", eintritt="2024-01-15",
             va=Vertragsart.FESTANSTELLUNG, hours=39, tarif="E10-3", eg="E10", stufe=3),
        dict(code="MA-002", vorname="Mehmet", nachname="Yilmaz",
             email="mehmet.yilmaz@zukunft-fuer-kinder.example", eintritt="2024-08-01",
             va=Vertragsart.FESTANSTELLUNG, hours=32, tarif="E9a-2", eg="E9a", stufe=2),
        dict(code="MA-003", vorname="Lisa", nachname="Hoffmann",
             email="lisa.hoffmann@zukunft-fuer-kinder.example", eintritt="2023-03-01",
             va=Vertragsart.FESTANSTELLUNG, hours=39, tarif="E8-4", eg="E8", stufe=4),
        dict(code="MA-004", vorname="Tobias", nachname="Wagner",
             email="tobias.wagner@zukunft-fuer-kinder.example", eintritt="2025-09-01",
             va=Vertragsart.MINIJOB, hours=10, base_override=556),
    ]
    refs: list[dict] = []
    for it in items:
        base = it.get("base_override") or (tarif.get(it.get("tarif"), 3500) if it.get("tarif") else 3500)
        emp = _get(db, Employee, org_id=org_id, employee_code=it["code"])
        if not emp:
            emp = Employee(
                org_id=org_id, employee_code=it["code"], vorname=it["vorname"],
                nachname=it["nachname"], email=it["email"],
                eintrittsdatum=_d(it["eintritt"]), ist_aktiv=True,
            )
            db.add(emp)
            db.flush()
        has_contract = db.execute(
            select(EmployeeContract).where(EmployeeContract.employee_id == emp.id)
        ).scalar_one_or_none()
        if not has_contract:
            db.add(EmployeeContract(
                org_id=org_id, employee_id=emp.id, vertragsart=it["va"],
                assigned_hours=Decimal(str(it["hours"])), base_salary=Decimal(str(base)),
                tarifwerk=Tarifwerk.TVOEDD if it.get("eg") else None,
                entgeltgruppe=it.get("eg"), stufe=it.get("stufe"),
                gueltig_ab=_d(it["eintritt"]),
            ))
        refs.append(dict(id=emp.id, code=it["code"], va=it["va"],
                         base=float(base), hours=it["hours"]))
    db.flush()
    print(f"  ✓ Mitarbeiter + Verträge: {len(items)}")
    return refs


# ─────────────────────────────────────────────────────────────────────
# 11. MonthlyPayroll + PayrollAllocation (Jan–März 2026)
# ─────────────────────────────────────────────────────────────────────
def ensure_payrolls(
    db: Session, org_id: str, employees: list[dict], kst: dict[str, str], fy2026: FiscalYear
) -> None:
    standard_hours = 39
    months = [_first_of_month(2026, m) for m in (1, 2, 3)]
    alloc_by_emp = {
        "MA-001": [("KST-101", 100)],
        "MA-002": [("KST-103", 100)],
        "MA-003": [("KST-201", 60), ("KST-202", 40)],
        "MA-004": [("KST-104", 100)],
    }
    count = 0
    for emp in employees:
        factor = 1.2121 if emp["va"] == Vertragsart.FESTANSTELLUNG else (
            1.085 if emp["va"] == Vertragsart.MINIJOB else 1.0
        )
        for monat in months:
            if _get(db, MonthlyPayroll, org_id=org_id, employee_id=emp["id"], monat=monat):
                continue
            calc = berechne_gehalt(
                base_salary=emp["base"], assigned_hours=emp["hours"],
                standard_hours=standard_hours, ag_faktor=factor, components=[],
            )
            payroll = MonthlyPayroll(
                org_id=org_id, employee_id=emp["id"], fiscal_year_id=fy2026.id, monat=monat,
                assigned_hours=Decimal(str(emp["hours"])), standard_hours=Decimal(str(standard_hours)),
                base_salary=Decimal(str(emp["base"])), ag_faktor=Decimal(str(factor)),
                actual_salary=_round2(calc.actual_salary),
                betrag_an_brutto=_round2(calc.an_brutto), betrag_ag_brutto=_round2(calc.ag_brutto),
                quelle="MANUELL",
            )
            db.add(payroll)
            db.flush()
            for code, prozent in alloc_by_emp[emp["code"]]:
                db.add(PayrollAllocation(
                    org_id=org_id, payroll_id=payroll.id, cost_center_id=kst[code],
                    prozent=Decimal(str(prozent)),
                    betrag_anteil=_round2(calc.ag_brutto * (prozent / 100)),
                ))
            count += 1
    db.flush()
    print(f"  ✓ Gehaltsabrechnungen Jan–Mär 2026: {count} neu")


# ─────────────────────────────────────────────────────────────────────
# 11b. Module PCM — salary tariffs (mid-year split) + Wochenstunden
# ─────────────────────────────────────────────────────────────────────
def ensure_pcm_phase1(
    db: Session,
    org_id: str,
    employees: list[dict],
    kst: dict[str, str],
    measures: dict[str, dict],
) -> None:
    """Seed the PCM Phase-1 spine: a TVöD-VKA E10 tariff with a mid-year
    validity split (Jan–Apr / May–open), its salary levels, and one
    Wochenstundenzuweisung for MA-001 → Hausaufgabenhilfe. Idempotent."""

    # Two non-overlapping validity windows = one mid-year tariff change.
    tariff_specs = [
        {"group": "E10", "level": 3, "amount": 4500, "vfrom": "2026-01-01", "vto": "2026-04-30"},
        {"group": "E10", "level": 3, "amount": 4650, "vfrom": "2026-05-01", "vto": None},
    ]
    jan_tariff_id: str | None = None
    for spec in tariff_specs:
        existing = db.execute(
            select(SalaryTariff).where(
                SalaryTariff.org_id == org_id,
                SalaryTariff.tariff_code == "TVöD-VKA",
                SalaryTariff.salary_group == spec["group"],
                SalaryTariff.level == spec["level"],
                SalaryTariff.valid_from == _d(spec["vfrom"]),
            )
        ).scalar_one_or_none()
        if existing:
            tariff = existing
        else:
            tariff = SalaryTariff(
                org_id=org_id,
                tariff_code="TVöD-VKA",
                salary_group=spec["group"],
                level=spec["level"],
                monthly_amount=Decimal(str(spec["amount"])),
                standard_hours=Decimal("39.00"),
                is_proposed=False,
                valid_from=_d(spec["vfrom"]),
                valid_to=_d(spec["vto"]) if spec["vto"] else None,
                bav_rate_pct=Decimal("4.70"),
            )
            db.add(tariff)
            db.flush()
        if spec["vfrom"] == "2026-01-01":
            jan_tariff_id = tariff.id
        # Salary levels (grade euro amounts) attached to each tariff row.
        for level_no, amount, months in ((3, spec["amount"], 60), (4, spec["amount"] + 180, None)):
            if not db.execute(
                select(SalaryLevel).where(
                    SalaryLevel.tariff_id == tariff.id,
                    SalaryLevel.salary_group == spec["group"],
                    SalaryLevel.level_no == level_no,
                )
            ).scalar_one_or_none():
                db.add(SalaryLevel(
                    org_id=org_id, tariff_id=tariff.id, salary_group=spec["group"],
                    level_no=level_no, monthly_amount=Decimal(str(amount)),
                    months_to_next_level=months,
                ))
    db.flush()

    # One Wochenstundenzuweisung: MA-001 → KST-101 / Hausaufgabenhilfe.
    ma001 = next((e for e in employees if e["code"] == "MA-001"), None)
    measure = measures.get("HAUSAUFGABEN")
    n_wsz = 0
    if ma001 and measure:
        contract = db.execute(
            select(EmployeeContract).where(EmployeeContract.employee_id == ma001["id"])
        ).scalar_one_or_none()
        if contract:
            # Link the contract to the (Jan–Apr) tariff to demonstrate the FK.
            if jan_tariff_id and contract.salary_tariff_id is None:
                contract.salary_tariff_id = jan_tariff_id
            # A near-term Stufenaufstieg so the Progression dashboard (P-T) shows
            # a realistic upcoming promotion in the demo data.
            if contract.next_level_date is None:
                contract.next_level_date = _d("2026-08-01")
            exists = db.execute(
                select(WochenstundenZuweisung).where(
                    WochenstundenZuweisung.employee_id == ma001["id"],
                    WochenstundenZuweisung.cost_center_id == kst["KST-101"],
                    WochenstundenZuweisung.effective_date == _d("2026-01-01"),
                )
            ).scalar_one_or_none()
            if not exists:
                db.add(WochenstundenZuweisung(
                    org_id=org_id, employee_id=ma001["id"],
                    salary_assignment_id=contract.id, cost_center_id=kst["KST-101"],
                    funding_measure_id=measure["id"],
                    finanzplan_position_id=measure["fp"].get("1.1"),
                    weekly_hours=Decimal("39.00"), effective_date=_d("2026-01-01"),
                ))
                n_wsz = 1
    db.flush()
    print(f"  ✓ PCM: 2 Tarif-Zeitfenster (E10) + 4 Stufen, {n_wsz} Wochenstunden-Zuweisung")


# ─────────────────────────────────────────────────────────────────────
# 12. Transactions + Splits + confirmed FundAllocations
# ─────────────────────────────────────────────────────────────────────
def ensure_transactions(
    db: Session, org_id: str, fy2025: FiscalYear, fy2026: FiscalYear,
    measures: dict[str, dict], kst: dict[str, str],
) -> None:
    existing = db.execute(
        select(Transaction.id).where(
            Transaction.org_id == org_id, Transaction.notiz.like("[DEMO]%")
        )
    ).scalars().all()
    if existing:
        print(f"  ✓ Demo-Transaktionen existieren bereits ({len(existing)}), überspringe")
        return

    kb_rows = db.execute(select(Kostenbereich.id, Kostenbereich.code)).all()
    code_to_id = {code: id_ for id_, code in kb_rows}

    A, E = TransactionTyp.AUSGABE, TransactionTyp.EINNAHME
    specs = [
        # Hausaufgabenhilfe (FY2026)
        (fy2026, "2026-01-31", 4870.5, A, "Sandra Becker", "Gehalt Januar 2026 — Projektkoordination Hausaufgabenhilfe", "PERSONAL_FESTANSTELLUNG", [("KST-101", 100, "HAUSAUFGABEN", "1.1")]),
        (fy2026, "2026-02-28", 4870.5, A, "Sandra Becker", "Gehalt Februar 2026 — Projektkoordination Hausaufgabenhilfe", "PERSONAL_FESTANSTELLUNG", [("KST-101", 100, "HAUSAUFGABEN", "1.1")]),
        (fy2026, "2026-03-31", 4870.5, A, "Sandra Becker", "Gehalt März 2026 — Projektkoordination Hausaufgabenhilfe", "PERSONAL_FESTANSTELLUNG", [("KST-101", 100, "HAUSAUFGABEN", "1.1")]),
        (fy2026, "2026-02-12", 387.45, A, "Lehrmittel-Verlag GmbH", "Lehr- und Arbeitsmaterial Hausaufgabenhilfe Q1", "SACH_BUERO", [("KST-101", 100, "HAUSAUFGABEN", "2.1")]),
        (fy2026, "2026-03-15", 1500.0, A, "Hausverwaltung Mitte GmbH", "Anteilige Miete Q1/2026 Projekträume", "MIETE", [("KST-101", 100, "HAUSAUFGABEN", "3.1")]),
        (fy2026, "2026-01-20", 12000.0, E, "Aktion Mensch", "1. Mittelabruf Hausaufgabenhilfe 2026", "EINNAHMEN_FOERDERUNG", [("KST-101", 100, "HAUSAUFGABEN", "1.1")]),
        # Sprachförderung (FY2026)
        (fy2026, "2026-01-31", 4823.13, A, "Mehmet Yilmaz", "Gehalt Januar 2026 Sprachförderung", "PERSONAL_FESTANSTELLUNG", [("KST-103", 100, "SPRACHFOERDERUNG", "P-1")]),
        (fy2026, "2026-02-28", 4823.13, A, "Mehmet Yilmaz", "Gehalt Februar 2026 Sprachförderung", "PERSONAL_FESTANSTELLUNG", [("KST-103", 100, "SPRACHFOERDERUNG", "P-1")]),
        (fy2026, "2026-02-05", 248.99, A, "Anton Verlag", "Lizenz Sprachlern-App 12 Monate", "IT_SOFTWARE", [("KST-103", 100, "SPRACHFOERDERUNG", "S-1")]),
        (fy2026, "2026-03-08", 567.4, A, "DB Vertrieb GmbH", "Bahn-Tickets Fortbildung Sprachförderung Köln", "SACH_REISE", [("KST-103", 100, "SPRACHFOERDERUNG", "R-1")]),
        (fy2026, "2026-03-22", 980.0, A, "Hausverwaltung Mitte GmbH", "Anteilige Miete Sprachförderung Q1/2026", "MIETE", [("KST-103", 100, "SPRACHFOERDERUNG", "M-1")]),
        (fy2026, "2026-03-31", 1100.0, A, "Tobias Wagner", "Honorar Schulmentoring März 2026", "PERSONAL_FESTANSTELLUNG", [("KST-104", 100, "SPRACHFOERDERUNG", "P-1")]),
        # Sommer-Ferienprogramm (FY2025)
        (fy2025, "2025-07-15", 8400.0, A, "Honorarkräfte Sammelabrechnung", "Honorare Ferienbetreuung Juli 2025", "PERSONAL_FESTANSTELLUNG", [("KST-102", 100, "FERIEN", "1")]),
        (fy2025, "2025-08-15", 9200.0, A, "Honorarkräfte Sammelabrechnung", "Honorare Ferienbetreuung August 2025", "PERSONAL_FESTANSTELLUNG", [("KST-102", 100, "FERIEN", "1")]),
        (fy2025, "2025-06-20", 3450.5, A, "Spielwaren Müller GmbH", "Materialkosten Workshop-Ausstattung Sommerprogramm", "SACH_BUERO", [("KST-102", 100, "FERIEN", "2")]),
        (fy2025, "2025-08-05", 1280.0, A, "Reisedienst Berlin GmbH", "Bus-Ausflug Spreewald Ferienprogramm", "SACH_REISE", [("KST-102", 100, "FERIEN", "3")]),
        (fy2025, "2025-06-15", 25000.0, E, "Stadt Berlin Jugendamt", "1. Abschlag Sommerprogramm 2025", "EINNAHMEN_FOERDERUNG", [("KST-102", 100, "FERIEN", "1")]),
    ]

    quote_by_measure = {"HAUSAUFGABEN": 0.8, "SPRACHFOERDERUNG": 0.75, "FERIEN": 1.0}
    n_tx = n_split = 0
    for fy, datum, betrag, typ, ag, vz, kb_code, splits in specs:
        abs_betrag = abs(betrag)
        signed = -abs_betrag if typ == A else abs_betrag
        tx = Transaction(
            org_id=org_id, fiscal_year_id=fy.id, datum=_d(datum),
            betrag=_round2(signed), typ=typ, auftraggeber=ag, verwendungszweck=vz,
            kostenbereich_id=code_to_id.get(kb_code), status=TransactionStatus.ZUGEORDNET,
            notiz="[DEMO] Seed-Daten",
        )
        db.add(tx)
        db.flush()
        n_tx += 1
        for kst_code, prozent, measure_key, fp_code in splits:
            split_betrag = _round2(abs_betrag * (prozent / 100))
            split = TransactionSplit(
                org_id=org_id, transaction_id=tx.id, cost_center_id=kst[kst_code],
                prozent=Decimal(str(prozent)), betrag_anteil=split_betrag,
            )
            db.add(split)
            db.flush()
            n_split += 1
            if typ == A:
                m = measures.get(measure_key)
                if not m:
                    continue
                quote = quote_by_measure.get(measure_key, 1.0)
                foerderung = _round2(float(split_betrag) * quote)
                eigenanteil = _round2(float(split_betrag) - float(foerderung))
                db.add(FundAllocation(
                    org_id=org_id, transaction_split_id=split.id, funding_measure_id=m["id"],
                    prozent=Decimal("100"), finanzplan_position_id=m["fp"].get(fp_code),
                    betrag_foerderfahig=split_betrag, betrag_foerderung=foerderung,
                    betrag_eigenanteil=eigenanteil, status="BESTAETIGT",
                ))
    db.flush()
    print(f"  ✓ Transaktionen: {n_tx}, Splits: {n_split}, FundAllocations bestätigt")


# ─────────────────────────────────────────────────────────────────────
# 13. Mittelabrufe
# ─────────────────────────────────────────────────────────────────────
def ensure_mittelabrufe(
    db: Session, org_id: str, measures: dict[str, dict], fy2025: FiscalYear, fy2026: FiscalYear
) -> None:
    if db.execute(select(Mittelabruf.id).where(Mittelabruf.org_id == org_id)).first():
        print("  ✓ Mittelabrufe bereits vorhanden, überspringe")
        return
    items = [
        ("HAUSAUFGABEN", fy2026, _add_days(TODAY, -38), 12000, 42, MittelabrufStatus.ABGERUFEN, 9000),
        ("HAUSAUFGABEN", fy2026, _add_days(TODAY, -30), 8000, 42, MittelabrufStatus.ABGERUFEN, 4500),
        ("HAUSAUFGABEN", fy2026, _d("2026-01-15"), 10000, 42, MittelabrufStatus.VERWENDET, 10000),
        ("SPRACHFOERDERUNG", fy2026, _add_days(TODAY, -10), 15000, 42, MittelabrufStatus.ABGERUFEN, 5800),
        ("SPRACHFOERDERUNG", fy2026, _d("2026-01-10"), 5000, 42, MittelabrufStatus.ABGELAUFEN, 4200),
        ("FERIEN", fy2025, _d("2025-06-15"), 25000, 60, MittelabrufStatus.VERWENDET, 25000),
    ]
    for key, fy, abruf, betrag, frist_tage, status, verwendet in items:
        m = measures.get(key)
        if not m:
            continue
        db.add(Mittelabruf(
            org_id=org_id, funding_measure_id=m["id"], fiscal_year_id=fy.id,
            abruf_datum=abruf, betrag=Decimal(str(betrag)), verwendungsfrist_tage=frist_tage,
            frist_bis=_add_days(abruf, frist_tage), status=status,
            betrag_verwendet=Decimal(str(verwendet)),
        ))
    db.flush()
    print(f"  ✓ Mittelabrufe: {len(items)}")


# ─────────────────────────────────────────────────────────────────────
# 14. Verwendungsnachweise
# ─────────────────────────────────────────────────────────────────────
def ensure_verw_nachweise(
    db: Session, org_id: str, measures: dict[str, dict], fy2025: FiscalYear, fy2026: FiscalYear
) -> None:
    if db.execute(select(VerwNachweis.id).where(VerwNachweis.org_id == org_id)).first():
        print("  ✓ Verwendungsnachweise bereits vorhanden, überspringe")
        return
    items = [
        ("FERIEN", fy2025, VerwendungsnachweisTyp.VERWENDUNGSNACHWEIS, VerwendungsnachweisStatus.ANERKANNT,
         _d("2025-06-01"), _d("2025-09-30"), _d("2025-12-31"), datetime(2025, 11, 15)),
        ("HAUSAUFGABEN", fy2026, VerwendungsnachweisTyp.ZWISCHENNACHWEIS, VerwendungsnachweisStatus.EINGEREICHT,
         _d("2026-01-01"), _d("2026-03-31"), _add_days(TODAY, 60),
         datetime.combine(_add_days(TODAY, -5), datetime.min.time())),
        ("SPRACHFOERDERUNG", fy2026, VerwendungsnachweisTyp.ZWISCHENNACHWEIS, VerwendungsnachweisStatus.OFFEN,
         _d("2026-01-01"), _d("2026-03-31"), _add_days(TODAY, 12), None),
    ]
    for key, fy, typ, status, von, bis, frist, eingereicht in items:
        m = measures.get(key)
        if not m:
            continue
        db.add(VerwNachweis(
            org_id=org_id, funding_measure_id=m["id"], fiscal_year_id=fy.id, typ=typ,
            status=status, zeitraum_von=von, zeitraum_bis=bis, frist=frist,
            eingereicht_am=eingereicht,
        ))
    db.flush()
    print(f"  ✓ Verwendungsnachweise: {len(items)}")


# ─────────────────────────────────────────────────────────────────────
# 15. Booking rules (for live CSV-import demo)
# ─────────────────────────────────────────────────────────────────────
def ensure_booking_rules(
    db: Session, org_id: str, kst: dict[str, str], measures: dict[str, dict]
) -> None:
    kb_rows = db.execute(select(Kostenbereich.id, Kostenbereich.code)).all()
    code_to_id = {code: id_ for id_, code in kb_rows}
    items = [
        ("IT-Abos → Verwaltung", None, "supabase", "IT_SOFTWARE", "GRUEN", 8, [("KST-201", 100)], None),
        ("Bahnreisen → Hausaufgabenhilfe", "DB Vertrieb", None, "SACH_REISE", "GELB", 3, [("KST-101", 100)], "HAUSAUFGABEN"),
        ("Miete IONOS → Geschäftsstelle", "IONOS", None, "IT_SOFTWARE", "GRUEN", 12, [("KST-202", 100)], None),
        ("Bürobedarf → Verwaltung", None, "büro", "SACH_BUERO", "ORANGE", 1, [("KST-201", 100)], None),
    ]
    n = 0
    for name, ag, vz, kb_code, conf, match_count, splits, measure_key in items:
        if _get(db, BookingRule, org_id=org_id, name=name):
            continue
        rule = BookingRule(
            org_id=org_id, name=name, aktiv=True, prioritaet=0,
            match_auftraggeber=ag, match_verwendungszweck=vz,
            match_kostenbereich_id=code_to_id.get(kb_code) if kb_code else None,
            confidence=conf, match_count=match_count,
            funding_measure_id=measures[measure_key]["id"] if measure_key else None,
        )
        db.add(rule)
        db.flush()
        for code, prozent in splits:
            db.add(BookingRuleSplit(
                rule_id=rule.id, cost_center_id=kst[code], prozent=Decimal(str(prozent))
            ))
        n += 1
    db.flush()
    print(f"  ✓ Buchungsregeln: {len(items)}")


# ─────────────────────────────────────────────────────────────────────
# Orchestration
# ─────────────────────────────────────────────────────────────────────
def seed(db: Session) -> None:
    print("\n╔══════════════════════════════════════════╗")
    print("║  FörderFlow Demo-Seed                    ║")
    print("╚══════════════════════════════════════════╝")
    print(f"User:  {USER_EMAIL}\nOrg:   {ORG_NAME}\nDatum: {TODAY.isoformat()}\n")

    org, _user = ensure_identity(db)

    if RESET:
        print(f'⚠️  RESET-Modus: lösche ALLE Daten der Org "{ORG_NAME}"...')
        reset_org_data(db, org.id, ResetOptions(keep_audit_log=False))
        print("  ✓ Reset abgeschlossen.\n")

    ensure_system_data(db)

    fy2025 = ensure_fiscal_year(db, org.id, 2025, geschlossen=True)
    fy2026 = ensure_fiscal_year(db, org.id, 2026, geschlossen=False)

    kst = ensure_cost_centers(db, org.id)
    funders = ensure_funders(db, org.id)
    ensure_employer_gross_factors(db, org.id)
    ensure_allocation_keys(db, org.id, kst)

    measures = ensure_funding_measures(db, org.id, funders, kst)
    ensure_bescheid_dokumente(db, org.id, measures)

    employees = ensure_employees(db, org.id)
    ensure_payrolls(db, org.id, employees, kst, fy2026)
    ensure_pcm_phase1(db, org.id, employees, kst, measures)

    ensure_transactions(db, org.id, fy2025, fy2026, measures, kst)
    ensure_mittelabrufe(db, org.id, measures, fy2025, fy2026)
    ensure_verw_nachweise(db, org.id, measures, fy2025, fy2026)
    ensure_booking_rules(db, org.id, kst, measures)

    db.commit()
    print(f'\n✓ Demo-Seed abgeschlossen für Org "{ORG_NAME}".\n')


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
