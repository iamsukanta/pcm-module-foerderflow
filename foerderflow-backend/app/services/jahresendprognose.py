"""Jahresendprognose — pure port of lib/jahresendprognose.ts.

90-day burn-rate extrapolation to project year-end spend vs. budget.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class PrognoseResult:
    monatsrate: float
    betrag_ist_gesamt: float
    prognose_gesamt: float
    prognose_prozent: float
    days_remaining: int
    status: str


def berechne_jahresendprognose(
    *, laufzeit_bis: date, allocations: list[dict], betrag_bewilligt: float
) -> PrognoseResult:
    today = date.today()
    days_remaining = max(0, math.ceil((laufzeit_bis - today).days))

    betrag_ist_gesamt = sum(a["betrag_foerderfahig"] for a in allocations)

    cutoff = today - timedelta(days=90)
    letzte90 = [a for a in allocations if a["datum"] >= cutoff]
    betrag_90 = sum(a["betrag_foerderfahig"] for a in letzte90)
    monatsrate = betrag_90 / 3

    monate_remaining = days_remaining / 30.44
    prognose_gesamt = betrag_ist_gesamt + monatsrate * monate_remaining
    prognose_prozent = (prognose_gesamt / betrag_bewilligt * 100) if betrag_bewilligt > 0 else 0

    if prognose_prozent > 100:
        status = "UEBERSCHREITUNG"
    elif prognose_prozent < 80:
        status = "UNTERAUSSCHOEPFUNG"
    else:
        status = "OK"

    return PrognoseResult(
        monatsrate=round(monatsrate * 100) / 100,
        betrag_ist_gesamt=round(betrag_ist_gesamt * 100) / 100,
        prognose_gesamt=round(prognose_gesamt * 100) / 100,
        prognose_prozent=round(prognose_prozent * 10) / 10,
        days_remaining=days_remaining,
        status=status,
    )
