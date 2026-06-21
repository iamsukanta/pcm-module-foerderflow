"""Payroll allocation views (Module PCM, Area N) — read-only reporting over the
PCM-generated ``payroll_allocations`` (origin = PCM)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AllocationOrigin
from app.models.payroll import MonthlyPayroll, PayrollAllocation
from app.utils.serialization import decimal_str

_MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
              "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
_NO_FM = "__none__"


def _label(m: date) -> str:
    return f"{_MONTHS_DE[m.month - 1]} {m.year}"


class PayrollAllocationService:
    def __init__(self, db: Session):
        self.db = db

    def _pcm_allocations(self, org_id: str, fiscal_year_id: str, monat: date | None):
        stmt = (
            select(PayrollAllocation, MonthlyPayroll)
            .join(MonthlyPayroll, PayrollAllocation.payroll_id == MonthlyPayroll.id)
            .where(
                MonthlyPayroll.org_id == org_id,
                MonthlyPayroll.fiscal_year_id == fiscal_year_id,
                PayrollAllocation.origin == AllocationOrigin.PCM,
            )
        )
        if monat is not None:
            stmt = stmt.where(MonthlyPayroll.monat == monat.replace(day=1))
        return self.db.execute(stmt).all()

    # ── N.1 overview (per period, grouped by funding measure) ──────────────────
    def overview(self, org_id: str, fiscal_year_id: str, monat: date) -> dict[str, Any]:
        rows = self._pcm_allocations(org_id, fiscal_year_id, monat)
        groups: dict[str, dict[str, Any]] = {}
        grand = Decimal(0)
        for alloc, payroll in rows:
            fm = alloc.funding_measure
            key = fm.id if fm else _NO_FM
            g = groups.setdefault(key, {
                "funding_measure_id": fm.id if fm else None,
                "funding_measure_name": fm.name if fm else "Ohne Fördermaßnahme",
                "total": Decimal(0),
                "rows": [],
            })
            emp = payroll.employee
            cc = alloc.cost_center
            fp = alloc.finanzplan_position
            g["rows"].append({
                "employee_name": f"{emp.vorname} {emp.nachname}".strip() if emp else "?",
                "cost_center": f"{cc.code} · {cc.name}" if cc else None,
                "finanzplan_position": fp.positionscode if fp else None,
                "betrag_anteil": decimal_str(alloc.betrag_anteil),
                "prozent": decimal_str(alloc.prozent),
                "payroll_status": payroll.status.value,
            })
            g["total"] += alloc.betrag_anteil
            grand += alloc.betrag_anteil
        out = sorted(groups.values(), key=lambda g: g["funding_measure_name"])
        for g in out:
            g["total"] = decimal_str(g["total"])
        return {
            "monat": monat.replace(day=1).isoformat(),
            "label": _label(monat),
            "grand_total": decimal_str(grand),
            "groups": out,
        }

    # ── N.2 per grant project (cross-period) ───────────────────────────────────
    def per_grant(
        self, org_id: str, fiscal_year_id: str, funding_measure_id: str
    ) -> dict[str, Any]:
        rows = self._pcm_allocations(org_id, fiscal_year_id, None)
        months: set[str] = set()
        per_emp: dict[str, dict[str, Any]] = {}
        col_totals: dict[str, Decimal] = {}
        grand = Decimal(0)
        fm_name = None
        for alloc, payroll in rows:
            if alloc.funding_measure_id != funding_measure_id:
                continue
            if alloc.funding_measure and fm_name is None:
                fm_name = alloc.funding_measure.name
            mk = payroll.monat.isoformat()
            months.add(mk)
            emp = payroll.employee
            ek = payroll.employee_id
            e = per_emp.setdefault(ek, {
                "employee_id": ek,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip() if emp else "?",
                "cells": {},
                "row_total": Decimal(0),
            })
            e["cells"][mk] = e["cells"].get(mk, Decimal(0)) + alloc.betrag_anteil
            e["row_total"] += alloc.betrag_anteil
            col_totals[mk] = col_totals.get(mk, Decimal(0)) + alloc.betrag_anteil
            grand += alloc.betrag_anteil
        out_rows = sorted(per_emp.values(), key=lambda e: e["employee_name"])
        for e in out_rows:
            e["cells"] = {k: decimal_str(v) for k, v in e["cells"].items()}
            e["row_total"] = decimal_str(e["row_total"])
        sorted_months = sorted(months)
        return {
            "funding_measure_id": funding_measure_id,
            "funding_measure_name": fm_name,
            "months": [{"monat": m, "label": _label(date.fromisoformat(m))} for m in sorted_months],
            "rows": out_rows,
            "column_totals": {m: decimal_str(v) for m, v in col_totals.items()},
            "grand_total": decimal_str(grand),
        }
