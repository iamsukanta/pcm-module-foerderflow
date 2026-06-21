"""Scenario planner controllers (Module PCM, Area L).

A scenario stores what-if parameter overrides (hour/level overrides, a global
tariff growth rate, hypothetical hires). Computing reuses the forecast engine's
per-month projection for baseline vs. scenario; promoting re-runs the committed
forecast with the overrides applied.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import ScenarioStatus
from app.models.master import FiscalYear
from app.models.organization import Organization
from app.models.payroll import Employee
from app.models.pcm_scenario import ForecastScenario, ForecastScenarioRow
from app.services.pcm._validate import req_str
from app.services.pcm.calc import compute_bav, round2
from app.services.pcm.forecast_engine import _forecast_one, _months, run_forecast
from app.services.pcm.tariff_lookup import resolve_tariff
from app.services.personal.berechnung import berechne_gehalt, get_ag_faktor
from app.utils.serialization import decimal_str

_MONTHS_DE = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
              "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _label(m: date) -> str:
    return f"{_MONTHS_DE[m.month - 1]} {m.year}"


def _scenario(s: ForecastScenario) -> dict[str, Any]:
    return {
        "id": s.id,
        "fiscal_year_id": s.fiscal_year_id,
        "name": s.name,
        "status": s.status.value,
        "params": s.params or {},
        "baseline_total": decimal_str(s.baseline_total),
        "scenario_total": decimal_str(s.scenario_total),
        "delta_total": decimal_str(s.delta_total),
        "computed_at": s.computed_at.isoformat() if s.computed_at else None,
    }


class ScenarioService:
    def __init__(self, db: Session):
        self.db = db

    def _get(self, org_id: str, id_: str) -> ForecastScenario:
        s = self.db.execute(
            select(ForecastScenario).where(
                ForecastScenario.id == id_, ForecastScenario.org_id == org_id
            )
        ).scalar_one_or_none()
        if s is None:
            raise APIError(404, "NOT_FOUND", "Szenario nicht gefunden.")
        return s

    # ── CRUD ───────────────────────────────────────────────────────────────────
    def list(self, org_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(ForecastScenario)
            .where(ForecastScenario.org_id == org_id)
            .order_by(ForecastScenario.created_at.desc())
        ).scalars().all()
        return [_scenario(s) for s in rows]

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        return _scenario(self._get(org_id, id_))

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        s = ForecastScenario(
            org_id=org_id,
            fiscal_year_id=req_str(body, "fiscal_year_id"),
            name=req_str(body, "name"),
            params=body.get("params") or {},
            status=ScenarioStatus.DRAFT,
        )
        self.db.add(s)
        self.db.commit()
        self.db.refresh(s)
        return _scenario(s)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        s = self._get(org_id, id_)
        if s.status == ScenarioStatus.PROMOTED:
            raise APIError(422, "SCENARIO_PROMOTED", "Promotetes Szenario ist nicht editierbar.")
        if "name" in body:
            s.name = req_str(body, "name")
        if "params" in body:
            s.params = body["params"] or {}
            s.status = ScenarioStatus.DRAFT  # params changed → recompute needed
        self.db.commit()
        self.db.refresh(s)
        return _scenario(s)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        s = self._get(org_id, id_)
        self.db.delete(s)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Szenario wurde gelöscht."}

    # ── compute (L.3 → L.4) ────────────────────────────────────────────────────
    def compute(self, org_id: str, id_: str) -> dict[str, Any]:
        s = self._get(org_id, id_)
        fy = self.db.get(FiscalYear, s.fiscal_year_id)
        if fy is None or fy.org_id != org_id:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        org = self.db.get(Organization, org_id)
        params = s.params or {}
        hour_ov = {o["employee_id"]: o["weekly_hours"] for o in params.get("hour_overrides", [])}
        level_ov = {o["employee_id"]: o["level"] for o in params.get("level_overrides", [])}
        growth = params.get("growth_rate_pct")
        months = _months(fy)
        run_at = datetime.now(UTC)

        self.db.execute(
            delete(ForecastScenarioRow).where(ForecastScenarioRow.scenario_id == s.id)
        )
        employees = self.db.execute(
            select(Employee).where(
                Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
            )
        ).scalars().all()

        base_total = scen_total = 0.0
        for emp in employees:
            name = f"{emp.vorname} {emp.nachname}".strip()
            override = {}
            if emp.id in hour_ov:
                override["hours"] = hour_ov[emp.id]
            if emp.id in level_ov:
                override["level"] = level_ov[emp.id]
            if growth:
                override["growth_pct"] = growth
            for month in months:
                base = _forecast_one(
                    self.db, org=org, org_id=org_id, fy_id=fy.id, emp=emp,
                    month=month, run_at=run_at, include_proposed=True, override=None,
                )
                if base is None:
                    continue
                scen = (
                    _forecast_one(
                        self.db, org=org, org_id=org_id, fy_id=fy.id, emp=emp,
                        month=month, run_at=run_at, include_proposed=True, override=override,
                    )
                    if override
                    else base
                )
                b = float(base.total_forecast)
                sc = float(scen.total_forecast)
                base_total += b
                scen_total += sc
                self.db.add(ForecastScenarioRow(
                    org_id=org_id, scenario_id=s.id, employee_id=emp.id,
                    employee_label=name, monat=month, baseline_total=round2(b),
                    scenario_total=round2(sc), delta=round2(sc - b),
                ))

        for hire in params.get("hires", []):
            label = hire.get("name") or f"Neue Stelle {hire.get('salary_group', '')}".strip()
            start = (
                date.fromisoformat(hire["start_month"]).replace(day=1)
                if hire.get("start_month")
                else fy.beginn.replace(day=1)
            )
            for month in months:
                if month < start:
                    continue
                cost = self._project_hire(org_id, org, hire, month)
                scen_total += cost
                self.db.add(ForecastScenarioRow(
                    org_id=org_id, scenario_id=s.id, employee_id=None,
                    employee_label=label, monat=month, baseline_total=Decimal("0.00"),
                    scenario_total=round2(cost), delta=round2(cost),
                ))

        s.baseline_total = round2(base_total)
        s.scenario_total = round2(scen_total)
        s.delta_total = round2(scen_total - base_total)
        s.status = ScenarioStatus.COMPUTED
        s.computed_at = run_at
        self.db.commit()
        return self.results(org_id, id_)

    def _project_hire(self, org_id: str, org, hire: dict[str, Any], month: date) -> float:
        hours = float(hire.get("weekly_hours", 0) or 0)
        base_full_time: float | None = None
        standard_hours = float(org.regelarbeitszeit_stunden)
        bav_rate = 0.0
        if hire.get("tariff_code") and hire.get("salary_group") and hire.get("level"):
            t = resolve_tariff(
                self.db, org_id=org_id, tariff_code=hire["tariff_code"],
                salary_group=hire["salary_group"], level=int(hire["level"]), month=month,
            )
            if t is not None:
                base_full_time = float(t.monthly_amount)
                standard_hours = float(t.standard_hours)
                bav_rate = float(t.bav_rate_pct or 0)
        if base_full_time is None:
            base_full_time = float(hire.get("monthly_amount", 0) or 0)
        ag_faktor = get_ag_faktor(self.db, org_id, "FESTANSTELLUNG", month)
        calc = berechne_gehalt(
            base_salary=base_full_time, assigned_hours=hours,
            standard_hours=standard_hours, ag_faktor=ag_faktor, components=[],
        )
        bav = compute_bav(actual_salary=calc.actual_salary, bav_rate_pct=bav_rate)
        return calc.ag_brutto + bav

    # ── results (L.4) ──────────────────────────────────────────────────────────
    def results(self, org_id: str, id_: str) -> dict[str, Any]:
        s = self._get(org_id, id_)
        rows = self.db.execute(
            select(ForecastScenarioRow).where(ForecastScenarioRow.scenario_id == s.id)
        ).scalars().all()
        by_month: dict[str, dict[str, Decimal]] = {}
        by_emp: dict[str, dict[str, Any]] = {}
        for r in rows:
            mk = r.monat.isoformat()
            mm = by_month.setdefault(mk, {"baseline": Decimal(0), "scenario": Decimal(0)})
            mm["baseline"] += r.baseline_total
            mm["scenario"] += r.scenario_total
            ek = r.employee_id or r.employee_label
            ee = by_emp.setdefault(ek, {
                "employee_id": r.employee_id, "label": r.employee_label,
                "baseline": Decimal(0), "scenario": Decimal(0),
            })
            ee["baseline"] += r.baseline_total
            ee["scenario"] += r.scenario_total
        return {
            "scenario": _scenario(s),
            "by_month": [
                {
                    "monat": k, "label": _label(date.fromisoformat(k)),
                    "baseline": decimal_str(v["baseline"]),
                    "scenario": decimal_str(v["scenario"]),
                    "delta": decimal_str(v["scenario"] - v["baseline"]),
                }
                for k, v in sorted(by_month.items())
            ],
            "by_employee": [
                {
                    "employee_id": v["employee_id"], "label": v["label"],
                    "baseline": decimal_str(v["baseline"]),
                    "scenario": decimal_str(v["scenario"]),
                    "delta": decimal_str(v["scenario"] - v["baseline"]),
                }
                for v in sorted(by_emp.values(), key=lambda e: e["label"])
            ],
        }

    # ── promote (L.5) ──────────────────────────────────────────────────────────
    def promote(self, org_id: str, id_: str) -> dict[str, Any]:
        s = self._get(org_id, id_)
        params = s.params or {}
        hour_ov = {o["employee_id"]: o["weekly_hours"] for o in params.get("hour_overrides", [])}
        level_ov = {o["employee_id"]: o["level"] for o in params.get("level_overrides", [])}
        growth = params.get("growth_rate_pct")
        # Build a per-employee override map (growth applies to every active employee).
        overrides: dict[str, dict[str, Any]] = {}
        emp_ids = set(hour_ov) | set(level_ov)
        if growth:
            emp_ids |= {
                e for (e,) in self.db.execute(
                    select(Employee.id).where(
                        Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
                    )
                ).all()
            }
        for eid in emp_ids:
            ov: dict[str, Any] = {}
            if eid in hour_ov:
                ov["hours"] = hour_ov[eid]
            if eid in level_ov:
                ov["level"] = level_ov[eid]
            if growth:
                ov["growth_pct"] = growth
            overrides[eid] = ov
        run_forecast(self.db, org_id, s.fiscal_year_id, overrides=overrides)
        s.status = ScenarioStatus.PROMOTED
        self.db.commit()
        return {
            "id": s.id,
            "status": s.status.value,
            "note": "Prognose mit Szenario-Parametern neu berechnet. Hypothetische "
                    "Neueinstellungen werden nicht in die Ist-Prognose übernommen.",
        }
