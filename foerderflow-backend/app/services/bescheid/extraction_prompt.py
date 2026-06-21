"""Bescheid extraction prompt + result normalization — port of
lib/bescheid/extraction-prompt.ts. Prompt text is verbatim (German)."""

from __future__ import annotations

from typing import Any

# Verbatim from lib/kostenarten.ts KOSTENBEREICH_CODES
KOSTENBEREICH_CODES = [
    "PERSONAL",
    "SACHKOSTEN",
    "GEMEINKOSTEN",
    "EINNAHMEN",
    "PERSONAL_FESTANSTELLUNG",
    "PERSONAL_HONORARE",
    "PERSONAL_EHRENAMT",
    "SACH_BUERO",
    "SACH_REISE",
    "SACH_BESCHAFFUNG",
    "SACH_MARKETING",
    "SACH_DIENSTLEISTUNGEN",
    "SACH_BEWIRTUNG",
    "SACH_VERANSTALTUNG",
    "SACH_MATERIAL",
    "SACH_FORTBILDUNG",
    "MIETE",
    "ENERGIE",
    "REINIGUNG",
    "RAUM_NEBENKOSTEN",
    "KOMMUNIKATION",
    "IT_SOFTWARE",
    "IT_INFRASTRUKTUR",
    "VERSICHERUNG",
    "RECHTSBERATUNG",
    "KONTOFUEHRUNG",
    "MITGLIEDSBEITRAEGE",
    "STEUERN_ABGABEN",
    "VERWALTUNG_SONSTIGE",
    "EINNAHMEN_FOERDERUNG",
    "EINNAHMEN_SPENDEN",
    "EINNAHMEN_PROJEKT",
    "EINNAHMEN_SONSTIGE",
    "EINNAHMEN_AAG_ERSTATTUNG",
]

_CODES_BLOCK = "\n".join(f'  - "{c}"' for c in KOSTENBEREICH_CODES)

