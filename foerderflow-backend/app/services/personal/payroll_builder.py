"""createMonthlyPayroll — port of lib/personal/payroll-builder.ts.

Builds a MonthlyPayroll from the active contract + active salary components
(monthly recurring + one-off for that month) using berechne_gehalt, with optional
manual overrides. Raises ValueError on duplicate month / no active contract.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.payroll import MonthlyPayroll, PayrollComponent, SalaryComponent
from app.services.personal.berechnung import berechne_gehalt, get_ag_faktor, get_aktiver_vertrag


def create_monthly_payroll(
    db: Session,
    *,
    org_id: str,
    employee_id: str,
    fiscal_year_id: str,
    monat: date,
    manual_overrides: dict[str, Any] | None = None,
) -> MonthlyPayroll:
    existing = db.execute(
        select(MonthlyPayroll).where(
            MonthlyPayroll.org_id == org_id,
            MonthlyPayroll.employee_id == employee_id,
            MonthlyPayroll.monat == monat,
        )
    ).scalar_one_or_none()
    if existing:
        raise ValueError(
            f"Abrechnung für diesen Mitarbeiter und Monat existiert bereits (ID: {existing.id})."
        )

    org = db.get(Organization, org_id)
    standard_hours = float(org.regelarbeitszeit_stunden)

    contract = get_aktiver_vertrag(db, employee_id, monat)
    if contract is None:
        raise ValueError("Kein aktiver Vertrag für diesen Mitarbeiter zum angegebenen Monat gefunden.")

    assigned_hours = float(contract.assigned_hours)
    base_salary = float(contract.base_salary)
    vertragsart = contract.vertragsart.value if hasattr(contract.vertragsart, "value") else contract.vertragsart
    ag_faktor = get_ag_faktor(db, org_id, vertragsart, monat)

    raw_components = (
        db.execute(
            select(SalaryComponent).where(
                SalaryComponent.contract_id == contract.id,
                SalaryComponent.org_id == org_id,
                SalaryComponent.ist_aktiv.is_(True),
                or_(
                    SalaryComponent.einmalig.is_(False),
                    (SalaryComponent.einmalig.is_(True)) & (SalaryComponent.gilt_fuer_monat == monat),
                ),
            )
        )
        .scalars()
        .all()
    )

    overrides = manual_overrides or {}
    if overrides.get("komponenten") is not None:
        component_source = [
            {
                "typ": c["typ"],
                "bezeichnung": c["bezeichnung"],
                "betrag": float(c["betrag"]),
                "nach_multiplikator": c["nach_multiplikator"],
            }
            for c in overrides["komponenten"]
        ]
    else:
        component_source = [
            {
                "typ": c.typ.value if hasattr(c.typ, "value") else c.typ,
                "bezeichnung": c.bezeichnung,
                "betrag": float(c.betrag),
                "nach_multiplikator": c.nach_multiplikator,
            }
            for c in raw_components
        ]

    berechnung = berechne_gehalt(
        base_salary=base_salary,
        assigned_hours=assigned_hours,
        standard_hours=standard_hours,
        ag_faktor=ag_faktor,
        components=[{"betrag": c["betrag"], "nach_multiplikator": c["nach_multiplikator"]} for c in component_source],
    )

    betrag_an_brutto = overrides.get("betrag_an_brutto", berechnung.an_brutto)
    betrag_ag_brutto = overrides.get("betrag_ag_brutto", berechnung.ag_brutto)

    payroll = MonthlyPayroll(
        org_id=org_id,
        employee_id=employee_id,
        fiscal_year_id=fiscal_year_id,
        monat=monat,
        assigned_hours=assigned_hours,
        standard_hours=standard_hours,
        base_salary=base_salary,
        ag_faktor=ag_faktor,
        actual_salary=berechnung.actual_salary,
        betrag_an_brutto=betrag_an_brutto,
        betrag_ag_brutto=betrag_ag_brutto,
        quelle="MANUELL",
    )
    db.add(payroll)
    db.flush()
    for c in component_source:
        db.add(
            PayrollComponent(
                payroll_id=payroll.id,
                typ=c["typ"],
                bezeichnung=c["bezeichnung"],
                betrag=c["betrag"],
                nach_multiplikator=c["nach_multiplikator"],
            )
        )
    db.commit()
    db.refresh(payroll)
    return payroll
