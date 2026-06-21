"""FastAPI auth/tenancy dependencies — port of `requireOrgSession` /
`requireSuperAdmin` (lib/session.ts).

Because the backend is stateless REST, the monolith's `selected_org_id` cookie is
replaced by an `X-Org-Id` request header (set by the BFF/frontend). Resolution
order matches the monolith: explicit org → header → first membership.
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import TokenError, decode_access_token
from app.db.session import get_db
from app.models.auth import OrganizationMembership, User
from app.models.enums import OrgRole
from app.models.organization import Organization
from app.permissions.rbac import role_satisfies

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class OrgContext:
    """Resolved request identity: the user, the active org, and the role there."""

    user: User
    organization: Organization
    membership: OrganizationMembership

    @property
    def role(self) -> OrgRole:
        return self.membership.role

    @property
    def org_id(self) -> str:
        return self.organization.id


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Decode the Bearer JWT and load the user. 401 if missing/invalid."""
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    try:
        payload = decode_access_token(creds.credentials)
    except TokenError:
        raise HTTPException(  # noqa: B904
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        )
    user_id = payload.get("sub")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def get_org_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    x_org_id: str | None = Header(default=None, alias="X-Org-Id"),
) -> OrgContext:
    """Resolve the active organization membership (port of requireOrgSession).

    - no memberships -> 403 (monolith redirects to /org-select)
    - explicit X-Org-Id not a membership -> 403
    - otherwise first membership
    """
    memberships = (
        db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user.id
            )
        )
        .scalars()
        .all()
    )
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="NO_ORG_MEMBERSHIP"
        )

    membership: OrganizationMembership | None = None
    if x_org_id:
        membership = next((m for m in memberships if m.org_id == x_org_id), None)
        if membership is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="ORG_NOT_ACCESSIBLE"
            )
    else:
        membership = memberships[0]

    org = db.get(Organization, membership.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="ORG_NOT_FOUND"
        )
    return OrgContext(user=user, organization=org, membership=membership)


def require_roles(*roles: OrgRole):
    """Dependency factory enforcing an OrgRole (port of requireRole)."""

    def _checker(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
        if roles and not role_satisfies(ctx.role, roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="INSUFFICIENT_ROLE"
            )
        return ctx

    return _checker


def require_super_admin(user: User = Depends(get_current_user)) -> User:
    """Port of requireSuperAdmin. 403 (not 404) — the monolith silently redirects;
    here the API returns 403 without revealing resource existence details."""
    if not user.is_super_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="SUPER_ADMIN_REQUIRED"
        )
    return user
