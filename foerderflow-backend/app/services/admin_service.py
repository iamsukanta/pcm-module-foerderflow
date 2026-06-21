"""Super-admin service — port of app/api/admin/*.

Organisations (list/create/detail/update/delete-if-empty), users (list/detail/
update super-admin flag + profile), members (add/role/remove with last-admin
guard), invites (revoke). All callers gated by require_super_admin in the route.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.auth import OrganizationMembership, OrgInvite, User
from app.models.master import CostCenter, FiscalYear
from app.models.funding import FundingMeasure
from app.models.organization import Organization
from app.models.transaction import Transaction

VALID_RECHTSFORM = ("EV", "GGMBH", "STIFTUNG", "ANDERE")
VALID_ROLE = ("ADMIN", "FINANCE", "READONLY")


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _d(v):
    return v.isoformat() if v else None


def _label(vorname, nachname, name, email) -> str:
    parts = [p for p in (vorname, nachname) if p]
    return " ".join(parts) or name or email or "—"


class AdminService:
    def __init__(self, db: Session):
        self.db = db

    def _count(self, model, **filters) -> int:
        stmt = select(func.count()).select_from(model)
        for k, v in filters.items():
            stmt = stmt.where(getattr(model, k) == v)
        return self.db.execute(stmt).scalar_one()

    # ── organisations ───────────────────────────────────────────────────────────
    def list_orgs(self) -> list[dict[str, Any]]:
        orgs = self.db.execute(select(Organization).order_by(Organization.name.asc())).scalars().all()
        out = []
        for o in orgs:
            out.append(
                {
                    "id": o.id,
                    "name": o.name,
                    "rechtsform": _ev(o.rechtsform),
                    "mitglieder_count": self._count(OrganizationMembership, org_id=o.id),
                    "transaction_count": self._count(Transaction, org_id=o.id),
                    "created_at": _d(o.created_at),
                }
            )
        return out

    def create_org(self, body: dict[str, Any]) -> dict[str, Any]:
        name = str(body.get("name") or "").strip()
        rechtsform = str(body.get("rechtsform") or "")
        try:
            workhours = float(body.get("regelarbeitszeit_stunden", 39))
        except (TypeError, ValueError):
            workhours = float("nan")
        if not name or not (2 <= len(name) <= 200):
            raise APIError(422, "VALIDATION_NAME", "Name muss 2–200 Zeichen lang sein.")
        if rechtsform not in VALID_RECHTSFORM:
            raise APIError(422, "VALIDATION_RECHTSFORM", "Ungültige Rechtsform.")
        if not (workhours == workhours) or workhours < 1 or workhours > 80:
            raise APIError(
                422, "VALIDATION_WORKHOURS", "Regelarbeitszeit muss zwischen 1 und 80 Stunden liegen."
            )
        org = Organization(name=name, rechtsform=rechtsform, regelarbeitszeit_stunden=workhours)
        self.db.add(org)
        self.db.flush()
        first_fy = body.get("firstFiscalYear")
        if isinstance(first_fy, dict):
            from datetime import date

            self.db.add(
                FiscalYear(
                    org_id=org.id,
                    jahr=first_fy["jahr"],
                    beginn=date.fromisoformat(first_fy["beginn"][:10]),
                    ende=date.fromisoformat(first_fy["ende"][:10]),
                )
            )
        self.db.commit()
        self.db.refresh(org)
        return {"data": {"id": org.id, "name": org.name}, "message": f'Organisation "{org.name}" angelegt.'}

    def get_org(self, id_: str) -> dict[str, Any]:
        org = self.db.execute(
            select(Organization)
            .where(Organization.id == id_)
            .options(selectinload(Organization.memberships).selectinload(OrganizationMembership.user))
        ).scalar_one_or_none()
        if org is None:
            raise APIError(404, "NOT_FOUND", "Organisation nicht gefunden.")
        invites = (
            self.db.execute(
                select(OrgInvite)
                .where(
                    OrgInvite.org_id == id_,
                    OrgInvite.used_at.is_(None),
                    OrgInvite.expires_at > datetime.now(timezone.utc),
                )
                .order_by(OrgInvite.created_at.desc())
                .options(selectinload(OrgInvite.created_by_user))
            )
            .scalars()
            .all()
        )
        members = sorted(org.memberships, key=lambda m: m.created_at)
        return {
            "data": {
                "id": org.id,
                "name": org.name,
                "rechtsform": _ev(org.rechtsform),
                "regelarbeitszeit_stunden": float(org.regelarbeitszeit_stunden),
                "created_at": _d(org.created_at),
                "counts": {
                    "transactions": self._count(Transaction, org_id=id_),
                    "funding_measures": self._count(FundingMeasure, org_id=id_),
                    "cost_centers": self._count(CostCenter, org_id=id_),
                },
                "members": [
                    {
                        "id": m.id,
                        "user_id": m.user_id,
                        "email": m.user.email,
                        "vorname": m.user.vorname,
                        "nachname": m.user.nachname,
                        "name": m.user.name,
                        "role": _ev(m.role),
                        "created_at": _d(m.created_at),
                    }
                    for m in members
                ],
                "invites": [
                    {
                        "id": i.id,
                        "email": i.email,
                        "role": _ev(i.role),
                        "expires_at": _d(i.expires_at),
                        "created_at": _d(i.created_at),
                        "created_by_label": _label(
                            i.created_by_user.vorname if i.created_by_user else None,
                            i.created_by_user.nachname if i.created_by_user else None,
                            i.created_by_user.name if i.created_by_user else None,
                            i.created_by_user.email if i.created_by_user else None,
                        ),
                    }
                    for i in invites
                ],
            }
        }

    def update_org(self, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        org = self.db.get(Organization, id_)
        if org is None:
            raise APIError(404, "NOT_FOUND", "Organisation nicht gefunden.")
        if isinstance(body.get("name"), str):
            v = body["name"].strip()
            if not (2 <= len(v) <= 200):
                raise APIError(422, "VALIDATION_NAME", "Name muss 2–200 Zeichen lang sein.")
            org.name = v
        if isinstance(body.get("rechtsform"), str):
            if body["rechtsform"] not in VALID_RECHTSFORM:
                raise APIError(422, "VALIDATION_RECHTSFORM", "Ungültige Rechtsform.")
            org.rechtsform = body["rechtsform"]
        if body.get("regelarbeitszeit_stunden") is not None:
            try:
                n = float(body["regelarbeitszeit_stunden"])
            except (TypeError, ValueError):
                n = float("nan")
            if not (n == n) or n < 1 or n > 80:
                raise APIError(422, "VALIDATION_WORKHOURS", "Regelarbeitszeit muss zwischen 1 und 80 liegen.")
            org.regelarbeitszeit_stunden = n
        self.db.commit()
        self.db.refresh(org)
        return {
            "data": {
                "id": org.id, "name": org.name, "rechtsform": _ev(org.rechtsform),
                "regelarbeitszeit_stunden": str(org.regelarbeitszeit_stunden),
                "created_at": _d(org.created_at), "updated_at": _d(org.updated_at),
            }
        }

    def delete_org(self, id_: str) -> dict[str, Any]:
        org = self.db.get(Organization, id_)
        if org is None:
            raise APIError(404, "NOT_FOUND", "Organisation nicht gefunden.")
        blockers = []
        if (n := self._count(Transaction, org_id=id_)) > 0:
            blockers.append(f"{n} Transaktion(en)")
        if (n := self._count(FundingMeasure, org_id=id_)) > 0:
            blockers.append(f"{n} Fördermaßnahme(n)")
        if (n := self._count(CostCenter, org_id=id_)) > 0:
            blockers.append(f"{n} Kostenstelle(n)")
        if (n := self._count(FiscalYear, org_id=id_)) > 0:
            blockers.append(f"{n} Haushaltsjahr(e)")
        if (n := self._count(OrganizationMembership, org_id=id_)) > 0:
            blockers.append(f"{n} Mitgliedschaft(en)")
        if blockers:
            raise APIError(
                409,
                "HAS_DEPENDENTS",
                f"Organisation kann nicht gelöscht werden — folgende Daten hängen daran: "
                f"{', '.join(blockers)}.",
                extra={"blockers": blockers},
            )
        self.db.delete(org)
        self.db.commit()
        return {"data": {"id": id_}, "message": "Organisation gelöscht."}

    # ── members ─────────────────────────────────────────────────────────────────
    def add_member(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        if self.db.get(Organization, org_id) is None:
            raise APIError(404, "ORG_NOT_FOUND", "Organisation nicht gefunden.")
        email = str(body["email"]).strip().lower() if body.get("email") else None
        user_id = str(body["user_id"]) if body.get("user_id") else None
        role = str(body.get("role") or "FINANCE")
        if not email and not user_id:
            raise APIError(422, "MISSING_USER_REF", "Entweder email oder user_id erforderlich.")
        if role not in VALID_ROLE:
            raise APIError(422, "VALIDATION_ROLE", "Ungültige Rolle.")
        user = (
            self.db.get(User, user_id)
            if user_id
            else self.db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        )
        if user is None:
            raise APIError(
                404,
                "USER_NOT_FOUND",
                "User existiert nicht in FörderFlow. Stattdessen via Email einladen — beim "
                "ersten Magic-Link-Login wird der User-Datensatz angelegt.",
            )
        existing = self.db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.org_id == org_id, OrganizationMembership.user_id == user.id
            )
        ).scalar_one_or_none()
        if existing:
            raise APIError(
                409,
                "ALREADY_MEMBER",
                f"User ist bereits Mitglied dieser Organisation (Rolle: {_ev(existing.role)}).",
            )
        m = OrganizationMembership(org_id=org_id, user_id=user.id, role=role)
        self.db.add(m)
        self.db.commit()
        self.db.refresh(m)
        return {
            "data": {"id": m.id, "user_id": user.id, "email": user.email, "role": _ev(m.role)},
            "message": f"{user.email} wurde als {role} hinzugefügt.",
        }

    def _last_admin_guard(self, org_id: str, current_role: str, new_role: str | None, force: bool) -> None:
        if current_role != "ADMIN" or new_role == "ADMIN" or force:
            return
        admin_count = self.db.execute(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(OrganizationMembership.org_id == org_id, OrganizationMembership.role == "ADMIN")
        ).scalar_one()
        if admin_count <= 1:
            msg = (
                "Letzter Org-Admin würde entfernt — Org würde ohne Admin verwaisen. Mit ?force=true erzwingen."
                if new_role is None
                else "Letzter Org-Admin würde degradiert — Org würde ohne Admin verwaisen. Mit ?force=true erzwingen."
            )
            raise APIError(409, "LAST_ADMIN", msg)

    def update_member(self, org_id: str, user_id: str, body: dict[str, Any], force: bool) -> dict[str, Any]:
        m = self.db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.org_id == org_id, OrganizationMembership.user_id == user_id
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Mitgliedschaft nicht gefunden.")
        role = str(body.get("role") or "")
        if role not in VALID_ROLE:
            raise APIError(422, "VALIDATION_ROLE", "Ungültige Rolle.")
        self._last_admin_guard(org_id, _ev(m.role), role, force)
        m.role = role
        self.db.commit()
        self.db.refresh(m)
        return {"data": {"id": m.id, "role": _ev(m.role)}}

    def remove_member(self, org_id: str, user_id: str, force: bool) -> dict[str, Any]:
        m = self.db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.org_id == org_id, OrganizationMembership.user_id == user_id
            )
        ).scalar_one_or_none()
        if m is None:
            raise APIError(404, "NOT_FOUND", "Mitgliedschaft nicht gefunden.")
        self._last_admin_guard(org_id, _ev(m.role), None, force)
        mid = m.id
        self.db.delete(m)
        self.db.commit()
        return {"data": {"id": mid}, "message": "Mitglied entfernt."}

    def revoke_invite(self, org_id: str, invite_id: str) -> dict[str, Any]:
        invite = self.db.get(OrgInvite, invite_id)
        if invite is None or invite.org_id != org_id:
            raise APIError(404, "NOT_FOUND", "Einladung nicht gefunden.")
        if invite.used_at:
            raise APIError(409, "ALREADY_USED", "Einladung wurde bereits eingelöst.")
        invite.expires_at = datetime.now(timezone.utc)
        self.db.commit()
        return {"data": {"id": invite_id}, "message": "Einladung widerrufen."}

    # ── users ─────────────────────────────────────────────────────────────────────
    def list_users(self) -> list[dict[str, Any]]:
        users = (
            self.db.execute(
                select(User)
                .order_by(User.email.asc())
                .options(
                    selectinload(User.sessions),
                    selectinload(User.memberships).selectinload(OrganizationMembership.organization),
                )
            )
            .scalars()
            .all()
        )
        out = []
        for u in users:
            sessions = sorted(u.sessions, key=lambda s: s.expires, reverse=True)
            memberships = sorted(u.memberships, key=lambda m: m.created_at)
            out.append(
                {
                    "id": u.id,
                    "email": u.email,
                    "vorname": u.vorname,
                    "nachname": u.nachname,
                    "name": u.name,
                    "is_super_admin": u.is_super_admin,
                    "org_count": len(u.memberships),
                    "session_count": len(u.sessions),
                    "letzter_login": _d(sessions[0].expires) if sessions else None,
                    "created_at": _d(u.created_at),
                    "memberships": [
                        {
                            "org_id": m.org_id,
                            "org_name": m.organization.name if m.organization else "",
                            "role": _ev(m.role),
                        }
                        for m in memberships
                    ],
                }
            )
        return out

    def get_user(self, id_: str) -> dict[str, Any]:
        u = self.db.execute(
            select(User)
            .where(User.id == id_)
            .options(selectinload(User.memberships).selectinload(OrganizationMembership.organization))
        ).scalar_one_or_none()
        if u is None:
            raise APIError(404, "NOT_FOUND", "User nicht gefunden.")
        members = sorted(u.memberships, key=lambda m: m.created_at)
        return {
            "data": {
                "id": u.id, "email": u.email, "vorname": u.vorname, "nachname": u.nachname,
                "name": u.name, "is_super_admin": u.is_super_admin, "created_at": _d(u.created_at),
                "memberships": [
                    {
                        "id": m.id, "org_id": m.organization.id, "org_name": m.organization.name,
                        "role": _ev(m.role), "created_at": _d(m.created_at),
                    }
                    for m in members
                ],
            }
        }

    def update_user(self, acting_user_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        target = self.db.get(User, id_)
        if target is None:
            raise APIError(404, "NOT_FOUND", "User nicht gefunden.")
        if isinstance(body.get("is_super_admin"), bool):
            if id_ == acting_user_id and body["is_super_admin"] is False:
                raise APIError(
                    409,
                    "SELF_REVOKE_FORBIDDEN",
                    "Du kannst dir nicht selbst den Super-Admin-Status entziehen — bitte einen "
                    "anderen Super-Admin bitten.",
                )
            target.is_super_admin = body["is_super_admin"]
        touched_name = False
        if "vorname" in body:
            v = body["vorname"]
            if v is not None and (not isinstance(v, str) or len(v) > 100):
                raise APIError(422, "VALIDATION_VORNAME", "Vorname ungültig.")
            target.vorname = v.strip() or None if isinstance(v, str) else None
            touched_name = True
        if "nachname" in body:
            v = body["nachname"]
            if v is not None and (not isinstance(v, str) or len(v) > 100):
                raise APIError(422, "VALIDATION_NACHNAME", "Nachname ungültig.")
            target.nachname = v.strip() or None if isinstance(v, str) else None
            touched_name = True
        if touched_name:
            parts = [p for p in (target.vorname, target.nachname) if p and p.strip()]
            target.name = " ".join(parts) if parts else None
        self.db.commit()
        self.db.refresh(target)
        return {
            "data": {
                "id": target.id, "email": target.email, "vorname": target.vorname,
                "nachname": target.nachname, "name": target.name,
                "is_super_admin": target.is_super_admin,
            }
        }
