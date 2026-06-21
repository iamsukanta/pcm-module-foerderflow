"""Employees + contracts + salary components — port of
app/api/protected/employees/*.

Money/hours serialize as strings (Prisma Decimal); dates as full ISO (the
employee routes use toISOString()). Contract creation closes the prior contract
(gueltig_bis = neu − 1 day). Components: monthly or one-off; deactivate via PATCH.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.enums import AuditActionType
from app.models.payroll import Employee, EmployeeContract, SalaryComponent
from app.services.pcm.audit_service import log_assignment_change
from app.utils.serialization import decimal_str

VALID_VERTRAGSART = ("FESTANSTELLUNG", "MINIJOB", "WERKVERTRAG", "EHRENAMT")
VALID_TARIFWERK = ("TVOEDD", "TVOEL", "AVR_CARITAS", "AVR_DD", "INDIVIDUELL")
VALID_COMPONENT_TYP = (
    "FESTBEZUG", "VWL_AG_ZUSCHUSS", "JOBTICKET_SACHBEZUG", "SALARY_ADJUSTMENT", "SONSTIGES",
)


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _iso(v):
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return datetime(v.year, v.month, v.day).isoformat()


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _parse_date(v: Any) -> date | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None


def _component(c: SalaryComponent) -> dict[str, Any]:
    return {
        "id": c.id,
        "org_id": c.org_id,
        "contract_id": c.contract_id,
        "typ": _ev(c.typ),
        "bezeichnung": c.bezeichnung,
        "betrag": decimal_str(c.betrag),
        "nach_multiplikator": c.nach_multiplikator,
        "einmalig": c.einmalig,
        "gilt_fuer_monat": _iso(c.gilt_fuer_monat),
        "ist_aktiv": c.ist_aktiv,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }


def _contract(c: EmployeeContract, with_components: bool = False) -> dict[str, Any]:
    row = {
        "id": c.id,
        "org_id": c.org_id,
        "employee_id": c.employee_id,
        "vertragsart": _ev(c.vertragsart),
        "assigned_hours": decimal_str(c.assigned_hours),
        "base_salary": decimal_str(c.base_salary),
        "tarifwerk": _ev(c.tarifwerk) if c.tarifwerk else None,
        "entgeltgruppe": c.entgeltgruppe,
        "stufe": c.stufe,
        "gueltig_ab": _iso(c.gueltig_ab),
        "gueltig_bis": _iso(c.gueltig_bis),
        "notiz": c.notiz,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }
    if with_components:
        row["components"] = [_component(x) for x in sorted(c.components, key=lambda x: x.created_at or datetime.min)]
    return row


def _employee(e: Employee, contracts: list[dict[str, Any]], active_contract_id: str | None = None) -> dict[str, Any]:
    row = {
        "id": e.id,
        "org_id": e.org_id,
        "employee_code": e.employee_code,
        "vorname": e.vorname,
        "nachname": e.nachname,
        "email": e.email,
        "eintrittsdatum": _iso(e.eintrittsdatum),
        "austrittsdatum": _iso(e.austrittsdatum),
        "ist_aktiv": e.ist_aktiv,
        "created_at": _iso(e.created_at),
        "updated_at": _iso(e.updated_at),
        "contracts": contracts,
    }
    if active_contract_id is not None or contracts:
        row["active_contract_id"] = active_contract_id
    return row


class EmployeeService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str) -> list[dict[str, Any]]:
        now = date.today()
        emps = (
            self.db.execute(
                select(Employee)
                .where(Employee.org_id == org_id)
                .order_by(Employee.nachname.asc())
                .options(selectinload(Employee.contracts))
            )
            .scalars()
            .all()
        )
        out = []
        for e in emps:
            contracts = sorted(e.contracts, key=lambda c: c.gueltig_ab, reverse=True)
            active = next(
                (c for c in contracts if c.gueltig_ab <= now and (c.gueltig_bis is None or c.gueltig_bis >= now)),
                None,
            )
            out.append(_employee(e, [_contract(c) for c in contracts], active.id if active else None))
        return out

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        e = self.db.execute(
            select(Employee)
            .where(Employee.id == id_, Employee.org_id == org_id)
            .options(selectinload(Employee.contracts).selectinload(EmployeeContract.components))
        ).scalar_one_or_none()
        if e is None:
            raise APIError(404, "NOT_FOUND", "Mitarbeiter nicht gefunden.")
        contracts = sorted(e.contracts, key=lambda c: c.gueltig_ab, reverse=True)
        return _employee(e, [_contract(c, with_components=True) for c in contracts])

    def _validate_contract(self, vertrag: dict[str, Any]) -> dict[str, Any]:
        if vertrag.get("vertragsart") not in VALID_VERTRAGSART:
            raise APIError(
                422, "VALIDATION_VERTRAGSART",
                f"Ungültige Vertragsart. Erlaubt: {', '.join(VALID_VERTRAGSART)}.",
            )
        hours = _num(vertrag.get("assigned_hours"))
        if not (hours == hours) or hours <= 0 or hours > 168:
            raise APIError(422, "VALIDATION_HOURS", "Stunden/Woche muss zwischen 0 und 168 liegen.")
        salary = _num(vertrag.get("base_salary"))
        if not (salary == salary) or salary < 0:
            raise APIError(422, "VALIDATION_SALARY", "Grundgehalt muss eine nicht-negative Zahl sein.")
        ga = _parse_date(vertrag.get("gueltig_ab"))
        if ga is None:
            raise APIError(422, "VALIDATION_GUELTIG_AB", "Gültig ab ist kein gültiges Datum.")
        tw = vertrag.get("tarifwerk")
        if tw not in (None, "") and tw not in VALID_TARIFWERK:
            raise APIError(422, "VALIDATION_TARIFWERK", f"Ungültiges Tarifwerk. Erlaubt: {', '.join(VALID_TARIFWERK)}.")
        return {"hours": hours, "salary": salary, "gueltig_ab": ga}

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        code = body.get("employee_code")
        if not isinstance(code, str) or not code.strip():
            raise APIError(422, "VALIDATION_CODE", "Personalnummer ist erforderlich.")
        vorname = body.get("vorname")
        if not isinstance(vorname, str) or not vorname.strip():
            raise APIError(422, "VALIDATION_VORNAME", "Vorname ist erforderlich.")
        nachname = body.get("nachname")
        if not isinstance(nachname, str) or not nachname.strip():
            raise APIError(422, "VALIDATION_NACHNAME", "Nachname ist erforderlich.")
        eintritt = _parse_date(body.get("eintrittsdatum"))
        if eintritt is None:
            raise APIError(422, "VALIDATION_EINTRITTSDATUM", "Eintrittsdatum ist kein gültiges Datum.")
        vertrag = body.get("erster_vertrag")
        if not isinstance(vertrag, dict):
            raise APIError(422, "VALIDATION_VERTRAG", "Erster Vertrag ist erforderlich.")
        v = self._validate_contract(vertrag)

        if self.db.execute(
            select(Employee.id).where(Employee.org_id == org_id, Employee.employee_code == code.strip())
        ).scalar_one_or_none():
            raise APIError(422, "CODE_DUPLICATE", "Personalnummer bereits vergeben.")

        email = body.get("email")
        emp = Employee(
            org_id=org_id,
            employee_code=code.strip(),
            vorname=vorname.strip(),
            nachname=nachname.strip(),
            email=email.strip() if isinstance(email, str) and email.strip() else None,
            eintrittsdatum=eintritt,
        )
        self.db.add(emp)
        self.db.flush()
        contract = EmployeeContract(
            org_id=org_id,
            employee_id=emp.id,
            vertragsart=vertrag["vertragsart"],
            assigned_hours=v["hours"],
            base_salary=v["salary"],
            tarifwerk=vertrag["tarifwerk"] if vertrag.get("tarifwerk") else None,
            entgeltgruppe=vertrag["entgeltgruppe"] if vertrag.get("entgeltgruppe") else None,
            stufe=vertrag["stufe"] if isinstance(vertrag.get("stufe"), int) else None,
            gueltig_ab=v["gueltig_ab"],
            gueltig_bis=None,
        )
        self.db.add(contract)
        self.db.commit()
        self.db.refresh(emp)
        self.db.refresh(contract)
        return _employee(emp, [_contract(contract)])

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        e = self.db.execute(
            select(Employee).where(Employee.id == id_, Employee.org_id == org_id)
        ).scalar_one_or_none()
        if e is None:
            raise APIError(404, "NOT_FOUND", "Mitarbeiter nicht gefunden.")
        if isinstance(body.get("vorname"), str) and body["vorname"].strip():
            e.vorname = body["vorname"].strip()
        if isinstance(body.get("nachname"), str) and body["nachname"].strip():
            e.nachname = body["nachname"].strip()
        if "email" in body:
            email = body["email"]
            e.email = email.strip() if isinstance(email, str) and email.strip() else None
        if "austrittsdatum" in body:
            a = body["austrittsdatum"]
            if a is None:
                e.austrittsdatum = None
            else:
                d = _parse_date(a)
                if d is None:
                    raise APIError(422, "VALIDATION_AUSTRITTSDATUM", "Austrittsdatum ist kein gültiges Datum.")
                e.austrittsdatum = d
        if isinstance(body.get("ist_aktiv"), bool):
            e.ist_aktiv = body["ist_aktiv"]
        self.db.commit()
        self.db.refresh(e)
        return {
            "id": e.id, "org_id": e.org_id, "employee_code": e.employee_code,
            "vorname": e.vorname, "nachname": e.nachname, "email": e.email,
            "eintrittsdatum": _iso(e.eintrittsdatum), "austrittsdatum": _iso(e.austrittsdatum),
            "ist_aktiv": e.ist_aktiv, "created_at": _iso(e.created_at), "updated_at": _iso(e.updated_at),
        }

    # ── contracts ──────────────────────────────────────────────────────────────
    def _employee_or_404(self, org_id: str, id_: str) -> Employee:
        e = self.db.execute(
            select(Employee).where(Employee.id == id_, Employee.org_id == org_id)
        ).scalar_one_or_none()
        if e is None:
            raise APIError(404, "NOT_FOUND", "Mitarbeiter nicht gefunden.")
        return e

    def list_contracts(self, org_id: str, employee_id: str) -> list[dict[str, Any]]:
        self._employee_or_404(org_id, employee_id)
        contracts = (
            self.db.execute(
                select(EmployeeContract)
                .where(EmployeeContract.employee_id == employee_id, EmployeeContract.org_id == org_id)
                .order_by(EmployeeContract.gueltig_ab.desc())
                .options(selectinload(EmployeeContract.components))
            )
            .scalars()
            .all()
        )
        return [_contract(c, with_components=True) for c in contracts]

    def create_contract(self, org_id: str, employee_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._employee_or_404(org_id, employee_id)
        v = self._validate_contract(body)
        latest = self.db.execute(
            select(EmployeeContract)
            .where(EmployeeContract.employee_id == employee_id, EmployeeContract.org_id == org_id)
            .order_by(EmployeeContract.gueltig_ab.desc())
            .limit(1)
        ).scalars().first()
        if latest and v["gueltig_ab"] <= latest.gueltig_ab:
            raise APIError(422, "VALIDATION_GUELTIG_AB_ORDER", "Gültig ab muss nach dem letzten Vertrag liegen.")
        if latest:
            latest.gueltig_bis = v["gueltig_ab"] - timedelta(days=1)
        notiz = body.get("notiz")
        contract = EmployeeContract(
            org_id=org_id,
            employee_id=employee_id,
            vertragsart=body["vertragsart"],
            assigned_hours=v["hours"],
            base_salary=v["salary"],
            tarifwerk=body["tarifwerk"] if body.get("tarifwerk") else None,
            entgeltgruppe=body["entgeltgruppe"] if body.get("entgeltgruppe") else None,
            stufe=body["stufe"] if isinstance(body.get("stufe"), int) else None,
            gueltig_ab=v["gueltig_ab"],
            gueltig_bis=None,
            notiz=notiz.strip() if isinstance(notiz, str) and notiz.strip() else None,
        )
        self.db.add(contract)
        self.db.flush()
        # Audit trail (Area O): every contract change is logged.
        log_assignment_change(
            self.db,
            org_id=org_id,
            employee_id=employee_id,
            action_type=AuditActionType.UPDATE,
            salary_assignment_id=contract.id,
            summary=(
                f"Neuer Vertrag: {contract.entgeltgruppe or contract.vertragsart} "
                f"ab {v['gueltig_ab'].isoformat()}"
            ),
            old_values=(
                {
                    "gueltig_ab": latest.gueltig_ab.isoformat(),
                    "gueltig_bis": latest.gueltig_bis.isoformat()
                    if latest.gueltig_bis
                    else None,
                }
                if latest
                else None
            ),
            new_values={
                "base_salary": decimal_str(contract.base_salary),
                "entgeltgruppe": contract.entgeltgruppe,
                "stufe": contract.stufe,
                "gueltig_ab": contract.gueltig_ab.isoformat(),
            },
        )
        self.db.commit()
        self.db.refresh(contract)
        return _contract(contract)

    # ── components ──────────────────────────────────────────────────────────────
    def _contract_or_404(self, org_id: str, employee_id: str, contract_id: str) -> EmployeeContract:
        c = self.db.execute(
            select(EmployeeContract).where(
                EmployeeContract.id == contract_id,
                EmployeeContract.employee_id == employee_id,
                EmployeeContract.org_id == org_id,
            )
        ).scalar_one_or_none()
        if c is None:
            raise APIError(404, "NOT_FOUND", "Vertrag nicht gefunden.")
        return c

    def list_components(self, org_id: str, employee_id: str, contract_id: str) -> list[dict[str, Any]]:
        self._contract_or_404(org_id, employee_id, contract_id)
        comps = (
            self.db.execute(
                select(SalaryComponent)
                .where(
                    SalaryComponent.contract_id == contract_id,
                    SalaryComponent.org_id == org_id,
                    SalaryComponent.ist_aktiv.is_(True),
                )
                .order_by(SalaryComponent.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [_component(c) for c in comps]

    def create_component(self, org_id: str, employee_id: str, contract_id: str, body: dict[str, Any]) -> dict[str, Any]:
        self._contract_or_404(org_id, employee_id, contract_id)
        if body.get("typ") not in VALID_COMPONENT_TYP:
            raise APIError(422, "VALIDATION_TYP", f"Ungültiger Typ. Erlaubt: {', '.join(VALID_COMPONENT_TYP)}.")
        bez = body.get("bezeichnung")
        if not isinstance(bez, str) or not bez.strip():
            raise APIError(422, "VALIDATION_BEZEICHNUNG", "Bezeichnung ist erforderlich.")
        betrag = _num(body.get("betrag"))
        if not (betrag == betrag):
            raise APIError(422, "VALIDATION_BETRAG", "Betrag muss eine Zahl sein.")
        einmalig = body.get("einmalig") is True
        gilt_fuer_monat = None
        if einmalig:
            d = _parse_date(body.get("gilt_fuer_monat"))
            if d is None:
                raise APIError(422, "VALIDATION_GILT_FUER_MONAT", "Gilt für Monat ist erforderlich wenn Einmalig.")
            gilt_fuer_monat = date(d.year, d.month, 1)
        comp = SalaryComponent(
            org_id=org_id,
            contract_id=contract_id,
            typ=body["typ"],
            bezeichnung=bez.strip(),
            betrag=betrag,
            nach_multiplikator=body.get("nach_multiplikator") is True,
            einmalig=einmalig,
            gilt_fuer_monat=gilt_fuer_monat,
            ist_aktiv=True,
        )
        self.db.add(comp)
        self.db.commit()
        self.db.refresh(comp)
        return _component(comp)

    def deactivate_component(self, org_id: str, employee_id: str, contract_id: str, component_id: str | None) -> dict[str, Any]:
        if not component_id:
            raise APIError(
                400, "INVALID_ACTION",
                "Ungültige Aktion. Erwartet: ?action=deactivate&componentId=xxx",
            )
        self._contract_or_404(org_id, employee_id, contract_id)
        comp = self.db.execute(
            select(SalaryComponent).where(
                SalaryComponent.id == component_id,
                SalaryComponent.contract_id == contract_id,
                SalaryComponent.org_id == org_id,
            )
        ).scalar_one_or_none()
        if comp is None:
            raise APIError(404, "NOT_FOUND", "Komponente nicht gefunden.")
        comp.ist_aktiv = False
        self.db.commit()
        return {"message": "Komponente deaktiviert."}
