"""/api/protected/buchungsregeln — BookingRule CRUD + preview + suggest + backfill."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.buchungsregel_service import BuchungsregelService

router = APIRouter(tags=["buchungsregeln"])


@router.get("/buchungsregeln")
def list_rules(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": BuchungsregelService(db).list(ctx.org_id)}


@router.post("/buchungsregeln", status_code=status.HTTP_201_CREATED)
async def create_rule(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    rule = BuchungsregelService(db).create(ctx.org_id, body)
    return {"data": rule, "message": "Buchungsregel gespeichert."}


@router.post("/buchungsregeln/preview")
async def preview_rule(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": BuchungsregelService(db).preview(ctx.org_id, body)}


@router.post("/buchungsregeln/suggest")
async def suggest_rule(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": BuchungsregelService(db).suggest(ctx.org_id, body)}


@router.put("/buchungsregeln/{id_}")
async def replace_rule(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    rule = BuchungsregelService(db).replace(ctx.org_id, id_, body)
    return {"data": rule, "message": "Regel aktualisiert."}


@router.patch("/buchungsregeln/{id_}")
async def patch_rule(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": BuchungsregelService(db).patch(ctx.org_id, id_, body)}


@router.delete("/buchungsregeln/{id_}")
def delete_rule(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=BuchungsregelService(db).delete(ctx.org_id, id_))


@router.get("/buchungsregeln/{id_}/backfill")
def backfill_count(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    include_assigned = request.query_params.get("include_assigned") == "true"
    return {"data": BuchungsregelService(db).backfill_count(ctx.org_id, id_, include_assigned)}


@router.post("/buchungsregeln/{id_}/backfill")
def backfill_apply(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    include_assigned = request.query_params.get("include_assigned") == "true"
    return BuchungsregelService(db).backfill_apply(ctx.org_id, id_, include_assigned)
