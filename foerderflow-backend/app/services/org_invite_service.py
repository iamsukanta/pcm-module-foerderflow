"""Org invite creation — port of lib/org-invites.ts.

Validates email, blocks existing members, expires old open invites, creates a
7-day invite, and sends the magic-link email (logged in dev). Shared by the
Org-Admin (org/invite) and Super-Admin (admin/.../invite) callers.
"""

from __future__ import annotations

import logging
import re
import smtplib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth import OrganizationMembership, OrgInvite, User
from app.models.organization import Organization

logger = logging.getLogger(__name__)
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


@dataclass
class InviteResult:
    ok: bool
    invite: dict | None = None
    error: str | None = None
    code: str | None = None
    status: int = 200


def _send_invite_email(to_email: str, org_name: str, inviter_label: str, url: str) -> None:
    if settings.environment != "production" or not settings.email_server_host:
        logger.info("[Invite] %s → %s", to_email, url)
        return
    msg = EmailMessage()
    msg["Subject"] = f"Du wurdest zu {org_name} auf FörderFlow eingeladen"
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg.set_content(
        f"Du wurdest von {inviter_label} zu {org_name} auf FörderFlow eingeladen.\n\n"
        f"Link: {url}\n\nDer Link ist 7 Tage gültig."
    )
    with smtplib.SMTP(settings.email_server_host, settings.email_server_port) as server:
        if settings.email_server_user:
            server.starttls()
            server.login(settings.email_server_user, settings.email_server_password)
        server.send_message(msg)


def create_org_invite(
    db: Session, *, org_id: str, email: str, role: str, created_by: str, inviter_label: str
) -> InviteResult:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        return InviteResult(False, error="Ungültige E-Mail-Adresse.", code="INVALID_EMAIL", status=400)

    existing_user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing_user:
        m = db.execute(
            select(OrganizationMembership).where(
                OrganizationMembership.org_id == org_id,
                OrganizationMembership.user_id == existing_user.id,
            )
        ).scalar_one_or_none()
        if m:
            return InviteResult(
                False,
                error="Diese Person ist bereits Mitglied der Organisation.",
                code="ALREADY_MEMBER",
                status=409,
            )

    org = db.get(Organization, org_id)
    if org is None:
        return InviteResult(False, error="Organisation nicht gefunden.", code="ORG_NOT_FOUND", status=404)

    # expire old open invites for this email
    db.execute(
        update(OrgInvite)
        .where(OrgInvite.org_id == org_id, OrgInvite.email == email, OrgInvite.used_at.is_(None))
        .values(expires_at=datetime.now(timezone.utc))
    )
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    invite = OrgInvite(org_id=org_id, email=email, role=role, expires_at=expires_at, created_by=created_by)
    db.add(invite)
    db.commit()
    db.refresh(invite)

    base = settings.frontend_url.rstrip("/")
    url = f"{base}/login?callbackUrl=/dashboard&invite={invite.token}"
    _send_invite_email(email, org.name, inviter_label, url)

    return InviteResult(
        ok=True,
        invite={
            "id": invite.id,
            "email": invite.email,
            "role": invite.role.value if hasattr(invite.role, "value") else invite.role,
            "expires_at": invite.expires_at.isoformat(),
        },
    )
