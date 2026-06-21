"""Buchungsregeln (BookingRule) — port of app/api/protected/buchungsregeln/*.

CRUD (PUT = full replace incl. splits; PATCH = aktiv/prioritaet/name/measure),
preview (matched count + sample + total), suggest (infer from selection),
backfill (GET count / POST apply, MAX 20000). 100%-split rule, KB existence,
betrag-range validation. Money → string, dates → YYYY-MM-DD.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.booking_rule import BookingRule, BookingRuleSplit
from app.models.master import Kostenbereich
from app.models.transaction import Transaction
from app.services.booking_rules import (
    apply_rule_to_transaction,
    build_rule_match_conditions,
    load_rule_with_splits,
)
from app.services.rule_inference import infer_rule
from app.services.transaction_batch import resolve_batch_input
from app.utils.serialization import decimal_str as _dec

MAX_BACKFILL = 20000
DEFAULT_STATUS = ["IMPORTIERT", "KATEGORISIERT"]


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


def _d(v) -> str | None:
    return v.isoformat() if v else None


def _num(v: Any) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


def _to_date(v: Any) -> date | None:
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(str(v)[:10])
        except ValueError:
            return None


def _kb_brief(kb) -> dict[str, Any] | None:
    return None if kb is None else {"id": kb.id, "code": kb.code, "bezeichnung": kb.bezeichnung}


def _split(s: BookingRuleSplit) -> dict[str, Any]:
    cc = s.cost_center
    ak = s.allocation_key
    return {
        "id": s.id,
        "rule_id": s.rule_id,
        "cost_center_id": s.cost_center_id,
        "prozent": _dec(s.prozent),
        "allocation_key_id": s.allocation_key_id,
        "funding_measure_id": s.funding_measure_id,
        "allocation_prozent": _dec(s.allocation_prozent),
        "cost_center": {"id": cc.id, "name": cc.name, "code": cc.code} if cc else None,
        "allocation_key": {"id": ak.id, "name": ak.name} if ak else None,
    }


def _rule_scalars(r: BookingRule) -> dict[str, Any]:
    return {
        "id": r.id,
        "org_id": r.org_id,
        "name": r.name,
        "aktiv": r.aktiv,
        "prioritaet": r.prioritaet,
        "match_auftraggeber": r.match_auftraggeber,
        "match_auftraggeber_exact": r.match_auftraggeber_exact,
        "match_verwendungszweck": r.match_verwendungszweck,
        "match_kostenbereich_id": r.match_kostenbereich_id,
        "match_iban_partner": r.match_iban_partner,
        "match_betrag_min": _dec(r.match_betrag_min),
        "match_betrag_max": _dec(r.match_betrag_max),
        "match_datum_von": _d(r.match_datum_von),
        "match_datum_bis": _d(r.match_datum_bis),
        "set_kostenbereich_id": r.set_kostenbereich_id,
        "match_count": r.match_count,
        "confidence": r.confidence,
        "funding_measure_id": r.funding_measure_id,
        "created_at": _d(r.created_at),
        "updated_at": _d(r.updated_at),
    }


def _rule_full(r: BookingRule) -> dict[str, Any]:
    row = _rule_scalars(r)
    row["splits"] = [_split(s) for s in r.splits]
    row["funding_measure"] = (
        {"id": r.funding_measure.id, "name": r.funding_measure.name} if r.funding_measure else None
    )
    row["match_kostenbereich"] = _kb_brief(r.match_kostenbereich)
    row["set_kostenbereich"] = _kb_brief(r.set_kostenbereich)
    return row


class BuchungsregelService:
    def __init__(self, db: Session):
        self.db = db

    def _full_opts(self):
        return (
            selectinload(BookingRule.splits).selectinload(BookingRuleSplit.cost_center),
            selectinload(BookingRule.splits).selectinload(BookingRuleSplit.allocation_key),
            selectinload(BookingRule.funding_measure),
            selectinload(BookingRule.match_kostenbereich),
            selectinload(BookingRule.set_kostenbereich),
        )

    # ── list ──────────────────────────────────────────────────────────────────
    def list(self, org_id: str) -> list[dict[str, Any]]:
        rules = (
            self.db.execute(
                select(BookingRule)
                .where(BookingRule.org_id == org_id)
                .order_by(BookingRule.prioritaet.desc())
                .options(*self._full_opts())
            )
            .scalars()
            .all()
        )
        return [_rule_full(r) for r in rules]

    # ── validation helpers ──────────────────────────────────────────────────────
    def _validate_common(self, org_id: str, body: dict[str, Any]) -> tuple[float | None, float | None]:
        if not isinstance(body.get("name"), str) or not body["name"].strip():
            raise APIError(400, "VALIDATION_NAME", "Name ist erforderlich.")
        splits = body.get("splits")
        if not splits:
            raise APIError(400, "VALIDATION_SPLITS", "Mindestens eine Kostenstelle erforderlich.")
        summe = sum(float(s.get("prozent", 0)) for s in splits)
        if abs(summe - 100) > 0.01:
            raise APIError(
                400, "SPLIT_SUM_NOT_100", f"Prozent-Summe muss 100% ergeben. Aktuell: {summe:.1f}%"
            )
        for kb_id in (body.get("match_kostenbereich_id"), body.get("set_kostenbereich_id")):
            if not kb_id:
                continue
            if self.db.execute(
                select(Kostenbereich.id).where(Kostenbereich.id == kb_id)
            ).scalar_one_or_none() is None:
                raise APIError(400, "INVALID_KOSTENBEREICH", "Unbekannter Kostenbereich.")
        bmin = _num(body.get("match_betrag_min"))
        bmax = _num(body.get("match_betrag_max"))
        if bmin is not None and (bmin != bmin or bmin < 0):
            raise APIError(
                422, "VALIDATION_BETRAG_MIN", "match_betrag_min muss eine nicht-negative Zahl sein."
            )
        if bmax is not None and (bmax != bmax or bmax < 0):
            raise APIError(
                422, "VALIDATION_BETRAG_MAX", "match_betrag_max muss eine nicht-negative Zahl sein."
            )
        if bmin is not None and bmax is not None and bmin > bmax:
            raise APIError(
                422,
                "VALIDATION_BETRAG_RANGE",
                "match_betrag_min darf nicht größer als match_betrag_max sein.",
            )
        return bmin, bmax

    def _split_rows(self, body: dict[str, Any]) -> list[BookingRuleSplit]:
        rows = []
        for s in body["splits"]:
            ap = s.get("allocation_prozent")
            rows.append(
                BookingRuleSplit(
                    cost_center_id=s["cost_center_id"],
                    prozent=float(s["prozent"]),
                    allocation_key_id=s.get("allocation_key_id"),
                    funding_measure_id=s.get("funding_measure_id"),
                    allocation_prozent=(float(ap) if ap not in (None, "") else None),
                )
            )
        return rows

    # ── create ──────────────────────────────────────────────────────────────────
    def create(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        bmin, bmax = self._validate_common(org_id, body)
        rule = BookingRule(
            org_id=org_id,
            name=body["name"].strip(),
            match_auftraggeber=(body.get("match_auftraggeber") or "").strip() or None,
            match_auftraggeber_exact=body.get("match_auftraggeber_exact") is True,
            match_verwendungszweck=(body.get("match_verwendungszweck") or "").strip() or None,
            match_kostenbereich_id=body.get("match_kostenbereich_id") or None,
            match_iban_partner=(body.get("match_iban_partner") or "").strip() or None,
            match_betrag_min=bmin,
            match_betrag_max=bmax,
            match_datum_von=_to_date(body.get("match_datum_von")),
            match_datum_bis=_to_date(body.get("match_datum_bis")),
            set_kostenbereich_id=body.get("set_kostenbereich_id") or None,
            prioritaet=body.get("prioritaet") if body.get("prioritaet") is not None else 0,
            funding_measure_id=body.get("funding_measure_id"),
        )
        rule.splits = self._split_rows(body)
        self.db.add(rule)
        self.db.commit()
        rule = self.db.execute(
            select(BookingRule).where(BookingRule.id == rule.id).options(*self._full_opts())
        ).scalar_one()
        return _rule_full(rule)

    # ── PUT (full replace) ───────────────────────────────────────────────────────
    def replace(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        existing = self.db.execute(
            select(BookingRule).where(BookingRule.id == id_, BookingRule.org_id == org_id)
        ).scalar_one_or_none()
        if existing is None:
            raise APIError(404, "NOT_FOUND", "Nicht gefunden.")
        bmin, bmax = self._validate_common(org_id, body)
        self.db.query(BookingRuleSplit).filter(BookingRuleSplit.rule_id == id_).delete(
            synchronize_session=False
        )
        existing.name = body["name"].strip()
        existing.match_auftraggeber = (body.get("match_auftraggeber") or "").strip() or None
        if "match_auftraggeber_exact" in body:
            existing.match_auftraggeber_exact = body["match_auftraggeber_exact"] is True
        existing.match_verwendungszweck = (body.get("match_verwendungszweck") or "").strip() or None
        existing.match_kostenbereich_id = body.get("match_kostenbereich_id") or None
        if "match_iban_partner" in body:
            existing.match_iban_partner = (body.get("match_iban_partner") or "").strip() or None
        if "match_betrag_min" in body:
            existing.match_betrag_min = bmin
        if "match_betrag_max" in body:
            existing.match_betrag_max = bmax
        if "match_datum_von" in body:
            existing.match_datum_von = _to_date(body.get("match_datum_von"))
        if "match_datum_bis" in body:
            existing.match_datum_bis = _to_date(body.get("match_datum_bis"))
        existing.set_kostenbereich_id = body.get("set_kostenbereich_id") or None
        existing.prioritaet = body.get("prioritaet") if body.get("prioritaet") is not None else 0
        existing.funding_measure_id = body.get("funding_measure_id")
        for s in self._split_rows(body):
            s.rule_id = id_
            self.db.add(s)
        self.db.commit()
        rule = self.db.execute(
            select(BookingRule).where(BookingRule.id == id_).options(*self._full_opts())
        ).scalar_one()
        return _rule_full(rule)

    # ── PATCH ─────────────────────────────────────────────────────────────────────
    def patch(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        rule = self.db.execute(
            select(BookingRule).where(BookingRule.id == id_, BookingRule.org_id == org_id)
        ).scalar_one_or_none()
        if rule is None:
            raise APIError(404, "NOT_FOUND", "Nicht gefunden.")
        if "aktiv" in body:
            rule.aktiv = body["aktiv"]
        if "prioritaet" in body and body["prioritaet"] is not None:
            rule.prioritaet = body["prioritaet"]
        if body.get("name"):
            rule.name = body["name"]
        if "funding_measure_id" in body:
            rule.funding_measure_id = body.get("funding_measure_id")
        self.db.commit()
        self.db.refresh(rule)
        return _rule_scalars(rule)

    def delete(self, org_id: str, id_: str) -> dict[str, Any]:
        rule = self.db.execute(
            select(BookingRule).where(BookingRule.id == id_, BookingRule.org_id == org_id)
        ).scalar_one_or_none()
        if rule is None:
            raise APIError(404, "NOT_FOUND", "Nicht gefunden.")
        self.db.delete(rule)
        self.db.commit()
        return {"message": "Regel gelöscht."}

    # ── preview ─────────────────────────────────────────────────────────────────
    def preview(self, org_id: str, match: dict[str, Any]) -> dict[str, Any]:
        has_any = any(
            [
                match.get("match_auftraggeber"),
                match.get("match_verwendungszweck"),
                match.get("match_kostenbereich_id"),
                match.get("match_iban_partner"),
                match.get("match_betrag_min") is not None,
                match.get("match_betrag_max") is not None,
                match.get("match_datum_von"),
                match.get("match_datum_bis"),
            ]
        )
        if not has_any:
            raise APIError(
                422,
                "NO_CONDITIONS",
                "Mindestens eine Match-Bedingung (Auftraggeber, Verwendungszweck oder "
                "Kostenbereich) ist erforderlich.",
            )
        conds = build_rule_match_conditions(org_id, match)
        matched_count = self.db.execute(
            select(func.count(Transaction.id)).where(and_(*conds))
        ).scalar_one()
        sample = (
            self.db.execute(
                select(Transaction)
                .where(and_(*conds))
                .order_by(Transaction.datum.desc())
                .limit(5)
                .options(selectinload(Transaction.kostenbereich))
            )
            .scalars()
            .all()
        )
        total = self.db.execute(
            select(func.coalesce(func.sum(Transaction.betrag), 0)).where(and_(*conds))
        ).scalar_one()
        return {
            "matched_count": matched_count,
            "sample": [
                {
                    "id": s.id,
                    "datum": _d(s.datum),
                    "betrag": _dec(s.betrag),
                    "auftraggeber": s.auftraggeber,
                    "verwendungszweck": s.verwendungszweck,
                    "kostenbereich": (
                        {"bezeichnung": s.kostenbereich.bezeichnung} if s.kostenbereich else None
                    ),
                }
                for s in sample
            ],
            "total_betrag": _dec(total) or "0",
        }

    # ── suggest ─────────────────────────────────────────────────────────────────
    def suggest(self, org_id: str, body: dict[str, Any]) -> dict[str, Any]:
        ids = resolve_batch_input(self.db, org_id, body)
        sample_ids = ids[:200]
        txs = (
            self.db.execute(
                select(Transaction.auftraggeber, Transaction.kostenbereich_id).where(
                    Transaction.id.in_(sample_ids), Transaction.org_id == org_id
                )
            )
            .all()
        )
        if not txs:
            raise APIError(422, "NO_TRANSACTIONS", "Keine Transaktionen in der Auswahl.")
        search_hint = (body.get("filter") or {}).get("search") if isinstance(body.get("filter"), dict) else None
        suggestion = infer_rule(
            [{"auftraggeber": a, "kostenbereich_id": k} for a, k in txs], search_hint
        )
        return {
            "suggestion": suggestion,
            "basis_count": len(txs),
            "total_in_selection": len(ids),
        }

    # ── backfill ─────────────────────────────────────────────────────────────────
    def _backfill_conditions(self, org_id: str, rule: BookingRule, include_assigned: bool):
        conds = build_rule_match_conditions(org_id, _rule_scalars(rule))
        status_filter = (
            [*DEFAULT_STATUS, "ZUGEORDNET", "ABGESCHLOSSEN"] if include_assigned else DEFAULT_STATUS
        )
        conds.append(Transaction.status.in_(status_filter))
        return conds

    def backfill_count(self, org_id: str, id_: str, include_assigned: bool) -> dict[str, Any]:
        rule = load_rule_with_splits(self.db, org_id, id_, active_only=True)
        if rule is None:
            raise APIError(404, "RULE_NOT_FOUND", "Regel nicht gefunden oder inaktiv.")
        conds = self._backfill_conditions(org_id, rule, include_assigned)
        count = self.db.execute(select(func.count(Transaction.id)).where(and_(*conds))).scalar_one()
        return {"count": count, "include_assigned": include_assigned}

    def backfill_apply(self, org_id: str, id_: str, include_assigned: bool) -> dict[str, Any]:
        rule = load_rule_with_splits(self.db, org_id, id_, active_only=True)
        if rule is None:
            raise APIError(404, "RULE_NOT_FOUND", "Regel nicht gefunden oder inaktiv.")
        conds = self._backfill_conditions(org_id, rule, include_assigned)
        total = self.db.execute(select(func.count(Transaction.id)).where(and_(*conds))).scalar_one()
        if total > MAX_BACKFILL:
            raise APIError(
                422,
                "BACKFILL_TOO_LARGE",
                f"Regel würde {total} Transaktionen verarbeiten — Maximum {MAX_BACKFILL}. "
                "Bitte Regel präzisieren.",
            )
        rows = self.db.execute(
            select(Transaction.id, Transaction.betrag).where(and_(*conds)).limit(MAX_BACKFILL)
        ).all()
        matched = 0
        skipped = 0
        for tx_id, betrag in rows:
            try:
                apply_rule_to_transaction(self.db, org_id, tx_id, abs(float(betrag)), rule)
                matched += 1
            except Exception:  # noqa: BLE001
                self.db.rollback()
                skipped += 1
        msg = f"{matched} Transaktion(en) per Backfill zugeordnet"
        if skipped:
            msg += f", {skipped} übersprungen"
        return {"data": {"matched": matched, "skipped": skipped, "total": total}, "message": msg + "."}
