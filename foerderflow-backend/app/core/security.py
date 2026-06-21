"""Auth primitives: JWT issuance/verification + magic-link tokens.

Per the migration decision, FörderFlow stays **passwordless**: a magic link is
emailed, and on verification the backend issues a JWT access token. No passwords
are stored (matches the monolith's NextAuth email-provider behavior + GDPR stance).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import secrets

from jose import JWTError, jwt

from app.core.config import settings


class TokenError(Exception):
    """Raised when a JWT is invalid or expired."""


def create_access_token(
    subject: str, extra_claims: dict[str, Any] | None = None
) -> str:
    """Issue a signed JWT. `subject` is the user id (sub claim)."""
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.access_token_expires_minutes)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "type": "access",
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.auth_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify signature + expiry; return claims. Raises TokenError on failure."""
    try:
        return jwt.decode(
            token, settings.auth_secret, algorithms=[settings.jwt_algorithm]
        )
    except JWTError as exc:  # noqa: B904
        raise TokenError(str(exc))


def generate_magic_link_token() -> str:
    """Opaque, URL-safe token stored in `verification_tokens` (single-use)."""
    return secrets.token_urlsafe(32)


def magic_link_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(
        minutes=settings.magic_link_expires_minutes
    )
