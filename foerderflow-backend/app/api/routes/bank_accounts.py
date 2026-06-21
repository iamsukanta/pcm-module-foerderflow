"""/api/protected/bank-accounts — BankAccount CRUD + saldo view."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.bank_account_service import BankAccountService

router = APIRouter(tags=["bank-accounts"])


@router.get("/bank-accounts")
def list_bank_accounts(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    include_inactive = request.query_params.get("includeInactive") == "true"
    return {"data": BankAccountService(db).list(ctx.org_id, include_inactive)}


@router.post("/bank-accounts", status_code=status.HTTP_201_CREATED)
async def create_bank_account(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    a = BankAccountService(db).create(ctx.org_id, body)
    return {"data": a, "message": f'Konto "{a["bezeichnung"]}" wurde angelegt.'}


@router.patch("/bank-accounts/{id_}")
async def update_bank_account(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": BankAccountService(db).update(ctx.org_id, id_, body)}


@router.delete("/bank-accounts/{id_}")
def delete_bank_account(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=BankAccountService(db).delete(ctx.org_id, id_))
