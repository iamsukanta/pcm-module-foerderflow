"""Pure PCM calculation helpers (no DB).

The §4 ANBest-P proration (Dreisatz) itself is reused from
``app.services.personal.berechnung.berechne_gehalt`` for AN/AG-Brutto parity with
the existing payroll path; this module adds the PCM-specific BAV computation and a
shared rounding helper.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def round2(value: float | Decimal) -> Decimal:
    """Round to 2 decimal places (half-up), matching the seed/service convention."""
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def compute_bav(*, actual_salary: float, bav_rate_pct: float) -> float:
    """Betriebliche Altersversorgung — employer pension at a flat rate.

    ``bav_amount = actual_salary × (bav_rate_pct / 100)``. An employer cost; it
    does not appear in the employee's AN-Brutto.
    """
    return actual_salary * (bav_rate_pct / 100.0)