EXTRACTION_PROMPT = f"""Du bist ein Experte für die Analyse deutscher Förderbescheide von Behörden, Stiftungen und öffentlichen Förderprogrammen.

Du erhältst den per OCR extrahierten Text eines Förderbescheids und gibst ein strukturiertes JSON-Objekt zurück.

WICHTIG: Gib NUR das JSON-Objekt zurück, keinen weiteren Text. Bei Unsicherheit setze das Feld auf null – rate nicht.

# Ausgabe-Schema

{{
  "name": string | null,
  "funder_name": string | null,
  "foerderquote": number | null,
  "finanzierungsart": "ANTEIL" | "FEHLBEDARF" | "FESTBETRAG" | null,
  "budget_gesamt": number | null,
  "eigenmittel": number | null,
  "drittmittel": number | null,
  "zuwendungsbetrag": number | null,
  "laufzeit_von": "YYYY-MM-DD" | null,
  "laufzeit_bis": "YYYY-MM-DD" | null,
  "mittelabruf_verfahren": "ANFORDERUNG" | "ABRUF" | "ABSCHLAG" | null,
  "verwaltungspauschale_erlaubt": boolean | null,
  "verwaltungspauschale_prozent": number | null,
  "budget_flexibilitaet_prozent": number | null,
  "overhead_limit_prozent": number | null,
  "mwst_nicht_foerderfahig": boolean,
  "finanzplan_positionen": [
    {{
      "positionscode": string,
      "bezeichnung": string,
      "betrag_bewilligt": number,
      "ueberziehung_limit_pct": number | null,
      "kostenbereich_code": string | null,
      "ist_pauschale": boolean,
      "pauschale_typ": "FIXER_BETRAG" | "PROZENT_GESAMT" | "PROZENT_PERSONAL" | null,
      "pauschale_prozent": number | null
    }}
  ],
  "rules": [...],
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "raw_hinweise": [...]
}}

# Feldbeschreibungen

## name
Bezeichnung der geförderten Maßnahme oder des Projekts, exakt wie im Bescheid genannt.
Beispiel: "Integrationsförderung Hamburg 2026–2027"

## funder_name
Name des Fördergebers (Behörde, Stiftung, etc.).
Beispiel: "Behörde für Arbeit, Gesundheit, Soziales, Familie und Integration"

## foerderquote
Prozentualer Anteil der Förderung am Gesamtbudget, als Zahl (nicht als Dezimalbruch).
Beispiel: 80 (für 80%), nicht 0.8

## finanzierungsart
- ANTEIL: Fördergeber übernimmt prozentualen Anteil der Gesamtausgaben
- FEHLBEDARF: Fördergeber deckt den verbleibenden Bedarf nach anderen Einnahmen
- FESTBETRAG: Fixer Förderbetrag unabhängig von tatsächlichen Ausgaben

## budget_gesamt
**Zuwendungsfähige Gesamtausgaben** in EUR als Zahl ohne Währungssymbol.
Das ist NICHT der Zuwendungsbetrag, sondern die Summe aller förderfähigen
Ausgaben aus dem Kosten-/Finanzierungsplan ("AUSGABEN insgesamt" bzw.
"EINNAHMEN insgesamt" im ausgeglichenen Plan).
Beispiel: 66447.22

## eigenmittel
NUR bei FEHLBEDARF: Eigenmittel-Plansumme der Org aus dem Finanzierungsplan-
Anhang (typisch Zeile "I. Eigenmittel" unter EINNAHMEN). Bei ANTEIL/FESTBETRAG
null.

## drittmittel
NUR bei FEHLBEDARF: Summe aller Drittmittel — "Zuwendung anderer" + "sonstige
Drittmittel" addiert. Wenn keine vorhanden: 0. Bei ANTEIL/FESTBETRAG null.

## zuwendungsbetrag
**Bewilligte Zuwendung / Höchstbetrag** in EUR aus dem Bescheidkopf (z.B.
"Zuwendung wird bewilligt bis zu einem Höchstbetrag von X €") oder Zeile
"VI. Zuwendungen" im Finanzierungsplan. Bei FEHLBEDARF Pflichtwert für
Plausibilitätscheck gegen den aus Gesamtausgaben/Eigenmittel berechneten
Fehlbedarf.

## laufzeit_von / laufzeit_bis
Projektlaufzeit als ISO-Datum "YYYY-MM-DD".
Beispiel: "2026-04-01"

## mittelabruf_verfahren
- ANFORDERUNG: Mittel werden vor den Ausgaben angefordert
- ABRUF: Tagesgenaue Auszahlung nur bei fälliger Zahlung
- ABSCHLAG: Regelmäßige Abschläge nach Zeitplan

## verwaltungspauschale_erlaubt
true wenn der Bescheid eine Verwaltungs- oder Overhead-Pauschale ausdrücklich erlaubt.

## verwaltungspauschale_prozent
Höhe der erlaubten Verwaltungspauschale in Prozent, oder null.
Beispiel: 15 (für 15%)

## budget_flexibilitaet_prozent
Erlaubte prozentuale Abweichung zwischen Kostenpositionen ohne Genehmigung.
Standard laut ANBest-P: 20. Nur setzen wenn im Bescheid explizit genannt.

## overhead_limit_prozent
Maximaler Gemeinkosten-Anteil am Förderbudget in Prozent, oder null.

## mwst_nicht_foerderfahig
true wenn der Bescheid Mehrwertsteuer/Umsatzsteuer explizit von der Förderung ausschließt.
Standardwert bei Nichtnennung: false

## finanzplan_positionen
Array aller Kostenpositionen aus dem Finanzierungsplan oder Kosten- und Finanzierungsplan des Bescheids.
Jeder Eintrag:
- positionscode: Positionsnummer oder -code exakt wie im Bescheid (z.B. "1", "Pos. 2", "A.1", "1.1.1")
- bezeichnung: Bezeichnung der Position exakt wie im Bescheid
- betrag_bewilligt: Bewilligter Betrag in EUR als Zahl
- ueberziehung_limit_pct: Erlaubte Überziehung in Prozent (z.B. 20 für 20%), oder null für Standard
- kostenbereich_code: Passender Code aus der Liste der erlaubten Codes (siehe unten), oder null
- ist_pauschale: true wenn die Position eine Verwaltungspauschale ist (siehe Heuristik unten), sonst false
- pauschale_typ: nur wenn ist_pauschale=true. "FIXER_BETRAG" wenn der Bescheid einen festen EUR-Betrag nennt (häufigster Fall, Berliner LAGeSo/Kommunal); "PROZENT_GESAMT" wenn ein Prozentsatz auf die Gesamtkosten angewendet wird; "PROZENT_PERSONAL" wenn ein Prozentsatz auf die direkten Personalkosten angewendet wird (ESF/BMBF-Standard). Sonst null.
- pauschale_prozent: nur wenn ist_pauschale=true und pauschale_typ in {{PROZENT_GESAMT, PROZENT_PERSONAL}}. Prozentsatz als Zahl (z.B. 13 für 13%). Sonst null.

Pauschale-Erkennungs-Heuristik (für ist_pauschale=true):
Markiere eine Position als Pauschale wenn die Bezeichnung eine der folgenden Sequenzen enthält:
- "anteilig" (z.B. "anteilig Geschäftsstelle", "Buchhaltung anteilig")
- "Pauschale", "pauschal", "Verwaltungspauschale"
- "Gemeinkostenpauschale", "Gemeinkosten-Pauschale"
- "Verwaltungsumlage", "Verwaltungs-Umlage"
- "Overhead-Pauschale", "Overhead pauschal"
- "Gemeinkostenzuschlag", "Verwaltungskostenanteil"

Default-Modus wenn ist_pauschale=true erkannt wurde aber unklar ist: pauschale_typ="FIXER_BETRAG", pauschale_prozent=null (der Bescheid hat einen festen EUR-Betrag). User korrigiert ggf. im Review-Step.

Erlaubte kostenbereich_code-Werte:
{_CODES_BLOCK}

Zuordnungshilfe (SKR42-orientiert, granular):
- Personalkosten, Gehälter, Löhne → PERSONAL_FESTANSTELLUNG
- Honorare, freie Mitarbeit, Werkverträge → PERSONAL_HONORARE
- Ehrenamtliche Aufwandsentschädigung → PERSONAL_EHRENAMT
- Bürobedarf, Papier, Hygieneartikel → SACH_BUERO
- Reise, Fahrtkosten, Übernachtung → SACH_REISE
- Anschaffungen, Geräte → SACH_BESCHAFFUNG
- Öffentlichkeitsarbeit, Druck, Werbung, Flyer → SACH_MARKETING
- Externe Dienstleister (allgemein), Beratung, Gehaltsservice → SACH_DIENSTLEISTUNGEN
- Bewirtung, Verpflegung, Catering → SACH_BEWIRTUNG
- Veranstaltungen, Aktionen, Events → SACH_VERANSTALTUNG
- Programm-/Lernmaterial, Bastelmaterial → SACH_MATERIAL
- Fortbildungen, Schulungen, Seminare → SACH_FORTBILDUNG
- Miete, Pacht, Hausgeld, Raumkosten → MIETE
- Strom, Gas, Heizung, Wasser, Energie → ENERGIE
- Reinigungsdienst, Putzmittel → REINIGUNG
- Sonstige Raumnebenkosten (nicht Energie/Reinigung) → RAUM_NEBENKOSTEN
- Telefon, Internet, Porto, Briefmarken → KOMMUNIKATION
- Software-Lizenzen, SaaS, IT-Wartung → IT_SOFTWARE
- Hardware, Server, Hosting → IT_INFRASTRUKTUR
- Anwalt, Steuerberater, Datenschutz, Notar → RECHTSBERATUNG
- Versicherungen (Haftpflicht, Inventar, Sach) → VERSICHERUNG
- Bankgebühren, Buchungsentgelte → KONTOFUEHRUNG
- Mitgliedsbeiträge in Fachverbänden/Dachorganisationen → MITGLIEDSBEITRAEGE
- Steuern, USt-Voranmeldungen, Finanzamt → STEUERN_ABGABEN
- Sonstige Verwaltung (Fallback) → VERWALTUNG_SONSTIGE
- Eigenmittel, Projekteinnahmen → EINNAHMEN_PROJEKT
- Spenden, Mitgliedsbeiträge der eigenen Organisation → EINNAHMEN_SPENDEN
- Zuwendungen, Förderungen → EINNAHMEN_FOERDERUNG
- AAG-Erstattung, Aufwendungsausgleichsgesetz, Krankengeld-/Mutterschutz-Erstattung → EINNAHMEN_AAG_ERSTATTUNG

## rules
Array der extrahierten Förderregeln und -bedingungen.
Jeder Eintrag:
- typ: einer der Regeltypen (siehe unten)
- schluessel: Kurzbezeichnung der Regel (Pflichtfeld)
- wert: Zahlenwert oder Textwert, oder null
- beschreibung: Erläuterung aus dem Bescheid, oder null

Regeltypen:
- KOSTENKATEGORIE_ERLAUBT: Schlüssel = Kostenart die explizit erlaubt ist
- KOSTENKATEGORIE_VERBOTEN: Schlüssel = Kostenart die nicht förderfähig ist
- BELEGPFLICHT_SPEZIAL: besondere Belegpflichten (z.B. "Stundennachweis Pflicht")
- EIGENANTEIL_MIN: Schlüssel = "Eigenanteil", Wert = Mindestprozentsatz
- VERWENDUNGSFRIST_TAGE: Schlüssel = "Verwendungsfrist", Wert = Anzahl Tage (z.B. "42")
  WICHTIG: Dieser Typ ist NUR für die ANBest-P Mittelverwendungsfrist nach Abruf (typisch 42 Tage).
  NICHT verwenden für:
  - Fristen zur Einreichung des Verwendungsnachweises → stattdessen raw_hinweise
  - Berichtsfristen, Zwischennachweisfristen → stattdessen ZWISCHENNACHWEIS_PFLICHT
  Beispiel korrekt: "Mittel müssen innerhalb von 6 Wochen nach Abruf verausgabt sein" → wert: "42"
  Beispiel falsch: "Verwendungsnachweis ist bis 31.07.2027 einzureichen" → raw_hinweise!
- ZWISCHENNACHWEIS_PFLICHT: Schlüssel = "Zwischennachweis", Wert = "true"
- PERSONALKOSTEN_HOECHSTSATZ: Schlüssel = Qualifikationsstufe (z.B. "AKADEMIKER", "TECHNIKER", "FACHARBEITER"), Wert = max. EUR/Monat

## confidence
Gesamtbewertung der Extraktionsqualität:
- HIGH: Alle Pflichtfelder (name, funder_name, budget_gesamt, laufzeit_von, laufzeit_bis, foerderquote) gefunden
- MEDIUM: 1–3 Pflichtfelder fehlen oder unklar
- LOW: Mehr als 3 Pflichtfelder fehlen

## raw_hinweise
Array von Textpassagen aus dem Bescheid die unklar, widersprüchlich oder für die manuelle Prüfung relevant sind.
Leer lassen wenn keine Unklarheiten.
"""

