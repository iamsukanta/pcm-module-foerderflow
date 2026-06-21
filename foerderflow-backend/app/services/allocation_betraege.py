"""Allocation amount calculation — port of lib/allocation-betraege.ts.

Balancing invariant (mandatory for Verwendungsnachweis): betrag_foerderfahig ==
betrag_foerderung + betrag_eigenanteil (to the cent). Eigenanteil is the REST of
the two rounded values, never rounded independently.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def _round2(x: float) -> float:
    """Match JS Math.round(x*100)/100 (half-up) for the non-negative amounts here."""
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class AllocationBetraege:
    betrag_foerderfahig: float
    betrag_foerderung: float
    betrag_eigenanteil: float


def compute_allocation_betraege(
    brutto: float, foerderquote: float, mwst_foerderfahig: bool, mwst_satz: float
) -> AllocationBetraege:
    betrag_netto = brutto / (1 + mwst_satz / 100)
    foerderfahig_raw = brutto if mwst_foerderfahig else betrag_netto
    foerderung_raw = foerderfahig_raw * foerderquote / 100

    betrag_foerderfahig = _round2(foerderfahig_raw)
    betrag_foerderung = _round2(foerderung_raw)
    betrag_eigenanteil = _round2(betrag_foerderfahig - betrag_foerderung)
    return AllocationBetraege(betrag_foerderfahig, betrag_foerderung, betrag_eigenanteil)
