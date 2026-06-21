"""SQLAlchemy declarative base + shared column conventions.

The monolith uses Prisma with `cuid()` string primary keys and snake_case table
names via `@@map`. We preserve both so the FastAPI backend can run against the
exact same PostgreSQL schema (byte-compatible migration target).
"""

from datetime import datetime

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable, explicit constraint naming so Alembic autogenerate is deterministic.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

try:  # Prefer real cuid generation (matches Prisma `@default(cuid())`).
    from cuid2 import cuid_wrapper

    _cuid_generator = cuid_wrapper()

    def generate_cuid() -> str:
        return _cuid_generator()

except ImportError:  # Fallback so the package imports without the optional dep.
    import secrets

    def generate_cuid() -> str:
        return "c" + secrets.token_hex(12)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CuidPK:
    """Mixin: string `cuid` primary key, matching Prisma `@id @default(cuid())`."""

    id: Mapped[str] = mapped_column(primary_key=True, default=generate_cuid)


class Timestamps:
    """Mixin: `created_at` / `updated_at`, matching Prisma `@default(now())` /
    `@updatedAt`."""

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )
