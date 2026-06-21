"""/api/protected/mittelabrufe — Mittelabruf CRUD + frist + kalender."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.mittelabruf_service import MittelabrufService

router = APIRouter(tags=["mittelabrufe"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


@router.get("/mittelabrufe")
def list_mittelabrufe(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": MittelabrufService(db).list(ctx.org_id, dict(request.query_params))}


@router.post("/mittelabrufe", status_code=status.HTTP_201_CREATED)
async def create_mittelabruf(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content={"data": MittelabrufService(db).create(ctx.org_id, body)},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/mittelabrufe/kalender")
def kalender(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    hj = request.query_params.get("haushaltsjahr_id")
    periode = request.query_params.get("periode") or "MONAT"
    return {"data": MittelabrufService(db).kalender(ctx.org_id, hj, periode)}


@router.get("/mittelabrufe/{id_}")
def get_mittelabruf(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": MittelabrufService(db).get(ctx.org_id, id_)}


@router.patch("/mittelabrufe/{id_}")
async def update_mittelabruf(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": MittelabrufService(db).update(ctx.org_id, _uid(ctx), id_, body)}


@router.patch("/mittelabrufe/{id_}/frist")
async def update_frist(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": MittelabrufService(db).update_frist(ctx.org_id, id_, body)}
