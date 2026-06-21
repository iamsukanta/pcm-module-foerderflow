"""Dashboard cockpit aggregation — port of app/dashboard/page.tsx server queries
+ GettingStartedWidget + FehlbedarfWidget. One payload for the whole landing page.

Money fields serialize as NUMBERS (the page uses Intl.NumberFormat on numbers).
days_left computed server-side (ceil of date diff)."""

from __future__ import annotations

import math
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.finanzplan import VerwNachweis
from app.models.funding import FundingMeasure
from app.models.master import CostCenter, FiscalYear
from app.models.mittelabruf import Mittelabruf
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.fehlbedarf_compliance import get_fehlbedarf_status


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _days_left(d: date, today: date) -> int:
    return math.ceil((d - today).days)


def _count(db: Session, model, **filters) -> int:
    stmt = select(func.count()).select_from(model)
    for k, v in filters.items():
        stmt = stmt.where(getattr(model, k) == v)
    return db.execute(stmt).scalar_one()


def load_cockpit(db: Session, org_id: str) -> dict[str, Any]:
    today = date.today()
    in14 = today + timedelta(days=14)
    in90 = today + timedelta(days=90)

    aktives_fy = db.execute(
        select(FiscalYear)
        .where(FiscalYear.org_id == org_id, FiscalYear.status == "OFFEN")
        .order_by(FiscalYear.jahr.desc())
    ).scalars().first()
    if aktives_fy:
        ytd_start = aktives_fy.beginn
        ytd_end = aktives_fy.ende
        ytd_label = f"GJ {aktives_fy.jahr}"
    else:
        ytd_start = date(today.year, 1, 1)
        ytd_end = date(today.year + 1, 1, 1)
        ytd_label = str(today.year)

    # Onboarding counts
    onboarding = {
        "fiscal_years": _count(db, FiscalYear, org_id=org_id),
        "cost_centers": _count(db, CostCenter, org_id=org_id),
        "funding_measures": _count(db, FundingMeasure, org_id=org_id),
        "transactions": _count(db, Transaction, org_id=org_id),
    }

    offene_transaktionen = db.execute(
        select(func.count())
        .select_from(Transaction)
        .where(Transaction.org_id == org_id, Transaction.status == "IMPORTIERT")
    ).scalar_one()

    # Aktive measures → Gesamtvolumen
    aktive = db.execute(
        select(FundingMeasure.id, FundingMeasure.budget_gesamt).where(
            FundingMeasure.org_id == org_id, FundingMeasure.status == "AKTIV"
        )
    ).all()
    gesamtvolumen = float(sum((b for _, b in aktive), Decimal(0)))
    aktive_count = len(aktive)

    # Top 5 measures by laufzeit_bis
    measures_top_rows = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.org_id == org_id, FundingMeasure.status == "AKTIV")
        .order_by(FundingMeasure.laufzeit_bis.asc())
        .limit(5)
        .options(selectinload(FundingMeasure.finanzplan_positionen))
    ).scalars().all()

    top_ids = [m.id for m in measures_top_rows]
    spend_by_measure: dict[str, float] = {}
    if top_ids:
        rows = db.execute(
            select(
                FundAllocation.funding_measure_id,
                func.coalesce(func.sum(FundAllocation.betrag_foerderung), 0),
            )
            .where(FundAllocation.org_id == org_id, FundAllocation.funding_measure_id.in_(top_ids))
            .group_by(FundAllocation.funding_measure_id)
        ).all()
        spend_by_measure = {mid: float(total) for mid, total in rows}

    measures_top = []
    for m in measures_top_rows:
        if m.finanzplan_positionen:
            budget_bewilligt = float(
                sum((p.betrag_bewilligt for p in m.finanzplan_positionen), Decimal(0))
            )
        else:
            budget_bewilligt = float(m.budget_gesamt) * float(m.foerderquote) / 100
        betrag_ist = spend_by_measure.get(m.id, 0.0)
        percent = min(100.0, (betrag_ist / budget_bewilligt) * 100) if budget_bewilligt > 0 else 0.0
        measures_top.append(
            {
                "id": m.id,
                "name": m.name,
                "budget_bewilligt": budget_bewilligt,
                "betrag_ist": betrag_ist,
                "percent": percent,
                "days_left": _days_left(m.laufzeit_bis, today),
            }
        )

    # Dringende Mittelabrufe (Frist <= 14 Tage)
    abrufe = db.execute(
        select(Mittelabruf)
        .where(
            Mittelabruf.org_id == org_id,
            Mittelabruf.frist_bis <= in14,
            Mittelabruf.status.notin_(["VERWENDET", "ZURUECKGEZAHLT"]),
        )
        .order_by(Mittelabruf.frist_bis.asc())
        .limit(5)
        .options(selectinload(Mittelabruf.funding_measure))
    ).scalars().all()
    dringende_abrufe = [
        {
            "id": a.id,
            "betrag": float(a.betrag),
            "frist_bis": a.frist_bis.isoformat(),
            "measure_name": a.funding_measure.name if a.funding_measure else "",
            "days_left": _days_left(a.frist_bis, today),
        }
        for a in abrufe
    ]

    # Ablaufende Massnahmen (laufzeit_bis in [today, in90])
    ablaufend = db.execute(
        select(FundingMeasure)
        .where(
            FundingMeasure.org_id == org_id,
            FundingMeasure.status == "AKTIV",
            FundingMeasure.laufzeit_bis >= today,
            FundingMeasure.laufzeit_bis <= in90,
        )
        .order_by(FundingMeasure.laufzeit_bis.asc())
        .limit(5)
    ).scalars().all()
    ablaufende_massnahmen = [
        {
            "id": m.id,
            "name": m.name,
            "laufzeit_bis": m.laufzeit_bis.isoformat(),
            "days_left": _days_left(m.laufzeit_bis, today),
        }
        for m in ablaufend
    ]

    # Dringende Verwendungsnachweise (Frist <= 14 Tage, offen)
    nachweise = db.execute(
        select(VerwNachweis)
        .where(
            VerwNachweis.org_id == org_id,
            VerwNachweis.status.notin_(["ANERKANNT", "ABGELEHNT"]),
            VerwNachweis.frist <= in14,
        )
        .order_by(VerwNachweis.frist.asc())
        .limit(5)
        .options(selectinload(VerwNachweis.funding_measure))
    ).scalars().all()
    dringende_nachweise = [
        {
            "id": n.id,
            "frist": n.frist.isoformat(),
            "typ": _ev(n.typ),
            "measure_name": n.funding_measure.name if n.funding_measure else "",
            "days_left": _days_left(n.frist, today),
        }
        for n in nachweise
    ]

    # YTD-Verbrauch + Eigenanteil
    ytd_row = db.execute(
        select(
            func.coalesce(func.sum(FundAllocation.betrag_foerderung), 0),
            func.coalesce(func.sum(FundAllocation.betrag_eigenanteil), 0),
        )
        .select_from(FundAllocation)
        .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
        .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
        .where(
            FundAllocation.org_id == org_id,
            Transaction.datum >= ytd_start,
            Transaction.datum < ytd_end,
        )
    ).one()
    verbraucht_ytd = float(ytd_row[0] or 0)
    eigenanteil_ytd = float(ytd_row[1] or 0)

    # Reserviert = Σ(betrag − betrag_verwendet) der ABGERUFEN-Mittelabrufe
    res_row = db.execute(
        select(
            func.coalesce(func.sum(Mittelabruf.betrag), 0),
            func.coalesce(func.sum(Mittelabruf.betrag_verwendet), 0),
        ).where(Mittelabruf.org_id == org_id, Mittelabruf.status == "ABGERUFEN")
    ).one()
    reserviert = max(0.0, float(res_row[0] or 0) - float(res_row[1] or 0))

    verbrauch_pct = (verbraucht_ytd / gesamtvolumen * 100) if gesamtvolumen > 0 else 0.0
    eigenanteil_quote = (
        (eigenanteil_ytd / (verbraucht_ytd + eigenanteil_ytd) * 100)
        if (verbraucht_ytd + eigenanteil_ytd) > 0
        else 0.0
    )

    # Fehlbedarf-Compliance widget
    candidates = db.execute(
        select(FundingMeasure)
        .where(
            FundingMeasure.org_id == org_id,
            FundingMeasure.status == "AKTIV",
            (
                (FundingMeasure.finanzierungsart == "FEHLBEDARF")
                | (
                    (FundingMeasure.finanzierungsart == "FESTBETRAG")
                    & (FundingMeasure.foerderquote == 100)
                )
            ),
        )
        .order_by(FundingMeasure.name.asc())
        .options(selectinload(FundingMeasure.funder))
    ).scalars().all()
    fehlbedarf = []
    for c in candidates:
        st = get_fehlbedarf_status(db, c.id, org_id)
        if st is None:
            continue
        fehlbedarf.append(
            {
                "id": c.id,
                "name": c.name,
                "funder_name": c.funder.name if c.funder else "",
                "status": st["status"],
                "zuwendung_hoechstbetrag": st["zuwendung_hoechstbetrag"],
                "fehlbedarf_zulaessig": st["fehlbedarf_zulaessig"],
                "zuwendung_abgerufen": st["zuwendung_abgerufen"],
                "verbleibend_abrufbar": st["verbleibend_abrufbar"],
                "nachricht": st.get("nachricht"),
            }
        )

    return {
        "onboarding": onboarding,
        "ytd_label": ytd_label,
        "kpi": {
            "gesamtvolumen": gesamtvolumen,
            "aktive_count": aktive_count,
            "verbraucht_ytd": verbraucht_ytd,
            "eigenanteil_ytd": eigenanteil_ytd,
            "reserviert": reserviert,
            "verbrauch_pct": verbrauch_pct,
            "eigenanteil_quote": eigenanteil_quote,
        },
        "offene_transaktionen": offene_transaktionen,
        "measures_top": measures_top,
        "dringende_abrufe": dringende_abrufe,
        "ablaufende_massnahmen": ablaufende_massnahmen,
        "dringende_nachweise": dringende_nachweise,
        "fehlbedarf": fehlbedarf,
    }
