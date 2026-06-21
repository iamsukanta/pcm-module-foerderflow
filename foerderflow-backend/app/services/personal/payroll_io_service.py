"""Payroll CSV import (Lohnjournal) + Lohnbüro CSV export.

Ports:
- POST /payroll/import — parse a payroll CSV, match employees, create MonthlyPayroll
  rows (snapshotting contract/salary), skip duplicates.
- GET  /payroll/lohnbuero-export — emit a German-formatted CSV (one row per
  employee × KST), columns selectable.
"""

from __future__ import annotations

import json
import math
import re
import time
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.master import FiscalYear
from app.models.organization import Organization
from app.models.payroll import Employee, MonthlyPayroll, PayrollAllocation
from app.services.personal.berechnung import (
    DEFAULT_AG_FAKTOR,
    berechne_gehalt,
    get_ag_faktor,
    get_aktiver_vertrag,
)

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB

DEFAULT_MAPPING = {
    "name": "Mitarbeiter",
    "monat": "Monat",
    "an_brutto": "Bruttoentgelt",
    "ag_brutto": "AG-Gesamtkosten",
}

ALL_SPALTEN = [
    "personalnummer",
    "name",
    "kst",
    "prozent",
    "an_brutto_anteil",
    "ag_brutto_anteil",
    "tarifgruppe",
    "stufe",
    "stunden",
]

SPALTEN_HEADERS = {
    "personalnummer": "Personalnummer",
    "name": "Name",
    "kst": "Kostenstelle",
    "prozent": "Anteil %",
    "an_brutto_anteil": "AN-Brutto-Anteil",
    "ag_brutto_anteil": "AG-Brutto-Anteil",
    "tarifgruppe": "Tarifgruppe",
    "stufe": "Stufe",
    "stunden": "Stunden/Woche",
}

DEFAULT_SPALTEN = [
    "personalnummer", "name", "kst", "prozent", "an_brutto_anteil", "ag_brutto_anteil",
]


def _fmt_de(value: float, decimals: int = 2) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def _detect_separator(line: str) -> str:
    semicolons = line.count(";")
    commas = line.count(",")
    return ";" if semicolons >= commas else ","


def _parse_csv(content: str, separator: str) -> list[dict[str, str]]:
    lines = [l for l in re.split(r"\r?\n", content) if l.strip()]
    if len(lines) < 2:
        return []
    headers = [h.strip().strip('"') for h in lines[0].split(separator)]
    out: list[dict[str, str]] = []
    for line in lines[1:]:
        values = [v.strip().strip('"') for v in line.split(separator)]
        out.append({h: (values[i] if i < len(values) else "") for i, h in enumerate(headers)})
    return out


def _parse_monat(raw: str) -> date | None:
    m = re.match(r"^(\d{2})\.(\d{4})$", raw)
    if m:
        return date(int(m.group(2)), int(m.group(1)), 1)
    m = re.match(r"^(\d{4})-(\d{2})$", raw)
    if m:
        return date(int(m.group(1)), int(m.group(2)), 1)
    return None


def _parse_german_number(raw: str) -> float:
    cleaned = raw.replace(".", "").replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return float("nan")


