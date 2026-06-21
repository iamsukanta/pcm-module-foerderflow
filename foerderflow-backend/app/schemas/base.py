"""Pydantic v2 schema foundation.

Serialization contract (matches the monolith's wire format, per PLANNING.md):
- Prisma serializes `Decimal` to JSON **strings**; the frontend parses with
  parseFloat. We mirror that by serializing Decimal as string.
- Dates use ISO-8601.

All read schemas inherit `ORMModel` (from_attributes=True) so they can be built
directly from SQLAlchemy instances.
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_serializer


class APIModel(BaseModel):
    """Base for request bodies / value objects."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)


class ORMModel(APIModel):
    """Base for response models read from ORM objects."""

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, str_strip_whitespace=True
    )


def decimal_to_str(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")


class MoneyMixin:
    """Reusable Decimal->string serializer for monetary/percent fields.

    Apply by listing the field names in `__decimal_fields__` on the subclass, or
    use `field_serializer` directly. Provided as a helper for consistency."""


def iso_date(value: date | None) -> str | None:
    return None if value is None else value.isoformat()


def iso_datetime(value: datetime | None) -> str | None:
    return None if value is None else value.isoformat()


class TimestampedRead(ORMModel):
    created_at: datetime
    updated_at: datetime | None = None

    @field_serializer("created_at", "updated_at")
    def _ser_ts(self, v: datetime | None) -> str | None:
        return iso_datetime(v)
