"""/api/protected/umlage-source-scopes — UmlageSourceScope CRUD."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.umlage_scope_service import UmlageScopeService

router = APIRouter(tags=["umlage-source-scopes"])


@router.get("/umlage-source-scopes")
def list_scopes(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": UmlageScopeService(db).list(ctx.org_id)}


@router.post("/umlage-source-scopes", status_code=status.HTTP_201_CREATED)
async def create_scope(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": UmlageScopeService(db).create(ctx.org_id, body)}


@router.get("/umlage-source-scopes/{id_}")
def get_scope(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": UmlageScopeService(db).get(ctx.org_id, id_)}


@router.patch("/umlage-source-scopes/{id_}")
async def update_scope(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": UmlageScopeService(db).update(ctx.org_id, id_, body)}


@router.delete("/umlage-source-scopes/{id_}")
def delete_scope(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=UmlageScopeService(db).delete(ctx.org_id, id_))
