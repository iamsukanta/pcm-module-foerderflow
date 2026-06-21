"""Module PCM (Personal Cost Management) — Phase 2 processing engine.

Pure, service-layer business logic (sync ``Session``) for the personnel-cost
spine modeled in Phase 1:

- ``tariff_lookup`` — validity-window tariff resolution + overlap validation
- ``doppelfoerderung`` — the hard hour/plan-% capacity guard
- ``payroll_engine`` — the monthly payroll run (Dreisatz, BAV, detail lines,
  PCM-origin allocations)

No HTTP routing or UI here — those are Phase 3 / Phase 4.
"""

from app.services.pcm.calc import compute_bav, round2
from app.services.pcm.doppelfoerderung import assert_assignment_allowed
from app.services.pcm.payroll_engine import run_monthly_payroll
from app.services.pcm.tariff_lookup import (
    assert_no_overlap,
    assert_window_valid,
    resolve_tariff,
)

__all__ = [
    "round2",
    "compute_bav",
    "resolve_tariff",
    "assert_no_overlap",
    "assert_window_valid",
    "assert_assignment_allowed",
    "run_monthly_payroll",
]
