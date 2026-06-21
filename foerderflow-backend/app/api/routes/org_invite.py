"""/api/protected/org/invite (+[id]) — org-admin invites + setup/organisation.

org/invite: list (any member), POST/DELETE require role ADMIN. setup/organisation:
super-admin (or ALLOW_SELF_SERVICE) creates an org + ADMIN membership for self.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_current_user, get_org_context
from app.models.auth import OrganizationMembership, OrgInvite, User
from app.models.organization import Organization
from app.services.org_invite_service import create_org_invite

router = APIRouter(tags=["org-invite"])


def _ev(v):
    return v.value if hasattr(v, "value") else v


@router.get("/org/invite")
def list_invites(ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    invites = (
        db.execute(
            select(OrgInvite)
            .where(
                OrgInvite.org_id == ctx.org_id,
                OrgInvite.used_at.is_(None),
                OrgInvite.expires_at > datetime.now(timezone.utc),
            )
            .order_by(OrgInvite.created_at.desc())
        )
        .scalars()
        .all()
    )
    return {
        "data": [
            {
                "id": i.id, "email": i.email, "role": _ev(i.role),
                "expires_at": i.expires_at.isoformat() if i.expires_at else None,
                "created_at": i.created_at.isoformat() if i.created_at else None,
            }
            for i in invites
        ]
    }


@router.post("/org/invite", status_code=status.HTTP_201_CREATED)
async def create_invite(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    if _ev(ctx.role) != "ADMIN":
        raise APIError(403, "INSUFFICIENT_ROLE", "Nur Org-Admins können Nutzer einladen.")
    body = await _json_body(request)
    role = body.get("role") or "FINANCE"
    if role not in ("ADMIN", "FINANCE", "READONLY"):
        raise APIError(400, "INVALID_ROLE", "Ungültige Rolle.")
    u = ctx.user
    inviter_label = (u.name or u.email or "Ein Teammitglied") if u else "Ein Teammitglied"
    result = create_org_invite(
        db, org_id=ctx.org_id, email=body.get("email") or "", role=role,
        created_by=u.id if u else "", inviter_label=inviter_label,
    )
    if not result.ok:
        raise APIError(result.status, result.code, result.error)
    return JSONResponse(content={"data": result.invite}, status_code=status.HTTP_201_CREATED)


@router.delete("/org/invite/{id_}")
def delete_invite(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    if _ev(ctx.role) != "ADMIN":
        raise APIError(403, "INSUFFICIENT_ROLE", "Nur Administratoren können Einladungen widerrufen.")
    invite = db.get(OrgInvite, id_)
    if invite is None or invite.org_id != ctx.org_id:
        raise APIError(404, "NOT_FOUND", "Einladung nicht gefunden.")
    if invite.used_at:
        raise APIError(409, "ALREADY_USED", "Einladung wurde bereits eingelöst.")
    invite.expires_at = datetime.now(timezone.utc)
    db.commit()
    return {"data": {"ok": True}}


# ── setup/organisation (mounted at /api/setup) ────────────────────────────────
setup_router = APIRouter(tags=["setup"])


@setup_router.post("/organisation")
async def setup_organisation(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    self_service = os.getenv("ALLOW_SELF_SERVICE") == "true"
    if not user.is_super_admin and not self_service:
        raise APIError(
            403,
            "FORBIDDEN",
            "Org-Anlage ist VoluLink Super-Admins vorbehalten. Bitte VoluLink kontaktieren, "
            "um eine Organisation einrichten zu lassen.",
        )
    body = await _json_body(request)
    name = body.get("name")
    rechtsform = body.get("rechtsform")
    if not name or not rechtsform:
        raise APIError(400, "HTTP_ERROR", "Name und Rechtsform erforderlich")
    if not user.is_super_admin:
        existing = db.execute(
            select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
        ).scalar_one_or_none()
        if existing:
            raise APIError(400, "HTTP_ERROR", "User hat bereits eine Organisation")
    org = Organization(
        name=name,
        rechtsform=rechtsform,
        regelarbeitszeit_stunden=body.get("regelarbeitszeit_stunden") or 39,
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMembership(org_id=org.id, user_id=user.id, role="ADMIN"))
    db.commit()
    return {"data": {"org_id": org.id, "name": org.name}}
