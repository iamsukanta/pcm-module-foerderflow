"""/api/protected — fund-allocations/summary, allocations/position-wahl-ausstehend,
opening-balances."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.misc_service import (
    FundAllocationSummaryService,
    OpeningBalanceService,
    PositionWahlService,
)

router = APIRouter(tags=["misc"])


@router.get("/dashboard/cockpit")
def dashboard_cockpit(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.dashboard_cockpit import load_cockpit

    return {"data": load_cockpit(db, ctx.org_id)}


@router.get("/fund-allocations/summary")
def fund_allocation_summary(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return FundAllocationSummaryService(db).summary(
        ctx.org_id, request.query_params.get("funding_measure_id")
    )


@router.get("/allocations/position-wahl-ausstehend")
def position_wahl_ausstehend(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": PositionWahlService(db).ausstehend(ctx.org_id)}


@router.get("/opening-balances")
def list_opening_balances(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {
        "data": OpeningBalanceService(db).list(
            ctx.org_id,
            request.query_params.get("bank_account_id"),
            request.query_params.get("fiscal_year_id"),
        )
    }


@router.post("/opening-balances", status_code=status.HTTP_201_CREATED)
async def upsert_opening_balance(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return OpeningBalanceService(db).upsert(ctx.org_id, body)
