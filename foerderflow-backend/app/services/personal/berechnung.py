"""Salary calculation + contract/factor lookup — port of lib/personal/berechnung*.ts.

Pure: berechne_gehalt. DB: get_ag_faktor (default 1.2121), get_aktiver_vertrag.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.payroll import EmployeeContract, EmployerGrossFactor

DEFAULT_AG_FAKTOR = 1.2121


@dataclass
class GehaltsBerechnung:
    actual_salary: float
    an_brutto: float
    ag_brutto: float
    komponenten_vor_multiplikator: float
    komponenten_nach_multiplikator: float


def berechne_gehalt(
    *,
    base_salary: float,
    assigned_hours: float,
    standard_hours: float,
    ag_faktor: float,
    components: list[dict],
) -> GehaltsBerechnung:
    actual_salary = base_salary * (assigned_hours / standard_hours)
    vor = sum(c["betrag"] for c in components if not c["nach_multiplikator"])
    nach = sum(c["betrag"] for c in components if c["nach_multiplikator"])
    an_brutto = actual_salary + vor
    ag_brutto = an_brutto * ag_faktor + nach
    return GehaltsBerechnung(actual_salary, an_brutto, ag_brutto, vor, nach)


def get_ag_faktor(db: Session, org_id: str, vertragsart: str, datum: date) -> float:
    factor = db.execute(
        select(EmployerGrossFactor)
        .where(
            EmployerGrossFactor.org_id == org_id,
            EmployerGrossFactor.vertragsart == vertragsart,
            EmployerGrossFactor.gueltig_ab <= datum,
            or_(EmployerGrossFactor.gueltig_bis.is_(None), EmployerGrossFactor.gueltig_bis >= datum),
        )
        .order_by(EmployerGrossFactor.gueltig_ab.desc())
    ).scalar_one_or_none()
    return float(factor.faktor) if factor else DEFAULT_AG_FAKTOR


def get_aktiver_vertrag(db: Session, employee_id: str, datum: date) -> EmployeeContract | None:
    return db.execute(
        select(EmployeeContract)
        .where(
            EmployeeContract.employee_id == employee_id,
            EmployeeContract.gueltig_ab <= datum,
            or_(EmployeeContract.gueltig_bis.is_(None), EmployeeContract.gueltig_bis >= datum),
        )
        .order_by(EmployeeContract.gueltig_ab.desc())
    ).scalar_one_or_none()
