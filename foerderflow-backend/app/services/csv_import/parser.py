"""Generic profile-based CSV parser — port of lib/import/csv-parser-generic.ts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.services.csv_import.detector import strip_bom, tokenize_csv_line

REQUIRED_FIELDS = ("datum", "betrag", "auftraggeber")


@dataclass
class ParsedRow:
    rowNumber: int
    datum: date
    valuta_datum: date | None
    betrag: float
    auftraggeber: str | None
    verwendungszweck: str | None
    buchungstext_typ: str | None
    iban_partner: str | None
    bic_partner: str | None
    externe_referenz: str | None
    glaeubiger_id: str | None
    mandatsreferenz: str | None
    saldo_nach_buchung: float | None
    waehrung: str | None
    bemerkung: str | None
    bank_account_iban: str | None
    raw_line: str


@dataclass
class GenericParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    detectedHeader: list[str] = field(default_factory=list)


def _parse_date(input_: str, fmt: str) -> date | None:
    s = (input_.strip().split()[0] if input_.strip() else input_.strip())
    if not s:
        return None
    if fmt == "dd.MM.yyyy":
        m = re.match(r"^(\d{2})\.(\d{2})\.(\d{4})$", s)
        if not m:
            return None
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    elif fmt == "yyyy-MM-dd":
        m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
        if not m:
            return None
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    elif fmt == "dd/MM/yyyy":
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if not m:
            return None
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    elif fmt == "MM/dd/yyyy":
        m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", s)
        if not m:
            return None
        month, day, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    else:
        return None
    if month < 1 or month > 12 or day < 1 or day > 31:
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_amount(input_: str, decimal_sep: str, thousand_sep: str | None) -> float | None:
    s = input_.strip()
    if not s:
        return None
    s = re.sub(r"[€$£]\s*", "", s)
    s = re.sub(r"\s*(EUR|USD|GBP)\s*$", "", s, flags=re.IGNORECASE)
    if thousand_sep:
        s = s.replace(thousand_sep, "")
    if decimal_sep == ",":
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def validate_mapping(mapping: dict[str, str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for f in REQUIRED_FIELDS:
        if f == "betrag":
            if not mapping.get("betrag") and not (
                mapping.get("betrag_soll") and mapping.get("betrag_haben")
            ):
                missing.append("betrag")
        elif not mapping.get(f):
            missing.append(f)
    return len(missing) == 0, missing


def parse_csv_with_profile(raw_content: str, profile: dict[str, Any]) -> GenericParseResult:
    mapping = profile["columnMappings"]
    ok, missing = validate_mapping(mapping)
    if not ok:
        return GenericParseResult(
            rows=[],
            errors=[
                {
                    "line": 0,
                    "message": f"Mapping unvollständig — fehlende Pflichtfelder: {', '.join(missing)}",
                    "raw": "",
                }
            ],
            detectedHeader=[],
        )

    content, _ = strip_bom(raw_content)
    all_lines = re.split(r"\r?\n", content)
    header_row = profile["headerRow"]
    if header_row - 1 >= len(all_lines):
        return GenericParseResult(
            errors=[{"line": 0, "message": "Header-Zeile außerhalb der Datei", "raw": ""}]
        )
    delimiter = profile["delimiter"]
    quote = profile.get("quoteChar", '"')
    header = tokenize_csv_line(all_lines[header_row - 1], delimiter, quote)
    data_lines = all_lines[header_row:]
    date_fmt = profile["dateFormat"]
    decimal_sep = profile["decimalSeparator"]
    thousand_sep = profile.get("thousandSeparator")

    rows: list[ParsedRow] = []
    errors: list[dict[str, Any]] = []

    def get_val(field_name: str, parts: list[str]) -> str | None:
        col = mapping.get(field_name)
        if not col:
            return None
        try:
            idx = header.index(col)
        except ValueError:
            return None
        if idx >= len(parts):
            return None
        v = parts[idx]
        if v is None:
            return None
        t = v.strip()
        return t if t else None

    for i, raw in enumerate(data_lines):
        if not raw.strip():
            continue
        line_num = header_row + 1 + i
        try:
            parts = tokenize_csv_line(raw, delimiter, quote)
        except Exception as e:  # noqa: BLE001
            errors.append({"line": line_num, "message": f"Tokenize fehlgeschlagen: {e}", "raw": raw})
            continue

        datum_raw = get_val("datum", parts)
        if not datum_raw:
            errors.append({"line": line_num, "message": "Datum fehlt", "raw": raw})
            continue
        datum = _parse_date(datum_raw, date_fmt)
        if not datum:
            errors.append(
                {
                    "line": line_num,
                    "message": f"Ungültiges Datum (Format {date_fmt}): {datum_raw}",
                    "raw": raw,
                }
            )
            continue

        betrag_raw = get_val("betrag", parts)
        if betrag_raw:
            betrag = _parse_amount(betrag_raw, decimal_sep, thousand_sep)
            if betrag is None:
                errors.append({"line": line_num, "message": f"Ungültiger Betrag: {betrag_raw}", "raw": raw})
                continue
        else:
            soll = _parse_amount(get_val("betrag_soll", parts) or "0", decimal_sep, thousand_sep) or 0
            haben = _parse_amount(get_val("betrag_haben", parts) or "0", decimal_sep, thousand_sep) or 0
            betrag = haben - soll

        auftraggeber_raw = get_val("auftraggeber", parts)
        auftraggeber = (
            auftraggeber_raw[:255]
            if auftraggeber_raw and len(auftraggeber_raw) > 255
            else auftraggeber_raw
        )
        verwendungszweck = get_val("verwendungszweck", parts)

        valuta_raw = get_val("valuta_datum", parts)
        valuta_datum = _parse_date(valuta_raw, date_fmt) if valuta_raw else None
        saldo_raw = get_val("saldo_nach_buchung", parts)
        saldo = _parse_amount(saldo_raw, decimal_sep, thousand_sep) if saldo_raw else None

        rows.append(
            ParsedRow(
                rowNumber=line_num,
                datum=datum,
                valuta_datum=valuta_datum,
                betrag=betrag,
                auftraggeber=auftraggeber,
                verwendungszweck=verwendungszweck,
                buchungstext_typ=get_val("buchungstext_typ", parts),
                iban_partner=get_val("iban_partner", parts),
                bic_partner=get_val("bic_partner", parts),
                externe_referenz=get_val("externe_referenz", parts),
                glaeubiger_id=get_val("glaeubiger_id", parts),
                mandatsreferenz=get_val("mandatsreferenz", parts),
                saldo_nach_buchung=saldo,
                waehrung=get_val("waehrung", parts),
                bemerkung=get_val("bemerkung", parts),
                bank_account_iban=get_val("bank_account_iban", parts),
                raw_line=raw,
            )
        )

    return GenericParseResult(rows=rows, errors=errors, detectedHeader=header)
