"""/api/protected/haushaltsjahre — FiscalYear CRUD + irreversible close."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.haushaltsjahr_service import HaushaltsjahrService

router = APIRouter(tags=["haushaltsjahre"])


@router.get("/haushaltsjahre")
def list_haushaltsjahre(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": HaushaltsjahrService(db).list(ctx.org_id)}


@router.post("/haushaltsjahre", status_code=status.HTTP_201_CREATED)
async def create_haushaltsjahr(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    result = HaushaltsjahrService(db).create(ctx.org_id, body)
    return JSONResponse(content=result, status_code=status.HTTP_201_CREATED)


@router.get("/haushaltsjahre/{id_}")
def get_haushaltsjahr(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": HaushaltsjahrService(db).get(ctx.org_id, id_)}


@router.patch("/haushaltsjahre/{id_}")
async def update_haushaltsjahr(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return HaushaltsjahrService(db).update(ctx.org_id, id_, body)


@router.post("/haushaltsjahre/{id_}/close")
async def close_haushaltsjahr(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return HaushaltsjahrService(db).close(ctx.org_id, id_, body, ctx.user.id if ctx.user else None)
