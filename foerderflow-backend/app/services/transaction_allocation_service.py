"""Transaction splits + Förderzuordnung (FundAllocation) — port of
app/api/protected/transaktionen/[id]/{splits,fund-allocation}.

The financial heart: 100%-split rule with cent-exact rounding correction, the
full fund-allocation validation chain (fiscal-year-open, split/measure ownership,
Doppelfinanzierung, Förderfähigkeit, Overhead-Limit, Bridge position decision,
Position-Überziehung) using the canonical allocation→position resolver, and the
balancing-invariant amount calc.

NOTE: the monolith's fire-and-forget Fehlbedarf compliance audit trigger after a
successful POST is deferred to the compliance slice (it is an audit side-effect
that does not change the response).
"""

from __future__ import annotations

from typing import Any

from fastapi import status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.core.errors import APIError
from app.models.booking_rule import BookingRule, BookingRuleSplit
from app.models.finanzplan import FinanzplanPosition, FinanzplanPositionKostenbereich
from app.models.funding import FundingMeasure
from app.models.transaction import FundAllocation, Transaction, TransactionSplit
from app.services.allocation_betraege import _round2, compute_allocation_betraege
from app.services.allocation_position_resolver import decide_allocation_position
from app.services.audit_service import log_audit
from app.services.foerderfahigkeit_service import (
    check_doppelfinanzierung,
    check_finanzplan_position_ueberziehung,
    check_overhead_limit,
    validate_foerderfahigkeit,
)
from app.utils.serialization import decimal_str as _dec


def _ev(v: Any) -> Any:
    return v.value if hasattr(v, "value") else v


