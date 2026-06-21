"""Auth & profile schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import EmailStr, Field

from app.models.enums import OrgRole
from app.schemas.base import APIModel, ORMModel


class MagicLinkRequest(APIModel):
    email: EmailStr
    callback_url: str | None = Field(default=None)


class TokenResponse(APIModel):
    access_token: str
    token_type: str = "bearer"


class MembershipRead(ORMModel):
    org_id: str
    org_name: str
    role: OrgRole
    created_at: datetime


class MeRead(ORMModel):
    id: str
    email: str
    name: str | None = None
    vorname: str | None = None
    nachname: str | None = None
    is_super_admin: bool
    memberships: list[MembershipRead]


class ProfileUpdate(APIModel):
    # null/empty clears the field; otherwise 1–100 chars after trim (validated in route)
    vorname: str | None = None
    nachname: str | None = None


class ProfileRead(ORMModel):
    id: str
    email: str
    vorname: str | None = None
    nachname: str | None = None
    name: str | None = None
