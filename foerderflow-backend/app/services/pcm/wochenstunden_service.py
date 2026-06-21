"""Wochenstundenzuweisung CRUD (Module PCM controllers).

Create/update run the Doppelförderungs guard
(``app.services.pcm.doppelfoerderung.assert_assignment_allowed``) before persisting.
The owning salary assignment is the employee's ``EmployeeContract``; if not given
explicitly, the active contract for ``effective_date`` is resolved.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import AllocationMethod, EmployeeType
from app.models.funding import FundingMeasure
from app.models.master import CostCenter
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm._validate import opt_date, parse_date, req_num, req_str
from app.services.pcm.doppelfoerderung import assert_assignment_allowed
from app.services.personal.berechnung import get_aktiver_vertrag
from app.utils.serialization import decimal_str


def _wsz(w: WochenstundenZuweisung) -> dict[str, Any]:
    return {
        "id": w.id,
        "org_id": w.org_id,
        "employee_id": w.employee_id,
        "salary_assignment_id": w.salary_assignment_id,
        "cost_center_id": w.cost_center_id,
        "funding_measure_id": w.funding_measure_id,
        "finanzplan_position_id": w.finanzplan_position_id,
        "weekly_hours": decimal_str(w.weekly_hours),
        "effective_date": w.effective_date.isoformat(),
        "end_date": w.end_date.isoformat() if w.end_date else None,
        "note": w.note,
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


class WochenstundenService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str, employee_id: str | None) -> list[dict[str, Any]]:
        stmt = select(WochenstundenZuweisung).where(
            WochenstundenZuweisung.org_id == org_id
        )
        if employee_id:
            stmt = stmt.where(WochenstundenZuweisung.employee_id == employee_id)
        stmt = stmt.order_by(WochenstundenZuweisung.effective_date)
        return [_wsz(w) for w in self.db.execute(stmt).scalars().all()]

    def matrix(self, org_id: str, as_of: date | None = None) -> dict[str, Any]:
        """E.1 — org-wide allocation matrix: active employees × cost centres,
        with each employee's total allocated vs. contracted (Doppelförderung)."""
        today = as_of or date.today()
        employees = (
            self.db.execute(
                select(Employee).where(
                    Employee.org_id == org_id,
                    Employee.ist_aktiv.is_(True),
                    Employee.employee_type == EmployeeType.REGULAR,
                )
            )
            .scalars()
            .all()
        )
        assignments = (
            self.db.execute(
                select(WochenstundenZuweisung).where(
                    WochenstundenZuweisung.org_id == org_id,
                    WochenstundenZuweisung.effective_date <= today,
                    or_(
                        WochenstundenZuweisung.end_date.is_(None),
                        WochenstundenZuweisung.end_date >= today,
                    ),
                )
            )
            .scalars()
            .all()
        )
        cc_ids = {a.cost_center_id for a in assignments}
        cost_centers = (
            self.db.execute(
                select(CostCenter)
                .where(CostCenter.id.in_(cc_ids))
                .order_by(CostCenter.code)
            ).scalars().all()
            if cc_ids
            else []
        )

        rows: list[dict[str, Any]] = []
        for emp in sorted(employees, key=lambda e: (e.nachname, e.vorname)):
            contract = get_aktiver_vertrag(self.db, emp.id, today)
            method = contract.allocation_method if contract else AllocationMethod.ACTUAL_HOURS
            is_plan = method == AllocationMethod.PLAN_PERCENTAGE
            capacity = 100.0 if is_plan else float(contract.assigned_hours) if contract else 0.0
            cells: dict[str, float] = {}
            total = 0.0
            for a in assignments:
                if a.employee_id != emp.id:
                    continue
                cells[a.cost_center_id] = cells.get(a.cost_center_id, 0.0) + float(a.weekly_hours)
                total += float(a.weekly_hours)
            if total > capacity + 0.01:
                status = "OVER"
            elif total < capacity - 0.01:
                status = "UNDER"
            else:
                status = "OK"
            rows.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "allocation_method": method.value,
                "unit": "%" if is_plan else "h",
                "capacity": round(capacity, 2),
                "total_allocated": round(total, 2),
                "status": status,
                "cells": {k: round(v, 2) for k, v in cells.items()},
            })
        return {
            "as_of": today.isoformat(),
            "cost_centers": [
                {"id": c.id, "code": c.code, "name": c.name, "typ": c.typ.value}
                for c in cost_centers
            ],
            "rows": rows,
        }

    def _get(self, org_id: str, id_: str) -> WochenstundenZuweisung:
        w = self.db.execute(
            select(WochenstundenZuweisung).where(
                WochenstundenZuweisung.id == id_,
                WochenstundenZuweisung.org_id == org_id,
            )
        ).scalar_one_or_none()
        if w is None:
            raise APIError(404, "NOT_FOUND", "Wochenstunden-Zuweisung nicht gefunden.")
        return w

    def _require_org(self, model, id_: str, org_id: str, label: str):
        obj = self.db.get(model, id_)
        if obj is None or obj.org_id != org_id:
            raise APIError(422, "NOT_FOUND", f"{label} nicht gefunden.")
        return obj

    def _contract_for(
        self, org_id: str, employee_id: str, effective_date: date, body: dict[str, Any]
    ) -> EmployeeContract:
        sa_id = body.get("salary_assignment_id")
        if isinstance(sa_id, str) and sa_id:
            contract = self.db.get(EmployeeContract, sa_id)
            if (
                contract is None
                or contract.org_id != org_id
                or contract.employee_id != employee_id
            ):
                raise APIError(422, "CONTRACT_INVALID", "Vertrag (salary_assignment_id) ungültig.")
            return contract
        contract = get_aktiver_vertrag(self.db, employee_id, effective_date)
        if contract is None:
            raise APIError(
                422, "NO_CONTRACT", "Kein aktiver Vertrag zum effective_date gefunden."
            )
        return contract

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        employee_id = req_str(body, "employee_id")
        cost_center_id = req_str(body, "cost_center_id")
        weekly_hours = req_num(body, "weekly_hours")
        effective_date = parse_date(body.get("effective_date"), "effective_date")
        end_date = opt_date(body.get("end_date"), "end_date")
        if weekly_hours <= 0:
            raise APIError(422, "VALIDATION_HOURS", "weekly_hours muss > 0 sein.")

        self._require_org(Employee, employee_id, org_id, "Mitarbeiter")
        self._require_org(CostCenter, cost_center_id, org_id, "Kostenstelle")
        funding_measure_id = body.get("funding_measure_id")
        if isinstance(funding_measure_id, str) and funding_measure_id:
            self._require_org(FundingMeasure, funding_measure_id, org_id, "Fördermaßnahme")
        else:
            funding_measure_id = None
        finanzplan_position_id = body.get("finanzplan_position_id") or None

        contract = self._contract_for(org_id, employee_id, effective_date, body)
        assert_assignment_allowed(
            self.db,
            org_id=org_id,
            contract=contract,
            new_weekly_hours=weekly_hours,
            effective_date=effective_date,
            funding_measure_id=funding_measure_id,
        )

        w = WochenstundenZuweisung(
            org_id=org_id,
            employee_id=employee_id,
            salary_assignment_id=contract.id,
            cost_center_id=cost_center_id,
            funding_measure_id=funding_measure_id,
            finanzplan_position_id=finanzplan_position_id,
            weekly_hours=Decimal(str(weekly_hours)),
            effective_date=effective_date,
            end_date=end_date,
            note=body.get("note") if isinstance(body.get("note"), str) else None,
        )
        self.db.add(w)
        self.db.commit()
        self.db.refresh(w)
        return _wsz(w)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        w = self._get(org_id, id_)
        new_hours = (
            req_num(body, "weekly_hours") if "weekly_hours" in body else float(w.weekly_hours)
        )
        new_effective = (
            parse_date(body["effective_date"], "effective_date")
            if "effective_date" in body
            else w.effective_date
        )
        if new_hours <= 0:
            raise APIError(422, "VALIDATION_HOURS", "weekly_hours muss > 0 sein.")

        contract = self.db.get(EmployeeContract, w.salary_assignment_id)
        if contract is not None:
            assert_assignment_allowed(
                self.db,
                org_id=org_id,
                contract=contract,
                new_weekly_hours=new_hours,
                effective_date=new_effective,
                funding_measure_id=w.funding_measure_id,
                exclude_id=id_,
            )

        if "weekly_hours" in body:
            w.weekly_hours = Decimal(str(new_hours))
        if "effective_date" in body:
            w.effective_date = new_effective
        if "end_date" in body:
            w.end_date = opt_date(body["end_date"], "end_date")
        if "cost_center_id" in body and body["cost_center_id"]:
            self._require_org(CostCenter, body["cost_center_id"], org_id, "Kostenstelle")
            w.cost_center_id = body["cost_center_id"]
        if "note" in body:
            w.note = body["note"] if isinstance(body["note"], str) else None
        self.db.commit()
        self.db.refresh(w)
        return _wsz(w)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        w = self._get(org_id, id_)
        self.db.delete(w)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Wochenstunden-Zuweisung wurde gelöscht."}
