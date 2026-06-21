"""Bonus templates + per-employee bonuses & adjustments controllers
(Module PCM, Areas G & H). Org-scoped ``{data}``/``APIError`` envelopes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import (
    AdjustmentType,
    BonusApplicableTo,
    BonusType,
    BruttoType,
    ProrationRule,
)
from app.models.payroll import Employee
from app.models.pcm_bonus import BonusPayment, BonusTemplate, SalaryAdjustment
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm._validate import opt_date, parse_date, req_num, req_str
from app.services.pcm.bonus_engine import template_matches
from app.services.personal.berechnung import get_aktiver_vertrag
from app.utils.serialization import decimal_str


def _enum(value: str, enum_cls, code: str):
    if value not in {m.value for m in enum_cls}:
        raise APIError(422, code, f"Ungültiger Wert: {value}.")
    return enum_cls(value)


def _template(t: BonusTemplate, matched_count: int | None = None) -> dict[str, Any]:
    out = {
        "id": t.id,
        "name": t.name,
        "tariff_code": t.tariff_code,
        "salary_group_min": t.salary_group_min,
        "salary_group_max": t.salary_group_max,
        "applicable_to": t.applicable_to.value,
        "type": t.type.value,
        "amount": decimal_str(t.amount),
        "brutto_type": t.brutto_type.value,
        "proration_rule": t.proration_rule.value,
        "reference_month": t.reference_month,
        "payment_month": t.payment_month,
        "prorate_by_employment_period": t.prorate_by_employment_period,
        "period_from": t.period_from.isoformat(),
        "period_to": t.period_to.isoformat() if t.period_to else None,
    }
    if matched_count is not None:
        out["matched_count"] = matched_count
    return out


def _payment(p: BonusPayment) -> dict[str, Any]:
    return {
        "id": p.id,
        "employee_id": p.employee_id,
        "type": p.type.value,
        "amount": decimal_str(p.amount),
        "brutto_type": p.brutto_type.value,
        "proration_rule": p.proration_rule.value,
        "reference_month": p.reference_month,
        "payment_month": p.payment_month,
        "prorate_by_employment_period": p.prorate_by_employment_period,
        "period_from": p.period_from.isoformat(),
        "period_to": p.period_to.isoformat() if p.period_to else None,
        "description": p.description,
        "source_template_id": p.source_template_id,
    }


def _adjustment(a: SalaryAdjustment) -> dict[str, Any]:
    return {
        "id": a.id,
        "employee_id": a.employee_id,
        "type": a.type.value,
        "amount": decimal_str(a.amount),
        "brutto_type": a.brutto_type.value,
        "proration_rule": a.proration_rule.value,
        "period_from": a.period_from.isoformat(),
        "period_to": a.period_to.isoformat() if a.period_to else None,
        "description": a.description,
    }


class BonusService:
    def __init__(self, db: Session):
        self.db = db

    # ── templates (G) ──────────────────────────────────────────────────────────
    def list_templates(self, org_id: str) -> list[dict[str, Any]]:
        templates = (
            self.db.execute(
                select(BonusTemplate)
                .where(BonusTemplate.org_id == org_id)
                .order_by(BonusTemplate.name)
            )
            .scalars()
            .all()
        )
        return [
            _template(t, self._matched_rows(org_id, t)[1]) for t in templates
        ]

    def _get_template(self, org_id: str, id_: str) -> BonusTemplate:
        t = self.db.execute(
            select(BonusTemplate).where(
                BonusTemplate.id == id_, BonusTemplate.org_id == org_id
            )
        ).scalar_one_or_none()
        if t is None:
            raise APIError(404, "NOT_FOUND", "Bonusvorlage nicht gefunden.")
        return t

    def get_template(self, org_id: str, id_: str) -> dict[str, Any]:
        return _template(self._get_template(org_id, id_))

    def _template_from_body(self, org_id: str, body: dict[str, Any]) -> BonusTemplate:
        btype = _enum(req_str(body, "type"), BonusType, "INVALID_BONUS_TYPE")
        if btype == BonusType.REFERENCE_MONTH and not (
            body.get("reference_month") and body.get("payment_month")
        ):
            raise APIError(
                422,
                "MISSING_MONTHS",
                "reference_month und payment_month sind für REFERENCE_MONTH erforderlich.",
            )
        return BonusTemplate(
            org_id=org_id,
            name=req_str(body, "name"),
            tariff_code=(body.get("tariff_code") or None),
            salary_group_min=(body.get("salary_group_min") or None),
            salary_group_max=(body.get("salary_group_max") or None),
            applicable_to=_enum(
                body.get("applicable_to", "ALL"), BonusApplicableTo, "INVALID_APPLICABLE_TO"
            ),
            type=btype,
            amount=Decimal(str(req_num(body, "amount"))),
            brutto_type=_enum(req_str(body, "brutto_type"), BruttoType, "INVALID_BRUTTO_TYPE"),
            proration_rule=_enum(
                body.get("proration_rule", "FULL"), ProrationRule, "INVALID_PRORATION"
            ),
            reference_month=body.get("reference_month"),
            payment_month=body.get("payment_month"),
            prorate_by_employment_period=bool(body.get("prorate_by_employment_period", False)),
            period_from=parse_date(body.get("period_from"), "period_from"),
            period_to=opt_date(body.get("period_to"), "period_to"),
        )

    def create_template(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        t = self._template_from_body(org_id, body)
        self.db.add(t)
        self.db.commit()
        self.db.refresh(t)
        return _template(t)

    def update_template(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        t = self._get_template(org_id, id_)
        fresh = self._template_from_body(org_id, body)
        for field in (
            "name", "tariff_code", "salary_group_min", "salary_group_max",
            "applicable_to", "type", "amount", "brutto_type", "proration_rule",
            "reference_month", "payment_month", "prorate_by_employment_period",
            "period_from", "period_to",
        ):
            setattr(t, field, getattr(fresh, field))
        self.db.commit()
        self.db.refresh(t)
        return _template(t)

    def delete_template(self, org_id: str, id_: str) -> dict[str, Any]:
        t = self._get_template(org_id, id_)
        self.db.delete(t)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Bonusvorlage wurde gelöscht."}

    # ── eligibility preview (G.3) ──────────────────────────────────────────────
    def _matched_rows(
        self, org_id: str, template: BonusTemplate
    ) -> tuple[list[dict[str, Any]], int]:
        today = date.today()
        employees = (
            self.db.execute(
                select(Employee).where(
                    Employee.org_id == org_id, Employee.ist_aktiv.is_(True)
                )
            )
            .scalars()
            .all()
        )
        rows: list[dict[str, Any]] = []
        matched = 0
        for emp in employees:
            contract = get_aktiver_vertrag(self.db, emp.id, today)
            if contract is None:
                rows.append({
                    "employee_id": emp.id,
                    "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                    "tariff_code": None, "salary_group": None,
                    "matched": False, "reason": "Kein aktiver Vertrag",
                })
                continue
            assignments = (
                self.db.execute(
                    select(WochenstundenZuweisung).where(
                        WochenstundenZuweisung.org_id == org_id,
                        WochenstundenZuweisung.employee_id == emp.id,
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
            from app.services.pcm.bonus_engine import _cost_center_flags

            has_project, has_overhead = _cost_center_flags(self.db, assignments)
            tariff_code = (
                contract.salary_tariff.tariff_code if contract.salary_tariff else None
            )
            ok = template_matches(
                template,
                tariff_code=tariff_code,
                salary_group=contract.entgeltgruppe,
                has_project=has_project,
                has_overhead=has_overhead,
            )
            if ok:
                matched += 1
            rows.append({
                "employee_id": emp.id,
                "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                "tariff_code": tariff_code,
                "salary_group": contract.entgeltgruppe,
                "matched": ok,
                "reason": None if ok else "Erfüllt Kriterien nicht",
            })
        return rows, matched

    def preview_eligibility(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        # Either an existing template id, or ad-hoc criteria from the unsaved form.
        if body.get("template_id"):
            template = self._get_template(org_id, body["template_id"])
        else:
            template = BonusTemplate(
                org_id=org_id,
                name="(Vorschau)",
                tariff_code=(body.get("tariff_code") or None),
                salary_group_min=(body.get("salary_group_min") or None),
                salary_group_max=(body.get("salary_group_max") or None),
                applicable_to=_enum(
                    body.get("applicable_to", "ALL"),
                    BonusApplicableTo, "INVALID_APPLICABLE_TO",
                ),
                type=BonusType.FIXED,
                amount=Decimal("0"),
                brutto_type=BruttoType.EMPLOYER,
                proration_rule=ProrationRule.FULL,
                period_from=date.today(),
            )
        rows, matched = self._matched_rows(org_id, template)
        return {"matched": matched, "total": len(rows), "rows": rows}

    # ── per-employee bonus payments (H) ────────────────────────────────────────
    def list_payments(self, org_id: str, employee_id: str) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                select(BonusPayment)
                .where(
                    BonusPayment.org_id == org_id,
                    BonusPayment.employee_id == employee_id,
                )
                .order_by(BonusPayment.period_from.desc())
            )
            .scalars()
            .all()
        )
        return [_payment(p) for p in rows]

    def create_payment(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        btype = _enum(req_str(body, "type"), BonusType, "INVALID_BONUS_TYPE")
        p = BonusPayment(
            org_id=org_id,
            employee_id=req_str(body, "employee_id"),
            type=btype,
            amount=Decimal(str(req_num(body, "amount"))),
            brutto_type=_enum(req_str(body, "brutto_type"), BruttoType, "INVALID_BRUTTO_TYPE"),
            proration_rule=_enum(
                body.get("proration_rule", "FULL"), ProrationRule, "INVALID_PRORATION"
            ),
            reference_month=body.get("reference_month"),
            payment_month=body.get("payment_month"),
            prorate_by_employment_period=bool(body.get("prorate_by_employment_period", False)),
            period_from=parse_date(body.get("period_from"), "period_from"),
            period_to=opt_date(body.get("period_to"), "period_to"),
            description=(body.get("description") or None),
        )
        self.db.add(p)
        self.db.commit()
        self.db.refresh(p)
        return _payment(p)

    def delete_payment(self, org_id: str, id_: str) -> dict[str, Any]:
        p = self.db.execute(
            select(BonusPayment).where(
                BonusPayment.id == id_, BonusPayment.org_id == org_id
            )
        ).scalar_one_or_none()
        if p is None:
            raise APIError(404, "NOT_FOUND", "Bonus nicht gefunden.")
        self.db.delete(p)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Bonus wurde gelöscht."}

    # ── per-employee salary adjustments (H) ────────────────────────────────────
    def list_adjustments(self, org_id: str, employee_id: str) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                select(SalaryAdjustment)
                .where(
                    SalaryAdjustment.org_id == org_id,
                    SalaryAdjustment.employee_id == employee_id,
                )
                .order_by(SalaryAdjustment.period_from.desc())
            )
            .scalars()
            .all()
        )
        return [_adjustment(a) for a in rows]

    def create_adjustment(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        a = SalaryAdjustment(
            org_id=org_id,
            employee_id=req_str(body, "employee_id"),
            type=_enum(req_str(body, "type"), AdjustmentType, "INVALID_ADJUSTMENT_TYPE"),
            amount=Decimal(str(req_num(body, "amount"))),
            brutto_type=_enum(req_str(body, "brutto_type"), BruttoType, "INVALID_BRUTTO_TYPE"),
            proration_rule=_enum(
                body.get("proration_rule", "FULL"), ProrationRule, "INVALID_PRORATION"
            ),
            period_from=parse_date(body.get("period_from"), "period_from"),
            period_to=opt_date(body.get("period_to"), "period_to"),
            description=(body.get("description") or None),
        )
        self.db.add(a)
        self.db.commit()
        self.db.refresh(a)
        return _adjustment(a)

    def delete_adjustment(self, org_id: str, id_: str) -> dict[str, Any]:
        a = self.db.execute(
            select(SalaryAdjustment).where(
                SalaryAdjustment.id == id_, SalaryAdjustment.org_id == org_id
            )
        ).scalar_one_or_none()
        if a is None:
            raise APIError(404, "NOT_FOUND", "Anpassung nicht gefunden.")
        self.db.delete(a)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Anpassung wurde gelöscht."}
