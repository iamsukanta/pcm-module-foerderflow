"""Auth & membership models — NextAuth-compatible schema.

Ports: User (users), Account (accounts), Session (sessions),
VerificationToken (verification_tokens), OrganizationMembership
(organization_memberships), OrgInvite (org_invites).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, generate_cuid
from app.models._types import created_at, cuid_pk, pg_enum, updated_at
from app.models.enums import OrgRole

if TYPE_CHECKING:
    from app.models.organization import Organization


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = cuid_pk()
    name: Mapped[str | None] = mapped_column(String, nullable=True)
    vorname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nachname: Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    email_verified: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    # VoluLink Super-Admin — cross-Org. Distinct from OrganizationMembership.role=ADMIN.
    is_super_admin: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    accounts: Mapped[list[Account]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    memberships: Mapped[list[OrganizationMembership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    created_invites: Mapped[list[OrgInvite]] = relationship(
        back_populates="created_by_user", foreign_keys="OrgInvite.created_by"
    )


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_account_id"),
        Index("ix_accounts_user_id", "user_id"),
    )

    id: Mapped[str] = cuid_pk()
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[int | None] = mapped_column(nullable=True)
    token_type: Mapped[str | None] = mapped_column(String, nullable=True)
    scope: Mapped[str | None] = mapped_column(String, nullable=True)
    id_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_state: Mapped[str | None] = mapped_column(String, nullable=True)

    user: Mapped[User] = relationship(back_populates="accounts")


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (Index("ix_sessions_user_id", "user_id"),)

    id: Mapped[str] = cuid_pk()
    session_token: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    expires: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class VerificationToken(Base):
    __tablename__ = "verification_tokens"
    __table_args__ = (UniqueConstraint("identifier", "token"),)

    # Prisma has no @id; the composite unique acts as the key. SQLAlchemy needs a
    # primary key, so `token` (globally @unique) is the natural PK.
    identifier: Mapped[str] = mapped_column(String, nullable=False)
    token: Mapped[str] = mapped_column(String, primary_key=True, unique=True)
    expires: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("org_id", "user_id"),
        Index("ix_organization_memberships_org_id", "org_id"),
        Index("ix_organization_memberships_user_id", "user_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[OrgRole] = mapped_column(
        pg_enum(OrgRole), default=OrgRole.READONLY, server_default="READONLY"
    )
    created_at: Mapped[datetime] = created_at()
    updated_at: Mapped[datetime] = updated_at()

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")


class OrgInvite(Base):
    __tablename__ = "org_invites"
    __table_args__ = (
        Index("ix_org_invites_token", "token"),
        Index("ix_org_invites_org_id", "org_id"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[OrgRole] = mapped_column(
        pg_enum(OrgRole), default=OrgRole.FINANCE, server_default="FINANCE"
    )
    token: Mapped[str] = mapped_column(String, unique=True, default=generate_cuid)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = created_at()

    organization: Mapped[Organization] = relationship(back_populates="invites")
    created_by_user: Mapped[User | None] = relationship(
        back_populates="created_invites", foreign_keys=[created_by]
    )