class PayrollIoService:
    def __init__(self, db: Session):
        self.db = db

    # ── import ────────────────────────────────────────────────────────────────
    def import_csv(
        self,
        org_id: str,
        file_content: str | None,
        file_size: int | None,
        fiscal_year_id: str | None,
        spalten_mapping_raw: str | None,
    ) -> dict[str, Any]:
        if file_content is None or not fiscal_year_id:
            raise APIError(400, "MISSING_FIELDS", "Datei und Haushaltsjahr sind erforderlich.")
        if file_size is not None and file_size > MAX_FILE_SIZE:
            raise APIError(400, "FILE_TOO_LARGE", "Datei zu groß (max. 5 MB).")

        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy is None:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")

        mapping = dict(DEFAULT_MAPPING)
        if spalten_mapping_raw:
            try:
                mapping.update(json.loads(spalten_mapping_raw))
            except (ValueError, TypeError):
                raise APIError(400, "INVALID_MAPPING", "Ungültiges JSON für spalten_mapping.")

        first_line = re.split(r"\r?\n", file_content)[0] if file_content else ""
        separator = _detect_separator(first_line)
        rows = _parse_csv(file_content, separator)

        employees = self.db.execute(
            select(Employee).where(Employee.org_id == org_id)
        ).scalars().all()

        existing = self.db.execute(
            select(MonthlyPayroll.employee_id, MonthlyPayroll.monat).where(
                MonthlyPayroll.org_id == org_id
            )
        ).all()
        existing_set = {f"{e}::{m.isoformat()}" for e, m in existing}

        org = self.db.get(Organization, org_id)
        standard_hours = float(org.regelarbeitszeit_stunden) if org else 0.0

        importiert = 0
        uebersprungen = 0
        nicht_gefunden: list[str] = []
        import_batch_id = f"payroll-import-{int(time.time() * 1000)}"

        for row in rows:
            name_raw = (row.get(mapping["name"]) or "").strip()
            monat_raw = (row.get(mapping["monat"]) or "").strip()
            an_brutto_raw = row.get(mapping["an_brutto"]) or ""
            ag_brutto_raw = row.get(mapping["ag_brutto"]) or ""

            if not name_raw and not monat_raw:
                continue

            monat = _parse_monat(monat_raw)
            if monat is None:
                nicht_gefunden.append(f'{name_raw} (Ungültiges Monatformat: "{monat_raw}")')
                continue

            matched = next((e for e in employees if e.employee_code == name_raw), None)
            if matched is None:
                matched = next(
                    (e for e in employees if name_raw.lower() in e.nachname.lower()), None
                )
            if matched is None:
                nicht_gefunden.append(name_raw or monat_raw)
                continue

            monat_key = f"{matched.id}::{monat.isoformat()}"
            if monat_key in existing_set:
                uebersprungen += 1
                continue

            an_brutto = _parse_german_number(an_brutto_raw)
            ag_brutto = _parse_german_number(ag_brutto_raw)

            contract = get_aktiver_vertrag(self.db, matched.id, monat)
            assigned_hours = 0.0
            base_salary = 0.0
            ag_faktor = DEFAULT_AG_FAKTOR
            actual_salary = 0.0
            if contract:
                assigned_hours = float(contract.assigned_hours)
                base_salary = float(contract.base_salary)
                ag_faktor = get_ag_faktor(
                    self.db, org_id, _ev(contract.vertragsart), monat
                )
                berechnung = berechne_gehalt(
                    base_salary=base_salary,
                    assigned_hours=assigned_hours,
                    standard_hours=standard_hours,
                    ag_faktor=ag_faktor,
                    components=[],
                )
                actual_salary = berechnung.actual_salary

            betrag_an_brutto = an_brutto if math.isfinite(an_brutto) else 0.0
            betrag_ag_brutto = ag_brutto if math.isfinite(ag_brutto) else 0.0

            try:
                self.db.add(
                    MonthlyPayroll(
                        org_id=org_id,
                        employee_id=matched.id,
                        fiscal_year_id=fiscal_year_id,
                        monat=monat,
                        assigned_hours=assigned_hours,
                        standard_hours=standard_hours,
                        base_salary=base_salary,
                        ag_faktor=ag_faktor,
                        actual_salary=actual_salary,
                        betrag_an_brutto=betrag_an_brutto,
                        betrag_ag_brutto=betrag_ag_brutto,
                        quelle="IMPORT",
                        import_batch_id=import_batch_id,
                    )
                )
                self.db.commit()
                existing_set.add(monat_key)
                importiert += 1
            except Exception:
                self.db.rollback()
                uebersprungen += 1

        return {"data": {"importiert": importiert, "uebersprungen": uebersprungen, "nicht_gefunden": nicht_gefunden}}

    # ── lohnbüro export ─────────────────────────────────────────────────────────
    def lohnbuero_export(
        self, org_id: str, monat_str: str | None, fiscal_year_id: str | None, spalten_str: str | None
    ) -> tuple[str, str]:
        if not monat_str or not re.match(r"^\d{4}-\d{2}$", monat_str):
            raise APIError(400, "VALIDATION_MONAT", "monat ist erforderlich (Format: YYYY-MM).")

        year, month = (int(x) for x in monat_str.split("-"))
        monat = date(year, month, 1)

        if spalten_str:
            requested = [s.strip() for s in spalten_str.split(",")]
            selected = [s for s in requested if s in ALL_SPALTEN]
        else:
            selected = list(DEFAULT_SPALTEN)

        if not selected:
            raise APIError(400, "NO_COLUMNS", "Keine gültigen Spalten angegeben.")

        conds = [MonthlyPayroll.org_id == org_id, MonthlyPayroll.monat == monat]
        if fiscal_year_id:
            conds.append(MonthlyPayroll.fiscal_year_id == fiscal_year_id)

        payrolls = self.db.execute(
            select(MonthlyPayroll)
            .where(*conds)
            .options(
                selectinload(MonthlyPayroll.employee).selectinload(Employee.contracts),
                selectinload(MonthlyPayroll.allocations).selectinload(PayrollAllocation.cost_center),
            )
        ).scalars().all()

        # order by employee.nachname asc
        payrolls = sorted(payrolls, key=lambda p: p.employee.nachname)

        csv_rows: list[list[str]] = []
        for payroll in payrolls:
            emp = payroll.employee
            contracts = sorted(emp.contracts, key=lambda c: c.gueltig_ab, reverse=True)
            active = contracts[0] if contracts else None
            full_name = f"{emp.nachname}, {emp.vorname}"
            an_brutto = float(payroll.betrag_an_brutto)
            ag_brutto = float(payroll.betrag_ag_brutto)

            def _cell(spalte: str, *, kst: str, prozent: str, an_anteil: str, ag_anteil: str) -> str:
                if spalte == "personalnummer":
                    return emp.employee_code
                if spalte == "name":
                    return full_name
                if spalte == "kst":
                    return kst
                if spalte == "prozent":
                    return prozent
                if spalte == "an_brutto_anteil":
                    return an_anteil
                if spalte == "ag_brutto_anteil":
                    return ag_anteil
                if spalte == "tarifgruppe":
                    return active.entgeltgruppe or "" if active else ""
                if spalte == "stufe":
                    return str(active.stufe) if active and active.stufe is not None else ""
                if spalte == "stunden":
                    return _fmt_de(float(active.assigned_hours), 2) if active else ""
                return ""

            allocations = sorted(payroll.allocations, key=lambda a: a.cost_center.code)
            if not allocations:
                csv_rows.append([
                    _cell(s, kst="", prozent="", an_anteil=_fmt_de(an_brutto), ag_anteil=_fmt_de(ag_brutto))
                    for s in selected
                ])
            else:
                for alloc in allocations:
                    prozent = float(alloc.prozent)
                    an_anteil = an_brutto * prozent / 100
                    ag_anteil = float(alloc.betrag_anteil)
                    cc = alloc.cost_center
                    csv_rows.append([
                        _cell(
                            s,
                            kst=f"{cc.code} {cc.name}",
                            prozent=_fmt_de(prozent, 3),
                            an_anteil=_fmt_de(an_anteil),
                            ag_anteil=_fmt_de(ag_anteil),
                        )
                        for s in selected
                    ])

        header = ";".join(SPALTEN_HEADERS[s] for s in selected)
        body = "\r\n".join(";".join(row) for row in csv_rows)
        csv = f"{header}\r\n{body}"
        filename = f"lohnschluessel_{monat_str}.csv"
        return csv, filename


def _ev(v):
    return v.value if hasattr(v, "value") else v
