"""Verwendungsnachweise — port of app/api/protected/verwendungsnachweise/* +
foerdermassnahmen/[id]/verwendungsnachweis/preview.

CRUD (status-transition matrix, snapshot immutability after EINGEREICHT, delete
only OFFEN), einreichen (build snapshot + EINGEREICHT, audit), preview (ampel +
soll-ist + unmapped-ist + belege coverage). Frist auto-fill from FunderNachweisFrist.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, exists, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.finanzplan import (
    FinanzplanPosition,
    FinanzplanPositionKostenbereich,
    VerwNachweis,
)
from app.models.funding import FundingMeasure
from app.models.master import FiscalYear
from app.models.mittelabruf import Mittelabruf
from app.models.transaction import FundAllocation, Transaction, TransactionBeleg, TransactionSplit
from app.models.transaction import BankAccount  # noqa: F401  (ensure mapper load)
from app.models.master import CostCenter
from app.services.ampel import berechne_ampel
from app.services.audit_service import log_audit
from app.services.finanzplan_ist import aggregate_ist_by_finanzplan_position
from app.services.funder_frist import berechne_nachweis_frist
from app.services.nachweis.aggregator import build_nachweis_data

VALID_TYPEN = ("ZWISCHENNACHWEIS", "VERWENDUNGSNACHWEIS", "SACHBERICHT_ONLY")
VALID_TRANSITIONS = {
    "OFFEN": ["IN_BEARBEITUNG"],
    "IN_BEARBEITUNG": ["OFFEN", "EINGEREICHT"],
    "EINGEREICHT": ["ANERKANNT", "ABGELEHNT"],
    "ANERKANNT": [],
    "ABGELEHNT": ["IN_BEARBEITUNG"],
}


def _ev(v):
    return v.value if hasattr(v, "value") else v


def _d(v):
    return v.isoformat() if v else None


def _parse_date(v: Any) -> date | None:
    if not isinstance(v, str) or not v:
        return None
    try:
        return datetime.fromisoformat(v.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None


def _nachweis(n: VerwNachweis, *, with_rel: bool = False) -> dict[str, Any]:
    row = {
        "id": n.id,
        "org_id": n.org_id,
        "funding_measure_id": n.funding_measure_id,
        "fiscal_year_id": n.fiscal_year_id,
        "zeitraum_von": _d(n.zeitraum_von),
        "zeitraum_bis": _d(n.zeitraum_bis),
        "frist": _d(n.frist),
        "typ": _ev(n.typ),
        "status": _ev(n.status),
        "snapshot_json": n.snapshot_json,
        "notiz": n.notiz,
        "eingereicht_am": _d(n.eingereicht_am),
        "eingereicht_von": n.eingereicht_von,
        "created_at": _d(n.created_at),
        "updated_at": _d(n.updated_at),
    }
    if with_rel:
        row["funding_measure"] = (
            {"name": n.funding_measure.name, "funder_id": n.funding_measure.funder_id}
            if n.funding_measure
            else None
        )
        row["fiscal_year"] = (
            {"jahr": n.fiscal_year.jahr, "status": _ev(n.fiscal_year.status)}
            if n.fiscal_year
            else None
        )
    return row


class VerwendungsnachweisService:
    def __init__(self, db: Session):
        self.db = db

    def list(self, org_id: str, funding_measure_id: str | None, status: str | None) -> list[dict[str, Any]]:
        conds = [VerwNachweis.org_id == org_id]
        if funding_measure_id:
            conds.append(VerwNachweis.funding_measure_id == funding_measure_id)
        if status:
            conds.append(VerwNachweis.status == status)
        rows = (
            self.db.execute(
                select(VerwNachweis)
                .where(*conds)
                .order_by(VerwNachweis.frist.asc())
                .options(
                    selectinload(VerwNachweis.funding_measure),
                    selectinload(VerwNachweis.fiscal_year),
                )
            )
            .scalars()
            .all()
        )
        out = []
        for n in rows:
            d = _nachweis(n)
            d["funding_measure"] = {"name": n.funding_measure.name} if n.funding_measure else None
            d["fiscal_year"] = {"jahr": n.fiscal_year.jahr} if n.fiscal_year else None
            out.append(d)
        return out

    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        n = self.db.execute(
            select(VerwNachweis)
            .where(VerwNachweis.id == id_, VerwNachweis.org_id == org_id)
            .options(
                selectinload(VerwNachweis.funding_measure),
                selectinload(VerwNachweis.fiscal_year),
            )
        ).scalar_one_or_none()
        if n is None:
            raise APIError(404, "NOT_FOUND", "Verwendungsnachweis nicht gefunden.")
        return _nachweis(n, with_rel=True)

    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        fmid = body.get("funding_measure_id")
        if not isinstance(fmid, str) or not fmid:
            raise APIError(422, "VALIDATION_MEASURE", "funding_measure_id ist erforderlich.")
        fyid = body.get("fiscal_year_id")
        if not isinstance(fyid, str) or not fyid:
            raise APIError(422, "VALIDATION_FISCAL_YEAR", "fiscal_year_id ist erforderlich.")

        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == fyid, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy is None:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        if _ev(fy.status) == "GESCHLOSSEN":
            raise APIError(
                409,
                "FISCAL_YEAR_CLOSED",
                f"Das Haushaltsjahr {fy.jahr} ist geschlossen. Kein neuer Verwendungsnachweis möglich.",
            )

        measure = self.db.execute(
            select(FundingMeasure).where(FundingMeasure.id == fmid, FundingMeasure.org_id == org_id)
        ).scalar_one_or_none()
        if measure is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")

        typ = body.get("typ")
        if typ not in VALID_TYPEN:
            raise APIError(422, "VALIDATION_TYP", f"Ungültiger Typ. Erlaubt: {', '.join(VALID_TYPEN)}.")

        zv = _parse_date(body.get("zeitraum_von"))
        if zv is None:
            raise APIError(422, "VALIDATION_ZEITRAUM_VON", "zeitraum_von muss ein gültiges Datum sein.")
        zb = _parse_date(body.get("zeitraum_bis"))
        if zb is None:
            raise APIError(422, "VALIDATION_ZEITRAUM_BIS", "zeitraum_bis muss ein gültiges Datum sein.")

        frist_raw = body.get("frist")
        frist_date: date | None = None
        if isinstance(frist_raw, str) and _parse_date(frist_raw):
            frist_date = _parse_date(frist_raw)
        elif frist_raw in (None, ""):
            auto = berechne_nachweis_frist(
                self.db,
                org_id=org_id,
                funder_id=measure.funder_id,
                nachweis_typ=typ,
                bewilligungs_ende=measure.laufzeit_bis,
                durchfuehrungs_ende=measure.durchfuehrungs_bis,
                hhj_ende=fy.ende or measure.laufzeit_bis,
            )
            if auto:
                frist_date = auto.frist
        else:
            raise APIError(422, "VALIDATION_FRIST", "frist muss ein gültiges Datum sein.")

        if frist_date is None:
            raise APIError(
                422,
                "VALIDATION_FRIST_MISSING",
                "Keine Frist gesetzt und kein Default für diesen Fördergeber + Nachweis-Typ "
                "hinterlegt. Bitte Frist explizit angeben oder Standard im Fördergeber-Setup "
                "pflegen.",
            )

        notiz = body.get("notiz")
        n = VerwNachweis(
            org_id=org_id,
            funding_measure_id=fmid,
            fiscal_year_id=fyid,
            zeitraum_von=zv,
            zeitraum_bis=zb,
            frist=frist_date,
            typ=typ,
            notiz=notiz.strip() if isinstance(notiz, str) and notiz.strip() else None,
        )
        self.db.add(n)
        self.db.commit()
        self.db.refresh(n)
        return _nachweis(n)

    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        n = self.db.execute(
            select(VerwNachweis).where(VerwNachweis.id == id_, VerwNachweis.org_id == org_id)
        ).scalar_one_or_none()
        if n is None:
            raise APIError(404, "NOT_FOUND", "Verwendungsnachweis nicht gefunden.")
        cur = _ev(n.status)

        if "snapshot_json" in body and cur in ("EINGEREICHT", "ANERKANNT", "ABGELEHNT"):
            raise APIError(
                409,
                "SNAPSHOT_IMMUTABLE",
                "snapshot_json kann nach Einreichung nicht mehr geändert werden.",
            )

        status = body.get("status")
        if status is not None:
            allowed = VALID_TRANSITIONS.get(cur, [])
            if status not in allowed:
                raise APIError(
                    409,
                    "INVALID_STATUS_TRANSITION",
                    f"Ungültiger Statusübergang: {cur} → {status}. "
                    f"Erlaubt: {', '.join(allowed) or 'keine'}.",
                )
            if status == "IN_BEARBEITUNG":
                fy = self.db.execute(
                    select(FiscalYear).where(
                        FiscalYear.id == n.fiscal_year_id, FiscalYear.org_id == org_id
                    )
                ).scalar_one_or_none()
                if fy and _ev(fy.status) == "GESCHLOSSEN":
                    raise APIError(
                        409,
                        "FISCAL_YEAR_CLOSED",
                        "Das Haushaltsjahr ist geschlossen. Keine Statusänderung möglich.",
                    )
            n.status = status
        if "notiz" in body:
            notiz = body["notiz"]
            n.notiz = notiz.strip() if isinstance(notiz, str) and notiz.strip() else None
        if "frist" in body and isinstance(body["frist"], str):
            d = _parse_date(body["frist"])
            if d:
                n.frist = d
        self.db.commit()
        self.db.refresh(n)
        return _nachweis(n)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        n = self.db.execute(
            select(VerwNachweis).where(VerwNachweis.id == id_, VerwNachweis.org_id == org_id)
        ).scalar_one_or_none()
        if n is None:
            raise APIError(404, "NOT_FOUND", "Verwendungsnachweis nicht gefunden.")
        if _ev(n.status) != "OFFEN":
            raise APIError(
                409,
                "INVALID_STATUS",
                f"Löschen nur im Status OFFEN möglich (aktuell: {_ev(n.status)}).",
            )
        self.db.delete(n)
        self.db.commit()
        return {"message": "Verwendungsnachweis wurde gelöscht."}

    def einreichen(self, org_id: str, user_id: str | None, id_: str) -> dict[str, Any]:
        n = self.db.execute(
            select(VerwNachweis).where(VerwNachweis.id == id_, VerwNachweis.org_id == org_id)
        ).scalar_one_or_none()
        if n is None:
            raise APIError(404, "NOT_FOUND", "Verwendungsnachweis nicht gefunden.")
        cur = _ev(n.status)
        if cur not in ("OFFEN", "IN_BEARBEITUNG"):
            raise APIError(
                409,
                "INVALID_STATUS",
                f"Einreichen nur aus Status OFFEN oder IN_BEARBEITUNG möglich (aktuell: {cur}).",
            )
        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == n.fiscal_year_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy and _ev(fy.status) == "GESCHLOSSEN":
            raise APIError(409, "FISCAL_YEAR_CLOSED", f"Das Haushaltsjahr {fy.jahr} ist geschlossen.")
        try:
            snapshot = build_nachweis_data(self.db, n.funding_measure_id, n.fiscal_year_id, org_id)
        except Exception as e:  # noqa: BLE001
            raise APIError(  # noqa: B904
                500, "SNAPSHOT_BUILD_FAILED", str(e) or "Snapshot konnte nicht erstellt werden."
            )
        n.status = "EINGEREICHT"
        n.snapshot_json = snapshot
        n.eingereicht_am = datetime.now(timezone.utc)
        n.eingereicht_von = user_id
        self.db.commit()
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="VERWENDUNGSNACHWEIS_EINREICHEN",
            entitaet="VerwNachweis",
            entitaet_id=id_,
            vorher={"status": cur},
            nachher={"status": "EINGEREICHT", "eingereicht_am": _d(n.eingereicht_am)},
        )
        self.db.refresh(n)
        return _nachweis(n)

    # ── preview ────────────────────────────────────────────────────────────────
    def preview(self, org_id: str, measure_id: str) -> dict[str, Any]:
        measure = self.db.execute(
            select(FundingMeasure)
            .where(FundingMeasure.id == measure_id, FundingMeasure.org_id == org_id)
            .options(
                selectinload(FundingMeasure.funder),
                selectinload(FundingMeasure.finanzplan_positionen),
            )
        ).scalar_one_or_none()
        if measure is None:
            raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")

        def _sum_weighted(extra_conds) -> float:
            stmt = (
                select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
                .where(FundAllocation.funding_measure_id == measure_id, FundAllocation.org_id == org_id)
            )
            for c in extra_conds:
                stmt = stmt.where(c)
            return float(self.db.execute(stmt).scalar_one() or 0)

        gesamt_ist = _sum_weighted([])

        # unmapped: tx without KB or KB not in any non-pauschale bridge of this measure
        bridge_exists = exists().where(
            and_(
                FinanzplanPositionKostenbereich.kostenbereich_id == Transaction.kostenbereich_id,
                FinanzplanPositionKostenbereich.finanzplan_position_id == FinanzplanPosition.id,
                FinanzplanPosition.funding_measure_id == measure_id,
                FinanzplanPosition.ist_pauschale.is_(False),
            )
        )
        unmapped = float(
            self.db.execute(
                select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
                .select_from(FundAllocation)
                .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
                .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
                .where(
                    FundAllocation.funding_measure_id == measure_id,
                    FundAllocation.org_id == org_id,
                    (Transaction.kostenbereich_id.is_(None)) | (~bridge_exists),
                )
            ).scalar_one()
            or 0
        )

        ist_by_position = aggregate_ist_by_finanzplan_position(self.db, measure_id, org_id)
        positionen = []
        for pos in sorted(measure.finanzplan_positionen, key=lambda p: p.sort_order):
            bewilligt = float(pos.betrag_bewilligt)
            ist = ist_by_position.get(pos.id, 0.0)
            positionen.append(
                {
                    "kostenart": f"{pos.positionscode}: {pos.bezeichnung}",
                    "bewilligt": bewilligt,
                    "ist": ist,
                    "abweichung": ist - bewilligt,
                }
            )
        gesamt_bewilligt = sum(p["bewilligt"] for p in positionen)

        tx_count = int(
            self.db.execute(
                select(func.count(func.distinct(TransactionSplit.transaction_id)))
                .select_from(FundAllocation)
                .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
                .where(FundAllocation.funding_measure_id == measure_id, FundAllocation.org_id == org_id)
            ).scalar_one()
            or 0
        )
        belege_count = int(
            self.db.execute(
                select(func.count(func.distinct(TransactionBeleg.id)))
                .select_from(FundAllocation)
                .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
                .join(TransactionBeleg, TransactionBeleg.transaction_id == TransactionSplit.transaction_id)
                .where(
                    FundAllocation.funding_measure_id == measure_id,
                    FundAllocation.org_id == org_id,
                    TransactionBeleg.geloescht_am.is_(None),
                )
            ).scalar_one()
            or 0
        )
        tx_mit_beleg = int(
            self.db.execute(
                select(func.count(func.distinct(TransactionBeleg.transaction_id)))
                .select_from(FundAllocation)
                .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
                .join(TransactionBeleg, TransactionBeleg.transaction_id == TransactionSplit.transaction_id)
                .where(
                    FundAllocation.funding_measure_id == measure_id,
                    FundAllocation.org_id == org_id,
                    TransactionBeleg.geloescht_am.is_(None),
                )
            ).scalar_one()
            or 0
        )
        fehlende_belege = max(0, tx_count - tx_mit_beleg)

        mittelabrufe = (
            self.db.execute(
                select(Mittelabruf)
                .where(Mittelabruf.funding_measure_id == measure_id, Mittelabruf.org_id == org_id)
                .order_by(Mittelabruf.abruf_datum.desc())
            )
            .scalars()
            .all()
        )

        overhead_ist = _sum_weighted([])
        overhead_ist = float(
            self.db.execute(
                select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
                .select_from(FundAllocation)
                .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
                .join(CostCenter, CostCenter.id == TransactionSplit.cost_center_id)
                .where(
                    FundAllocation.funding_measure_id == measure_id,
                    FundAllocation.org_id == org_id,
                    CostCenter.typ == "OVERHEAD",
                )
            ).scalar_one()
            or 0
        )
        overhead_ist_prozent = (overhead_ist / gesamt_ist * 100) if gesamt_ist > 0 else 0
        betrag_bewilligt = float(measure.budget_gesamt)
        ampel = berechne_ampel(
            betrag_bewilligt=betrag_bewilligt,
            betrag_ist=gesamt_ist,
            laufzeit_von=measure.laufzeit_von,
            laufzeit_bis=measure.laufzeit_bis,
            overhead_limit_prozent=float(measure.overhead_limit_prozent) if measure.overhead_limit_prozent is not None else None,
            overhead_ist_prozent=overhead_ist_prozent,
        )

        return {
            "data": {
                "massnahme": {
                    "name": measure.name,
                    "foerdergeber": measure.funder.name,
                    "laufzeit_von": measure.laufzeit_von.isoformat(),
                    "laufzeit_bis": measure.laufzeit_bis.isoformat(),
                    "foerderquote_prozent": float(measure.foerderquote),
                },
                "budget": {
                    "positionen": positionen,
                    "gesamt_bewilligt": gesamt_bewilligt,
                    "gesamt_ist": gesamt_ist,
                    "gesamt_foerderfahig": gesamt_ist,
                    "unmapped_ist": unmapped,
                },
                "transaktionen_count": tx_count,
                "belege_count": belege_count,
                "fehlende_belege": fehlende_belege,
                "mittelabrufe": [
                    {"datum": m.abruf_datum.isoformat(), "betrag": float(m.betrag), "status": _ev(m.status)}
                    for m in mittelabrufe
                ],
                "ampel_status": ampel.status,
                "ampel_gruende": ampel.gruende,
            }
        }
