"""Bank-/Kassenkonten (BankAccount) — port of app/api/protected/bank-accounts/*.

Code is unique per org; IBAN is globally unique. Saldo views convert Decimal to
plain numbers (the monolith uses Number()), so those fields serialize as numbers.
DELETE is a hard delete only when no transactions/opening balances depend on it.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from fastapi import status
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.transaction import BankAccount
from app.repositories.bank_account_repository import BankAccountRepository

IBAN_RE = re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{10,30}$", re.IGNORECASE)
VALID_TYPES = ("BANK", "KASSE", "ONLINE_WALLET")


def _account(a: BankAccount) -> dict[str, Any]:
    return {
        "id": a.id,
        "org_id": a.org_id,
        "code": a.code,
        "bezeichnung": a.bezeichnung,
        "typ": a.typ.value,
        "iban": a.iban,
        "bic": a.bic,
        "bankname": a.bankname,
        "ist_aktiv": a.ist_aktiv,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _round2(value: Decimal) -> float:
    return round(float(value), 2)


class BankAccountService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BankAccountRepository(db)

    def list(self, org_id: str, include_inactive: bool) -> list[dict[str, Any]]:
        accounts = self.repo.list_with_opening(org_id, include_inactive)
        sums = self.repo.transaction_sums(org_id)
        result = []
        for a in accounts:
            total_opening = sum(
                (ob.saldo_eroeffnung for ob in a.opening_balances), Decimal(0)
            )
            movements = sums.get(a.id, Decimal(0))
            row = _account(a)
            row["opening_balances"] = [
                {
                    "id": ob.id,
                    "bank_account_id": ob.bank_account_id,
                    "fiscal_year_id": ob.fiscal_year_id,
                    "saldo_eroeffnung": float(ob.saldo_eroeffnung),
                    "datum": ob.datum.isoformat(),
                    "notiz": ob.notiz,
                    "created_at": ob.created_at.isoformat() if ob.created_at else None,
                    "updated_at": ob.updated_at.isoformat() if ob.updated_at else None,
                    "fiscal_year": {
                        "id": ob.fiscal_year.id,
                        "jahr": ob.fiscal_year.jahr,
                    },
                }
                for ob in a.opening_balances
            ]
            row["_count"] = {"transactions": self.repo.transaction_count(a.id)}
            row["saldo_aktuell"] = _round2(total_opening + movements)
            row["bewegungen_summe"] = _round2(movements)
            result.append(row)
        return result

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        code = str(body.get("code") or "").strip()
        bezeichnung = str(body.get("bezeichnung") or "").strip()
        typ = str(body.get("typ") or "BANK")
        iban = (
            re.sub(r"\s+", "", str(body["iban"]).strip())
            if body.get("iban")
            else None
        )
        bic = str(body["bic"]).strip() if body.get("bic") else None
        bankname = str(body["bankname"]).strip() if body.get("bankname") else None

        if not code or not (2 <= len(code) <= 50):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_CODE",
                "Code muss 2–50 Zeichen lang sein.",
            )
        if not bezeichnung or not (2 <= len(bezeichnung) <= 120):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_BEZEICHNUNG",
                "Bezeichnung muss 2–120 Zeichen lang sein.",
            )
        if typ not in VALID_TYPES:
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY, "VALIDATION_TYP", "Ungültiger Typ."
            )
        if iban and not IBAN_RE.match(iban):
            raise APIError(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "VALIDATION_IBAN",
                "Ungültige IBAN.",
            )
        if self.repo.get_by_code(org_id, code):
            raise APIError(
                status.HTTP_409_CONFLICT,
                "CODE_DUPLICATE",
                f'Code "{code}" ist bereits vergeben.',
            )
        if iban and self.repo.get_by_iban(iban):
            raise APIError(
                status.HTTP_409_CONFLICT,
                "IBAN_DUPLICATE",
                "Diese IBAN ist bereits einem anderen Konto zugeordnet.",
            )
        a = BankAccount(
            org_id=org_id,
            code=code,
            bezeichnung=bezeichnung,
            typ=typ,
            iban=iban,
            bic=bic,
            bankname=bankname,
        )
        self.repo.add(a)
        self.db.commit()
        self.db.refresh(a)
        return _account(a)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        a = self.repo.get(org_id, id_)
        if a is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Konto nicht gefunden."
            )
        if isinstance(body.get("bezeichnung"), str):
            v = body["bezeichnung"].strip()
            if not (2 <= len(v) <= 120):
                raise APIError(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "VALIDATION_BEZEICHNUNG",
                    "Bezeichnung muss 2–120 Zeichen lang sein.",
                )
            a.bezeichnung = v
        if "bic" in body:
            a.bic = str(body["bic"]).strip() if body["bic"] else None
        if "bankname" in body:
            a.bankname = str(body["bankname"]).strip() if body["bankname"] else None
        if isinstance(body.get("ist_aktiv"), bool):
            a.ist_aktiv = body["ist_aktiv"]
        self.db.commit()
        self.db.refresh(a)
        return _account(a)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        a = self.repo.get(org_id, id_)
        if a is None:
            raise APIError(
                status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Konto nicht gefunden."
            )
        tx = self.repo.transaction_count(id_)
        ob = self.repo.opening_balance_count(id_)
        if tx > 0 or ob > 0:
            raise APIError(
                status.HTTP_409_CONFLICT,
                "HAS_DEPENDENTS",
                f"Konto kann nicht gelöscht werden — {tx} Transaktion(en), {ob} "
                "Eröffnungssaldi hängen daran. Stattdessen deaktivieren.",
            )
        self.db.delete(a)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Konto gelöscht."}
