"""VWN itemized personnel-cost report (Module PCM, Area M).

Apportions each employee-month's ``payroll_detail_lines`` to a funding measure by
that month's PCM allocation share, producing an employee × component matrix for
the Verwendungsnachweis. Config (M.1) selects which components appear as named
line items; the rest roll up into an aggregate column.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import AllocationOrigin, PayrollDetailComponent
from app.models.funding import FundingMeasure
from app.models.payroll import MonthlyPayroll, PayrollAllocation
from app.models.pcm_vwn import VwnPersonnelConfig
from app.utils.serialization import decimal_str

DEFAULT_COMPONENTS = [c.value for c in PayrollDetailComponent]


class VwnService:
    def __init__(self, db: Session):
        self.db = db

    def _fm(self, org_id: str, fm_id: str) -> FundingMeasure:
        fm = self.db.get(FundingMeasure, fm_id)
        if fm is None or fm.org_id != org_id:
            raise APIError(404, "NOT_FOUND", "Fördermaßnahme nicht gefunden.")
        return fm

    # ── M.1 config ─────────────────────────────────────────────────────────────
    def get_config(self, org_id: str, fm_id: str) -> dict[str, Any]:
        self._fm(org_id, fm_id)
        cfg = self.db.execute(
            select(VwnPersonnelConfig).where(
                VwnPersonnelConfig.org_id == org_id,
                VwnPersonnelConfig.funding_measure_id == fm_id,
            )
        ).scalar_one_or_none()
        if cfg is None:
            return {
                "funding_measure_id": fm_id,
                "visible_components": DEFAULT_COMPONENTS,
                "bav_required": True,
                "aggregate_label": "Sonstiges",
                "hide_zero": True,
            }
        out = cfg.as_dict()
        if not out["visible_components"]:
            out["visible_components"] = DEFAULT_COMPONENTS
        return out

    def save_config(self, org_id: str, fm_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._fm(org_id, fm_id)
        cfg = self.db.execute(
            select(VwnPersonnelConfig).where(
                VwnPersonnelConfig.org_id == org_id,
                VwnPersonnelConfig.funding_measure_id == fm_id,
            )
        ).scalar_one_or_none()
        if cfg is None:
            cfg = VwnPersonnelConfig(org_id=org_id, funding_measure_id=fm_id)
            self.db.add(cfg)
        if "visible_components" in body:
            comps = body["visible_components"]
            cfg.visible_components = [c for c in comps if c in DEFAULT_COMPONENTS]
        if "bav_required" in body:
            cfg.bav_required = bool(body["bav_required"])
        if "aggregate_label" in body and body["aggregate_label"]:
            cfg.aggregate_label = str(body["aggregate_label"])[:80]
        if "hide_zero" in body:
            cfg.hide_zero = bool(body["hide_zero"])
        self.db.commit()
        return self.get_config(org_id, fm_id)

    # ── M.2 preview ────────────────────────────────────────────────────────────
    def preview(
        self, org_id: str, fm_id: str, from_month: date, to_month: date
    ) -> dict[str, Any]:
        fm = self._fm(org_id, fm_id)
        cfg = self.get_config(org_id, fm_id)
        visible: list[str] = cfg["visible_components"]
        aggregate_label = cfg["aggregate_label"]
        a, b = from_month.replace(day=1), to_month.replace(day=1)

        rows = self.db.execute(
            select(PayrollAllocation, MonthlyPayroll)
            .join(MonthlyPayroll, PayrollAllocation.payroll_id == MonthlyPayroll.id)
            .where(
                MonthlyPayroll.org_id == org_id,
                PayrollAllocation.origin == AllocationOrigin.PCM,
                PayrollAllocation.funding_measure_id == fm_id,
                MonthlyPayroll.monat >= a,
                MonthlyPayroll.monat <= b,
            )
        ).all()

        # Total PCM prozent each payroll directs to this funding measure.
        prozent_by_payroll: dict[str, float] = {}
        payroll_by_id: dict[str, MonthlyPayroll] = {}
        for alloc, payroll in rows:
            prozent_by_payroll[payroll.id] = (
                prozent_by_payroll.get(payroll.id, 0.0) + float(alloc.prozent)
            )
            payroll_by_id[payroll.id] = payroll

        per_emp: dict[str, dict[str, Any]] = {}
        for pid, prozent in prozent_by_payroll.items():
            payroll = payroll_by_id[pid]
            emp = payroll.employee
            e = per_emp.setdefault(payroll.employee_id, {
                "employee_id": payroll.employee_id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip() if emp else "?",
                "comp": {},
            })
            for line in payroll.detail_lines:
                amt = float(line.amount) * prozent / 100.0
                e["comp"][line.component.value] = e["comp"].get(line.component.value, 0.0) + amt

        # Build output rows + totals.
        comp_totals: dict[str, float] = dict.fromkeys(visible, 0.0)
        agg_total = 0.0
        out_rows = []
        for e in sorted(per_emp.values(), key=lambda e: e["employee_name"]):
            cells = {c: round(e["comp"].get(c, 0.0), 2) for c in visible}
            agg = round(sum(v for k, v in e["comp"].items() if k not in visible), 2)
            total = round(sum(cells.values()) + agg, 2)
            for c in visible:
                comp_totals[c] += cells[c]
            agg_total += agg
            out_rows.append({
                "employee_id": e["employee_id"],
                "employee_name": e["employee_name"],
                "cells": {c: decimal_str(Decimal(str(cells[c]))) for c in visible},
                "aggregate": decimal_str(Decimal(str(agg))),
                "total": decimal_str(Decimal(str(total))),
            })

        shown = visible
        if cfg["hide_zero"]:
            shown = [c for c in visible if round(comp_totals[c], 2) != 0]
        grand = round(sum(comp_totals.values()) + agg_total, 2)
        return {
            "funding_measure_id": fm_id,
            "funding_measure_name": fm.name,
            "from_month": a.isoformat(),
            "to_month": b.isoformat(),
            "components": shown,
            "aggregate_label": aggregate_label,
            "has_aggregate": round(agg_total, 2) != 0,
            "rows": out_rows,
            "component_totals": {
                c: decimal_str(Decimal(str(round(comp_totals[c], 2)))) for c in shown
            },
            "aggregate_total": decimal_str(Decimal(str(round(agg_total, 2)))),
            "grand_total": decimal_str(Decimal(str(grand))),
        }

    # ── M.3 export ─────────────────────────────────────────────────────────────
    def export_csv(
        self, org_id: str, fm_id: str, from_month: date, to_month: date
    ) -> tuple[str, bytes]:
        data = self.preview(org_id, fm_id, from_month, to_month)
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=";")
        header = ["Mitarbeiter:in", *data["components"]]
        if data["has_aggregate"]:
            header.append(data["aggregate_label"])
        header.append("Summe")
        w.writerow(header)
        for r in data["rows"]:
            row = [r["employee_name"], *[r["cells"][c] for c in data["components"]]]
            if data["has_aggregate"]:
                row.append(r["aggregate"])
            row.append(r["total"])
            w.writerow(row)
        totals = ["Summe", *[data["component_totals"][c] for c in data["components"]]]
        if data["has_aggregate"]:
            totals.append(data["aggregate_total"])
        totals.append(data["grand_total"])
        w.writerow(totals)
        filename = f"VWN_Personalkosten_{data['from_month']}_{data['to_month']}.csv"
        return filename, buf.getvalue().encode("utf-8-sig")
