"""External payroll import (Module PCM, Area J).

Parses an external payroll file (employee-row CSV for DATEV/Personio/quarterly,
or a cost-centre BAB for Diamant), matches employees, distributes the gross over
the covered months, and on confirm writes ``monthly_payrolls`` (quelle = IMPORT).

Distribution: CSV_QUARTERLY splits each employee's gross equally over the period
months (remainder to the last month); DATEV/Personio book the gross to
``period_from``; DIAMANT_BAB distributes each cost centre's certified total over
employees by weekly hours, then equally over months.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from dateutil.relativedelta import relativedelta
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.enums import ImportSourceType, PayrollStatus
from app.models.master import CostCenter, FiscalYear
from app.models.payroll import Employee, MonthlyPayroll
from app.models.pcm_import import PayrollImportBatch
from app.models.pcm_personnel import WochenstundenZuweisung
from app.services.pcm._validate import opt_date, parse_date, req_str
from app.services.pcm.period_service import assert_period_not_locked
from app.services.pcm.tariff_import_service import _parse_amount
from app.utils.serialization import decimal_str

_EXTERNAL_KEYS = {"external_id", "personalnummer", "personalnr", "id", "mitarbeiternr"}
_NAME_KEYS = {"name", "mitarbeiter", "mitarbeiterin"}
_GROSS_KEYS = {"ag_brutto", "ag-brutto", "gross", "brutto", "betrag", "summe", "total"}
_AN_KEYS = {"an_brutto", "an-brutto"}
_CC_KEYS = {"kostenstelle", "kst", "cost_center", "costcenter"}


def _decode(content: bytes) -> str:
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(enc)
        except UnicodeDecodeError:
            continue
    raise APIError(500, "IMPORT_PARSE_FAILED", "Datei-Encoding nicht lesbar.")


def _rows(content: bytes) -> list[dict[str, str]]:
    text = _decode(content)
    first = text.splitlines()[0] if text.splitlines() else ""
    delim = ";" if first.count(";") > first.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delim)
    rows = list(reader)
    if not rows:
        raise APIError(422, "IMPORT_PARSE_FAILED", "Keine Daten gefunden.")
    header = [h.strip().lower() for h in rows[0]]
    out = []
    for raw in rows[1:]:
        if not any(c.strip() for c in raw):
            continue
        out.append({header[i]: raw[i] for i in range(min(len(header), len(raw)))})
    return out


def _pick(row: dict[str, str], keys: set[str]) -> str | None:
    for k, v in row.items():
        if k in keys and v.strip():
            return v.strip()
    return None


def _months(period_from: date, period_to: date) -> list[date]:
    out, cur = [], period_from.replace(day=1)
    end = period_to.replace(day=1)
    while cur <= end:
        out.append(cur)
        cur = cur + relativedelta(months=1)
    return out


def _split(gross: float, months: list[date], single: bool) -> list[dict[str, Any]]:
    if not months:
        return []
    if single or len(months) == 1:
        return [{"monat": months[0].isoformat(), "amount": round(gross, 2)}]
    per = round(gross / len(months), 2)
    dist = [{"monat": m.isoformat(), "amount": per} for m in months]
    dist[-1]["amount"] = round(gross - per * (len(months) - 1), 2)  # remainder
    return dist


class PayrollImportService:
    def __init__(self, db: Session):
        self.db = db

    # ── J.1 list ───────────────────────────────────────────────────────────────
    def list(self, org_id: str) -> list[dict[str, Any]]:
        rows = self.db.execute(
            select(PayrollImportBatch)
            .where(PayrollImportBatch.org_id == org_id)
            .order_by(PayrollImportBatch.created_at.desc())
        ).scalars().all()
        return [{
            "id": b.id,
            "source_type": b.source_type.value,
            "period_from": b.period_from.isoformat(),
            "period_to": b.period_to.isoformat(),
            "note": b.note,
            "status": b.status.value,
            "row_count": b.row_count,
            "matched_count": b.matched_count,
            "total_gross": decimal_str(b.total_gross),
            "processed_at": b.processed_at.isoformat() if b.processed_at else None,
        } for b in rows]

    def _match(self, org_id: str, *, external_id: str | None, name: str | None):
        if external_id:
            emp = self.db.execute(
                select(Employee).where(
                    Employee.org_id == org_id,
                    Employee.employee_external_id == external_id,
                )
            ).scalars().first()
            if emp:
                return emp
        if name:
            for emp in self.db.execute(
                select(Employee).where(Employee.org_id == org_id)
            ).scalars():
                if f"{emp.vorname} {emp.nachname}".strip().lower() == name.lower():
                    return emp
        return None

    # ── J.3–J.7 preview ────────────────────────────────────────────────────────
    def preview(
        self, org_id: str, *, source: str, content: bytes, meta: dict[str, Any]
    ) -> dict[str, Any]:
        src = source if source in {s.value for s in ImportSourceType} else None
        if src is None:
            raise APIError(422, "INVALID_SOURCE", "Unbekannte Importquelle.")
        period_from = parse_date(meta.get("period_from"), "period_from")
        period_to = opt_date(meta.get("period_to"), "period_to") or period_from
        if src == ImportSourceType.CSV_QUARTERLY.value and not meta.get("period_to"):
            period_to = (period_from + relativedelta(months=2))
        months = _months(period_from, period_to)
        single = src in (ImportSourceType.DATEV_EXTF.value, ImportSourceType.PERSONIO.value)

        if src == ImportSourceType.DIAMANT_BAB.value:
            out_rows = self._preview_bab(org_id, content, months)
        else:
            out_rows = self._preview_employees(org_id, content, months, single)

        matched = sum(1 for r in out_rows if r["matched_employee_id"])
        total = sum(r["gross"] for r in out_rows)
        return {
            "source_type": src,
            "period_from": period_from.isoformat(),
            "period_to": period_to.isoformat(),
            "row_count": len(out_rows),
            "matched_count": matched,
            "unmatched_count": len(out_rows) - matched,
            "total_gross": round(total, 2),
            "rows": out_rows,
        }

    def _preview_employees(self, org_id, content, months, single) -> list[dict[str, Any]]:
        out = []
        for row in _rows(content):
            ext = _pick(row, _EXTERNAL_KEYS)
            name = _pick(row, _NAME_KEYS)
            gross = _parse_amount(_pick(row, _GROSS_KEYS)) or 0.0
            an = _parse_amount(_pick(row, _AN_KEYS))
            emp = self._match(org_id, external_id=ext, name=name)
            out.append({
                "external_id": ext,
                "name": name,
                "matched_employee_id": emp.id if emp else None,
                "matched_name": f"{emp.vorname} {emp.nachname}".strip() if emp else None,
                "gross": round(gross, 2),
                "an_gross": round(an, 2) if an is not None else None,
                "distribution": _split(gross, months, single),
            })
        return out

    def _preview_bab(self, org_id, content, months) -> list[dict[str, Any]]:
        out = []
        for row in _rows(content):
            cc_code = _pick(row, _CC_KEYS)
            total = _parse_amount(_pick(row, _GROSS_KEYS)) or 0.0
            if not cc_code:
                continue
            cc = self.db.execute(
                select(CostCenter).where(
                    CostCenter.org_id == org_id, CostCenter.code == cc_code
                )
            ).scalars().first()
            if cc is None:
                out.append({"external_id": cc_code, "name": f"KST {cc_code}",
                            "matched_employee_id": None, "matched_name": None,
                            "gross": round(total, 2), "an_gross": None, "distribution": []})
                continue
            today = months[0]
            assigns = self.db.execute(
                select(WochenstundenZuweisung).where(
                    WochenstundenZuweisung.org_id == org_id,
                    WochenstundenZuweisung.cost_center_id == cc.id,
                    WochenstundenZuweisung.effective_date <= today,
                    or_(
                        WochenstundenZuweisung.end_date.is_(None),
                        WochenstundenZuweisung.end_date >= today,
                    ),
                )
            ).scalars().all()
            total_hours = sum(float(a.weekly_hours) for a in assigns) or 1.0
            for a in assigns:
                emp = self.db.get(Employee, a.employee_id)
                share = float(a.weekly_hours) / total_hours * total
                out.append({
                    "external_id": cc_code,
                    "name": f"{emp.vorname} {emp.nachname}".strip() if emp else "?",
                    "matched_employee_id": a.employee_id,
                    "matched_name": f"{emp.vorname} {emp.nachname}".strip() if emp else None,
                    "gross": round(share, 2),
                    "an_gross": None,
                    "distribution": _split(share, months, single=False),
                })
        return out

    # ── J.8 confirm / commit ───────────────────────────────────────────────────
    def confirm(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        source = req_str(body, "source_type")
        if source not in {s.value for s in ImportSourceType}:
            raise APIError(422, "INVALID_SOURCE", "Unbekannte Importquelle.")
        period_from = parse_date(body.get("period_from"), "period_from")
        period_to = opt_date(body.get("period_to"), "period_to") or period_from
        rows = body.get("rows") or []

        batch = PayrollImportBatch(
            org_id=org_id, source_type=ImportSourceType(source),
            period_from=period_from, period_to=period_to,
            note=(body.get("note") or None), processed_at=datetime.now(UTC),
        )
        self.db.add(batch)
        self.db.flush()

        written = skipped = 0
        total = Decimal(0)
        matched = 0
        for row in rows:
            emp_id = row.get("matched_employee_id")
            if not emp_id:
                continue
            matched += 1
            for d in row.get("distribution", []):
                monat = date.fromisoformat(d["monat"]).replace(day=1)
                amount = Decimal(str(d["amount"]))
                fy = self.db.execute(
                    select(FiscalYear).where(
                        FiscalYear.org_id == org_id,
                        FiscalYear.beginn <= monat,
                        FiscalYear.ende >= monat,
                    )
                ).scalars().first()
                if fy is None:
                    skipped += 1
                    continue
                assert_period_not_locked(self.db, org_id=org_id, monat=monat)
                existing = self.db.execute(
                    select(MonthlyPayroll).where(
                        MonthlyPayroll.org_id == org_id,
                        MonthlyPayroll.employee_id == emp_id,
                        MonthlyPayroll.monat == monat,
                    )
                ).scalar_one_or_none()
                if existing is not None and existing.quelle != "IMPORT":
                    skipped += 1
                    continue
                an = row.get("an_gross")
                an_amount = Decimal(str(an)) if an is not None else amount
                if existing is None:
                    existing = MonthlyPayroll(
                        org_id=org_id, employee_id=emp_id, fiscal_year_id=fy.id,
                        monat=monat, assigned_hours=Decimal(0), standard_hours=Decimal(0),
                        base_salary=Decimal(0), ag_faktor=Decimal(0),
                    )
                    self.db.add(existing)
                existing.fiscal_year_id = fy.id
                existing.actual_salary = amount
                existing.betrag_an_brutto = an_amount
                existing.betrag_ag_brutto = amount
                existing.bav_amount = Decimal(0)
                existing.fringe_benefits_amount = Decimal(0)
                existing.status = PayrollStatus.CALCULATED
                existing.quelle = "IMPORT"
                existing.import_batch_id = batch.id
                written += 1
                total += amount

        batch.row_count = len(rows)
        batch.matched_count = matched
        batch.total_gross = total
        self.db.commit()
        return {
            "batch_id": batch.id,
            "written": written,
            "skipped": skipped,
            "total_gross": decimal_str(total),
        }
