"""Built-in CSV import profiles — port of lib/import/builtin-profiles.ts."""

from __future__ import annotations

from typing import Any

BUILTIN_PROFILES: list[dict[str, Any]] = [
    {
        "name": "BFS-SozialBank (Umsätze CSV)",
        "beschreibung": (
            "Bank für Sozialwirtschaft / SozialBank AG — semicolon-separierter Umsatz-Export, "
            "BOM-präfixiert, 18 Spalten inkl. IBAN beider Seiten, Glaeubiger-ID und Mandatsreferenz."
        ),
        "autoDetectPattern": (
            "Bezeichnung Auftragskonto;IBAN Auftragskonto;BIC Auftragskonto;"
            "Bankname Auftragskonto;Buchungstag;Valutadatum"
        ),
        "config": {
            "delimiter": ";",
            "encoding": "utf-8-sig",
            "quoteChar": '"',
            "decimalSeparator": ",",
            "thousandSeparator": None,
            "dateFormat": "dd.MM.yyyy",
            "headerRow": 1,
            "skipRows": 0,
            "columnMappings": {
                "bank_account_iban": "IBAN Auftragskonto",
                "datum": "Buchungstag",
                "valuta_datum": "Valutadatum",
                "auftraggeber": "Name Zahlungsbeteiligter",
                "iban_partner": "IBAN Zahlungsbeteiligter",
                "bic_partner": "BIC (SWIFT-Code) Zahlungsbeteiligter",
                "buchungstext_typ": "Buchungstext",
                "verwendungszweck": "Verwendungszweck",
                "betrag": "Betrag",
                "waehrung": "Waehrung",
                "saldo_nach_buchung": "Saldo nach Buchung",
                "bemerkung": "Bemerkung",
                "glaeubiger_id": "Glaeubiger ID",
                "mandatsreferenz": "Mandatsreferenz",
            },
        },
    },
    {
        "name": "Finom (CSV Export)",
        "beschreibung": "Finom Banking — komma-separiert, US-Dezimal, Datum mit Uhrzeit-Anhang.",
        "autoDetectPattern": "Buchungsdatum,Auftraggeber",
        "config": {
            "delimiter": ",",
            "encoding": "utf-8",
            "quoteChar": '"',
            "decimalSeparator": ".",
            "thousandSeparator": None,
            "dateFormat": "dd.MM.yyyy",
            "headerRow": 1,
            "skipRows": 0,
            "columnMappings": {
                "datum": "Buchungsdatum",
                "auftraggeber": "Auftraggeber/Empfänger",
                "verwendungszweck": "Verwendungszweck",
                "betrag": "Betrag",
            },
        },
    },
    {
        "name": "Sparkasse (CSV-CAMT Export)",
        "beschreibung": (
            "Sparkassen-CSV-CAMT-Export — semicolon, deutsche Notation, Header-Zeile in Zeile 1."
        ),
        "autoDetectPattern": "Auftragskonto;Buchungstag;Valutadatum;Buchungstext",
        "config": {
            "delimiter": ";",
            "encoding": "windows-1252",
            "quoteChar": '"',
            "decimalSeparator": ",",
            "thousandSeparator": ".",
            "dateFormat": "dd.MM.yyyy",
            "headerRow": 1,
            "skipRows": 0,
            "columnMappings": {
                "bank_account_iban": "Auftragskonto",
                "datum": "Buchungstag",
                "valuta_datum": "Valutadatum",
                "buchungstext_typ": "Buchungstext",
                "verwendungszweck": "Verwendungszweck",
                "auftraggeber": "Beguenstigter/Zahlungspflichtiger",
                "iban_partner": "Kontonummer/IBAN",
                "bic_partner": "BIC (SWIFT-Code)",
                "betrag": "Betrag",
                "waehrung": "Waehrung",
                "glaeubiger_id": "Glaeubiger-ID",
                "mandatsreferenz": "Mandatsreferenz",
            },
        },
    },
    {
        "name": "DKB (CSV)",
        "beschreibung": (
            "DKB Privatkundenexport — semicolon, Header mit Konto-Block davor (skipRows>0)."
        ),
        "autoDetectPattern": '"Buchungsdatum";"Wertstellung"',
        "config": {
            "delimiter": ";",
            "encoding": "windows-1252",
            "quoteChar": '"',
            "decimalSeparator": ",",
            "thousandSeparator": ".",
            "dateFormat": "dd.MM.yyyy",
            "headerRow": 6,
            "skipRows": 5,
            "columnMappings": {
                "datum": "Buchungsdatum",
                "valuta_datum": "Wertstellung",
                "auftraggeber": "Zahlungspflichtige*r",
                "buchungstext_typ": "Umsatztyp",
                "verwendungszweck": "Verwendungszweck",
                "iban_partner": "IBAN",
                "betrag": "Betrag (€)",
                "saldo_nach_buchung": "Kontostand (€)",
                "mandatsreferenz": "Mandatsreferenz",
                "glaeubiger_id": "Gläubiger-ID",
            },
        },
    },
    {
        "name": "PayPal (Aktivitätenbericht CSV)",
        "beschreibung": (
            "PayPal Aktivitätenbericht — komma-separiert, US-Format, viele Spalten "
            "(Brutto, Netto, Gebühr)."
        ),
        "autoDetectPattern": '"Datum","Uhrzeit","Zeitzone","Name","Typ"',
        "config": {
            "delimiter": ",",
            "encoding": "utf-8",
            "quoteChar": '"',
            "decimalSeparator": ",",
            "thousandSeparator": ".",
            "dateFormat": "dd.MM.yyyy",
            "headerRow": 1,
            "skipRows": 0,
            "columnMappings": {
                "datum": "Datum",
                "auftraggeber": "Name",
                "buchungstext_typ": "Typ",
                "verwendungszweck": "Artikelbezeichnung",
                "betrag": "Netto",
                "waehrung": "Währung",
                "externe_referenz": "Transaktionscode",
            },
        },
    },
]


def find_builtin_profile(header_line: str) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for p in BUILTIN_PROFILES:
        if p["autoDetectPattern"] in header_line:
            if best is None or len(p["autoDetectPattern"]) > len(best["autoDetectPattern"]):
                best = p
    return best
