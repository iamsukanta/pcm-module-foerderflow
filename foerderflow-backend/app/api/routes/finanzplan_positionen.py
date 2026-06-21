"""/api/protected/finanzplan-positionen — FinanzplanPosition CRUD +
Deckungsfähigkeit pool view."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.finanzplan_position_service import FinanzplanPositionService

router = APIRouter(tags=["finanzplan-positionen"])


@router.get("/finanzplan-positionen")
def list_positionen(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fmid = request.query_params.get("funding_measure_id")
    return {"data": FinanzplanPositionService(db).list(ctx.org_id, fmid)}


@router.post("/finanzplan-positionen", status_code=status.HTTP_201_CREATED)
async def create_position(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    result = FinanzplanPositionService(db).create(ctx.org_id, body)
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.get("/finanzplan-positionen/{id_}")
def get_position(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": FinanzplanPositionService(db).get(ctx.org_id, id_)}


@router.patch("/finanzplan-positionen/{id_}")
async def update_position(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(content=FinanzplanPositionService(db).update(ctx.org_id, id_, body))


@router.get("/finanzplan-positionen/{id_}/deckungsfaehigkeit")
def deckungsfaehigkeit(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return FinanzplanPositionService(db).deckungsfaehigkeit(ctx.org_id, id_)


@router.delete("/finanzplan-positionen/{id_}")
def delete_position(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=FinanzplanPositionService(db).delete(ctx.org_id, id_))
