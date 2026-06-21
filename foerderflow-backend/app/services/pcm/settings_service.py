"""PCM module settings (Area A): setup overview (A.1), org BAV rate (A.2),
external-system ID mapping (A.4). Payroll-period management (A.3) is served by the
period endpoints (Area I)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import FiscalYear
from app.models.organization import Organization
from app.models.payroll import Employee
from app.models.pcm_tariff import SalaryLevel, SalaryTariff
from app.utils.serialization import decimal_str


class PcmSettingsService:
    def __init__(self, db: Session):
        self.db = db

    def _count(self, model, *where) -> int:
        return int(
            self.db.execute(select(func.count()).select_from(model).where(*where)).scalar_one()
        )

    # ── A.1 overview ───────────────────────────────────────────────────────────
    def overview(self, org_id: str) -> dict[str, Any]:
        org = self.db.get(Organization, org_id)
        today = date.today()
        fy = self.db.execute(
            select(FiscalYear).where(
                FiscalYear.org_id == org_id,
                FiscalYear.beginn <= today,
                FiscalYear.ende >= today,
            )
        ).scalars().first()
        tariffs = self._count(
            SalaryTariff, SalaryTariff.org_id == org_id, SalaryTariff.deleted_at.is_(None)
        )
        levels = self._count(SalaryLevel, SalaryLevel.org_id == org_id)
        employees = self._count(
            Employee, Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
        )
        tariff_bav = self._count(
            SalaryTariff,
            SalaryTariff.org_id == org_id,
            SalaryTariff.bav_rate_pct.is_not(None),
            SalaryTariff.deleted_at.is_(None),
        )
        bav_configured = bool(org and org.bav_rate_pct and org.bav_rate_pct > 0) or tariff_bav > 0
        return {
            "checklist": {
                "tariffs_entered": tariffs > 0,
                "levels_entered": levels > 0,
                "bav_configured": bav_configured,
                "has_employees": employees > 0,
                "fiscal_year_active": fy is not None,
            },
            "bav_rate_pct": decimal_str(org.bav_rate_pct) if org else "0",
            "active_fiscal_year": (
                {"jahr": fy.jahr, "status": fy.status.value} if fy else None
            ),
        }

    # ── A.2 BAV rate ───────────────────────────────────────────────────────────
    def get_bav(self, org_id: str) -> dict[str, Any]:
        org = self.db.get(Organization, org_id)
        rows = self.db.execute(
            select(SalaryTariff.tariff_code, SalaryTariff.bav_rate_pct).where(
                SalaryTariff.org_id == org_id,
                SalaryTariff.bav_rate_pct.is_not(None),
                SalaryTariff.deleted_at.is_(None),
            )
        ).all()
        overrides: dict[str, str | None] = {}
        for code, rate in rows:
            overrides.setdefault(code, decimal_str(rate))
        return {
            "bav_rate_pct": decimal_str(org.bav_rate_pct) if org else "0",
            "tariff_overrides": [
                {"tariff_code": k, "bav_rate_pct": v} for k, v in sorted(overrides.items())
            ],
        }

    def set_bav(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        org = self.db.get(Organization, org_id)
        if org is None:
            raise APIError(404, "NOT_FOUND", "Organisation nicht gefunden.")
        raw = body.get("bav_rate_pct")
        try:
            rate = Decimal(str(raw))
        except (TypeError, ValueError) as exc:
            raise APIError(422, "INVALID_RATE", "bav_rate_pct muss eine Zahl sein.") from exc
        if rate < 0 or rate > 100:
            raise APIError(422, "INVALID_RATE", "BAV-Satz muss zwischen 0 und 100 liegen.")
        org.bav_rate_pct = rate
        self.db.commit()
        return self.get_bav(org_id)

    # ── A.4 external system ID mapping ─────────────────────────────────────────
    def external_ids(self, org_id: str) -> list[dict[str, Any]]:
        emps = self.db.execute(
            select(Employee)
            .where(Employee.org_id == org_id)
            .order_by(Employee.nachname, Employee.vorname)
        ).scalars().all()
        return [{
            "id": e.id,
            "employee_code": e.employee_code,
            "name": f"{e.vorname} {e.nachname}".strip(),
            "employee_external_id": e.employee_external_id,
        } for e in emps]

    def set_external_id(
        self, org_id: str, employee_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        emp = self.db.execute(
            select(Employee).where(
                Employee.id == employee_id, Employee.org_id == org_id
            )
        ).scalar_one_or_none()
        if emp is None:
            raise APIError(404, "NOT_FOUND", "Mitarbeiter:in nicht gefunden.")
        emp.employee_external_id = (body.get("employee_external_id") or None)
        self.db.commit()
        return {
            "id": emp.id,
            "employee_code": emp.employee_code,
            "name": f"{emp.vorname} {emp.nachname}".strip(),
            "employee_external_id": emp.employee_external_id,
        }
