"""/api/protected/verwendungsnachweise — VerwNachweis CRUD + einreichen."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.verwendungsnachweis_service import VerwendungsnachweisService

router = APIRouter(tags=["verwendungsnachweise"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


@router.get("/verwendungsnachweise")
def list_nachweise(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fmid = request.query_params.get("funding_measure_id")
    status_q = request.query_params.get("status")
    return {"data": VerwendungsnachweisService(db).list(ctx.org_id, fmid, status_q)}


@router.post("/verwendungsnachweise", status_code=status.HTTP_201_CREATED)
async def create_nachweis(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content={"data": VerwendungsnachweisService(db).create(ctx.org_id, body)},
        status_code=status.HTTP_201_CREATED,
    )


@router.get("/verwendungsnachweise/{id_}")
def get_nachweis(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": VerwendungsnachweisService(db).get(ctx.org_id, id_)}


@router.patch("/verwendungsnachweise/{id_}")
async def update_nachweis(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": VerwendungsnachweisService(db).update(ctx.org_id, id_, body)}


@router.delete("/verwendungsnachweise/{id_}")
def delete_nachweis(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=VerwendungsnachweisService(db).delete(ctx.org_id, id_))


@router.post("/verwendungsnachweise/{id_}/einreichen")
def einreichen(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    data = VerwendungsnachweisService(db).einreichen(ctx.org_id, _uid(ctx), id_)
    return {"data": data, "message": "Verwendungsnachweis wurde erfolgreich eingereicht."}
