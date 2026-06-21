"""Ampel-Warnsystem — pure port of lib/ampel.ts. ROT > GELB > GRUEN."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date


@dataclass
class AmpelResult:
    status: str
    ausschoepfung_prozent: float
    gruende: list[str]


def berechne_ampel(
    *,
    betrag_bewilligt: float,
    betrag_ist: float,
    laufzeit_von: date,
    laufzeit_bis: date,
    overhead_limit_prozent: float | None,
    overhead_ist_prozent: float,
) -> AmpelResult:
    ausschoepfung = (betrag_ist / betrag_bewilligt * 100) if betrag_bewilligt > 0 else 0.0
    today = date.today()
    days_until_expiry = math.ceil((laufzeit_bis - today).days)
    total_days = max(1, math.ceil((laufzeit_bis - laufzeit_von).days))
    days_elapsed = max(0, math.ceil((today - laufzeit_von).days))
    soll = min(100, days_elapsed / total_days * 100)
    tempo_abw = abs(ausschoepfung - soll)
    gruende: list[str] = []

    if overhead_limit_prozent is not None and overhead_ist_prozent > overhead_limit_prozent:
        gruende.append(
            f"Gemeinkostendeckel überschritten: {overhead_ist_prozent:.1f}% "
            f"(Limit: {overhead_limit_prozent}%)"
        )
        return AmpelResult("ROT", ausschoepfung, gruende)
    if ausschoepfung > 95:
        gruende.append(f"Ausschöpfung bei {ausschoepfung:.1f}% — Budgetüberlauf droht")
        return AmpelResult("ROT", ausschoepfung, gruende)
    if ausschoepfung < 40 and 0 <= days_until_expiry < 90:
        gruende.append(
            f"Nur {ausschoepfung:.1f}% ausgeschöpft bei {days_until_expiry} verbleibenden "
            "Tagen — Unterausschöpfung kritisch"
        )
        return AmpelResult("ROT", ausschoepfung, gruende)
    if ausschoepfung >= 80:
        gruende.append(f"Ausschöpfung bei {ausschoepfung:.1f}% — Budget wird knapp")
        return AmpelResult("GELB", ausschoepfung, gruende)
    if tempo_abw > 10 and days_elapsed > 0:
        gruende.append(
            f"Ausgabentempo weicht {tempo_abw:.1f}% vom Soll-Kurs ab "
            f"(Soll: {soll:.1f}%, Ist: {ausschoepfung:.1f}%)"
        )
        return AmpelResult("GELB", ausschoepfung, gruende)
    gruende.append(f"Ausschöpfung {ausschoepfung:.1f}% — im Zielkorridor")
    return AmpelResult("GRUEN", ausschoepfung, gruende)
