"""/api/protected/me — own profile + memberships (port of app/api/protected/me)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.dependencies.auth import get_current_user
from app.db.session import get_db
from app.models.auth import OrganizationMembership, User
from app.schemas.auth import ProfileUpdate

router = APIRouter(tags=["me"])


def _compose_name(vorname: str | None, nachname: str | None) -> str | None:
    parts = [s for s in (vorname, nachname) if s and s.strip()]
    return " ".join(parts) if parts else None


@router.get("/me")
def get_me(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict[str, Any]:
    memberships = (
        db.execute(
            select(OrganizationMembership)
            .where(OrganizationMembership.user_id == user.id)
            .order_by(OrganizationMembership.created_at.asc())
        )
        .scalars()
        .all()
    )
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "vorname": user.vorname,
            "nachname": user.nachname,
            "is_super_admin": user.is_super_admin,
            "memberships": [
                {
                    "org_id": m.org_id,
                    "org_name": m.organization.name,
                    "role": m.role.value,
                    "created_at": m.created_at.isoformat(),
                }
                for m in memberships
            ],
        }
    }


def _normalize(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    trimmed = value.strip()
    if not trimmed:
        return None
    if len(trimmed) > 100:
        raise APIError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"VALIDATION_{field.upper()}",
            f"{field} darf max. 100 Zeichen lang sein.",
        )
    return trimmed


@router.put("/me")
def update_me(
    body: ProfileUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    vorname = _normalize(body.vorname, "vorname")
    nachname = _normalize(body.nachname, "nachname")
    user.vorname = vorname
    user.nachname = nachname
    user.name = _compose_name(vorname, nachname)
    db.commit()
    db.refresh(user)
    return {
        "data": {
            "id": user.id,
            "email": user.email,
            "vorname": user.vorname,
            "nachname": user.nachname,
            "name": user.name,
        },
        "message": "Profil aktualisiert.",
    }
