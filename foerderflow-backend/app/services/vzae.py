"""VZÄ + Soll-Ist status helpers — port of lib/personal/vzae.ts."""

from __future__ import annotations


def berechne_vzae(assigned_hours: float, standard_hours: float) -> float:
    if standard_hours == 0:
        return 0.0
    return assigned_hours / standard_hours


def berechne_vzae_anteil(vzae: float, prozent: float) -> float:
    return vzae * prozent / 100


def berechne_soll_ist_status(soll: float, ist: float) -> str:
    if soll == 0:
        return "UEBERSCHRITTEN" if ist > 0 else "OK"
    ratio = ist / soll
    if ratio > 1:
        return "UEBERSCHRITTEN"
    if ratio >= 0.95:
        return "KRITISCH"
    if ratio >= 0.80:
        return "WARNING"
    return "OK"