_PAUSCHALE_TYPEN = {"FIXER_BETRAG", "PROZENT_GESAMT", "PROZENT_PERSONAL"}


def _num(v: Any) -> float | None:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def normalize_extraktion(parsed: dict[str, Any]) -> dict[str, Any]:
    """Faithful port of the post-parse normalization in ocr.ts (Call 2)."""
    positionen_raw = parsed.get("finanzplan_positionen")
    positionen = []
    if isinstance(positionen_raw, list):
        for p in positionen_raw:
            ptyp = p.get("pauschale_typ")
            positionen.append(
                {
                    "positionscode": str(p.get("positionscode") or ""),
                    "bezeichnung": str(p.get("bezeichnung") or ""),
                    "betrag_bewilligt": _num(p.get("betrag_bewilligt")) or 0,
                    "ueberziehung_limit_pct": _num(p.get("ueberziehung_limit_pct")),
                    "kostenbereich_code": p.get("kostenbereich_code")
                    if isinstance(p.get("kostenbereich_code"), str)
                    else None,
                    "ist_pauschale": p.get("ist_pauschale") is True,
                    "pauschale_typ": ptyp if ptyp in _PAUSCHALE_TYPEN else None,
                    "pauschale_prozent": _num(p.get("pauschale_prozent")),
                }
            )

    rules = parsed.get("rules")
    raw_hinweise = parsed.get("raw_hinweise")
    return {
        "name": parsed.get("name") if parsed.get("name") is not None else None,
        "funder_name": parsed.get("funder_name") if parsed.get("funder_name") is not None else None,
        "foerderquote": _num(parsed.get("foerderquote")),
        "finanzierungsart": parsed.get("finanzierungsart") if parsed.get("finanzierungsart") is not None else None,
        "budget_gesamt": _num(parsed.get("budget_gesamt")),
        "eigenmittel": _num(parsed.get("eigenmittel")),
        "drittmittel": _num(parsed.get("drittmittel")),
        "zuwendungsbetrag": _num(parsed.get("zuwendungsbetrag")),
        "laufzeit_von": parsed.get("laufzeit_von") if parsed.get("laufzeit_von") is not None else None,
        "laufzeit_bis": parsed.get("laufzeit_bis") if parsed.get("laufzeit_bis") is not None else None,
        "mittelabruf_verfahren": parsed.get("mittelabruf_verfahren")
        if parsed.get("mittelabruf_verfahren") is not None
        else None,
        "verwaltungspauschale_erlaubt": parsed.get("verwaltungspauschale_erlaubt")
        if parsed.get("verwaltungspauschale_erlaubt") is not None
        else None,
        "verwaltungspauschale_prozent": _num(parsed.get("verwaltungspauschale_prozent")),
        "budget_flexibilitaet_prozent": _num(parsed.get("budget_flexibilitaet_prozent")),
        "overhead_limit_prozent": _num(parsed.get("overhead_limit_prozent")),
        "mwst_nicht_foerderfahig": parsed.get("mwst_nicht_foerderfahig") is True,
        "finanzplan_positionen": positionen,
        "rules": rules if isinstance(rules, list) else [],
        "confidence": parsed.get("confidence") if parsed.get("confidence") is not None else "LOW",
        "raw_hinweise": raw_hinweise if isinstance(raw_hinweise, list) else [],
    }
