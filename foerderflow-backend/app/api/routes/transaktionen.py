"""/api/protected/transaktionen — list (cockpit), details, manual edit.

Splits / fund-allocation / belege / batch / import land in the following
sub-slices of the transactions engine.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from fastapi import status
from fastapi.responses import JSONResponse

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from fastapi import File, Form, UploadFile

from app.core.errors import APIError
from app.services.booking_rules import apply_rule_to_transaction, load_rule_with_splits
from app.services.csv_import.import_service import ImportService
from app.services.transaction_digest import daily_digest
from app.services.massnahme_zuordnung import (
    assign_massnahme_to_transaction,
    load_massnahme_context,
)
from app.services.transaction_allocation_service import TransactionAllocationService
from app.services.transaction_batch import resolve_batch_input
from app.services.transaction_confirm import confirm_transaction
from app.services.transaction_service import TransactionService

router = APIRouter(tags=["transaktionen"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


# ── import (CSV) ─────────────────────────────────────────────────────────────
@router.post("/transaktionen/import")
async def import_transactions(
    file: UploadFile = File(...),
    fiscal_year_id: str | None = Form(default=None),
    csv_import_profile_id: str | None = Form(default=None),
    fallback_bank_account_id: str | None = Form(default=None),
    custom_mapping: str | None = Form(default=None),
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
    return ImportService(db).run_import(
        ctx.org_id,
        _uid(ctx) or "unknown",
        filename=file.filename or "import.csv",
        size=len(raw),
        content=content,
        fiscal_year_id=fiscal_year_id,
        profile_id=csv_import_profile_id,
        custom_mapping_json=custom_mapping,
        fallback_bank_account_id=fallback_bank_account_id,
    )


@router.put("/transaktionen/import")
async def import_preview(
    file: UploadFile = File(...),
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")
    return ImportService(db).preview(content)


@router.get("/transaktionen/digest")
def transaktionen_digest(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": daily_digest(db, ctx.org_id)}


@router.get("/transaktionen")
def list_transaktionen(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return TransactionService(db).list(ctx.org_id, dict(request.query_params))


@router.get("/transaktionen/{id_}")
def get_transaktion(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": TransactionService(db).get(ctx.org_id, id_)}


@router.patch("/transaktionen/{id_}")
async def update_transaktion(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": TransactionService(db).update(ctx.org_id, id_, body)}


# ── splits ───────────────────────────────────────────────────────────────────
@router.put("/transaktionen/{id_}/splits")
async def set_splits(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(content=TransactionAllocationService(db).set_splits(ctx.org_id, id_, body))


# ── fund-allocation ──────────────────────────────────────────────────────────
@router.get("/transaktionen/{id_}/fund-allocation")
def list_fund_allocation(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": TransactionAllocationService(db).list_allocations(ctx.org_id, id_)}


@router.post("/transaktionen/{id_}/fund-allocation", status_code=status.HTTP_201_CREATED)
async def create_fund_allocation(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=TransactionAllocationService(db).create_allocation(ctx.org_id, _uid(ctx), id_, body),
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/transaktionen/{id_}/fund-allocation")
async def update_fund_allocation(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=TransactionAllocationService(db).update_allocation(ctx.org_id, _uid(ctx), id_, body)
    )


@router.delete("/transaktionen/{id_}/fund-allocation")
async def delete_fund_allocation(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=TransactionAllocationService(db).delete_allocation(ctx.org_id, _uid(ctx), id_, body)
    )


# ── massnahme (inline assign to all splits) ──────────────────────────────────
@router.post("/transaktionen/{id_}/massnahme")
async def assign_massnahme(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    fmid = body.get("funding_measure_id")
    if not fmid:
        raise APIError(400, "HTTP_ERROR", "funding_measure_id ist erforderlich.")
    context = load_massnahme_context(db, ctx.org_id, fmid)
    if context is None:
        raise APIError(404, "HTTP_ERROR", "Fördermassnahme nicht gefunden.")
    result = assign_massnahme_to_transaction(db, ctx.org_id, id_, fmid, context)
    if not result.ok:
        raise APIError(404, "HTTP_ERROR", result.reason or "Fehler.")
    return JSONResponse(content={"message": "Fördermassnahme zugeordnet."})


# ── confirm ──────────────────────────────────────────────────────────────────
@router.patch("/transaktionen/{id_}/confirm")
def confirm(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    result = confirm_transaction(db, ctx.org_id, id_)
    if not result.ok:
        raise APIError(404, "HTTP_ERROR", result.reason or "Fehler.")
    return JSONResponse(content={"message": "Transaktion bestätigt."})


# ── batch ops ────────────────────────────────────────────────────────────────
@router.post("/transaktionen/batch-confirm")
async def batch_confirm(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    ids = resolve_batch_input(db, ctx.org_id, body)
    confirmed = 0
    skipped: list[dict[str, str]] = []
    for tid in ids:
        r = confirm_transaction(db, ctx.org_id, tid)
        if r.ok:
            confirmed += 1
        else:
            skipped.append({"id": r.id, "reason": r.reason or ""})
    msg = f"{confirmed} Transaktion(en) bestätigt"
    if skipped:
        msg += f", {len(skipped)} übersprungen"
    return {"data": {"confirmed": confirmed, "skipped": skipped}, "message": msg + "."}


@router.post("/transaktionen/batch-massnahme")
async def batch_massnahme(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    fmid = body.get("funding_measure_id")
    if not isinstance(fmid, str) or not fmid:
        raise APIError(422, "VALIDATION_MASSNAHME", "funding_measure_id ist erforderlich.")
    ids = resolve_batch_input(db, ctx.org_id, body)
    context = load_massnahme_context(db, ctx.org_id, fmid)
    if context is None:
        raise APIError(404, "MASSNAHME_NOT_FOUND", "Fördermassnahme nicht gefunden.")
    matched = 0
    skipped: list[dict[str, str]] = []
    for tid in ids:
        r = assign_massnahme_to_transaction(db, ctx.org_id, tid, fmid, context)
        if r.ok:
            matched += 1
        else:
            skipped.append({"id": r.id, "reason": r.reason or ""})
    msg = f"{matched} Fördermassnahme(n) zugeordnet"
    if skipped:
        msg += f", {len(skipped)} übersprungen"
    return {"data": {"matched": matched, "skipped": skipped}, "message": msg + "."}


@router.post("/transaktionen/batch-regeln")
async def batch_regeln(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from sqlalchemy import select as _select

    from app.models.transaction import Transaction

    body = await _json_body(request)
    rule_id = body.get("rule_id")
    if not isinstance(rule_id, str) or not rule_id:
        raise APIError(422, "VALIDATION_RULE", "rule_id ist erforderlich.")
    rule = load_rule_with_splits(db, ctx.org_id, rule_id, active_only=True)
    if rule is None:
        raise APIError(404, "HTTP_ERROR", "Regel nicht gefunden oder inaktiv.")
    ids = resolve_batch_input(db, ctx.org_id, body)
    rows = db.execute(
        _select(Transaction.id, Transaction.betrag).where(
            Transaction.id.in_(ids), Transaction.org_id == ctx.org_id
        )
    ).all()
    matched = 0
    skipped = 0
    for tx_id, betrag in rows:
        try:
            apply_rule_to_transaction(db, ctx.org_id, tx_id, abs(float(betrag)), rule)
            matched += 1
        except Exception:  # noqa: BLE001
            db.rollback()
            skipped += 1
    msg = f"{matched} Transaktion(en) zugeordnet"
    if skipped:
        msg += f", {skipped} übersprungen"
    return {"data": {"matched": matched, "skipped": skipped}, "message": msg + "."}