class TransactionAllocationService:
    def __init__(self, db: Session):
        self.db = db

    def _tx(self, org_id: str, id_: str, options=()) -> Transaction | None:
        stmt = select(Transaction).where(
            Transaction.id == id_, Transaction.org_id == org_id
        )
        for o in options:
            stmt = stmt.options(o)
        return self.db.execute(stmt).scalar_one_or_none()

    # ── PUT splits ─────────────────────────────────────────────────────────────
    def set_splits(self, org_id: str, id_: str, body: dict[str, Any]) -> dict[str, Any]:
        tx = self._tx(org_id, id_)
        if tx is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden.")
        splits = body.get("splits") or []

        if splits:
            summe = sum(float(s.get("prozent", 0)) for s in splits)
            if abs(summe - 100) > 0.01:
                raise APIError(
                    400,
                    "SPLIT_SUM_NOT_100",
                    f"Prozent-Summe muss 100% ergeben. Aktuell: {summe:.1f}%",
                )

        betrag = abs(float(tx.betrag))

        # delete existing splits (+ their fund_allocations via cascade)
        existing = (
            self.db.execute(
                select(TransactionSplit).where(TransactionSplit.transaction_id == id_)
            )
            .scalars()
            .all()
        )
        for s in existing:
            self.db.delete(s)
        self.db.flush()

        if splits:
            betraege: list[float] = []
            running = 0.0
            for i in range(len(splits) - 1):
                b = _round2(betrag * float(splits[i]["prozent"]) / 100)
                betraege.append(b)
                running += b
            betraege.append(_round2(betrag - running))
            for s, b in zip(splits, betraege):
                self.db.add(
                    TransactionSplit(
                        org_id=org_id,
                        transaction_id=id_,
                        cost_center_id=s["cost_center_id"],
                        prozent=float(s["prozent"]),
                        betrag_anteil=b,
                        allocation_key_id=s.get("allocation_key_id"),
                    )
                )
            tx.status = "KATEGORISIERT"
        else:
            tx.status = "IMPORTIERT"

        save_rule = body.get("save_as_rule")
        if save_rule and save_rule.get("name") and splits:
            rule = BookingRule(
                org_id=org_id,
                name=save_rule["name"],
                match_auftraggeber=save_rule.get("match_auftraggeber") or None,
                match_verwendungszweck=save_rule.get("match_verwendungszweck") or None,
                match_kostenbereich_id=save_rule.get("match_kostenbereich_id") or None,
                prioritaet=0,
            )
            self.db.add(rule)
            self.db.flush()
            for s in splits:
                self.db.add(
                    BookingRuleSplit(
                        rule_id=rule.id,
                        cost_center_id=s["cost_center_id"],
                        prozent=float(s["prozent"]),
                        allocation_key_id=s.get("allocation_key_id"),
                    )
                )
        self.db.commit()
        return {"data": self._serialize_tx_with_splits(org_id, id_), "message": "Kostenstellen-Zuordnung gespeichert."}

    def _serialize_tx_with_splits(self, org_id: str, id_: str) -> dict[str, Any]:
        from app.services.transaction_service import _tx_scalars

        tx = self.db.execute(
            select(Transaction)
            .where(Transaction.id == id_, Transaction.org_id == org_id)
            .options(
                selectinload(Transaction.splits).selectinload(TransactionSplit.cost_center),
                selectinload(Transaction.splits).selectinload(TransactionSplit.allocation_key),
                selectinload(Transaction.splits)
                .selectinload(TransactionSplit.fund_allocations)
                .selectinload(FundAllocation.funding_measure),
            )
        ).scalar_one()
        row = _tx_scalars(tx)
        row["splits"] = [
            {
                "id": s.id,
                "org_id": s.org_id,
                "transaction_id": s.transaction_id,
                "cost_center_id": s.cost_center_id,
                "prozent": _dec(s.prozent),
                "betrag_anteil": _dec(s.betrag_anteil),
                "allocation_key_id": s.allocation_key_id,
                "cost_center": {"id": s.cost_center.id, "name": s.cost_center.name, "code": s.cost_center.code},
                "allocation_key": (
                    {"id": s.allocation_key.id, "name": s.allocation_key.name}
                    if s.allocation_key
                    else None
                ),
                "fund_allocations": [
                    {
                        "id": a.id,
                        "funding_measure_id": a.funding_measure_id,
                        "funding_measure": {"id": a.funding_measure.id, "name": a.funding_measure.name},
                    }
                    for a in s.fund_allocations
                ],
            }
            for s in tx.splits
        ]
        return row

    # ── GET fund-allocation ────────────────────────────────────────────────────
    def list_allocations(self, org_id: str, id_: str) -> list[dict[str, Any]]:
        if self._tx(org_id, id_) is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden.")
        allocations = (
            self.db.execute(
                select(FundAllocation)
                .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
                .where(
                    FundAllocation.org_id == org_id,
                    TransactionSplit.transaction_id == id_,
                )
                .order_by(FundAllocation.created_at.asc())
                .options(
                    selectinload(FundAllocation.funding_measure),
                    selectinload(FundAllocation.transaction_split).selectinload(
                        TransactionSplit.cost_center
                    ),
                )
            )
            .scalars()
            .all()
        )
        return [self._alloc_full(a) for a in allocations]

    def _alloc_full(self, a: FundAllocation) -> dict[str, Any]:
        fm = a.funding_measure
        s = a.transaction_split
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
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "updated_at": a.updated_at.isoformat() if a.updated_at else None,
            "funding_measure": {
                "id": fm.id,
                "name": fm.name,
                "foerderquote": _dec(fm.foerderquote),
                "status": _ev(fm.status),
            },
            "transaction_split": {
                "id": s.id,
                "prozent": _dec(s.prozent),
                "betrag_anteil": _dec(s.betrag_anteil),
                "cost_center": {"name": s.cost_center.name, "code": s.cost_center.code},
            },
        }

    # ── POST fund-allocation ───────────────────────────────────────────────────
    def create_allocation(
        self, org_id: str, user_id: str | None, id_: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        split_id = body.get("transaction_split_id")
        measure_id = body.get("funding_measure_id")
        finanzplan_position_id = body.get("finanzplan_position_id")
        notiz = body.get("notiz")
        if not split_id or not measure_id:
            raise APIError(
                400,
                "MISSING_FIELDS",
                "transaction_split_id und funding_measure_id sind erforderlich.",
            )

        tx = self._tx(
            org_id,
            id_,
            options=(selectinload(Transaction.fiscal_year), selectinload(Transaction.kostenbereich)),
        )
        if tx is None:
            raise APIError(404, "NOT_FOUND", "Transaktion nicht gefunden.")
        if _ev(tx.fiscal_year.status) != "OFFEN":
            raise APIError(
                400,
                "FISCAL_YEAR_CLOSED",
                "Das Haushaltsjahr dieser Transaktion ist geschlossen — keine neuen "
                "Zuordnungen erlaubt.",
            )

        split = self.db.execute(
            select(TransactionSplit)
            .where(
                TransactionSplit.id == split_id,
                TransactionSplit.transaction_id == id_,
                TransactionSplit.org_id == org_id,
            )
            .options(selectinload(TransactionSplit.cost_center))
        ).scalar_one_or_none()
        if split is None:
            raise APIError(
                404,
                "SPLIT_NOT_FOUND",
                "Split nicht gefunden oder gehört nicht zu dieser Transaktion.",
            )

        measure = self.db.execute(
            select(FundingMeasure).where(
                FundingMeasure.id == measure_id,
                FundingMeasure.org_id == org_id,
                FundingMeasure.status == "AKTIV",
            )
        ).scalar_one_or_none()
        if measure is None:
            raise APIError(
                404, "MEASURE_NOT_FOUND", "Fördermassnahme nicht gefunden oder nicht aktiv."
            )

        doppel = check_doppelfinanzierung(self.db, split_id, measure_id)
        if not doppel.valid:
            raise APIError(409, "DOPPELFINANZIERUNG", doppel.errors[0], extra={"errors": doppel.errors})

        kb_code = tx.kostenbereich.code if tx.kostenbereich else None
        foerder = validate_foerderfahigkeit(
            self.db, measure_id, kb_code, abs(float(split.betrag_anteil))
        )
        if not foerder.valid:
            raise APIError(
                400,
                "NOT_FOERDERFAHIG",
                foerder.errors[0],
                extra={"errors": foerder.errors, "warnings": foerder.warnings},
            )

        brutto = abs(float(split.betrag_anteil))
        betraege = compute_allocation_betraege(
            brutto,
            float(measure.foerderquote),
            measure.mwst_foerderfahig,
            float(measure.mwst_satz_prozent),
        )

        mwst_warnings: list[str] = []
        if not measure.mwst_foerderfahig:
            from app.services.foerderfahigkeit_service import format_eur

            mwst_warnings.append(
                f"Vorsteuerabzugsberechtigt: Förderfähiger Betrag ist "
                f"{format_eur(betraege.betrag_foerderfahig)} (Netto), nicht {format_eur(brutto)} "
                f"(Brutto). MwSt-Satz: {_dec(measure.mwst_satz_prozent)}%."
            )

        overhead = (
            check_overhead_limit(
                self.db, measure_id, org_id, betraege.betrag_foerderfahig, split.cost_center.id
            )
            if split.cost_center
            else type("R", (), {"warnings": []})()
        )

        position_warnings: list[str] = []
        if tx.kostenbereich_id:
            bridge_rows = (
                self.db.execute(
                    select(FinanzplanPosition.id, FinanzplanPosition.positionscode, FinanzplanPosition.bezeichnung)
                    .join(
                        FinanzplanPositionKostenbereich,
                        FinanzplanPositionKostenbereich.finanzplan_position_id == FinanzplanPosition.id,
                    )
                    .where(
                        FinanzplanPositionKostenbereich.org_id == org_id,
                        FinanzplanPositionKostenbereich.kostenbereich_id == tx.kostenbereich_id,
                        FinanzplanPosition.funding_measure_id == measure_id,
                        FinanzplanPosition.ist_pauschale.is_(False),
                    )
                ).all()
            )
            candidates = [
                {"id": r[0], "positionscode": r[1], "bezeichnung": r[2]} for r in bridge_rows
            ]
            decision = decide_allocation_position(candidates, finanzplan_position_id)
            if decision.kind == "error_kb_not_in_bescheid":
                raise APIError(
                    422,
                    "KB_NOT_IN_BESCHEID",
                    f'Kostenbereich "{kb_code}" ist im Bescheid dieser Fördermassnahme nicht '
                    "hinterlegt. Bitte im Bescheid-Wizard ergänzen oder eine andere "
                    "Fördermassnahme wählen.",
                    extra={"measure_id": measure_id, "kostenbereich_code": kb_code},
                )
            if decision.kind == "error_multi_position_needed":
                raise APIError(
                    422,
                    "MULTI_POSITION_MAPPING",
                    f'Kostenbereich "{kb_code}" kann in dieser Fördermassnahme auf '
                    f"{len(decision.candidates)} Positionen wirken — bitte Position wählen, "
                    "sonst Doppelzählung.",
                    extra={"candidates": decision.candidates},
                )
            if decision.kind == "error_position_not_in_bridge":
                raise APIError(
                    422,
                    "POSITION_NOT_IN_BRIDGE",
                    f'Die gewählte FinanzplanPosition ist nicht mit Kostenbereich "{kb_code}" '
                    "verbunden.",
                )
            effective_position_id = decision.position_id
            if effective_position_id:
                pcheck = check_finanzplan_position_ueberziehung(
                    self.db, effective_position_id, org_id, betraege.betrag_foerderfahig
                )
                if not pcheck.valid:
                    raise APIError(
                        409,
                        "POSITION_UEBERZIEHUNG",
                        pcheck.errors[0],
                        extra={"errors": pcheck.errors},
                    )
                position_warnings.extend(pcheck.warnings)

        allocation = FundAllocation(
            org_id=org_id,
            transaction_split_id=split_id,
            funding_measure_id=measure_id,
            prozent=100,
            finanzplan_position_id=finanzplan_position_id,
            betrag_foerderfahig=betraege.betrag_foerderfahig,
            betrag_foerderung=betraege.betrag_foerderung,
            betrag_eigenanteil=betraege.betrag_eigenanteil,
            notiz=notiz,
        )
        self.db.add(allocation)
        tx.status = "ZUGEORDNET"
        self.db.commit()

        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="FUND_ALLOCATION_CREATE",
            entitaet="FundAllocation",
            entitaet_id=allocation.id,
            nachher={
                "id": allocation.id,
                "transaction_split_id": split_id,
                "funding_measure_id": measure_id,
                "finanzplan_position_id": finanzplan_position_id,
                "betrag_foerderfahig": betraege.betrag_foerderfahig,
                "betrag_foerderung": betraege.betrag_foerderung,
                "betrag_eigenanteil": betraege.betrag_eigenanteil,
            },
        )

        allocation = self.db.execute(
            select(FundAllocation)
            .where(FundAllocation.id == allocation.id)
            .options(
                selectinload(FundAllocation.funding_measure),
                selectinload(FundAllocation.transaction_split).selectinload(
                    TransactionSplit.cost_center
                ),
            )
        ).scalar_one()
        return {
            "data": self._alloc_full(allocation),
            "warnings": [*mwst_warnings, *foerder.warnings, *overhead.warnings, *position_warnings],
        }

    # ── PATCH fund-allocation (set position) ───────────────────────────────────
    def update_allocation(
        self, org_id: str, user_id: str | None, id_: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        allocation_id = body.get("allocation_id")
        finanzplan_position_id = body.get("finanzplan_position_id")
        if not allocation_id or not finanzplan_position_id:
            raise APIError(
                400,
                "MISSING_FIELDS",
                "allocation_id und finanzplan_position_id sind erforderlich.",
            )
        allocation = self.db.execute(
            select(FundAllocation)
            .where(FundAllocation.id == allocation_id, FundAllocation.org_id == org_id)
            .options(
                selectinload(FundAllocation.transaction_split)
                .selectinload(TransactionSplit.transaction)
                .selectinload(Transaction.fiscal_year),
                selectinload(FundAllocation.transaction_split)
                .selectinload(TransactionSplit.transaction)
                .selectinload(Transaction.kostenbereich),
            )
        ).scalar_one_or_none()
        if allocation is None or allocation.transaction_split.transaction_id != id_:
            raise APIError(404, "NOT_FOUND", "Förderzuordnung nicht gefunden.")
        tx = allocation.transaction_split.transaction
        if _ev(tx.fiscal_year.status) != "OFFEN":
            raise APIError(
                400,
                "FISCAL_YEAR_CLOSED",
                "Das Haushaltsjahr dieser Transaktion ist geschlossen — keine Änderung erlaubt.",
            )
        kb = tx.kostenbereich
        if kb is None:
            raise APIError(
                422,
                "TRANSACTION_NO_KOSTENBEREICH",
                "Transaktion hat keinen Kostenbereich — Position-Wahl nicht möglich. "
                "Bitte zuerst Kostenbereich setzen.",
            )
        bridge = self.db.execute(
            select(FinanzplanPositionKostenbereich.id)
            .join(
                FinanzplanPosition,
                FinanzplanPosition.id == FinanzplanPositionKostenbereich.finanzplan_position_id,
            )
            .where(
                FinanzplanPositionKostenbereich.org_id == org_id,
                FinanzplanPositionKostenbereich.kostenbereich_id == kb.id,
                FinanzplanPositionKostenbereich.finanzplan_position_id == finanzplan_position_id,
                FinanzplanPosition.funding_measure_id == allocation.funding_measure_id,
                FinanzplanPosition.ist_pauschale.is_(False),
            )
        ).scalar_one_or_none()
        if bridge is None:
            raise APIError(
                422,
                "POSITION_NOT_IN_BRIDGE",
                f'Die gewählte FinanzplanPosition ist nicht mit Kostenbereich "{kb.code}" '
                "verbunden oder gehört nicht zu dieser Fördermassnahme.",
            )
        gewichtet = float(allocation.betrag_foerderfahig) * float(allocation.prozent) / 100
        pcheck = check_finanzplan_position_ueberziehung(
            self.db, finanzplan_position_id, org_id, gewichtet
        )
        if not pcheck.valid:
            raise APIError(
                409, "POSITION_UEBERZIEHUNG", pcheck.errors[0], extra={"errors": pcheck.errors}
            )
        vorher = allocation.finanzplan_position_id
        allocation.finanzplan_position_id = finanzplan_position_id
        self.db.commit()
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="FUND_ALLOCATION_UPDATE",
            entitaet="FundAllocation",
            entitaet_id=allocation_id,
            vorher={"finanzplan_position_id": vorher},
            nachher={"finanzplan_position_id": finanzplan_position_id},
        )
        return {
            "data": {"id": allocation_id, "finanzplan_position_id": finanzplan_position_id},
            "warnings": pcheck.warnings,
        }

    # ── DELETE fund-allocation ─────────────────────────────────────────────────
    def delete_allocation(
        self, org_id: str, user_id: str | None, id_: str, body: dict[str, Any]
    ) -> dict[str, Any]:
        split_id = body.get("transaction_split_id")
        measure_id = body.get("funding_measure_id")
        if not split_id:
            raise APIError(400, "MISSING_FIELDS", "transaction_split_id ist erforderlich.")
        split = self.db.execute(
            select(TransactionSplit).where(
                TransactionSplit.id == split_id,
                TransactionSplit.transaction_id == id_,
                TransactionSplit.org_id == org_id,
            )
        ).scalar_one_or_none()
        if split is None:
            raise APIError(404, "NOT_FOUND", "Split nicht gefunden.")

        conds = [
            FundAllocation.transaction_split_id == split_id,
            FundAllocation.org_id == org_id,
        ]
        if measure_id:
            conds.append(FundAllocation.funding_measure_id == measure_id)
        allocations = self.db.execute(select(FundAllocation).where(and_(*conds))).scalars().all()
        if not allocations:
            raise APIError(404, "NOT_FOUND", "Förderzuordnung nicht gefunden.")
        first = allocations[0]
        snapshot = {
            "id": first.id,
            "transaction_split_id": split_id,
            "funding_measure_id": first.funding_measure_id,
            "betrag_foerderung": _dec(first.betrag_foerderung),
            "betrag_eigenanteil": _dec(first.betrag_eigenanteil),
        }
        for a in allocations:
            self.db.delete(a)
        self.db.flush()

        remaining = self.db.execute(
            select(func.count(FundAllocation.id))
            .join(TransactionSplit, TransactionSplit.id == FundAllocation.transaction_split_id)
            .where(FundAllocation.org_id == org_id, TransactionSplit.transaction_id == id_)
        ).scalar_one()
        if remaining == 0:
            tx = self._tx(org_id, id_)
            if tx:
                tx.status = "KATEGORISIERT"
        self.db.commit()
        log_audit(
            self.db,
            org_id=org_id,
            user_id=user_id,
            aktion="FUND_ALLOCATION_DELETE",
            entitaet="FundAllocation",
            entitaet_id=first.id,
            vorher=snapshot,
        )
        return {"data": {"deleted": True}}
