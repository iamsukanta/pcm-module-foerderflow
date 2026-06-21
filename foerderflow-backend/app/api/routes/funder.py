"""/api/protected/funder — Funder (Fördergeber) CRUD (hard delete if unused)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.funder_service import FunderService

router = APIRouter(tags=["funder"])


@router.get("/funder")
def list_funder(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": FunderService(db).list(ctx.org_id)}


@router.post("/funder", status_code=status.HTTP_201_CREATED)
async def create_funder(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    f = FunderService(db).create(ctx.org_id, body)
    return {"data": f, "message": f'Fördergeber „{f["name"]}" wurde erfolgreich angelegt.'}


@router.get("/funder/{id_}")
def get_funder(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": FunderService(db).get(ctx.org_id, id_)}


@router.patch("/funder/{id_}")
async def update_funder(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    f = FunderService(db).update(ctx.org_id, id_, body)
    return {"data": f, "message": f'Fördergeber „{f["name"]}" wurde aktualisiert.'}


@router.delete("/funder/{id_}")
def delete_funder(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=FunderService(db).delete(ctx.org_id, id_))
