"""Cost-forecast read/run controllers (Module PCM, Area K)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.payroll import Employee
from app.models.pcm_forecast import PersonalCostForecast
from app.services.pcm.forecast_engine import run_forecast
from app.utils.serialization import decimal_str

_MONTHS_DE = [
    "Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
    "Jul", "Aug", "Sep", "Okt", "Nov", "Dez",
]


def _label(monat: date) -> str:
    return f"{_MONTHS_DE[monat.month - 1]} {monat.year}"


class ForecastService:
    def __init__(self, db: Session):
        self.db = db

    def run(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        fiscal_year_id = body.get("fiscal_year_id")
        if not fiscal_year_id:
            raise APIError(422, "VALIDATION_REQUIRED", "fiscal_year_id ist erforderlich.")
        include_proposed = bool(body.get("include_proposed", True))
        return run_forecast(
            self.db, org_id, fiscal_year_id, include_proposed=include_proposed
        )

    def _rows(self, org_id: str, fy_id: str) -> list[PersonalCostForecast]:
        return list(
            self.db.execute(
                select(PersonalCostForecast).where(
                    PersonalCostForecast.org_id == org_id,
                    PersonalCostForecast.fiscal_year_id == fy_id,
                )
            ).scalars()
        )

    def _names(self, org_id: str) -> dict[str, str]:
        rows = self.db.execute(
            select(Employee.id, Employee.vorname, Employee.nachname).where(
                Employee.org_id == org_id
            )
        ).all()
        return {r[0]: f"{r[1]} {r[2]}".strip() for r in rows}

    # ── K.1 dashboard ──────────────────────────────────────────────────────────
    def dashboard(self, org_id: str, fy_id: str) -> dict[str, Any]:
        rows = self._rows(org_id, fy_id)
        last_run = max((r.forecast_run_at for r in rows), default=None)
        by_month: dict[str, Decimal] = {}
        warnings: dict[str, int] = {}
        employees: set[str] = set()
        grand = Decimal(0)
        for r in rows:
            employees.add(r.employee_id)
            key = r.monat.isoformat()
            by_month[key] = by_month.get(key, Decimal(0)) + r.total_forecast
            grand += r.total_forecast
            if r.warning:
                warnings[r.warning] = warnings.get(r.warning, 0) + 1
        months = [
            {"monat": k, "label": _label(date.fromisoformat(k)), "total": decimal_str(v)}
            for k, v in sorted(by_month.items())
        ]
        return {
            "fiscal_year_id": fy_id,
            "last_run_at": last_run.isoformat() if last_run else None,
            "employee_count": len(employees),
            "grand_total": decimal_str(grand),
            "by_month": months,
            "warnings": warnings,
            "has_forecast": bool(rows),
        }

    # ── K.4 matrix ─────────────────────────────────────────────────────────────
    def matrix(self, org_id: str, fy_id: str) -> dict[str, Any]:
        rows = self._rows(org_id, fy_id)
        names = self._names(org_id)
        months = sorted({r.monat.isoformat() for r in rows})
        per_emp: dict[str, dict[str, Any]] = {}
        col_totals: dict[str, Decimal] = {m: Decimal(0) for m in months}
        for r in rows:
            e = per_emp.setdefault(
                r.employee_id,
                {"employee_id": r.employee_id, "employee_name": names.get(r.employee_id, "?"),
                 "cells": {}, "row_total": Decimal(0), "warnings": 0},
            )
            e["cells"][r.monat.isoformat()] = decimal_str(r.total_forecast)
            e["row_total"] += r.total_forecast
            if r.warning:
                e["warnings"] += 1
            col_totals[r.monat.isoformat()] += r.total_forecast
        out_rows = sorted(per_emp.values(), key=lambda e: e["employee_name"])
        for e in out_rows:
            e["row_total"] = decimal_str(e["row_total"])
        return {
            "months": [{"monat": m, "label": _label(date.fromisoformat(m))} for m in months],
            "rows": out_rows,
            "column_totals": {m: decimal_str(v) for m, v in col_totals.items()},
        }

    # ── K.5 employee-month detail ──────────────────────────────────────────────
    def detail(self, org_id: str, employee_id: str, monat: date) -> dict[str, Any]:
        monat = monat.replace(day=1)
        r = self.db.execute(
            select(PersonalCostForecast).where(
                PersonalCostForecast.org_id == org_id,
                PersonalCostForecast.employee_id == employee_id,
                PersonalCostForecast.monat == monat,
            )
        ).scalar_one_or_none()
        if r is None:
            raise APIError(404, "NOT_FOUND", "Keine Prognose für diesen Monat.")
        names = self._names(org_id)
        return {
            "employee_id": r.employee_id,
            "employee_name": names.get(r.employee_id, "?"),
            "monat": r.monat.isoformat(),
            "label": _label(r.monat),
            "forecast_level": r.forecast_level,
            "forecast_salary": decimal_str(r.forecast_salary),
            "standard_hours": decimal_str(r.standard_hours),
            "forecast_hours": decimal_str(r.forecast_hours),
            "prorated_salary": decimal_str(r.prorated_salary),
            "an_brutto": decimal_str(r.an_brutto),
            "ag_brutto": decimal_str(r.ag_brutto),
            "bav_amount": decimal_str(r.bav_amount),
            "fringe_amount": decimal_str(r.fringe_amount),
            "total_forecast": decimal_str(r.total_forecast),
            "warning": r.warning,
            "components": r.components or [],
        }

    # ── K.6 warnings ───────────────────────────────────────────────────────────
    def warnings(self, org_id: str, fy_id: str) -> dict[str, Any]:
        names = self._names(org_id)
        rows = [r for r in self._rows(org_id, fy_id) if r.warning]
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(r.warning, []).append({
                "employee_id": r.employee_id,
                "employee_name": names.get(r.employee_id, "?"),
                "monat": r.monat.isoformat(),
                "label": _label(r.monat),
                "total_forecast": decimal_str(r.total_forecast),
            })
        return {
            "total": len(rows),
            "groups": [
                {"warning": k, "count": len(v), "rows": v}
                for k, v in sorted(groups.items())
            ],
        }
