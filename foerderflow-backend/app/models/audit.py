"""AuditLog (audit_logs) — fire-and-forget audit trail. org_id is denormalized
(no FK / relation in Prisma)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models._types import JSONBType, cuid_pk


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_org_id_entitaet", "org_id", "entitaet"),
        Index("ix_audit_logs_org_id_user_id", "org_id", "user_id"),
        Index("ix_audit_logs_created_at", "created_at"),
    )

    id: Mapped[str] = cuid_pk()
    org_id: Mapped[str] = mapped_column(String, nullable=False)  # denormalized, no FK
    user_id: Mapped[str | None] = mapped_column(String, nullable=True)
    aktion: Mapped[str] = mapped_column(String(100), nullable=False)
    entitaet: Mapped[str] = mapped_column(String(100), nullable=False)
    entitaet_id: Mapped[str] = mapped_column(String(200), nullable=False)
    vorher: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    nachher: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
