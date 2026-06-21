"""Persistence pipeline — port of lib/import/transaction-import.ts.

Resolves bank accounts (per-row IBAN / fallback / auto-create), classifies typ,
infers Kostenbereich, de-dupes (existing + within-import), creates the ImportBatch
+ Transactions atomically, then applies booking rules per new transaction, and
provides the saldo-consistency check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master import Kostenbereich
from app.models.transaction import (
    BankAccount,
    ImportBatch,
    OpeningBalance,
    Transaction,
)
from app.services.booking_rules import apply_rule_to_transaction
from app.services.csv_import.duplicate import create_duplikat_hash, find_duplicates
from app.services.csv_import.heuristics import infer_kostenbereich_code
from app.services.csv_import.parser import ParsedRow


@dataclass
class PersistResult:
    batch_id: str
    anzahl_importiert: int
    anzahl_duplikate: int
    anzahl_auto_matched: int
    bank_accounts_neu: list[str] = field(default_factory=list)
    bank_account_id_count: dict[str, int] = field(default_factory=dict)


def classify_transaction_typ(row: ParsedRow, own_ibans: set[str]) -> str:
    if row.iban_partner and row.iban_partner in own_ibans:
        return "INTERNE_UMBUCHUNG"
    if row.betrag < 0:
        return "AUSGABE"
    if row.betrag > 0:
        return "EINNAHME"
    return "INTERNE_UMBUCHUNG"


def _load_bank_account_map(db: Session, org_id: str) -> dict[str, str]:
    rows = db.execute(
        select(BankAccount.id, BankAccount.iban).where(
            BankAccount.org_id == org_id, BankAccount.iban.is_not(None)
        )
    ).all()
    return {iban: id_ for id_, iban in rows}


def _create_bank_account_for_iban(db: Session, org_id: str, iban: str) -> tuple[str, str]:
    suffix = iban[-4:]
    code = f"AUTO-{suffix}"
    existing = db.execute(
        select(BankAccount.id).where(BankAccount.org_id == org_id, BankAccount.code == code)
    ).scalar_one_or_none()
    if existing:
        code = f"AUTO-{iban[-6:]}"
    acc = BankAccount(org_id=org_id, code=code, bezeichnung=iban, typ="BANK", iban=iban, ist_aktiv=True)
    db.add(acc)
    db.flush()
    return acc.id, acc.code


def persist_parsed_rows(
    db: Session,
    rows: list[ParsedRow],
    *,
    org_id: str,
    fiscal_year_id: str,
    user_id: str,
    csv_import_profile_id: str | None = None,
    fallback_bank_account_id: str | None = None,
    auto_create_bank_account: bool = True,
    dateiname: str,
    format: str = "GENERIC_CSV",
) -> PersistResult:
    iban_to_account = _load_bank_account_map(db, org_id)
    bank_accounts_neu: list[str] = []
    unique_ibans = {r.bank_account_iban for r in rows if r.bank_account_iban}

    if auto_create_bank_account:
        for iban in unique_ibans:
            if iban not in iban_to_account:
                acc_id, code = _create_bank_account_for_iban(db, org_id, iban)
                iban_to_account[iban] = acc_id
                bank_accounts_neu.append(code)

    own_ibans = set(iban_to_account.keys())
    all_hashes = [create_duplikat_hash(r.datum, r.betrag, r.auftraggeber) for r in rows]
    existing_hashes = find_duplicates(db, org_id, all_hashes)

    kb_rows = db.execute(select(Kostenbereich.id, Kostenbereich.code)).all()
    code_to_id = {code: id_ for id_, code in kb_rows}

    anzahl_duplikate = 0
    bank_account_id_count: dict[str, int] = {}

    batch = ImportBatch(
        org_id=org_id,
        fiscal_year_id=fiscal_year_id,
        format=format,
        csv_import_profile_id=csv_import_profile_id,
        dateiname=dateiname,
        importiert_von=user_id,
        anzahl_fehler=0,
    )
    db.add(batch)
    db.flush()

    seen_hashes: set[str] = set()
    inserted = 0
    for row in rows:
        h = create_duplikat_hash(row.datum, row.betrag, row.auftraggeber)
        if h in existing_hashes or h in seen_hashes:
            anzahl_duplikate += 1
            continue
        seen_hashes.add(h)

        bank_account_id = (
            iban_to_account.get(row.bank_account_iban) if row.bank_account_iban else None
        ) or fallback_bank_account_id or None
        if bank_account_id:
            bank_account_id_count[bank_account_id] = bank_account_id_count.get(bank_account_id, 0) + 1

        typ = classify_transaction_typ(row, own_ibans)
        inferred = infer_kostenbereich_code(row.auftraggeber, row.verwendungszweck, row.buchungstext_typ)
        kostenbereich_id = code_to_id.get(inferred) if inferred else None

        externe_referenz = row.externe_referenz
        if not externe_referenz and row.verwendungszweck:
            m = re.search(r"EREF:\s*([A-Za-z0-9.\-_]+)", row.verwendungszweck)
            if m:
                externe_referenz = m.group(1)

        db.add(
            Transaction(
                org_id=org_id,
                fiscal_year_id=fiscal_year_id,
                import_batch_id=batch.id,
                bank_account_id=bank_account_id,
                datum=row.datum,
                valuta_datum=row.valuta_datum,
                betrag=row.betrag,
                saldo_nach_buchung=row.saldo_nach_buchung,
                typ=typ,
                auftraggeber=row.auftraggeber,
                iban_partner=row.iban_partner,
                bic_partner=row.bic_partner,
                verwendungszweck=row.verwendungszweck,
                externe_referenz=externe_referenz,
                glaeubiger_id=row.glaeubiger_id,
                mandatsreferenz=row.mandatsreferenz,
                buchungstext_typ=row.buchungstext_typ,
                kostenbereich_id=kostenbereich_id,
                duplikat_hash=h,
                status="IMPORTIERT",
            )
        )
        inserted += 1

    batch.anzahl_importiert = inserted
    batch.anzahl_duplikate = anzahl_duplikate
    db.commit()

    # Apply booking rules per new transaction (separate from bulk insert).
    from app.services.booking_rules import build_rule_match_conditions  # noqa: F401

    imported = (
        db.execute(
            select(Transaction).where(
                Transaction.import_batch_id == batch.id, Transaction.org_id == org_id
            )
        )
        .scalars()
        .all()
    )
    auto_matched = 0
    for tx in imported:
        rule = _find_matching_rule(db, org_id, tx)
        if rule:
            try:
                apply_rule_to_transaction(db, org_id, tx.id, abs(float(tx.betrag)), rule)
                auto_matched += 1
            except Exception:  # noqa: BLE001
                db.rollback()

    return PersistResult(
        batch_id=batch.id,
        anzahl_importiert=len(imported),
        anzahl_duplikate=anzahl_duplikate,
        anzahl_auto_matched=auto_matched,
        bank_accounts_neu=bank_accounts_neu,
        bank_account_id_count=bank_account_id_count,
    )


def _find_matching_rule(db: Session, org_id: str, tx: Transaction):
    """Port of findMatchingRule: first active rule (priority desc) whose set
    conditions all match the transaction."""
    from app.models.booking_rule import BookingRule
    from sqlalchemy.orm import selectinload

    rules = (
        db.execute(
            select(BookingRule)
            .where(BookingRule.org_id == org_id, BookingRule.aktiv.is_(True))
            .order_by(BookingRule.prioritaet.desc())
            .options(selectinload(BookingRule.splits))
        )
        .scalars()
        .all()
    )
    brutto_abs = abs(float(tx.betrag))
    ag = (tx.auftraggeber or "").lower()
    vz = (tx.verwendungszweck or "").lower()
    for rule in rules:
        if rule.match_auftraggeber:
            ma = rule.match_auftraggeber.lower()
            ok = (ag == ma) if rule.match_auftraggeber_exact else (ma in ag)
            if not ok:
                continue
        if rule.match_verwendungszweck and rule.match_verwendungszweck.lower() not in vz:
            continue
        if rule.match_kostenbereich_id and rule.match_kostenbereich_id != tx.kostenbereich_id:
            continue
        if rule.match_iban_partner and rule.match_iban_partner != (tx.iban_partner or None):
            continue
        if rule.match_betrag_min is not None and brutto_abs < float(rule.match_betrag_min):
            continue
        if rule.match_betrag_max is not None and brutto_abs > float(rule.match_betrag_max):
            continue
        if rule.match_datum_von and tx.datum < rule.match_datum_von:
            continue
        if rule.match_datum_bis and tx.datum > rule.match_datum_bis:
            continue
        return rule
    return None


# ── saldo consistency ─────────────────────────────────────────────────────────
def check_saldo_consistency(
    db: Session, org_id: str, fiscal_year_id: str, rows: list[ParsedRow]
) -> list[dict[str, Any]]:
    accounts = db.execute(
        select(BankAccount.id, BankAccount.iban).where(
            BankAccount.org_id == org_id, BankAccount.iban.is_not(None)
        )
    ).all()
    iban_to_account = {iban: id_ for id_, iban in accounts}

    per_iban: dict[str, dict[str, Any]] = {}
    for r in rows:
        if not r.bank_account_iban:
            continue
        a = per_iban.setdefault(r.bank_account_iban, {"sum": 0.0, "last_saldo": None, "last_datum": None})
        a["sum"] += r.betrag
        if r.saldo_nach_buchung is not None and (a["last_datum"] is None or r.datum >= a["last_datum"]):
            a["last_saldo"] = r.saldo_nach_buchung
            a["last_datum"] = r.datum

    results: list[dict[str, Any]] = []
    for iban, agg in per_iban.items():
        acc_id = iban_to_account.get(iban)
        if not acc_id:
            continue
        opening = db.execute(
            select(OpeningBalance.saldo_eroeffnung).where(
                OpeningBalance.bank_account_id == acc_id,
                OpeningBalance.fiscal_year_id == fiscal_year_id,
            )
        ).scalar_one_or_none()
        opening_num = float(opening) if opening is not None else None
        expected_end = opening_num + agg["sum"] if opening_num is not None else None
        diff = (
            agg["last_saldo"] - expected_end
            if expected_end is not None and agg["last_saldo"] is not None
            else None
        )
        results.append(
            {
                "bank_account_id": acc_id,
                "iban": iban,
                "opening": opening_num,
                "sum_betrag": round(agg["sum"], 2),
                "expected_end": round(expected_end, 2) if expected_end is not None else None,
                "csv_last_saldo": agg["last_saldo"],
                "diff": round(diff, 2) if diff is not None else None,
                "passed": diff is None or abs(diff) < 0.01,
            }
        )
    return results
