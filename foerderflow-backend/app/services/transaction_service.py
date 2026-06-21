"""Transaktionen core — port of app/api/protected/transaktionen (GET list, GET/PATCH [id]).

List supports the full cockpit filter set, pagination, and cockpit KPIs. Money
serializes as strings (Prisma Decimal), dates as YYYY-MM-DD.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.booking_rule import BookingRuleApplication
from app.models.master import Kostenbereich
from app.models.transaction import (
    FundAllocation,
    ImportBatch,
    Transaction,
    TransactionBeleg,
    TransactionSplit,
)
from app.services.transaction_filter import build_conditions, read_filter
from app.utils.serialization import decimal_str as _dec


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _d(v) -> str | None:
    return v.isoformat() if v else None


def _tx_scalars(t: Transaction) -> dict[str, Any]:
    return {
        "id": t.id,
        "org_id": t.org_id,
        "fiscal_year_id": t.fiscal_year_id,
        "import_batch_id": t.import_batch_id,
        "bank_account_id": t.bank_account_id,
        "datum": _d(t.datum),
        "valuta_datum": _d(t.valuta_datum),
        "betrag": _dec(t.betrag),
        "saldo_nach_buchung": _dec(t.saldo_nach_buchung),
        "typ": _ev(t.typ),
        "auftraggeber": t.auftraggeber,
        "iban_partner": t.iban_partner,
        "bic_partner": t.bic_partner,
        "verwendungszweck": t.verwendungszweck,
        "externe_referenz": t.externe_referenz,
        "glaeubiger_id": t.glaeubiger_id,
        "mandatsreferenz": t.mandatsreferenz,
        "buchungstext_typ": t.buchungstext_typ,
        "kostenbereich_id": t.kostenbereich_id,
        "notiz": t.notiz,
        "status": _ev(t.status),
        "duplikat_hash": t.duplikat_hash,
        "created_at": _d(t.created_at),
        "updated_at": _d(t.updated_at),
    }


def _kb_brief(kb: Kostenbereich | None) -> dict[str, Any] | None:
    return None if kb is None else {"id": kb.id, "code": kb.code, "bezeichnung": kb.bezeichnung}


def _fund_alloc(a: FundAllocation, measure_full: bool) -> dict[str, Any]:
    fm = a.funding_measure
    if measure_full:
        from app.services.foerdermassnahme_service import _scalars as _fm_scalars

        measure = _fm_scalars(fm)
    else:
        measure = {"id": fm.id, "name": fm.name}
    return {
        "id": a.id,
        "org_id": a.org_id,
        "transaction_split_id": a.transaction_split_id,
        "funding_measure_id": a.funding_measure_id,
        "prozent": _dec(a.prozent),
        "finanzplan_position_id": a.finanzplan_position_id,
        "betrag_foerderfahig": _dec(a.betrag_foerderfahig),
        "betrag_foerderung": _dec(a.betrag_foerderung),
        "betrag_eigenanteil": _dec(a.betrag_eigenanteil),
        "status": a.status,
        "notiz": a.notiz,
        "created_at": _d(a.created_at),
        "updated_at": _d(a.updated_at),
        "funding_measure": measure,
    }


def _split(s: TransactionSplit, cc_full: bool, measure_full: bool) -> dict[str, Any]:
    cc = s.cost_center
    cost_center = (
        {
            "id": cc.id,
            "org_id": cc.org_id,
            "name": cc.name,
            "code": cc.code,
            "typ": _ev(cc.typ),
            "ist_aktiv": cc.ist_aktiv,
            "parent_id": cc.parent_id,
            "created_at": _d(cc.created_at),
            "updated_at": _d(cc.updated_at),
        }
        if cc_full
        else {"id": cc.id, "name": cc.name, "code": cc.code}
    )
    return {
        "id": s.id,
        "org_id": s.org_id,
        "transaction_id": s.transaction_id,
        "cost_center_id": s.cost_center_id,
        "prozent": _dec(s.prozent),
        "betrag_anteil": _dec(s.betrag_anteil),
        "allocation_key_id": s.allocation_key_id,
        "created_at": _d(s.created_at),
        "updated_at": _d(s.updated_at),
        "cost_center": cost_center,
        "fund_allocations": [_fund_alloc(a, measure_full) for a in s.fund_allocations],
    }


def _beleg(b: TransactionBeleg) -> dict[str, Any]:
    return {
        "id": b.id,
        "org_id": b.org_id,
        "transaction_id": b.transaction_id,
        "datei_pfad": b.datei_pfad,
        "datei_name": b.datei_name,
        "datei_typ": b.datei_typ,
        "externe_referenz": b.externe_referenz,
        "retention_until": _d(b.retention_until),
        "geloescht_am": _d(b.geloescht_am),
        "created_at": _d(b.created_at),
    }


class TransactionService:
    def __init__(self, db: Session):
        self.db = db

    # ── list ──────────────────────────────────────────────────────────────────
    def list(self, org_id: str, params: dict[str, Any]) -> dict[str, Any]:
        f = read_filter(params)
        cockpit = params.get("cockpit") == "true"
        page = max(1, int(params.get("page") or 1))
        limit = min(100, max(1, int(params.get("limit") or 50)))
        skip = (page - 1) * limit
        conds = build_conditions(org_id, f)

        total = self.db.execute(
            select(func.count(Transaction.id)).where(and_(*conds))
        ).scalar_one()

        opts = [
            selectinload(Transaction.splits).selectinload(TransactionSplit.cost_center),
            selectinload(Transaction.belege),
            selectinload(Transaction.kostenbereich),
            selectinload(Transaction.rule_applications),
        ]
        if cockpit:
            opts.append(
                selectinload(Transaction.splits)
                .selectinload(TransactionSplit.fund_allocations)
                .selectinload(FundAllocation.funding_measure)
            )
        txs = (
            self.db.execute(
                select(Transaction)
                .where(and_(*conds))
                .order_by(Transaction.datum.desc())
                .offset(skip)
                .limit(limit)
                .options(*opts)
            )
            .scalars()
            .all()
        )

        data = []
        for t in txs:
            row = _tx_scalars(t)
            row["_count"] = {"splits": len(t.splits), "belege": len(t.belege)}
            row["kostenbereich"] = _kb_brief(t.kostenbereich)
            apps = sorted(t.rule_applications, key=lambda a: a.applied_at, reverse=True)
            row["rule_applications"] = [
                {
                    "confidence": a.confidence,
                    "rule_id": a.rule_id,
                    "applied_at": _d(a.applied_at),
                }
                for a in apps[:1]
            ]
            row["confidence"] = apps[0].confidence if apps else None
            if cockpit:
                massnahme = None
                for s in t.splits:
                    for a in s.fund_allocations:
                        if a.funding_measure:
                            massnahme = {"id": a.funding_measure.id, "name": a.funding_measure.name}
                            break
                    if massnahme:
                        break
                row["massnahme"] = massnahme
                row["splits"] = [
                    _split(s, cc_full=False, measure_full=False) for s in t.splits
                ]
            data.append(row)

        result: dict[str, Any] = {
            "data": data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "pages": (total + limit - 1) // limit if limit else 0,
            },
        }
        if cockpit:
            einnahmen = float(
                self.db.execute(
                    select(func.coalesce(func.sum(Transaction.betrag), 0)).where(
                        and_(*conds, Transaction.betrag > 0)
                    )
                ).scalar_one()
            )
            ausgaben = float(
                self.db.execute(
                    select(func.coalesce(func.sum(Transaction.betrag), 0)).where(
                        and_(*conds, Transaction.betrag < 0)
                    )
                ).scalar_one()
            )
            zugeordnet = self.db.execute(
                select(func.count(Transaction.id)).where(
                    and_(*conds, Transaction.status.in_(["ZUGEORDNET", "ABGESCHLOSSEN"]))
                )
            ).scalar_one()
            result["kpis"] = {
                "einnahmen": einnahmen,
                "ausgaben": ausgaben,
                "cashflow": einnahmen + ausgaben,
                "total": total,
                "zugeordnet": zugeordnet,
                "fortschritt": round(zugeordnet / total * 100) if total > 0 else 0,
            }
        return result

    # ── get ───────────────────────────────────────────────────────────────────
    def get(self, org_id: str, id_: str) -> dict[str, Any]:
        t = self.db.execute(
            select(Transaction)
            .where(Transaction.id == id_, Transaction.org_id == org_id)
            .options(
                selectinload(Transaction.kostenbereich),
                selectinload(Transaction.splits).selectinload(TransactionSplit.cost_center),
                selectinload(Transaction.splits)
                .selectinload(TransactionSplit.fund_allocations)
                .selectinload(FundAllocation.funding_measure),
                selectinload(Transaction.belege),
                selectinload(Transaction.import_batch),
                selectinload(Transaction.rule_applications).selectinload(
                    BookingRuleApplication.rule
                ),
            )
        ).scalar_one_or_none()
        if t is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden")
        row = _tx_scalars(t)
        row["kostenbereich"] = _kb_brief(t.kostenbereich)
        row["splits"] = [_split(s, cc_full=True, measure_full=True) for s in t.splits]
        row["belege"] = [_beleg(b) for b in t.belege if b.geloescht_am is None]
        ib = t.import_batch
        row["import_batch"] = (
            None
            if ib is None
            else {
                "id": ib.id,
                "org_id": ib.org_id,
                "fiscal_year_id": ib.fiscal_year_id,
                "format": _ev(ib.format),
                "csv_import_profile_id": ib.csv_import_profile_id,
                "dateiname": ib.dateiname,
                "anzahl_importiert": ib.anzahl_importiert,
                "anzahl_duplikate": ib.anzahl_duplikate,
                "anzahl_fehler": ib.anzahl_fehler,
                "import_log": ib.import_log,
                "importiert_von": ib.importiert_von,
                "created_at": _d(ib.created_at),
            }
        )
        apps = sorted(t.rule_applications, key=lambda a: a.applied_at, reverse=True)
        row["rule_applications"] = [
            {
                "id": a.id,
                "org_id": a.org_id,
                "transaction_id": a.transaction_id,
                "rule_id": a.rule_id,
                "applied_at": _d(a.applied_at),
                "applied_by": a.applied_by,
                "confidence": a.confidence,
                "rule": (
                    {"id": a.rule.id, "name": a.rule.name, "confidence": a.rule.confidence}
                    if a.rule
                    else None
                ),
            }
            for a in apps[:1]
        ]
        return row

    # ── patch (manual edit) ────────────────────────────────────────────────────
    def update(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        t = self.db.execute(
            select(Transaction).where(Transaction.id == id_, Transaction.org_id == org_id)
        ).scalar_one_or_none()
        if t is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden")

        if "kostenbereich_id" in body and body["kostenbereich_id"] is not None:
            exists_kb = self.db.execute(
                select(Kostenbereich.id).where(Kostenbereich.id == body["kostenbereich_id"])
            ).scalar_one_or_none()
            if exists_kb is None:
                raise APIError(400, "INVALID_KOSTENBEREICH", "Unbekannter Kostenbereich")
            t.kostenbereich_id = body["kostenbereich_id"]
        elif "kostenbereich_id" in body:
            t.kostenbereich_id = None
        if "notiz" in body:
            t.notiz = body["notiz"]
        if "auftraggeber" in body:
            t.auftraggeber = body["auftraggeber"]
        self.db.commit()
        t = self.db.execute(
            select(Transaction)
            .where(Transaction.id == id_)
            .options(selectinload(Transaction.kostenbereich))
        ).scalar_one()
        row = _tx_scalars(t)
        row["kostenbereich"] = _kb_brief(t.kostenbereich)
        return row
