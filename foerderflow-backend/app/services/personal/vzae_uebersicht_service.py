"""VZÄ-Übersicht per measure × fiscal year — port of personal/vzae-uebersicht.

Aggregates payroll allocations on the measure's cost centers, groups by payroll
(summing prozent + betrag across KSTs), then by month, computing VZÄ-Projekt.
Money/VZÄ values serialize as NUMBERS. laufzeit dates as full ISO (toISOString).
"""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.funding import FundingMeasure, FundingMeasureCostCenter
from app.models.payroll import Employee, MonthlyPayroll, PayrollAllocation
from app.services.vzae import berechne_vzae, berechne_vzae_anteil


def _iso(d: date) -> str:
    return f"{d.isoformat()}T00:00:00.000Z"


class VzaeUebersichtService:
    def __init__(self, db: Session):
        self.db = db

    def uebersicht(
        self, org_id: str, funding_measure_id: str | None, fiscal_year_id: str | None
    ) -> dict[str, Any]:
        if not funding_measure_id or not fiscal_year_id:
            raise APIError(
                400, "MISSING_PARAMS", "funding_measure_id und fiscal_year_id sind erforderlich."
            )

        measure = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none()
        if measure is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")

        massnahme = {
            "name": measure.name,
            "laufzeit_von": _iso(measure.laufzeit_von),
            "laufzeit_bis": _iso(measure.laufzeit_bis),
        }

        kst_ids = self.db.execute(
            select(FundingMeasureCostCenter.cost_center_id).where(
                FundingMeasureCostCenter.funding_measure_id == funding_measure_id,
                FundingMeasureCostCenter.org_id == org_id,
            )
        ).scalars().all()

        if not kst_ids:
            return {
                "massnahme": massnahme,
                "monate": [],
                "gesamt_betrag": 0,
                "gesamt_vzae_monate": 0,
            }

        allocations = self.db.execute(
            select(PayrollAllocation)
            .join(MonthlyPayroll, MonthlyPayroll.id == PayrollAllocation.payroll_id)
            .where(
                PayrollAllocation.org_id == org_id,
                PayrollAllocation.cost_center_id.in_(kst_ids),
                MonthlyPayroll.fiscal_year_id == fiscal_year_id,
            )
            .options(
                selectinload(PayrollAllocation.payroll).selectinload(MonthlyPayroll.employee)
            )
        ).scalars().all()

        # Group by payroll_id: sum prozent + betrag across KSTs
        by_payroll: dict[str, dict[str, Any]] = {}
        for alloc in allocations:
            agg = by_payroll.get(alloc.payroll_id)
            if agg:
                agg["summe_prozent"] += float(alloc.prozent)
                agg["summe_betrag"] += float(alloc.betrag_anteil)
            else:
                by_payroll[alloc.payroll_id] = {
                    "payroll": alloc.payroll,
                    "summe_prozent": float(alloc.prozent),
                    "summe_betrag": float(alloc.betrag_anteil),
                }

        # Group aggregated payrolls by month (YYYY-MM)
        by_monat: dict[str, list[dict[str, Any]]] = {}
        for agg in by_payroll.values():
            p = agg["payroll"]
            monat_key = f"{p.monat.year:04d}-{p.monat.month:02d}"
            vzae_gesamt = berechne_vzae(float(p.assigned_hours), float(p.standard_hours))
            prozent_kst = agg["summe_prozent"]
            vzae_projekt = berechne_vzae_anteil(vzae_gesamt, prozent_kst)
            stunden_projekt = float(p.assigned_hours) * prozent_kst / 100
            eintrag = {
                "employee": {
                    "vorname": p.employee.vorname,
                    "nachname": p.employee.nachname,
                    "employee_code": p.employee.employee_code,
                },
                "vzae_gesamt": vzae_gesamt,
                "vzae_projekt": vzae_projekt,
                "stunden_projekt": stunden_projekt,
                "betrag_ag_brutto": agg["summe_betrag"],
                "prozent_kst": prozent_kst,
            }
            by_monat.setdefault(monat_key, []).append(eintrag)

        monate = []
        for monat in sorted(by_monat.keys()):
            eintraege = by_monat[monat]
            summe_vzae_projekt = sum(e["vzae_projekt"] for e in eintraege)
            summe_betrag = sum(e["betrag_ag_brutto"] for e in eintraege)
            monate.append(
                {
                    "monat": monat,
                    "eintraege": eintraege,
                    "summe_vzae_projekt": summe_vzae_projekt,
                    "summe_betrag": summe_betrag,
                }
            )

        gesamt_betrag = sum(m["summe_betrag"] for m in monate)
        gesamt_vzae_monate = sum(m["summe_vzae_projekt"] for m in monate)

        return {
            "massnahme": massnahme,
            "monate": monate,
            "gesamt_betrag": gesamt_betrag,
            "gesamt_vzae_monate": gesamt_vzae_monate,
        }
