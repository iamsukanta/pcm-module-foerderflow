"""Smaller endpoints: fund-allocations summary, position-wahl-ausstehend,
opening-balances — ports of the respective monolith routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.funding import FundingMeasure
from app.models.master import FiscalYear, Kostenbereich
from app.models.transaction import (
    BankAccount,
    FundAllocation,
    OpeningBalance,
    Transaction,
    TransactionSplit,
)
from app.utils.serialization import decimal_str as _dec


def _ev(v):
    return v.value if hasattr(v, "value") else v


class FundAllocationSummaryService:
    def __init__(self, db: Session):
        self.db = db

    def summary(self, org_id: str, funding_measure_id: str | None) -> dict[str, Any]:
        if not funding_measure_id:
            raise APIError(400, "MISSING_PARAMS", "funding_measure_id ist erforderlich.")
        if self.db.execute(
            select(FundingMeasure.id).where(
                FundingMeasure.id == funding_measure_id, FundingMeasure.org_id == org_id
            )
        ).scalar_one_or_none() is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
        allocations = (
            self.db.execute(
                select(FundAllocation)
                .where(FundAllocation.funding_measure_id == funding_measure_id, FundAllocation.org_id == org_id)
                .options(
                    selectinload(FundAllocation.transaction_split).selectinload(TransactionSplit.transaction)
                )
            )
            .scalars()
            .all()
        )
        total_ff = sum(float(a.betrag_foerderfahig) for a in allocations)
        total_fo = sum(float(a.betrag_foerderung) for a in allocations)
        total_ea = sum(float(a.betrag_eigenanteil) for a in allocations)
        tx_ids = {a.transaction_split.transaction.id for a in allocations}
        status_breakdown: dict[str, int] = {}
        for a in allocations:
            st = _ev(a.transaction_split.transaction.status)
            status_breakdown[st] = status_breakdown.get(st, 0) + 1
        return {
            "data": {
                "funding_measure_id": funding_measure_id,
                "total_foerderfahig": f"{total_ff:.2f}",
                "total_foerderung": f"{total_fo:.2f}",
                "total_eigenanteil": f"{total_ea:.2f}",
                "anzahl_transaktionen": len(tx_ids),
                "status_breakdown": status_breakdown,
            }
        }


class PositionWahlService:
    def __init__(self, db: Session):
        self.db = db

    def ausstehend(self, org_id: str) -> list[dict[str, Any]]:
        # Allocations with no explicit position whose KB maps to >1 non-pauschale
        # position in the measure (would be double-counted until a position is chosen).
        candidates = (
            self.db.execute(
                select(FundAllocation)
                .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
                .join(Transaction, Transaction.id == TransactionSplit.transaction_id)
                .where(
                    FundAllocation.org_id == org_id,
                    FundAllocation.finanzplan_position_id.is_(None),
                    Transaction.kostenbereich_id.is_not(None),
                )
                .order_by(Transaction.datum.desc())
                .options(
                    selectinload(FundAllocation.transaction_split)
                    .selectinload(TransactionSplit.transaction)
                    .selectinload(Transaction.kostenbereich),
                    selectinload(FundAllocation.funding_measure),
                )
            )
            .scalars()
            .all()
        )
        out = []
        for a in candidates:
            tx = a.transaction_split.transaction
            positions = (
                self.db.execute(
                    select(FinanzplanPosition)
                    .join(
                        FinanzplanPositionKostenbereich,
                        FinanzplanPositionKostenbereich.finanzplan_position_id == FinanzplanPosition.id,
                    )
                    .where(
                        FinanzplanPositionKostenbereich.kostenbereich_id == tx.kostenbereich_id,
                        FinanzplanPositionKostenbereich.org_id == org_id,
                        FinanzplanPosition.funding_measure_id == a.funding_measure_id,
                        FinanzplanPosition.ist_pauschale.is_(False),
                    )
                    .order_by(FinanzplanPosition.sort_order, FinanzplanPosition.positionscode)
                )
                .scalars()
                .all()
            )
            if len(positions) <= 1:
                continue
            kb = tx.kostenbereich
            out.append(
                {
                    "allocation_id": a.id,
                    "transaction": {
                        "id": tx.id,
                        "auftraggeber": tx.auftraggeber,
                        "datum": tx.datum.isoformat() if tx.datum else None,
                        "betrag": _dec(tx.betrag),
                        "kostenbereich": (
                            {"code": kb.code, "bezeichnung": kb.bezeichnung} if kb else None
                        ),
                    },
                    "funding_measure": {"id": a.funding_measure.id, "name": a.funding_measure.name},
                    "betrag_foerderfahig": _dec(a.betrag_foerderfahig),
                    "candidates": [
                        {"id": p.id, "positionscode": p.positionscode, "bezeichnung": p.bezeichnung}
                        for p in positions
                    ],
                }
            )
        return out


class OpeningBalanceService:
    def __init__(self, db: Session):
        self.db = db

    def _ob(self, r: OpeningBalance, with_rel: bool = True) -> dict[str, Any]:
        row = {
            "id": r.id,
            "bank_account_id": r.bank_account_id,
            "fiscal_year_id": r.fiscal_year_id,
            "saldo_eroeffnung": float(r.saldo_eroeffnung),
            "datum": r.datum.isoformat() if r.datum else None,
            "notiz": r.notiz,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        if with_rel:
            ba = r.bank_account
            row["bank_account"] = (
                {"id": ba.id, "code": ba.code, "bezeichnung": ba.bezeichnung, "iban": ba.iban} if ba else None
            )
            fy = r.fiscal_year
            row["fiscal_year"] = {"id": fy.id, "jahr": fy.jahr} if fy else None
        return row

    def list(self, org_id: str, bank_account_id: str | None, fiscal_year_id: str | None) -> list[dict[str, Any]]:
        stmt = (
            select(OpeningBalance)
            .join(BankAccount, BankAccount.id == OpeningBalance.bank_account_id)
            .where(BankAccount.org_id == org_id)
            .options(
                selectinload(OpeningBalance.bank_account), selectinload(OpeningBalance.fiscal_year)
            )
        )
        if bank_account_id:
            stmt = stmt.where(OpeningBalance.bank_account_id == bank_account_id)
        if fiscal_year_id:
            stmt = stmt.where(OpeningBalance.fiscal_year_id == fiscal_year_id)
        rows = self.db.execute(stmt).scalars().all()
        rows.sort(key=lambda r: (-(r.fiscal_year.jahr if r.fiscal_year else 0), r.bank_account.code if r.bank_account else ""))
        return [self._ob(r) for r in rows]

    def upsert(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        bank_account_id = str(body.get("bank_account_id") or "")
        fiscal_year_id = str(body.get("fiscal_year_id") or "")
        try:
            saldo = float(body.get("saldo_eroeffnung"))
        except (TypeError, ValueError):
            saldo = float("nan")
        if not bank_account_id or not fiscal_year_id:
            raise APIError(422, "MISSING_FIELDS", "bank_account_id und fiscal_year_id erforderlich.")
        if not (saldo == saldo):
            raise APIError(422, "VALIDATION_SALDO", "saldo_eroeffnung muss eine Zahl sein.")
        account = self.db.execute(
            select(BankAccount).where(BankAccount.id == bank_account_id, BankAccount.org_id == org_id)
        ).scalar_one_or_none()
        if account is None:
            raise APIError(404, "ACCOUNT_NOT_FOUND", "Konto nicht gefunden.")
        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy is None:
            raise APIError(404, "FY_NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        datum_raw = body.get("datum")
        effective_datum = (
            date.fromisoformat(str(datum_raw)[:10]) if datum_raw else fy.beginn
        )
        notiz = str(body["notiz"]) if body.get("notiz") else None
        existing = self.db.execute(
            select(OpeningBalance).where(
                OpeningBalance.bank_account_id == bank_account_id,
                OpeningBalance.fiscal_year_id == fiscal_year_id,
            )
        ).scalar_one_or_none()
        if existing:
            existing.saldo_eroeffnung = saldo
            existing.datum = effective_datum
            existing.notiz = notiz
            ob = existing
        else:
            ob = OpeningBalance(
                bank_account_id=bank_account_id,
                fiscal_year_id=fiscal_year_id,
                saldo_eroeffnung=saldo,
                datum=effective_datum,
                notiz=notiz,
            )
            self.db.add(ob)
        self.db.commit()
        self.db.refresh(ob)
        return {"data": self._ob(ob, with_rel=False), "message": "Eröffnungssaldo gespeichert."}
