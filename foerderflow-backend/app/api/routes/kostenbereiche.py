"""/api/protected/kostenbereiche — read-only cost-category taxonomy."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.kostenbereich_service import KostenbereichService

router = APIRouter(tags=["kostenbereiche"])


@router.get("/kostenbereiche")
def list_kostenbereiche(
    request: Request,
    _ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    nur_obergruppen = request.query_params.get("nur_obergruppen") == "true"
    return {"data": KostenbereichService(db).list(nur_obergruppen)}
