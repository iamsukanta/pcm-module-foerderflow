"""/api/protected/fristen — consolidated deadline list."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.fristen_service import FristenService

router = APIRouter(tags=["fristen"])


@router.get("/fristen")
def list_fristen(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    raw = request.query_params.get("days_ahead")
    try:
        days_ahead = int(raw) if raw else 90
    except ValueError:
        days_ahead = -1
    if days_ahead < 1 or days_ahead > 365:
        raise APIError(422, "VALIDATION_DAYS_AHEAD", "days_ahead muss zwischen 1 und 365 liegen.")
    return {"data": FristenService(db).load_fristen(ctx.org_id, days_ahead)}


@router.get("/fristen/kritische-count")
def kritische_count(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Count of deadlines due within 7 days — feeds the sidebar badge (BFF
    equivalent of the monolith's server-side countKritischeFristen helper)."""
    return {"data": {"count": FristenService(db).count_kritische_fristen(ctx.org_id)}}
