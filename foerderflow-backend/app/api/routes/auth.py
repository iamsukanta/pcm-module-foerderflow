"""Auth endpoints — passwordless magic-link → JWT.

Port of the monolith's NextAuth email flow:
  POST /api/auth/magic-link  -> create single-use token, email link
  POST /api/auth/verify      -> consume token, mark email verified, issue JWT
  POST /api/auth/signout     -> stateless (client discards JWT)
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.core.security import (
    create_access_token,
    generate_magic_link_token,
    magic_link_expiry,
)
from app.db.session import get_db
from app.models.auth import User, VerificationToken
from app.schemas.auth import MagicLinkRequest, TokenResponse
from app.services.email_service import send_magic_link

router = APIRouter(tags=["auth"])


@router.post("/magic-link", status_code=status.HTTP_202_ACCEPTED)
def request_magic_link(
    body: MagicLinkRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    """Always returns 202 (no user enumeration). Creates a user row on first login,
    matching the monolith's email-provider auto-provisioning."""
    email = body.email.lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if user is None:
        user = User(email=email)
        db.add(user)

    token = generate_magic_link_token()
    db.add(
        VerificationToken(
            identifier=email, token=token, expires=magic_link_expiry()
        )
    )
    db.commit()
    send_magic_link(email, token, body.callback_url)
    return {"message": "Falls ein Konto existiert, wurde ein Login-Link versendet."}


@router.post("/verify", response_model=TokenResponse)
def verify_magic_link(token: str, db: Session = Depends(get_db)) -> TokenResponse:
    vt = db.get(VerificationToken, token)
    if vt is None:
        raise APIError(status.HTTP_400_BAD_REQUEST, "INVALID_TOKEN", "Ungültiger Link.")
    if vt.expires.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        db.execute(delete(VerificationToken).where(VerificationToken.token == token))
        db.commit()
        raise APIError(status.HTTP_400_BAD_REQUEST, "EXPIRED_TOKEN", "Link abgelaufen.")

    user = db.execute(
        select(User).where(User.email == vt.identifier)
    ).scalar_one_or_none()
    if user is None:
        raise APIError(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "User nicht gefunden.")

    if user.email_verified is None:
        user.email_verified = datetime.now(timezone.utc)
    # Single-use: consume the token.
    db.execute(delete(VerificationToken).where(VerificationToken.token == token))
    db.commit()

    return TokenResponse(access_token=create_access_token(subject=user.id))


@router.post("/signout")
def signout() -> dict[str, str]:
    # JWT is stateless; the client discards it. Endpoint kept for parity.
    return {"message": "Abgemeldet."}
