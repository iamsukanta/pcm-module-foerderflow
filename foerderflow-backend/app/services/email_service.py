"""Magic-link email delivery.

In development (or when SMTP isn't configured) the link is logged instead of sent,
mirroring the monolith's mailpit-based dev workflow. SMTP wiring uses the same
EMAIL_* settings as the monolith.
"""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger(__name__)


def build_magic_link(token: str, callback_url: str | None) -> str:
    base = settings.frontend_url.rstrip("/")
    cb = callback_url or "/dashboard"
    return f"{base}/login/verify?token={token}&callbackUrl={cb}"


def send_magic_link(to_email: str, token: str, callback_url: str | None = None) -> None:
    link = build_magic_link(token, callback_url)

    if not settings.email_server_host or settings.environment != "production":
        logger.info("[magic-link] (dev) for %s: %s", to_email, link)
        return

    msg = EmailMessage()
    msg["Subject"] = "Ihr FörderFlow-Login"
    msg["From"] = settings.email_from
    msg["To"] = to_email
    msg.set_content(
        f"Hallo,\n\nmit diesem Link melden Sie sich bei FörderFlow an:\n\n{link}\n\n"
        f"Der Link ist {settings.magic_link_expires_minutes // 60} Stunden gültig.\n"
    )
    with smtplib.SMTP(settings.email_server_host, settings.email_server_port) as server:
        if settings.email_server_user:
            server.starttls()
            server.login(settings.email_server_user, settings.email_server_password)
        server.send_message(msg)
    logger.info("[magic-link] sent to %s", to_email)
