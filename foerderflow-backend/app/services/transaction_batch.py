"""Batch input resolver — port of lib/transaction-batch-input.ts.

Accepts either explicit transaction_ids[] (Mode A) or a filter object with
optional excluded_ids (Mode B, select-all-across-pages). Resolves to an id list
using the same build_conditions WHERE source as the list endpoint. Raises APIError
on invalid input / batch too large.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select

from app.core.errors import APIError
from app.models.transaction import Transaction
from app.services.transaction_filter import build_conditions

MAX_BATCH_SIZE = 20000


def resolve_batch_input(db, org_id: str, body: dict[str, Any]) -> list[str]:
    tx_ids = body.get("transaction_ids")
    if isinstance(tx_ids, list) and len(tx_ids) > 0:
        ids = [x for x in tx_ids if isinstance(x, str)]
        if not ids:
            raise APIError(422, "VALIDATION_IDS", "transaction_ids enthält keine gültigen IDs.")
        if len(ids) > MAX_BATCH_SIZE:
            raise APIError(
                422, "BATCH_TOO_LARGE", f"Maximal {MAX_BATCH_SIZE} Transaktionen pro Batch-Request."
            )
        return ids

    flt = body.get("filter")
    if isinstance(flt, dict):
        excluded = {
            x for x in (body.get("excluded_ids") or []) if isinstance(x, str)
        }
        conds = build_conditions(org_id, flt)
        count = db.execute(select(func.count(Transaction.id)).where(and_(*conds))).scalar_one()
        if count - len(excluded) > MAX_BATCH_SIZE:
            raise APIError(
                422,
                "BATCH_TOO_LARGE",
                f"Filter trifft {count - len(excluded)} Transaktionen — Maximum "
                f"{MAX_BATCH_SIZE} pro Request. Bitte Filter weiter eingrenzen.",
            )
        rows = db.execute(
            select(Transaction.id).where(and_(*conds)).limit(MAX_BATCH_SIZE + len(excluded))
        ).all()
        ids = [r[0] for r in rows if r[0] not in excluded]
        if not ids:
            raise APIError(422, "FILTER_EMPTY", "Der Filter trifft keine Transaktionen.")
        return ids

    raise APIError(
        422, "VALIDATION_INPUT", "Entweder transaction_ids[] oder filter muss übergeben werden."
    )
