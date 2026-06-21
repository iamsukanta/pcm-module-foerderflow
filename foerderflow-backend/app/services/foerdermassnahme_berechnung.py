"""Zuwendungs-Berechnung — port of lib/foerdermassnahme-berechnung.ts (berechneZuwendung)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


def round2(x: float) -> float:
    return float(Decimal(repr(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@dataclass
class ZuwendungsBerechnung:
    zuwendung: float
    foerderquote: float


def berechne_zuwendung(
    finanzierungsart: str,
    gesamtausgaben: float,
    foerderquote_input: float | None = None,
    eigenmittel: float | None = None,
    drittmittel: float | None = None,
) -> ZuwendungsBerechnung:
    if finanzierungsart == "ANTEIL":
        q = foerderquote_input or 0
        return ZuwendungsBerechnung(round2(gesamtausgaben * (q / 100)), q)
    if finanzierungsart == "FEHLBEDARF":
        eigen = eigenmittel or 0
        dritt = drittmittel or 0
        zuwendung = gesamtausgaben - eigen - dritt
        quote = (zuwendung / gesamtausgaben) * 100 if gesamtausgaben > 0 else 0
        return ZuwendungsBerechnung(round2(zuwendung), round2(quote))
    if finanzierungsart == "FESTBETRAG":
        return ZuwendungsBerechnung(round2(gesamtausgaben), 0)
    raise ValueError(f"Unbekannte Finanzierungsart: {finanzierungsart}")
