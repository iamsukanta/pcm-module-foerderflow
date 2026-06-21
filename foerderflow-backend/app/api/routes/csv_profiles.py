"""/api/protected/csv-profiles — CSV import profile list + create."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.csv_profile_service import CsvProfileService

router = APIRouter(tags=["csv-profiles"])


@router.get("/csv-profiles")
def list_profiles(
    ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": CsvProfileService(db).list(ctx.org_id)}


@router.post("/csv-profiles", status_code=status.HTTP_201_CREATED)
async def create_profile(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": CsvProfileService(db).create(ctx.org_id, body)}
