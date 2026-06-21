"""/api/protected/verteilungsschluessel — AllocationKey CRUD + neue-version."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.verteilungsschluessel_service import VerteilungsschluesselService

router = APIRouter(tags=["verteilungsschluessel"])


@router.get("/verteilungsschluessel")
def list_keys(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    include_inactive = request.query_params.get("includeInactive") == "true"
    return {"data": VerteilungsschluesselService(db).list(ctx.org_id, include_inactive)}


@router.post("/verteilungsschluessel", status_code=status.HTTP_201_CREATED)
async def create_key(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=VerteilungsschluesselService(db).create(ctx.org_id, body),
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/verteilungsschluessel/{id_}")
def get_key(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": VerteilungsschluesselService(db).get(ctx.org_id, id_)}


@router.post(
    "/verteilungsschluessel/{id_}/neue-version", status_code=status.HTTP_201_CREATED
)
async def neue_version(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=VerteilungsschluesselService(db).neue_version(ctx.org_id, id_, body),
        status_code=status.HTTP_201_CREATED,
    )


@router.patch("/verteilungsschluessel/{id_}")
async def update_key(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return VerteilungsschluesselService(db).update(ctx.org_id, id_, body)


@router.delete("/verteilungsschluessel/{id_}")
def delete_key(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return VerteilungsschluesselService(db).deactivate(ctx.org_id, id_)
