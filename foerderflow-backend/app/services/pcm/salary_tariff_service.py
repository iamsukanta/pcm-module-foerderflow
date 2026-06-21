"""Salary-tariff CRUD + levels + month resolution (Module PCM controllers).

Org-scoped, ``{data}``/``APIError`` envelopes like the rest of the API. Create and
update enforce the validity-window no-overlap rule via
``app.services.pcm.tariff_lookup.assert_no_overlap``.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import FiscalYear
from app.models.payroll import Employee, EmployeeContract
from app.models.pcm_tariff import SalaryLevel, SalaryTariff
from app.services.pcm._validate import (
    opt_date,
    opt_num,
    parse_date,
    req_int,
    req_num,
    req_str,
)
from app.services.pcm.tariff_lookup import (
    assert_fiscal_year_open,
    assert_no_overlap,
    assert_window_valid,
    resolve_tariff,
)
from app.utils.serialization import decimal_str


def _natural_key(group: str) -> tuple[str, int, str]:
    """Natural sort key for a salary group: 'E2' < 'E10' (not lexicographic).

    Splits the leading alpha prefix from the numeric body so 'E1, E2, … E10, E11'
    order correctly. A trailing sub-grade suffix (e.g. 'S6a') sorts after 'S6'.
    """
    i = 0
    while i < len(group) and not group[i].isdigit():
        i += 1
    prefix = group[:i]
    j = i
    while j < len(group) and group[j].isdigit():
        j += 1
    number = int(group[i:j]) if j > i else 0
    suffix = group[j:]
    return (prefix, number, suffix)


def _tariff(t: SalaryTariff) -> dict[str, Any]:
    return {
        "id": t.id,
        "org_id": t.org_id,
        "tariff_code": t.tariff_code,
        "salary_group": t.salary_group,
        "level": t.level,
        "monthly_amount": decimal_str(t.monthly_amount),
        "standard_hours": decimal_str(t.standard_hours),
        "is_proposed": t.is_proposed,
        "valid_from": t.valid_from.isoformat(),
        "valid_to": t.valid_to.isoformat() if t.valid_to else None,
        "bav_rate_pct": decimal_str(t.bav_rate_pct),
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
    }


def _level(level: SalaryLevel) -> dict[str, Any]:
    return {
        "id": level.id,
        "org_id": level.org_id,
        "tariff_id": level.tariff_id,
        "salary_group": level.salary_group,
        "level_no": level.level_no,
        "monthly_amount": decimal_str(level.monthly_amount),
        "months_to_next_level": level.months_to_next_level,
    }


class SalaryTariffService:
    def __init__(self, db: Session):
        self.db = db

    # ── reads ─────────────────────────────────────────────────────────────────
    def list(self, org_id: str, filters: dict[str, str]) -> list[dict[str, Any]]:
        stmt = select(SalaryTariff).where(
            SalaryTariff.org_id == org_id, SalaryTariff.deleted_at.is_(None)
        )
        if filters.get("tariff_code"):
            stmt = stmt.where(SalaryTariff.tariff_code == filters["tariff_code"])
        if filters.get("salary_group"):
            stmt = stmt.where(SalaryTariff.salary_group == filters["salary_group"])
        is_proposed = filters.get("is_proposed")
        if is_proposed in ("true", "false"):
            stmt = stmt.where(SalaryTariff.is_proposed.is_(is_proposed == "true"))
        stmt = stmt.order_by(
            SalaryTariff.tariff_code,
            SalaryTariff.salary_group,
            SalaryTariff.level,
            SalaryTariff.valid_from,
        )
        return [_tariff(t) for t in self.db.execute(stmt).scalars().all()]

    def _get(self, org_id: str, id_: str) -> SalaryTariff:
        t = self.db.execute(
            select(SalaryTariff).where(
                SalaryTariff.id == id_,
                SalaryTariff.org_id == org_id,
                SalaryTariff.deleted_at.is_(None),
            )
        ).scalar_one_or_none()
        if t is None:
            raise APIError(404, "NOT_FOUND", "Tarif-Eintrag nicht gefunden.")
        return t

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        t = self._get(org_id, id_)
        row = _tariff(t)
        row["levels"] = [
            _level(level)
            for level in sorted(t.levels, key=lambda level: level.level_no)
        ]
        return row

    def resolve(self, org_id: str, params: dict[str, str]) -> dict[str, Any] | None:
        tariff_code = params.get("tariff_code")
        salary_group = params.get("salary_group")
        level = params.get("level")
        month = params.get("month")
        if not (tariff_code and salary_group and level and month):
            raise APIError(
                422,
                "MISSING_FIELDS",
                "tariff_code, salary_group, level und month sind erforderlich.",
            )
        try:
            level_int = int(level)
            month_date = date.fromisoformat(month)
        except ValueError:
            raise APIError(  # noqa: B904
                422, "VALIDATION", "level (Zahl) und month (YYYY-MM-DD) erforderlich."
            )
        t = resolve_tariff(
            self.db,
            org_id=org_id,
            tariff_code=tariff_code,
            salary_group=salary_group,
            level=level_int,
            month=month_date,
        )
        return _tariff(t) if t is not None else None

    # ── writes ────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        tariff_code = req_str(body, "tariff_code")
        salary_group = req_str(body, "salary_group")
        level = req_int(body, "level")
        monthly_amount = req_num(body, "monthly_amount")
        standard_hours = req_num(body, "standard_hours")
        valid_from = parse_date(body.get("valid_from"), "valid_from")
        valid_to = opt_date(body.get("valid_to"), "valid_to")
        is_proposed = bool(body.get("is_proposed", False))
        bav_rate_pct = opt_num(body, "bav_rate_pct")

        if standard_hours <= 0:
            raise APIError(422, "VALIDATION_STANDARD_HOURS", "standard_hours muss > 0 sein.")

        assert_fiscal_year_open(self.db, org_id=org_id, on=valid_from)
        assert_no_overlap(
            self.db,
            org_id=org_id,
            tariff_code=tariff_code,
            salary_group=salary_group,
            level=level,
            is_proposed=is_proposed,
            valid_from=valid_from,
            valid_to=valid_to,
        )

        t = SalaryTariff(
            org_id=org_id,
            tariff_code=tariff_code,
            salary_group=salary_group,
            level=level,
            monthly_amount=Decimal(str(monthly_amount)),
            standard_hours=Decimal(str(standard_hours)),
            is_proposed=is_proposed,
            valid_from=valid_from,
            valid_to=valid_to,
            bav_rate_pct=Decimal(str(bav_rate_pct)) if bav_rate_pct is not None else None,
        )
        self.db.add(t)
        self.db.flush()
        for lvl in body.get("levels") or []:
            self._add_level(org_id, t.id, t.salary_group, lvl)
        self.db.commit()
        self.db.refresh(t)
        return _tariff(t)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        t = self._get(org_id, id_)
        # Apply changes to a working copy of the key/window fields.
        tariff_code = req_str(body, "tariff_code") if "tariff_code" in body else t.tariff_code
        salary_group = (
            req_str(body, "salary_group") if "salary_group" in body else t.salary_group
        )
        level = req_int(body, "level") if "level" in body else t.level
        is_proposed = bool(body["is_proposed"]) if "is_proposed" in body else t.is_proposed
        valid_from = (
            parse_date(body["valid_from"], "valid_from")
            if "valid_from" in body
            else t.valid_from
        )
        valid_to = (
            opt_date(body["valid_to"], "valid_to") if "valid_to" in body else t.valid_to
        )

        assert_fiscal_year_open(self.db, org_id=org_id, on=valid_from)
        # Re-check the no-overlap rule against the other rows.
        assert_no_overlap(
            self.db,
            org_id=org_id,
            tariff_code=tariff_code,
            salary_group=salary_group,
            level=level,
            is_proposed=is_proposed,
            valid_from=valid_from,
            valid_to=valid_to,
            exclude_id=id_,
        )

        t.tariff_code = tariff_code
        t.salary_group = salary_group
        t.level = level
        t.is_proposed = is_proposed
        t.valid_from = valid_from
        t.valid_to = valid_to
        if "monthly_amount" in body:
            t.monthly_amount = Decimal(str(req_num(body, "monthly_amount")))
        if "standard_hours" in body:
            sh = req_num(body, "standard_hours")
            if sh <= 0:
                raise APIError(422, "VALIDATION_STANDARD_HOURS", "standard_hours muss > 0 sein.")
            t.standard_hours = Decimal(str(sh))
        if "bav_rate_pct" in body:
            rate = opt_num(body, "bav_rate_pct")
            t.bav_rate_pct = Decimal(str(rate)) if rate is not None else None
        self.db.commit()
        self.db.refresh(t)
        return _tariff(t)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        t = self._get(org_id, id_)
        # ROW_IN_USE guard: block delete if any contract (salary assignment) is on
        # this tariff row. The row may still be edited — only deletion is blocked.
        in_use = self.db.execute(
            select(func.count())
            .select_from(EmployeeContract)
            .where(
                EmployeeContract.org_id == org_id,
                EmployeeContract.salary_tariff_id == id_,
            )
        ).scalar_one()
        if in_use:
            raise APIError(
                422,
                "ROW_IN_USE",
                "Dieser Tarif-Eintrag kann nicht gelöscht werden — "
                f"{in_use} Mitarbeitende sind ihm zugeordnet.",
                extra={"employee_count": int(in_use)},
            )
        # Soft-delete to preserve audit/payroll history (DevGuide §4.5).
        t.deleted_at = datetime.now(UTC)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Tarif-Eintrag wurde gelöscht."}

    # ── levels ────────────────────────────────────────────────────────────────
    def _add_level(
        self, org_id: str, tariff_id: str, default_group: str, body: dict[str, Any]
    ) -> SalaryLevel:
        level = SalaryLevel(
            org_id=org_id,
            tariff_id=tariff_id,
            salary_group=(body.get("salary_group") or default_group),
            level_no=req_int(body, "level_no"),
            monthly_amount=Decimal(str(req_num(body, "monthly_amount"))),
            months_to_next_level=(
                req_int(body, "months_to_next_level")
                if body.get("months_to_next_level") is not None
                else None
            ),
        )
        self.db.add(level)
        return level

    def list_levels(self, org_id: str, tariff_id: str) -> list[dict[str, Any]]:
        t = self._get(org_id, tariff_id)
        return [_level(level) for level in sorted(t.levels, key=lambda level: level.level_no)]

    def create_level(
        self, org_id: str, tariff_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        t = self._get(org_id, tariff_id)
        level = self._add_level(org_id, t.id, t.salary_group, body)
        self.db.commit()
        self.db.refresh(level)
        return _level(level)

    def update_level(
        self, org_id: str, level_id: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        level = self.db.execute(
            select(SalaryLevel).where(
                SalaryLevel.id == level_id, SalaryLevel.org_id == org_id
            )
        ).scalar_one_or_none()
        if level is None:
            raise APIError(404, "NOT_FOUND", "Stufe nicht gefunden.")
        if "monthly_amount" in body:
            amount = req_num(body, "monthly_amount")
            if amount <= 0:
                raise APIError(422, "INVALID_AMOUNT", "Betrag muss > 0 sein.")
            level.monthly_amount = Decimal(str(amount))
        if "months_to_next_level" in body:
            raw = body["months_to_next_level"]
            if raw is None:
                level.months_to_next_level = None  # maximum tier
            else:
                months = req_int(body, "months_to_next_level")
                if months <= 0:
                    raise APIError(
                        422, "VALIDATION_INT", "months_to_next_level muss > 0 sein."
                    )
                level.months_to_next_level = months
        self.db.commit()
        self.db.refresh(level)
        return _level(level)

    def delete_level(self, org_id: str, level_id: str) -> dict[str, Any]:
        level = self.db.execute(
            select(SalaryLevel).where(
                SalaryLevel.id == level_id, SalaryLevel.org_id == org_id
            )
        ).scalar_one_or_none()
        if level is None:
            raise APIError(404, "NOT_FOUND", "Stufe nicht gefunden.")
        self.db.delete(level)
        self.db.commit()
        return {"data": {"id": level_id}, "message": "Stufe wurde gelöscht."}

    # ── tariff-code aggregation (D.1) ─────────────────────────────────────────
    def _current_fiscal_year(self, org_id: str, on: date):
        return (
            self.db.execute(
                select(FiscalYear).where(
                    FiscalYear.org_id == org_id,
                    FiscalYear.beginn <= on,
                    FiscalYear.ende >= on,
                )
            )
            .scalars()
            .first()
        )

    @staticmethod
    def _covers(row: SalaryTariff, month: date) -> bool:
        return row.valid_from <= month and (
            row.valid_to is None or row.valid_to >= month
        )

    @staticmethod
    def _month_iter(start: date, end: date) -> Iterable[date]:
        cur = start.replace(day=1)
        while cur <= end:
            yield cur
            cur = cur + relativedelta(months=1)

    def _has_coverage_gap(
        self, current_rows: list[SalaryTariff], fy: FiscalYear, today: date
    ) -> bool:
        """A (salary_group, level) that has current rows but is uncovered for some
        forward month within the fiscal year is a data gap."""
        keys: dict[tuple[str, int], list[SalaryTariff]] = {}
        for r in current_rows:
            keys.setdefault((r.salary_group, r.level), []).append(r)
        start = max(fy.beginn, today.replace(day=1))
        for rows in keys.values():
            for month in self._month_iter(start, fy.ende):
                if not any(self._covers(r, month) for r in rows):
                    return True
        return False

    def tariff_codes(
        self, org_id: str, *, status: str | None = None, search: str | None = None
    ) -> list[dict[str, Any]]:
        rows = (
            self.db.execute(
                select(SalaryTariff).where(
                    SalaryTariff.org_id == org_id, SalaryTariff.deleted_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        today = date.today()
        fy = self._current_fiscal_year(org_id, today)
        emp_counts = dict(
            self.db.execute(
                select(
                    SalaryTariff.tariff_code,
                    func.count(func.distinct(EmployeeContract.employee_id)),
                )
                .join(
                    EmployeeContract,
                    EmployeeContract.salary_tariff_id == SalaryTariff.id,
                )
                .where(
                    SalaryTariff.org_id == org_id,
                    SalaryTariff.deleted_at.is_(None),
                )
                .group_by(SalaryTariff.tariff_code)
            ).all()
        )

        by_code: dict[str, list[SalaryTariff]] = {}
        for r in rows:
            by_code.setdefault(r.tariff_code, []).append(r)

        out: list[dict[str, Any]] = []
        for code, rs in by_code.items():
            current = [r for r in rs if not r.is_proposed]
            proposed = [r for r in rs if r.is_proposed]
            has_current = any(self._covers(r, today) for r in current)
            has_gap = bool(fy) and self._has_coverage_gap(current, fy, today)
            cur_from = min((r.valid_from for r in current), default=None)
            if current and all(r.valid_to is not None for r in current):
                cur_to = max(r.valid_to for r in current if r.valid_to is not None)
            else:
                cur_to = None
            ref = current or rs
            std = next((r.standard_hours for r in ref), None)
            bav = next(
                (r.bav_rate_pct for r in ref if r.bav_rate_pct is not None), None
            )
            out.append(
                {
                    "tariff_code": code,
                    "grade_count": len({r.salary_group for r in rs}),
                    "row_count": len(rs),
                    "proposed_count": len(proposed),
                    "employee_count": int(emp_counts.get(code, 0)),
                    "has_current": has_current,
                    "has_proposed": bool(proposed),
                    "has_gap": has_gap,
                    "current_valid_from": cur_from.isoformat() if cur_from else None,
                    "current_valid_to": cur_to.isoformat() if cur_to else None,
                    "standard_hours": decimal_str(std),
                    "bav_rate_pct": decimal_str(bav),
                }
            )

        if search:
            needle = search.lower()
            out = [o for o in out if needle in o["tariff_code"].lower()]
        if status == "active":
            out = [o for o in out if o["has_current"]]
        elif status == "proposed":
            out = [o for o in out if o["has_proposed"]]
        elif status == "gap":
            out = [o for o in out if o["has_gap"]]
        out.sort(key=lambda o: o["tariff_code"].lower())
        return out

    # ── rows / levels by tariff code (D.2, D.5) ───────────────────────────────
    def rows_by_code(
        self, org_id: str, tariff_code: str, filters: dict[str, str]
    ) -> list[dict[str, Any]]:
        stmt = select(SalaryTariff).where(
            SalaryTariff.org_id == org_id,
            SalaryTariff.tariff_code == tariff_code,
            SalaryTariff.deleted_at.is_(None),
        )
        if filters.get("salary_group"):
            stmt = stmt.where(SalaryTariff.salary_group == filters["salary_group"])
        is_proposed = filters.get("is_proposed")
        if is_proposed in ("true", "false"):
            stmt = stmt.where(SalaryTariff.is_proposed.is_(is_proposed == "true"))
        rows = self.db.execute(stmt).scalars().all()
        rows = sorted(
            rows,
            key=lambda r: (_natural_key(r.salary_group), r.level, r.valid_from),
        )
        return [_tariff(r) for r in rows]

    def levels_by_code(
        self, org_id: str, tariff_code: str, salary_group: str | None = None
    ) -> list[dict[str, Any]]:
        stmt = (
            select(SalaryLevel)
            .join(SalaryTariff, SalaryLevel.tariff_id == SalaryTariff.id)
            .where(
                SalaryLevel.org_id == org_id,
                SalaryTariff.tariff_code == tariff_code,
                SalaryTariff.deleted_at.is_(None),
            )
        )
        if salary_group:
            stmt = stmt.where(SalaryLevel.salary_group == salary_group)
        levels = self.db.execute(stmt).scalars().all()
        levels = sorted(
            levels, key=lambda lvl: (_natural_key(lvl.salary_group), lvl.level_no)
        )
        return [_level(lvl) for lvl in levels]

    # ── inline overlap check (D.3) ────────────────────────────────────────────
    def check_overlap(self, org_id: str, params: dict[str, str]) -> dict[str, Any]:
        tariff_code = req_str(params, "tariff_code")
        salary_group = req_str(params, "salary_group")
        try:
            level = int(params["level"])
        except (KeyError, TypeError, ValueError) as exc:
            raise APIError(  # noqa: B904
                422, "VALIDATION_INT", "level muss eine ganze Zahl sein."
            ) from exc
        is_proposed = str(params.get("is_proposed", "false")).lower() == "true"
        valid_from = parse_date(params.get("valid_from"), "valid_from")
        valid_to = opt_date(params.get("valid_to"), "valid_to")
        exclude_id = params.get("exclude_id") or None
        assert_window_valid(valid_from, valid_to)
        new_to = valid_to or date.max
        existing = (
            self.db.execute(
                select(SalaryTariff).where(
                    SalaryTariff.org_id == org_id,
                    SalaryTariff.tariff_code == tariff_code,
                    SalaryTariff.salary_group == salary_group,
                    SalaryTariff.level == level,
                    SalaryTariff.is_proposed.is_(is_proposed),
                    SalaryTariff.deleted_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        for row in existing:
            if exclude_id is not None and row.id == exclude_id:
                continue
            row_to = row.valid_to or date.max
            if row.valid_from <= new_to and row_to >= valid_from:
                return {"overlap": True, "conflict": _tariff(row)}
        return {"overlap": False, "conflict": None}

    # ── upcoming progressions (P-T) ───────────────────────────────────────────
    def progressions_upcoming(
        self, org_id: str, *, months_ahead: int = 6, tariff_code: str | None = None
    ) -> list[dict[str, Any]]:
        today = date.today()
        horizon = today + relativedelta(months=months_ahead)
        contracts = (
            self.db.execute(
                select(EmployeeContract, Employee)
                .join(Employee, EmployeeContract.employee_id == Employee.id)
                .where(
                    EmployeeContract.org_id == org_id,
                    EmployeeContract.salary_tariff_id.is_not(None),
                    EmployeeContract.entgeltgruppe.is_not(None),
                    EmployeeContract.stufe.is_not(None),
                    Employee.ist_aktiv.is_(True),
                )
            )
            .all()
        )
        out: list[dict[str, Any]] = []
        for contract, emp in contracts:
            if contract.gueltig_bis is not None and contract.gueltig_bis < today:
                continue
            tariff = contract.salary_tariff
            if tariff is None or tariff.deleted_at is not None:
                continue
            if tariff_code and tariff.tariff_code != tariff_code:
                continue
            level_row = self.db.execute(
                select(SalaryLevel).where(
                    SalaryLevel.org_id == org_id,
                    SalaryLevel.tariff_id == tariff.id,
                    SalaryLevel.salary_group == contract.entgeltgruppe,
                    SalaryLevel.level_no == contract.stufe,
                )
            ).scalar_one_or_none()
            if level_row is None or level_row.months_to_next_level is None:
                continue  # no rule or maximum tier
            if contract.next_level_date is not None:
                promotion_date = contract.next_level_date
                source = "MANUAL"
            else:
                promotion_date = contract.gueltig_ab + relativedelta(
                    months=level_row.months_to_next_level
                )
                source = "AUTO"
            if promotion_date > horizon:
                continue
            next_level_row = self.db.execute(
                select(SalaryLevel).where(
                    SalaryLevel.org_id == org_id,
                    SalaryLevel.tariff_id == tariff.id,
                    SalaryLevel.salary_group == contract.entgeltgruppe,
                    SalaryLevel.level_no == contract.stufe + 1,
                )
            ).scalar_one_or_none()
            current_amount = level_row.monthly_amount
            next_amount = (
                next_level_row.monthly_amount
                if next_level_row is not None
                else current_amount
            )
            months_in_tier = (
                (today.year - contract.gueltig_ab.year) * 12
                + today.month
                - contract.gueltig_ab.month
            )
            out.append(
                {
                    "employee_id": emp.id,
                    "employee_name": f"{emp.vorname} {emp.nachname}".strip(),
                    "tariff_code": tariff.tariff_code,
                    "salary_group": contract.entgeltgruppe,
                    "current_level": contract.stufe,
                    "next_level": contract.stufe + 1,
                    "months_in_tier": max(0, months_in_tier),
                    "months_required": level_row.months_to_next_level,
                    "progression_date": promotion_date.isoformat(),
                    "source": source,
                    "days_until": (promotion_date - today).days,
                    "current_amount": decimal_str(current_amount),
                    "next_amount": decimal_str(next_amount),
                    "delta_monthly": decimal_str(next_amount - current_amount),
                    "in_forecast": False,
                }
            )
        out.sort(key=lambda o: o["progression_date"])
        return out
