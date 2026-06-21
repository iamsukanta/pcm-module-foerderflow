"""Field-hint mapping suggestion — port of lib/import/field-hints.ts."""

from __future__ import annotations

import re

FIELD_HINTS: dict[str, list[str]] = {
    "datum": ["buchungstag", "belegdatum", "datum", "booking date", "date"],
    "valuta_datum": ["valutadatum", "valuta", "wertstellung", "value date"],
    "betrag": ["betrag", "umsatz", "wert", "amount", "value"],
    "betrag_soll": ["soll", "debit", "ausgabe", "lastschrift"],
    "betrag_haben": ["haben", "credit", "einnahme", "gutschrift"],
    "auftraggeber": [
        "name zahlungsbeteiligter", "zahlungsbeteiligter", "beguenstigter",
        "begünstigter", "auftraggeber", "empfänger", "empfaenger",
        "counterparty", "partner", "name",
    ],
    "verwendungszweck": [
        "verwendungszweck", "zweck", "purpose", "reference", "subject",
        "buchungstext", "description",
    ],
    "buchungstext_typ": [
        "buchungstext-typ", "buchungsart", "transaction type", "txn type", "buchungstext",
    ],
    "iban_partner": [
        "iban zahlungsbeteiligter", "iban partner", "partner_iban",
        "iban des empfängers", "iban empfaenger",
    ],
    "bic_partner": [
        "bic (swift-code) zahlungsbeteiligter", "bic zahlungsbeteiligter",
        "bic partner", "swift", "bic",
    ],
    "bank_account_iban": [
        "iban auftragskonto", "iban auftrag", "iban des kontos", "kontonummer",
        "konto", "account", "iban",
    ],
    "saldo_nach_buchung": ["saldo nach buchung", "saldo", "balance"],
    "externe_referenz": [
        "end-to-end", "endtoend", "eref", "belegnummer", "referenz", "transaktions-id",
    ],
    "glaeubiger_id": ["glaeubiger id", "gläubiger id", "glaeubiger-id", "creditor id"],
    "mandatsreferenz": ["mandatsreferenz", "mandat-ref", "mandat", "mandate"],
    "waehrung": ["waehrung", "währung", "currency"],
    "bemerkung": ["bemerkung", "notiz", "memo", "comment", "kommentar"],
}


def _normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().strip())


def _best_hint_for_header(header: str):
    norm = _normalize(header)
    best = None
    for field, hints in FIELD_HINTS.items():
        for idx, hint in enumerate(hints):
            if hint in norm:
                cand = {"field": field, "hintLength": len(hint), "hintIndex": idx}
                if (
                    best is None
                    or cand["hintLength"] > best["hintLength"]
                    or (cand["hintLength"] == best["hintLength"] and cand["hintIndex"] < best["hintIndex"])
                ):
                    best = cand
    return best


def suggest_mapping(header_columns: list[str]) -> dict[str, str]:
    mapping: dict[str, dict] = {}
    for source_col in header_columns:
        match = _best_hint_for_header(source_col)
        if not match:
            continue
        field = match["field"]
        existing = mapping.get(field)
        if (
            existing is None
            or match["hintLength"] > existing["hintLength"]
            or (match["hintLength"] == existing["hintLength"] and match["hintIndex"] < existing["hintIndex"])
        ):
            mapping[field] = {
                "sourceCol": source_col,
                "hintLength": match["hintLength"],
                "hintIndex": match["hintIndex"],
            }
    return {field: info["sourceCol"] for field, info in mapping.items()}
