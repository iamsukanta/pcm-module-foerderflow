"""Fristen — port of lib/fristen.ts (loadFristen, daysUntil, dringlichkeit,
countKritischeFristen) and lib/mittelabruf-frist.ts (getFristStatus,
getTageVerbleibend)."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.finanzplan import VerwNachweis
from app.models.funding import FundingMeasure
from app.models.master import FiscalYear
from app.models.mittelabruf import Mittelabruf

TYP_LABEL = {
    "ZWISCHENNACHWEIS": "Zwischennachweis",
    "VERWENDUNGSNACHWEIS": "Verwendungsnachweis",
    "SACHBERICHT_ONLY": "Sachbericht",
}


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def days_until(deadline: date) -> int:
    import math

    today = date.today()
    return math.ceil((deadline - today).days)


def dringlichkeit(tage: int) -> str:
    if tage <= 7:
        return "KRITISCH"
    if tage <= 14:
        return "WARNUNG"
    return "OK"


def get_frist_status(frist_bis: date, status: str) -> str:
    if status in ("VERWENDET", "ZURUECKGEZAHLT"):
        return "OK"
    today = date.today()
    if status == "ABGELAUFEN" or frist_bis < today:
        return "ABGELAUFEN"
    tage = (frist_bis - today).days
    if tage <= 7:
        return "KRITISCH"
    if tage <= 14:
        return "WARNING"
    return "OK"


def get_tage_verbleibend(frist_bis: date) -> int:
    return (frist_bis - date.today()).days


def _fmt_eur0(n: float) -> str:
    s = f"{round(n):,}".replace(",", ".")
    return f"{s} €"


class FristenService:
    def __init__(self, db: Session):
        self.db = db

    def load_fristen(self, org_id: str, days_ahead: int = 90) -> list[dict[str, Any]]:
        today = date.today()
        ende = date.fromordinal(today.toordinal() + days_ahead)
        items: list[dict[str, Any]] = []

        mittelabrufe = (
            self.db.execute(
                select(Mittelabruf)
                .where(
                    Mittelabruf.org_id == org_id,
                    Mittelabruf.status.notin_(["VERWENDET", "ZURUECKGEZAHLT"]),
                    Mittelabruf.frist_bis <= ende,
                )
                .options(selectinload(Mittelabruf.funding_measure))
            )
            .scalars()
            .all()
        )
        for m in mittelabrufe:
            tage = days_until(m.frist_bis)
            items.append(
                {
                    "id": m.id,
                    "typ": "MITTELABRUF",
                    "bezeichnung": f"Mittelabruf — {m.funding_measure.name}",
                    "detail": f"Betrag {_fmt_eur0(float(m.betrag))}",
                    "frist": m.frist_bis.isoformat(),
                    "tage_verbleibend": tage,
                    "dringlichkeit": dringlichkeit(tage),
                    "entity_link": f"/dashboard/mittelabrufe/{m.id}",
                }
            )

        nachweise = (
            self.db.execute(
                select(VerwNachweis)
                .where(
                    VerwNachweis.org_id == org_id,
                    VerwNachweis.status.notin_(["ANERKANNT", "ABGELEHNT"]),
                    VerwNachweis.frist <= ende,
                )
                .options(selectinload(VerwNachweis.funding_measure))
            )
            .scalars()
            .all()
        )
        for n in nachweise:
            tage = days_until(n.frist)
            items.append(
                {
                    "id": n.id,
                    "typ": "VERWENDUNGSNACHWEIS",
                    "bezeichnung": f"{TYP_LABEL[_ev(n.typ)]} — {n.funding_measure.name}",
                    "detail": None,
                    "frist": n.frist.isoformat(),
                    "tage_verbleibend": tage,
                    "dringlichkeit": dringlichkeit(tage),
                    "entity_link": f"/dashboard/verwendungsnachweise/{n.id}",
                }
            )

        massnahmen = (
            self.db.execute(
                select(FundingMeasure).where(
                    FundingMeasure.org_id == org_id,
                    FundingMeasure.status == "AKTIV",
                    FundingMeasure.laufzeit_bis <= ende,
                )
            )
            .scalars()
            .all()
        )
        for m in massnahmen:
            tage = days_until(m.laufzeit_bis)
            items.append(
                {
                    "id": m.id,
                    "typ": "MASSNAHME_LAUFZEIT",
                    "bezeichnung": f"Massnahme läuft ab — {m.name}",
                    "detail": None,
                    "frist": m.laufzeit_bis.isoformat(),
                    "tage_verbleibend": tage,
                    "dringlichkeit": dringlichkeit(tage),
                    "entity_link": f"/dashboard/foerdermassnahmen/{m.id}",
                }
            )

        haushaltsjahre = (
            self.db.execute(
                select(FiscalYear).where(
                    FiscalYear.org_id == org_id,
                    FiscalYear.status == "OFFEN",
                    FiscalYear.ende <= ende,
                )
            )
            .scalars()
            .all()
        )
        for fy in haushaltsjahre:
            tage = days_until(fy.ende)
            items.append(
                {
                    "id": fy.id,
                    "typ": "HAUSHALTSJAHR",
                    "bezeichnung": f"Haushaltsjahr {fy.jahr} endet",
                    "detail": None,
                    "frist": fy.ende.isoformat(),
                    "tage_verbleibend": tage,
                    "dringlichkeit": dringlichkeit(tage),
                    "entity_link": f"/dashboard/haushaltsjahre/{fy.id}",
                }
            )

        items.sort(key=lambda x: x["tage_verbleibend"])
        return items

    def count_kritische_fristen(self, org_id: str) -> int:
        today = date.today()
        in7 = date.fromordinal(today.toordinal() + 7)
        a = self.db.execute(
            select(func.count(Mittelabruf.id)).where(
                Mittelabruf.org_id == org_id,
                Mittelabruf.status.notin_(["VERWENDET", "ZURUECKGEZAHLT"]),
                Mittelabruf.frist_bis <= in7,
            )
        ).scalar_one()
        b = self.db.execute(
            select(func.count(VerwNachweis.id)).where(
                VerwNachweis.org_id == org_id,
                VerwNachweis.status.notin_(["ANERKANNT", "ABGELEHNT"]),
                VerwNachweis.frist <= in7,
            )
        ).scalar_one()
        c = self.db.execute(
            select(func.count(FundingMeasure.id)).where(
                FundingMeasure.org_id == org_id,
                FundingMeasure.status == "AKTIV",
                FundingMeasure.laufzeit_bis <= in7,
            )
        ).scalar_one()
        d = self.db.execute(
            select(func.count(FiscalYear.id)).where(
                FiscalYear.org_id == org_id,
                FiscalYear.status == "OFFEN",
                FiscalYear.ende <= in7,
            )
        ).scalar_one()
        return a + b + c + d
