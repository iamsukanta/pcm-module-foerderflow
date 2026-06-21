"""/api/protected/kostenstellen — CostCenter CRUD (soft-delete).

Faithful port: `{data}` / `{error,code}` envelopes, custom validation codes,
org-scoping, soft-delete with child cascade + warnings. Guarded by org session
only (no role restriction), matching the monolith.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.kostenstelle_service import KostenstelleService

router = APIRouter(tags=["kostenstellen"])


async def _json_body(request: Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        raise APIError(  # noqa: B904
            status.HTTP_400_BAD_REQUEST,
            "INVALID_JSON",
            "Ungültiges JSON im Request-Body.",
        )
    if not isinstance(data, dict):
        raise APIError(
            status.HTTP_400_BAD_REQUEST,
            "INVALID_JSON",
            "Ungültiges JSON im Request-Body.",
        )
    return data


@router.get("/kostenstellen")
def list_kostenstellen(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    include_inactive = request.query_params.get("includeInactive") == "true"
    data = KostenstelleService(db).list(ctx.org_id, include_inactive)
    return {"data": data}


@router.post("/kostenstellen", status_code=status.HTTP_201_CREATED)
async def create_kostenstelle(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    kst = KostenstelleService(db).create(ctx.org_id, body)
    return {
        "data": kst,
        "message": f'Kostenstelle „{kst["name"]}" wurde erfolgreich angelegt.',
    }


@router.get("/kostenstellen/{id_}")
def get_kostenstelle(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": KostenstelleService(db).get(ctx.org_id, id_)}


@router.patch("/kostenstellen/{id_}")
async def update_kostenstelle(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    kst = KostenstelleService(db).update(ctx.org_id, id_, body)
    return {"data": kst, "message": f'Kostenstelle „{kst["name"]}" wurde gespeichert.'}


@router.delete("/kostenstellen/{id_}")
def deactivate_kostenstelle(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    result = KostenstelleService(db).deactivate(ctx.org_id, id_)
    return JSONResponse(content=result)
