"""Transaction filter → SQLAlchemy conditions — port of
lib/transaction-filter-where.ts. Single source of truth for the list + batch
endpoints' WHERE clause (cockpit display and bulk processing must match).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, exists, func

from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.models.booking_rule import BookingRuleApplication


def _parse_date(v: Any) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None


def _parse_number(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        return None
    return n if n == n else None  # NaN guard


def read_filter(params: dict[str, Any]) -> dict[str, Any]:
    g = params.get
    raw_massn = g("has_massnahme")
    return {
        "fiscal_year_id": g("fiscal_year_id"),
        "status": g("status"),
        "kostenbereich_id": g("kostenbereich_id"),
        "cost_center_id": g("cost_center_id"),
        "funding_measure_id": g("funding_measure_id"),
        "bank_account_id": g("bank_account_id"),
        "iban_partner": g("iban_partner"),
        "search": g("search"),
        "confidence": g("confidence"),
        "datum_von": g("datum_von"),
        "datum_bis": g("datum_bis"),
        "betrag_min": _parse_number(g("betrag_min")),
        "betrag_max": _parse_number(g("betrag_max")),
        "has_massnahme": True if raw_massn == "true" else (False if raw_massn == "false" else None),
    }


def build_conditions(org_id: str, f: dict[str, Any]) -> list:
    conds = [Transaction.org_id == org_id]
    if f.get("fiscal_year_id"):
        conds.append(Transaction.fiscal_year_id == f["fiscal_year_id"])
    if f.get("status"):
        conds.append(Transaction.status == f["status"])
    if f.get("kostenbereich_id"):
        conds.append(Transaction.kostenbereich_id == f["kostenbereich_id"])
    if f.get("bank_account_id"):
        conds.append(Transaction.bank_account_id == f["bank_account_id"])
    if f.get("iban_partner"):
        conds.append(Transaction.iban_partner == f["iban_partner"].strip())

    if f.get("search"):
        s = f["search"]
        like = f"%{s}%"
        conds.append(
            func.lower(Transaction.auftraggeber).like(func.lower(like))
            | func.lower(Transaction.verwendungszweck).like(func.lower(like))
        )

    dvon = _parse_date(f.get("datum_von"))
    dbis = _parse_date(f.get("datum_bis"))
    if dvon:
        conds.append(Transaction.datum >= dvon)
    if dbis:
        conds.append(Transaction.datum <= dbis)

    if f.get("betrag_min") is not None:
        conds.append(Transaction.betrag >= f["betrag_min"])
    if f.get("betrag_max") is not None:
        conds.append(Transaction.betrag <= f["betrag_max"])

    if f.get("confidence"):
        conds.append(
            exists().where(
                and_(
                    BookingRuleApplication.transaction_id == Transaction.id,
                    BookingRuleApplication.confidence == f["confidence"],
                )
            )
        )

    # split-based filters (cost_center / funding_measure must hit the same split)
    split_conds = [TransactionSplit.transaction_id == Transaction.id]
    has_split_filter = False
    if f.get("cost_center_id"):
        split_conds.append(TransactionSplit.cost_center_id == f["cost_center_id"])
        has_split_filter = True
    if f.get("funding_measure_id"):
        split_conds.append(
            exists().where(
                and_(
                    FundAllocation.transaction_split_id == TransactionSplit.id,
                    FundAllocation.funding_measure_id == f["funding_measure_id"],
                )
            )
        )
        has_split_filter = True

    if has_split_filter:
        conds.append(exists().where(and_(*split_conds)))
    elif f.get("has_massnahme") is True:
        conds.append(
            exists().where(
                and_(
                    TransactionSplit.transaction_id == Transaction.id,
                    exists().where(FundAllocation.transaction_split_id == TransactionSplit.id),
                )
            )
        )
    elif f.get("has_massnahme") is False:
        conds.append(
            ~exists().where(
                and_(
                    TransactionSplit.transaction_id == Transaction.id,
                    exists().where(FundAllocation.transaction_split_id == TransactionSplit.id),
                )
            )
        )

    return conds
