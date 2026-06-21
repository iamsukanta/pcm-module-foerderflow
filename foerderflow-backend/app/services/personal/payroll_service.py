"""MonthlyPayroll + allocations + analytics + gross-factors + tarif — port of
app/api/protected/payroll/*, employer-gross-factors, tarif, personal/soll-ist.

Money/hours serialize as strings; monat as YYYY-MM-DD. Allocation POST replaces
all allocations (100%-sum invariant), supports allocation_key_id expansion.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.allocation import AllocationKey
from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.funding import FundingMeasure, FundingMeasureCostCenter
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import (
    Employee,
    EmployerGrossFactor,
    MonthlyPayroll,
    PayrollAllocation,
    PayrollComponent,
    TarifTabelle,
)
from app.services.audit_service import log_audit  # noqa: F401  (used in set_allocations)
from app.services.personal.payroll_builder import create_monthly_payroll
from app.services.vzae import berechne_soll_ist_status
from app.utils.serialization import decimal_str

VALID_VERTRAGSART = ("FESTANSTELLUNG", "MINIJOB", "WERKVERTRAG", "EHRENAMT")
VALID_TARIFWERK = ("TVOEDD", "TVOEL", "AVR_CARITAS", "AVR_DD", "INDIVIDUELL")


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _round2(x: float) -> float:
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _ymd(d: date) -> str:
    return d.isoformat()


def _payroll(p: MonthlyPayroll) -> dict[str, Any]:
    return {
        "id": p.id,
        "org_id": p.org_id,
        "employee_id": p.employee_id,
        "fiscal_year_id": p.fiscal_year_id,
        "monat": _ymd(p.monat),
        "assigned_hours": decimal_str(p.assigned_hours),
        "standard_hours": decimal_str(p.standard_hours),
        "base_salary": decimal_str(p.base_salary),
        "ag_faktor": decimal_str(p.ag_faktor),
        "actual_salary": decimal_str(p.actual_salary),
        "betrag_an_brutto": decimal_str(p.betrag_an_brutto),
        "betrag_ag_brutto": decimal_str(p.betrag_ag_brutto),
        "quelle": p.quelle,
        "import_batch_id": p.import_batch_id,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _alloc(a: PayrollAllocation, with_rel: bool = True) -> dict[str, Any]:
    row = {
        "id": a.id,
        "org_id": a.org_id,
        "payroll_id": a.payroll_id,
        "cost_center_id": a.cost_center_id,
        "prozent": decimal_str(a.prozent),
        "betrag_anteil": decimal_str(a.betrag_anteil),
        "allocation_key_id": a.allocation_key_id,
    }
    if with_rel:
        cc = a.cost_center
        row["cost_center"] = {"id": cc.id, "name": cc.name, "code": cc.code} if cc else None
        ak = a.allocation_key
        row["allocation_key"] = {"id": ak.id, "name": ak.name} if ak else None
    return row


class PayrollService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        conds = [MonthlyPayroll.org_id == org_id]
        if params.get("fiscal_year_id"):
            conds.append(MonthlyPayroll.fiscal_year_id == params["fiscal_year_id"])
        if params.get("employee_id"):
            conds.append(MonthlyPayroll.employee_id == params["employee_id"])
        if params.get("monat"):
            try:
                y, m = params["monat"].split("-")
                conds.append(MonthlyPayroll.monat == date(int(y), int(m), 1))
            except (ValueError, AttributeError):
                pass
        rows = (
            self.db.execute(
                select(MonthlyPayroll)
                .where(*conds)
                .order_by(MonthlyPayroll.monat.desc())
                .options(selectinload(MonthlyPayroll.employee), selectinload(MonthlyPayroll.allocations))
            )
            .scalars()
            .all()
        )
        out = []
        for p in rows:
            d = _payroll(p)
            d["employee"] = {
                "vorname": p.employee.vorname,
                "nachname": p.employee.nachname,
                "employee_code": p.employee.employee_code,
            }
            d["_count"] = {"allocations": len(p.allocations)}
            out.append(d)
        out.sort(key=lambda x: (x["monat"], ""), reverse=True)
        return out

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        emp_id = body.get("employee_id")
        if not isinstance(emp_id, str) or not emp_id:
            raise APIError(422, "VALIDATION_EMPLOYEE_ID", "employee_id ist erforderlich.")
        fy_id = body.get("fiscal_year_id")
        if not isinstance(fy_id, str) or not fy_id:
            raise APIError(422, "VALIDATION_FISCAL_YEAR_ID", "fiscal_year_id ist erforderlich.")
        monat_str = body.get("monat")
        import re

        if not isinstance(monat_str, str) or not re.match(r"^\d{4}-\d{2}$", monat_str):
            raise APIError(422, "VALIDATION_MONAT", "monat muss im Format YYYY-MM angegeben werden.")
        if self.db.execute(
            select(Employee.id).where(Employee.id == emp_id, Employee.org_id == org_id)
        ).scalar_one_or_none() is None:
            raise APIError(404, "NOT_FOUND", "Mitarbeiter nicht gefunden.")
        if self.db.execute(
            select(FiscalYear.id).where(FiscalYear.id == fy_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none() is None:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        y, m = monat_str.split("-")
        monat = date(int(y), int(m), 1)
        try:
            payroll = create_monthly_payroll(
                self.db,
                org_id=org_id,
                employee_id=emp_id,
                fiscal_year_id=fy_id,
                monat=monat,
                manual_overrides=body.get("manual_overrides"),
            )
        except ValueError as e:
            msg = str(e)
            if "existiert bereits" in msg:
                raise APIError(409, "DUPLICATE", msg)  # noqa: B904
            if "Kein aktiver Vertrag" in msg:
                raise APIError(422, "NO_CONTRACT", msg)  # noqa: B904
            raise APIError(500, "INTERNAL_ERROR", msg)  # noqa: B904
        return _payroll(payroll)

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        p = self.db.execute(
            select(MonthlyPayroll)
            .where(MonthlyPayroll.id == id_, MonthlyPayroll.org_id == org_id)
            .options(
                selectinload(MonthlyPayroll.employee),
                selectinload(MonthlyPayroll.components),
                selectinload(MonthlyPayroll.allocations).selectinload(PayrollAllocation.cost_center),
            )
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")
        d = _payroll(p)
        d["employee"] = {
            "vorname": p.employee.vorname,
            "nachname": p.employee.nachname,
            "employee_code": p.employee.employee_code,
        }
        d["components"] = [
            {
                "id": c.id, "payroll_id": c.payroll_id, "typ": _ev(c.typ),
                "bezeichnung": c.bezeichnung, "betrag": decimal_str(c.betrag),
                "nach_multiplikator": c.nach_multiplikator,
            }
            for c in p.components
        ]
        d["allocations"] = [_alloc(a) for a in p.allocations]
        return d

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        p = self.db.execute(
            select(MonthlyPayroll).where(MonthlyPayroll.id == id_, MonthlyPayroll.org_id == org_id)
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")
        if p.quelle != "MANUELL":
            raise APIError(
                422, "READONLY_IMPORT",
                "Importierte Abrechnungen können nicht manuell bearbeitet werden.",
            )
        changed = False
        if isinstance(body.get("betrag_an_brutto"), (int, float)) and not isinstance(body["betrag_an_brutto"], bool):
            p.betrag_an_brutto = body["betrag_an_brutto"]
            changed = True
        if isinstance(body.get("betrag_ag_brutto"), (int, float)) and not isinstance(body["betrag_ag_brutto"], bool):
            p.betrag_ag_brutto = body["betrag_ag_brutto"]
            changed = True
        if not changed:
            raise APIError(422, "NO_FIELDS", "Keine gültigen Felder zum Aktualisieren angegeben.")
        self.db.commit()
        self.db.refresh(p)
        return _payroll(p)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        p = self.db.execute(
            select(MonthlyPayroll)
            .where(MonthlyPayroll.id == id_, MonthlyPayroll.org_id == org_id)
            .options(selectinload(MonthlyPayroll.allocations))
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")
        if len(p.allocations) > 0:
            raise APIError(
                422, "HAS_ALLOCATIONS",
                "Abrechnung kann nicht gelöscht werden — es existieren noch Kostenstellen-Zuordnungen.",
            )
        self.db.delete(p)
        self.db.commit()
        return {"message": "Abrechnung wurde gelöscht."}

    # ── allocations ────────────────────────────────────────────────────────────
    def list_allocations(self, org_id: str, payroll_id: str) -> list[dict[str, Any]]:
        if self.db.execute(
            select(MonthlyPayroll.id).where(MonthlyPayroll.id == payroll_id, MonthlyPayroll.org_id == org_id)
        ).scalar_one_or_none() is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")
        rows = (
            self.db.execute(
                select(PayrollAllocation)
                .where(PayrollAllocation.payroll_id == payroll_id, PayrollAllocation.org_id == org_id)
                .options(
                    selectinload(PayrollAllocation.cost_center),
                    selectinload(PayrollAllocation.allocation_key),
                )
            )
            .scalars()
            .all()
        )
        rows.sort(key=lambda a: a.cost_center.code if a.cost_center else "")
        return [_alloc(a) for a in rows]

    def set_allocations(self, org_id: str, user_id: str | None, payroll_id: str, body: dict[str, Any]) -> dict[str, Any]:
        payroll = self.db.execute(
            select(MonthlyPayroll).where(MonthlyPayroll.id == payroll_id, MonthlyPayroll.org_id == org_id)
        ).scalar_one_or_none()
        if payroll is None:
            raise APIError(404, "NOT_FOUND", "Abrechnung nicht gefunden.")

        used_key_id = None
        raw = body.get("allocations")
        key_id = body.get("allocation_key_id")
        if isinstance(key_id, str) and key_id:
            key = self.db.execute(
                select(AllocationKey)
                .where(AllocationKey.id == key_id, AllocationKey.org_id == org_id)
                .options(selectinload(AllocationKey.positions))
            ).scalar_one_or_none()
            if key is None:
                raise APIError(404, "NOT_FOUND", "Verteilungsschlüssel nicht gefunden.")
            allocations_input = [
                {"cost_center_id": p.cost_center_id, "prozent": float(p.prozent)} for p in key.positions
            ]
            used_key_id = key.id
        elif isinstance(raw, list):
            allocations_input = [
                {"cost_center_id": str(a.get("cost_center_id") or ""), "prozent": float(a.get("prozent") or 0)}
                for a in raw
            ]
        else:
            raise APIError(
                422, "MISSING_FIELDS",
                "allocations (Array) oder allocation_key_id (String) ist erforderlich.",
            )

        if not allocations_input:
            raise APIError(422, "EMPTY_ALLOCATIONS", "Mindestens eine Zuordnung ist erforderlich.")
        for a in allocations_input:
            if not (a["prozent"] == a["prozent"]) or a["prozent"] <= 0 or a["prozent"] > 100:
                raise APIError(422, "INVALID_PROZENT", "Alle Prozentwerte müssen zwischen 0 und 100 liegen.")
        summe = round(sum(a["prozent"] for a in allocations_input), 10)
        if abs(summe - 100) > 0.01:
            raise APIError(
                400, "INVARIANT_SUM_NOT_100",
                f"Die Summe der Prozentanteile muss 100,00 % ergeben. Aktuell: {summe:.2f} %.",
                extra={"summe_prozent": summe},
            )
        cc_ids = [a["cost_center_id"] for a in allocations_input]
        valid = self.db.execute(
            select(CostCenter.id).where(
                CostCenter.id.in_(cc_ids), CostCenter.org_id == org_id, CostCenter.ist_aktiv.is_(True)
            )
        ).all()
        if len({r[0] for r in valid}) != len(set(cc_ids)):
            raise APIError(
                422, "COST_CENTER_INVALID",
                "Eine oder mehrere Kostenstellen wurden nicht gefunden oder sind inaktiv.",
            )

        betrag_ag = float(payroll.betrag_ag_brutto)
        self.db.query(PayrollAllocation).filter(PayrollAllocation.payroll_id == payroll_id).delete(
            synchronize_session=False
        )
        created = []
        for a in allocations_input:
            pa = PayrollAllocation(
                org_id=org_id,
                payroll_id=payroll_id,
                cost_center_id=a["cost_center_id"],
                prozent=a["prozent"],
                betrag_anteil=_round2(betrag_ag * a["prozent"] / 100),
                allocation_key_id=used_key_id,
            )
            self.db.add(pa)
            created.append(pa)
        self.db.commit()
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="PAYROLL_ALLOCATION_UPDATE",
            entitaet="PayrollAllocation",
            entitaet_id=payroll_id,
            nachher={"payroll_id": payroll_id, "allocation_count": len(created), "allocation_key_id": used_key_id},
        )
        for pa in created:
            self.db.refresh(pa)
        return {
            "data": [_alloc(a, with_rel=False) for a in created],
            "message": f"{len(created)} Zuordnung(en) gespeichert.",
        }

    # ── monat-uebersicht ────────────────────────────────────────────────────────
    def monat_uebersicht(self, org_id: str, monat_str: str | None, fiscal_year_id: str | None) -> list[dict[str, Any]]:
        import re

        if not monat_str or not re.match(r"^\d{4}-\d{2}$", monat_str):
            raise APIError(400, "VALIDATION_MONAT", "monat ist erforderlich (Format: YYYY-MM).")
        y, m = monat_str.split("-")
        monat = date(int(y), int(m), 1)
        employees = (
            self.db.execute(
                select(Employee)
                .where(Employee.org_id == org_id, Employee.ist_aktiv.is_(True))
                .order_by(Employee.nachname.asc())
            )
            .scalars()
            .all()
        )
        conds = [MonthlyPayroll.org_id == org_id, MonthlyPayroll.monat == monat]
        if fiscal_year_id:
            conds.append(MonthlyPayroll.fiscal_year_id == fiscal_year_id)
        payrolls = (
            self.db.execute(
                select(MonthlyPayroll)
                .where(*conds)
                .options(selectinload(MonthlyPayroll.allocations).selectinload(PayrollAllocation.cost_center))
            )
            .scalars()
            .all()
        )
        by_emp = {p.employee_id: p for p in payrolls}
        out = []
        for emp in employees:
            p = by_emp.get(emp.id)
            allocations = (
                [
                    {
                        "cost_center_id": a.cost_center_id,
                        "cost_center_name": a.cost_center.name,
                        "prozent": float(a.prozent),
                        "betrag_anteil": float(a.betrag_anteil),
                    }
                    for a in p.allocations
                ]
                if p
                else []
            )
            summe = sum(a["prozent"] for a in allocations)
            out.append(
                {
                    "employee": {
                        "id": emp.id, "vorname": emp.vorname, "nachname": emp.nachname,
                        "employee_code": emp.employee_code,
                    },
                    "payroll": (
                        {
                            "id": p.id, "betrag_ag_brutto": float(p.betrag_ag_brutto),
                            "betrag_an_brutto": float(p.betrag_an_brutto), "quelle": p.quelle,
                        }
                        if p
                        else None
                    ),
                    "allocations": allocations,
                    "summe_prozent": round(summe * 1000) / 1000,
                    "hat_abrechnung": p is not None,
                }
            )
        return out

    # ── personal soll-ist ───────────────────────────────────────────────────────
    def personal_soll_ist(self, org_id: str, funding_measure_id: str | None, fiscal_year_id: str | None) -> dict[str, Any]:
        if not funding_measure_id:
            raise APIError(400, "MISSING_PARAMS", "funding_measure_id ist erforderlich.")
        if self.db.execute(
            select(FundingMeasure.id).where(
                FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none() is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
        positionen = (
            self.db.execute(
                select(FinanzplanPosition)
                .where(
                    FinanzplanPosition.funding_measure_id == funding_measure_id,
                    FinanzplanPosition.org_id == org_id,
                )
                .order_by(FinanzplanPosition.sort_order.asc())
                .options(
                    selectinload(FinanzplanPosition.kostenbereiche).selectinload(
                        FinanzplanPositionKostenbereich.kostenbereich
                    )
                )
            )
            .scalars()
            .all()
        )
        kst_ids = [
            r[0]
            for r in self.db.execute(
                select(FundingMeasureCostCenter.cost_center_id).where(
                    FundingMeasureCostCenter.funding_measure_id == funding_measure_id,
                    FundingMeasureCostCenter.org_id == org_id,
                )
            ).all()
        ]
        betrag_ist = 0.0
        if kst_ids:
            stmt = (
                select(func.coalesce(func.sum(PayrollAllocation.betrag_anteil), 0))
                .select_from(PayrollAllocation)
                .where(
                    PayrollAllocation.org_id == org_id,
                    PayrollAllocation.cost_center_id.in_(kst_ids),
                )
            )
            if fiscal_year_id:
                stmt = stmt.join(
                    MonthlyPayroll, MonthlyPayroll.id == PayrollAllocation.payroll_id
                ).where(MonthlyPayroll.fiscal_year_id == fiscal_year_id)
            betrag_ist = float(self.db.execute(stmt).scalar_one() or 0)

        data = []
        for fp in positionen:
            soll = float(fp.betrag_bewilligt)
            ist_personal = any(k.kostenbereich.ist_personal for k in fp.kostenbereiche)
            pos_ist = betrag_ist if ist_personal else 0
            data.append(
                {
                    "kostenart": f"{fp.positionscode}: {fp.bezeichnung}",
                    "betrag_soll": soll,
                    "betrag_ist": pos_ist,
                    "differenz": soll - pos_ist,
                    "ausschoepfung_prozent": (pos_ist / soll * 100) if soll > 0 else 0,
                    "status": berechne_soll_ist_status(soll, pos_ist),
                }
            )
        return {"data": data, "gesamt_ist": betrag_ist, "gesamt_soll": sum(d["betrag_soll"] for d in data)}


# ── employer gross factors ─────────────────────────────────────────────────────
class GrossFactorService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str) -> list[dict[str, Any]]:
        factors = (
            self.db.execute(
                select(EmployerGrossFactor)
                .where(EmployerGrossFactor.org_id == org_id)
                .order_by(EmployerGrossFactor.vertragsart.asc(), EmployerGrossFactor.gueltig_ab.desc())
            )
            .scalars()
            .all()
        )
        return [
            {
                "id": f.id, "org_id": f.org_id, "vertragsart": _ev(f.vertragsart),
                "faktor": decimal_str(f.faktor), "gueltig_ab": f.gueltig_ab.isoformat(),
                "gueltig_bis": f.gueltig_bis.isoformat() if f.gueltig_bis else None,
                "notiz": f.notiz, "created_at": f.created_at.isoformat() if f.created_at else None,
            }
            for f in factors
        ]

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if body.get("vertragsart") not in VALID_VERTRAGSART:
            raise APIError(
                422, "VALIDATION_VERTRAGSART",
                f"Ungültige Vertragsart. Erlaubt: {', '.join(VALID_VERTRAGSART)}.",
            )
        try:
            faktor = float(body.get("faktor"))
        except (TypeError, ValueError):
            faktor = float("nan")
        if not (faktor == faktor) or faktor <= 0:
            raise APIError(422, "VALIDATION_FAKTOR", "Faktor muss eine positive Zahl sein.")
        ga = body.get("gueltig_ab")
        try:
            new_ga = date.fromisoformat(ga[:10]) if isinstance(ga, str) else None
        except ValueError:
            new_ga = None
        if new_ga is None:
            raise APIError(422, "VALIDATION_GUELTIG_AB", "Gültig ab ist kein gültiges Datum.")
        current = self.db.execute(
            select(EmployerGrossFactor)
            .where(
                EmployerGrossFactor.org_id == org_id,
                EmployerGrossFactor.vertragsart == body["vertragsart"],
                EmployerGrossFactor.gueltig_bis.is_(None),
            )
            .order_by(EmployerGrossFactor.gueltig_ab.desc())
            .limit(1)
        ).scalars().first()
        if current:
            current.gueltig_bis = new_ga - timedelta(days=1)
        notiz = body.get("notiz")
        f = EmployerGrossFactor(
            org_id=org_id,
            vertragsart=body["vertragsart"],
            faktor=faktor,
            gueltig_ab=new_ga,
            gueltig_bis=None,
            notiz=notiz.strip() if isinstance(notiz, str) and notiz.strip() else None,
        )
        self.db.add(f)
        self.db.commit()
        self.db.refresh(f)
        return {
            "id": f.id, "org_id": f.org_id, "vertragsart": _ev(f.vertragsart),
            "faktor": decimal_str(f.faktor), "gueltig_ab": f.gueltig_ab.isoformat(), "gueltig_bis": None, "notiz": f.notiz,
        }


# ── tarif lookup ────────────────────────────────────────────────────────────────
class TarifService:
    def __init__(self, db: Session):
        self.db = db

    def lookup(self, tarifwerk: str | None, entgeltgruppe: str | None, jahr_str: str | None) -> list[dict[str, Any]]:
        if not tarifwerk or tarifwerk not in VALID_TARIFWERK:
            raise APIError(
                400, "VALIDATION_TARIFWERK",
                f"Ungültiges Tarifwerk. Erlaubt: {', '.join(VALID_TARIFWERK)}.",
            )
        if not entgeltgruppe:
            raise APIError(400, "VALIDATION_ENTGELTGRUPPE", "Entgeltgruppe ist erforderlich.")
        try:
            jahr = int(jahr_str)
        except (TypeError, ValueError):
            jahr = 0
        if not jahr_str or jahr < 2000 or jahr > 2100:
            raise APIError(400, "VALIDATION_JAHR", "Jahr muss eine gültige vierstellige Zahl sein.")
        rows = (
            self.db.execute(
                select(TarifTabelle)
                .where(
                    TarifTabelle.tarifwerk == tarifwerk,
                    TarifTabelle.entgeltgruppe == entgeltgruppe,
                    TarifTabelle.jahr == jahr,
                )
                .order_by(TarifTabelle.stufe.asc())
            )
            .scalars()
            .all()
        )
        return [{"stufe": r.stufe, "betrag": f"{float(r.betrag):.2f}"} for r in rows]
