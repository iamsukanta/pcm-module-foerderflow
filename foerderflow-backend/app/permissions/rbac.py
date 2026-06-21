"""RBAC policy — mirrors the monolith `lib/session.ts` semantics.

Two distinct authority axes (preserved exactly):
- OrgRole (ADMIN / FINANCE / READONLY) — scoped within one organization.
- User.is_super_admin — VoluLink platform admin, cross-org (the /admin area).
"""

from app.models.enums import OrgRole

# Roles permitted to mutate data (READONLY is view-only).
WRITE_ROLES: tuple[OrgRole, ...] = (OrgRole.ADMIN, OrgRole.FINANCE)
ADMIN_ROLES: tuple[OrgRole, ...] = (OrgRole.ADMIN,)
ALL_ROLES: tuple[OrgRole, ...] = (OrgRole.ADMIN, OrgRole.FINANCE, OrgRole.READONLY)


def role_satisfies(role: OrgRole, required: tuple[OrgRole, ...]) -> bool:
    return role in required
