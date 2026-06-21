"""/api/admin/* — VoluLink super-admin (organisations, users, members, invites).

All gated by require_super_admin (403 SUPER_ADMIN_REQUIRED for non-admins).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import require_super_admin
from app.models.auth import User
from app.services.admin_service import AdminService
from app.services.org_invite_service import create_org_invite

router = APIRouter(tags=["admin"])


def _label(u: User) -> str:
    parts = [p for p in (u.vorname, u.nachname) if p]
    return " ".join(parts) or u.name or u.email or "VoluLink Super-Admin"


# ── organisations ───────────────────────────────────────────────────────────
@router.get("/admin/organisations")
def list_orgs(_u: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": AdminService(db).list_orgs()}


@router.post("/admin/organisations", status_code=status.HTTP_201_CREATED)
async def create_org(
    request: Request, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(content=AdminService(db).create_org(body), status_code=status.HTTP_201_CREATED)


@router.get("/admin/organisations/{id_}")
def get_org(id_: str, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return AdminService(db).get_org(id_)


@router.put("/admin/organisations/{id_}")
async def update_org(
    id_: str, request: Request, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return AdminService(db).update_org(id_, body)


@router.delete("/admin/organisations/{id_}")
def delete_org(id_: str, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(content=AdminService(db).delete_org(id_))


# ── members ─────────────────────────────────────────────────────────────────
@router.post("/admin/organisations/{id_}/members", status_code=status.HTTP_201_CREATED)
async def add_member(
    id_: str, request: Request, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(content=AdminService(db).add_member(id_, body), status_code=status.HTTP_201_CREATED)


@router.put("/admin/organisations/{id_}/members/{user_id}")
async def update_member(
    id_: str, user_id: str, request: Request, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    force = request.query_params.get("force") == "true"
    return AdminService(db).update_member(id_, user_id, body, force)


@router.delete("/admin/organisations/{id_}/members/{user_id}")
def remove_member(
    id_: str, user_id: str, request: Request, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> JSONResponse:
    force = request.query_params.get("force") == "true"
    return JSONResponse(content=AdminService(db).remove_member(id_, user_id, force))


# ── invites ─────────────────────────────────────────────────────────────────
@router.post("/admin/organisations/{id_}/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    id_: str, request: Request, u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> JSONResponse:
    from app.core.errors import APIError

    body = await _json_body(request)
    role = body.get("role") or "FINANCE"
    if role not in ("ADMIN", "FINANCE", "READONLY"):
        raise APIError(400, "INVALID_ROLE", "Ungültige Rolle.")
    result = create_org_invite(
        db, org_id=id_, email=body.get("email") or "", role=role, created_by=u.id, inviter_label=_label(u)
    )
    if not result.ok:
        raise APIError(result.status, result.code, result.error)
    return JSONResponse(content={"data": result.invite}, status_code=status.HTTP_201_CREATED)


@router.delete("/admin/organisations/{id_}/invites/{invite_id}")
def revoke_invite(
    id_: str, invite_id: str, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> JSONResponse:
    return JSONResponse(content=AdminService(db).revoke_invite(id_, invite_id))


# ── users ───────────────────────────────────────────────────────────────────
@router.get("/admin/users")
def list_users(_u: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": AdminService(db).list_users()}


@router.get("/admin/users/{id_}")
def get_user(id_: str, _u: User = Depends(require_super_admin), db: Session = Depends(get_db)) -> dict[str, Any]:
    return AdminService(db).get_user(id_)


@router.put("/admin/users/{id_}")
async def update_user(
    id_: str, request: Request, u: User = Depends(require_super_admin), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return AdminService(db).update_user(u.id, id_, body)
