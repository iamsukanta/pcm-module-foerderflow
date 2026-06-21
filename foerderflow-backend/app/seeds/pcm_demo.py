"""Module PCM — complete demo dataset.

Builds a self-contained, loginnable org ("PCM Demo GmbH" / pcm-demo@volulink.de)
with a full Personal-Cost-Management dataset: funder + funding measures +
Finanzplan positions, cost centres, a TVöD-VKA tariff grid (incl. a mid-year
split) with levels, five employees with contracts + hour assignments, a bonus
template, per-employee bonuses/adjustments, a leave period with a placeholder,
then runs the January-2026 payroll and the cost forecast.

Idempotent: if the org already has employee MA-001 it only re-runs payroll
(re-run safe). The exact figures are documented in
``documents/FoerderFlow_PCM_DemoDataset_v1.md``.

Run:  python -m app.seeds.pcm_demo
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.auth import OrganizationMembership, User
from app.models.enums import (
    AdjustmentType,
    BonusApplicableTo,
    BonusType,
    BruttoType,
    CostCenterTyp,
    EmployeeType,
    FiscalYearStatus,
    FunderTyp,
    LeaveType,
    MittelabrufVerfahren,
    OrgRole,
    ProrationRule,
    Rechtsform,
    Vertragsart,
)
from app.models.finanzplan import FinanzplanPosition
from app.models.funding import FundingMeasure
from app.models.master import CostCenter, FiscalYear, Funder
from app.models.organization import Organization
from app.models.payroll import Employee, EmployeeContract, EmployerGrossFactor
from app.models.pcm_bonus import BonusPayment, BonusTemplate, SalaryAdjustment
from app.models.pcm_leave import EmployeeLeavePeriod
from app.models.pcm_personnel import WochenstundenZuweisung
from app.models.pcm_tariff import SalaryLevel, SalaryTariff
from app.services.pcm.forecast_engine import run_forecast
from app.services.pcm.payroll_engine import run_monthly_payroll

USER_EMAIL = "pcm-demo@volulink.de"
ORG_NAME = "PCM Demo GmbH"
D = lambda s: Decimal(str(s))  # noqa: E731


def _get(db: Session, model, **f):
    return db.execute(select(model).filter_by(**f)).scalar_one_or_none()


def _identity(db: Session) -> Organization:
    user = _get(db, User, email=USER_EMAIL)
    if not user:
        user = User(email=USER_EMAIL, name="PCM Demo", is_super_admin=True)
        db.add(user)
        db.flush()
    org = _get(db, Organization, name=ORG_NAME)
    if not org:
        org = Organization(name=ORG_NAME, rechtsform=Rechtsform.GGMBH,
                            regelarbeitszeit_stunden=D("39.00"), bav_rate_pct=D("0"))
        db.add(org)
        db.flush()
    else:
        org.bav_rate_pct = D("0")
    if not _get(db, OrganizationMembership, org_id=org.id, user_id=user.id):
        db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role=OrgRole.ADMIN))
        db.flush()
    return org


def _build(db: Session, org: Organization) -> None:
    oid = org.id

    # ── fiscal year + employer gross factor ────────────────────────────────────
    fy = FiscalYear(org_id=oid, jahr=2026, beginn=date(2026, 1, 1),
                    ende=date(2026, 12, 31), status=FiscalYearStatus.OFFEN)
    db.add(fy)
    db.add(EmployerGrossFactor(org_id=oid, vertragsart=Vertragsart.FESTANSTELLUNG,
                               faktor=D("1.2000"), gueltig_ab=date(2026, 1, 1)))
    db.flush()

    # ── cost centres ───────────────────────────────────────────────────────────
    cc_proj = CostCenter(org_id=oid, code="KST-100", name="Hausaufgabenhilfe",
                         typ=CostCenterTyp.PROJECT, ist_aktiv=True)
    cc_proj2 = CostCenter(org_id=oid, code="KST-200", name="Ferienprogramm",
                          typ=CostCenterTyp.PROJECT, ist_aktiv=True)
    cc_oh = CostCenter(org_id=oid, code="KST-900", name="Verwaltung (Overhead)",
                       typ=CostCenterTyp.OVERHEAD, ist_aktiv=True)
    db.add_all([cc_proj, cc_proj2, cc_oh])
    db.flush()

    # ── funder + funding measures + finanzplan positions ───────────────────────
    funder = Funder(org_id=oid, name="Sozialreferat München", typ=FunderTyp.KOMMUNE)
    db.add(funder)
    db.flush()
    fm1 = FundingMeasure(org_id=oid, funder_id=funder.id, name="Hausaufgabenhilfe 2026",
                         budget_gesamt=D("200000"), foerderquote=D("80"),
                         laufzeit_von=date(2026, 1, 1), laufzeit_bis=date(2026, 12, 31),
                         mittelabruf_verfahren=MittelabrufVerfahren.ANFORDERUNG)
    fm2 = FundingMeasure(org_id=oid, funder_id=funder.id, name="Ferienprogramm 2026",
                         budget_gesamt=D("80000"), foerderquote=D("90"),
                         laufzeit_von=date(2026, 1, 1), laufzeit_bis=date(2026, 12, 31),
                         mittelabruf_verfahren=MittelabrufVerfahren.ANFORDERUNG)
    db.add_all([fm1, fm2])
    db.flush()
    fp1 = FinanzplanPosition(org_id=oid, funding_measure_id=fm1.id, positionscode="1.1",
                             bezeichnung="Personalkosten", betrag_bewilligt=D("120000"))
    fp2 = FinanzplanPosition(org_id=oid, funding_measure_id=fm2.id, positionscode="1.1",
                             bezeichnung="Personalkosten", betrag_bewilligt=D("50000"))
    db.add_all([fp1, fp2])
    db.flush()

    # ── tariff grid (TVöD-VKA) + mid-year split on E10/3 ───────────────────────
    def tariff(group, level, amount, vfrom="2026-01-01", vto=None):
        t = SalaryTariff(org_id=oid, tariff_code="TVöD-VKA", salary_group=group,
                         level=level, monthly_amount=D(amount), standard_hours=D("39.00"),
                         is_proposed=False, valid_from=date.fromisoformat(vfrom),
                         valid_to=date.fromisoformat(vto) if vto else None,
                         bav_rate_pct=D("4.70"))
        db.add(t)
        db.flush()
        return t

    grid = {
        ("E8", 1): 3000, ("E8", 2): 3200, ("E8", 3): 3400, ("E8", 4): 3600,
        ("E9", 1): 3300, ("E9", 2): 3500, ("E9", 3): 3700, ("E9", 4): 3900,
        ("E10", 1): 3600, ("E10", 2): 3800, ("E10", 4): 4200,
    }
    rows: dict[tuple, SalaryTariff] = {}
    for (g, lv), amt in grid.items():
        rows[(g, lv)] = tariff(g, lv, amt)
    # E10/3 mid-year split: Jan–Apr 4000, May–open 4100.
    rows[("E10", 3)] = tariff("E10", 3, 4000, "2026-01-01", "2026-04-30")
    tariff("E10", 3, 4100, "2026-05-01", None)

    def levels(row, group, ladder):
        for lvl, amt, months in ladder:
            db.add(SalaryLevel(org_id=oid, tariff_id=row.id, salary_group=group,
                               level_no=lvl, monthly_amount=D(amt),
                               months_to_next_level=months))
    levels(rows[("E10", 3)], "E10", [(1, 3600, 12), (2, 3800, 24), (3, 4000, 36), (4, 4200, None)])
    levels(rows[("E9", 2)], "E9", [(1, 3300, 12), (2, 3500, 24), (3, 3700, 36), (4, 3900, None)])
    levels(rows[("E8", 4)], "E8", [(1, 3000, 12), (2, 3200, 24), (3, 3400, 36), (4, 3600, None)])
    db.flush()

    # ── employees + contracts ──────────────────────────────────────────────────
    def employee(code, vor, nach, ext, group, stufe, tariff_row, *, next_level=None):
        e = Employee(org_id=oid, employee_code=code, vorname=vor, nachname=nach,
                     eintrittsdatum=date(2024, 1, 1), ist_aktiv=True,
                     employee_external_id=ext)
        db.add(e)
        db.flush()
        c = EmployeeContract(org_id=oid, employee_id=e.id,
                             vertragsart=Vertragsart.FESTANSTELLUNG, assigned_hours=D("39"),
                             base_salary=tariff_row.monthly_amount, entgeltgruppe=group,
                             stufe=stufe, gueltig_ab=date(2026, 1, 1),
                             salary_tariff_id=tariff_row.id, next_level_date=next_level)
        db.add(c)
        db.flush()
        return e, c

    ma1, c1 = employee("MA-001", "Anna", "Becker", "P-1001", "E10", 3, rows[("E10", 3)],
                       next_level=date(2026, 8, 1))
    ma2, c2 = employee("MA-002", "Mehmet", "Yıldız", "P-1002", "E9", 2, rows[("E9", 2)])
    ma3, c3 = employee("MA-003", "Sofia", "Rossi", "P-1003", "E8", 4, rows[("E8", 4)])
    ma4, c4 = employee("MA-004", "Jonas", "Klein", "P-1004", "E10", 1, rows[("E10", 1)])
    ma5, c5 = employee("MA-005", "Laura", "Wagner", "P-1005", "E9", 1, rows[("E9", 1)])

    # ── hour assignments (Stellenplan) ─────────────────────────────────────────
    def wsz(emp, contract, cc, hours, fm=None, fp=None):
        db.add(WochenstundenZuweisung(
            org_id=oid, employee_id=emp.id, salary_assignment_id=contract.id,
            cost_center_id=cc.id, funding_measure_id=fm.id if fm else None,
            finanzplan_position_id=fp.id if fp else None, weekly_hours=D(hours),
            effective_date=date(2026, 1, 1)))

    wsz(ma1, c1, cc_proj, "39", fm1, fp1)
    wsz(ma2, c2, cc_proj, "26", fm1, fp1)
    wsz(ma2, c2, cc_proj2, "13", fm2, fp2)
    wsz(ma3, c3, cc_proj, "20", fm1, fp1)
    wsz(ma3, c3, cc_oh, "19")  # overhead, no funding measure
    wsz(ma4, c4, cc_proj2, "39", fm2, fp2)
    wsz(ma5, c5, cc_proj, "39", fm1, fp1)
    db.flush()

    # ── bonuses, adjustments ───────────────────────────────────────────────────
    db.add(BonusTemplate(org_id=oid, name="Münchenzulage EG1–EG15", tariff_code=None,
                         applicable_to=BonusApplicableTo.ALL, type=BonusType.FIXED,
                         amount=D("270"), brutto_type=BruttoType.EMPLOYER,
                         proration_rule=ProrationRule.FULL, period_from=date(2026, 1, 1)))
    db.add(BonusPayment(org_id=oid, employee_id=ma1.id, type=BonusType.PERCENT,
                        amount=D("2"), brutto_type=BruttoType.EMPLOYER,
                        proration_rule=ProrationRule.FULL, period_from=date(2026, 1, 1),
                        description="LOB Leistungsbonus 2%"))
    db.add(SalaryAdjustment(org_id=oid, employee_id=ma3.id, type=AdjustmentType.ADDITION,
                            amount=D("50"), brutto_type=BruttoType.NEITHER,
                            proration_rule=ProrationRule.FULL, period_from=date(2026, 1, 1),
                            description="Jobticket (Sachbezug)"))
    db.add(SalaryAdjustment(org_id=oid, employee_id=ma2.id, type=AdjustmentType.DEDUCTION,
                            amount=D("80"), brutto_type=BruttoType.EMPLOYEE,
                            proration_rule=ProrationRule.FULL, period_from=date(2026, 1, 1),
                            description="Dienstwagen-Abzug"))
    db.flush()

    # ── leave period + placeholder (MA-005 on Elternzeit) ──────────────────────
    placeholder = Employee(org_id=oid, employee_code="VTR-001", vorname="Vertretung",
                           nachname="Laura Wagner", eintrittsdatum=date(2026, 1, 1),
                           ist_aktiv=True, employee_type=EmployeeType.PLACEHOLDER)
    db.add(placeholder)
    db.flush()
    db.add(EmployeeLeavePeriod(
        org_id=oid, employee_id=ma5.id, leave_type=LeaveType.ELTERNZEIT,
        start_date=date(2026, 1, 1), expected_end_date=date(2026, 9, 30),
        replacement_employee_id=placeholder.id, funder_notification_required=True,
        note="Elternzeit; Vertretung über Platzhalter."))
    db.commit()

    # ── run January payroll + forecast ─────────────────────────────────────────
    for emp in (ma1, ma2, ma3, ma4, ma5):
        run_monthly_payroll(db, org_id=oid, employee_id=emp.id,
                            fiscal_year_id=fy.id, monat=date(2026, 1, 1))
    run_forecast(db, oid, fy.id, include_proposed=True)
    print("  [OK] Januar-Abrechnung + Jahresprognose berechnet")


def main() -> None:
    db = SessionLocal()
    try:
        org = _identity(db)
        if _get(db, Employee, org_id=org.id, employee_code="MA-001"):
            # Already seeded — just recompute payroll (re-run safe).
            fy = _get(db, FiscalYear, org_id=org.id, jahr=2026)
            for code in ("MA-001", "MA-002", "MA-003", "MA-004", "MA-005"):
                emp = _get(db, Employee, org_id=org.id, employee_code=code)
                run_monthly_payroll(db, org_id=org.id, employee_id=emp.id,
                                    fiscal_year_id=fy.id, monat=date(2026, 1, 1))
            run_forecast(db, org.id, fy.id, include_proposed=True)
            print(f"[OK] PCM-Demo bereits vorhanden (Org {org.id}); Abrechnung neu berechnet.")
        else:
            _build(db, org)
            print(f"[OK] PCM-Demo angelegt — Org {org.id}, Login {USER_EMAIL}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
