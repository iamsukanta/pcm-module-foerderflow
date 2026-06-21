"""Canonical wire-format serialization helpers (shared across services).

Decimal → string matching Prisma/decimal.js `toString()`, which drops trailing
zeros: 100000.00 → "100000", 80.00 → "80", 33.330 → "33.33", 19.0 → "19".
"""

from __future__ import annotations

from decimal import Decimal


def decimal_str(v: Decimal | float | int | None) -> str | None:
    if v is None:
        return None
    # Tolerate plain numerics: the identity map may hold a Python-assigned
    # float/int that hasn't round-tripped through the DB as a Decimal yet.
    if not isinstance(v, Decimal):
        v = Decimal(str(v))
    if v == 0:
        return "0"
    normalized = v.normalize()
    # `normalize()` can yield scientific notation (1E+5); format 'f' expands it.
    return format(normalized, "f")
