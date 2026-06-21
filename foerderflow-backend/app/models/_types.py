"""Shared column-type helpers for the ORM models."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedColumn, mapped_column

from app.db.base import generate_cuid

# JSONB on PostgreSQL, plain JSON on other dialects (e.g. the SQLite test harness).
JSONBType = JSONB().with_variant(JSON(), "sqlite")


def pg_enum(enum_cls: type[PyEnum]) -> SAEnum:
    """Build a native PostgreSQL ENUM bound to the Prisma `@@map` type name.

    Using the same enum type name + values keeps the database byte-compatible
    with the monolith's Prisma-managed schema.
    """
    return SAEnum(
        enum_cls,
        name=getattr(enum_cls, "__pg_name__", enum_cls.__name__.lower()),
        values_callable=lambda e: [m.value for m in e],
        native_enum=True,
        create_constraint=False,
    )


def cuid_pk() -> MappedColumn[str]:
    """String `cuid` primary key, matching Prisma `@id @default(cuid())`."""
    return mapped_column(String, primary_key=True, default=generate_cuid)


def created_at() -> MappedColumn[datetime]:
    return mapped_column(DateTime, server_default=func.now(), nullable=False)


def updated_at() -> MappedColumn[datetime]:
    return mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


# Re-export for convenient typed annotations in model modules.
__all__ = ["pg_enum", "cuid_pk", "created_at", "updated_at", "Mapped"]
