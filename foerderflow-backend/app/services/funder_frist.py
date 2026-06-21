"""Funder default Nachweis-Fristen — port of lib/funder-frist.ts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master import FunderNachweisFrist


@dataclass
class FristErgebnis:
    frist: date
    bezug: str
    tage_offset: int
    quelle: str


def _bezugsdatum(bezug: str, bewilligungs_ende: date, durchfuehrungs_ende: date | None, hhj_ende: date) -> date:
    if bezug == "HHJ_ENDE":
        return hhj_ende
    if bezug == "DURCHFUEHRUNG_ENDE":
        return durchfuehrungs_ende or bewilligungs_ende
    return bewilligungs_ende  # BEWILLIGUNG_ENDE


def frist_aus_regel(
    bezug: str,
    tage_offset: int,
    beschreibung: str | None,
    bewilligungs_ende: date,
    durchfuehrungs_ende: date | None,
    hhj_ende: date,
) -> FristErgebnis:
    anker = _bezugsdatum(bezug, bewilligungs_ende, durchfuehrungs_ende, hhj_ende)
    return FristErgebnis(
        frist=anker + timedelta(days=tage_offset),
        bezug=bezug,
        tage_offset=tage_offset,
        quelle=beschreibung or "Standard-Frist des Fördergebers",
    )


def berechne_nachweis_frist(
    db: Session,
    *,
    org_id: str,
    funder_id: str,
    nachweis_typ: str,
    bewilligungs_ende: date,
    durchfuehrungs_ende: date | None,
    hhj_ende: date,
) -> FristErgebnis | None:
    regel = db.execute(
        select(FunderNachweisFrist).where(
            FunderNachweisFrist.org_id == org_id,
            FunderNachweisFrist.funder_id == funder_id,
            FunderNachweisFrist.nachweis_typ == nachweis_typ,
        )
    ).scalar_one_or_none()
    if regel is None:
        return None
    bezug = regel.bezug.value if hasattr(regel.bezug, "value") else regel.bezug
    return frist_aus_regel(
        bezug, regel.tage_offset, regel.beschreibung, bewilligungs_ende, durchfuehrungs_ende, hhj_ende
    )
