"""Kostenbereich heuristics — port of lib/import/heuristics.ts.

Infers a Kostenbereich code (SKR42 taxonomy) from auftraggeber + verwendungszweck
(+ buchungstext_typ), specific-first. Returns the code string or None; the
persistence layer maps unknown codes to NULL via the org's taxonomy.
"""

from __future__ import annotations

import re


def infer_kostenbereich_code(
    auftraggeber: str | None,
    verwendungszweck: str | None,
    buchungstext_typ: str | None = None,
) -> str | None:
    ag = (auftraggeber or "").lower()
    vz = (verwendungszweck or "").lower()
    bt = (buchungstext_typ or "").lower()
    combined = f"{ag} {vz} {bt}"

    def has(*subs: str) -> bool:
        return any(s in combined for s in subs)

    # Bank-Buchhaltung
    if (
        bt == "abschluss"
        or "entgelt" in bt
        or has("kontogebühr", "kontoführungsentgelt", "kontofuehrungsentgelt",
               "buchungspostenentgelt", "buchungsposten")
    ):
        return "KONTOFUEHRUNG"

    # AAG-Erstattung (before Spende)
    if (
        has("aufwendungsausgleich", "aag-erstattung", "aag erstattung",
            "krankengeld-erstattung", "krankengelderstattung", "u1-erstattung",
            "u2-erstattung", "mutterschutz-erstattung", "mutterschaftsgeld-erstattung")
        or ("erstattung" in combined
            and re.search(r"aok|tk|techniker krankenkasse|barmer|dak|knappschaft|ikk|bkk|krankenkasse", ag))
    ):
        return "EINNAHMEN_AAG_ERSTATTUNG"

    # Spendengutschriften
    if "spendengutschrift" in bt or ("spende" in combined and "mitgliedsbeitrag" not in combined):
        return "EINNAHMEN_SPENDEN"

    # Personalkosten
    if has("gehalt", "lohn", "gehaltsabrechnung"):
        return "PERSONAL_FESTANSTELLUNG"

    if re.search(r"winheller|kanzlei|partnerschaftsges|partmbb|lachnit|pirron|notar", ag):
        return "RECHTSBERATUNG"

    if has("honorar", "werkvertrag"):
        return "PERSONAL_HONORARE"

    # Konkrete Anbieter
    if re.search(r"vattenfall|naturstrom|gasag|stadtwerke|eprimo|mainova|e\.on|enbw|rwe", ag) or re.search(
        r"vattenfall|naturstrom|gasag|stadtwerke|eprimo|mainova", combined
    ):
        return "ENERGIE"

    if re.search(r"asc alster|asc-alster|asc[ -]?alsterservice|mitrovic|fit und clean|putzdienst", combined):
        return "REINIGUNG"

    if re.search(r"telekom|vodafone|fonial|drillisch|m-net|telefonica|o2 germany|congstar", ag):
        return "KOMMUNIKATION"

    if any(s in ag for s in ("domainfactory", "ionos", "hetzner", "hostinger", "aws", "cloudflare", "vercel")):
        return "IT_INFRASTRUKTUR"

    if re.search(r"microsoft|msft|adobe|personio|supabase|github|google workspace|google ireland|figma|notion|zoom", ag):
        return "IT_SOFTWARE"

    if re.search(r"linkedin|meta platforms|facebook ireland", ag):
        return "SACH_MARKETING"

    if re.search(r"union versicherung|bgw|haftpflicht|allianz|axa versicherung|debeka|gothaer", ag):
        return "VERSICHERUNG"

    if (
        has("deutschlandticket", "bahnticket", "fahrkarte")
        or "db vertrieb" in ag
        or "deutsche bahn" in ag
    ):
        return "SACH_REISE"

    if "stadtpension" in ag or has("hotel", "unterkunft"):
        return "SACH_REISE"

    # Steuern
    if (
        has("umsatzsteuer", "ust-voranmeldung", "ust voranmeldung", "mehrwertsteuer")
        or ("finanzamt" in combined and has("steuer", "mwst", "vorauszahlung"))
    ):
        return "STEUERN_ABGABEN"

    # Bezeichnungs-/VZ-Schlüsselwörter
    if re.search(r"(strom|gas|heizung|fernwärme|wasser)\b", combined) or re.search(r"\benergie\b", combined):
        return "ENERGIE"
    if re.search(r"reinigung|putzdienst", combined):
        return "REINIGUNG"
    if re.search(r"miete|hausgeld|pacht", combined):
        return "MIETE"
    if re.search(r"raumnebenkost|nebenkosten", combined):
        return "RAUM_NEBENKOSTEN"
    if re.search(r"telefon|internet|porto|briefmarken|dhl|deutsche post", combined):
        return "KOMMUNIKATION"
    if re.search(r"software|saas|lizenz", combined):
        return "IT_SOFTWARE"
    if re.search(r"hosting|server|domain\b", combined):
        return "IT_INFRASTRUKTUR"
    if re.search(r"anwalt|kanzlei|steuerber|datenschutzber|notar|rechtsber", combined):
        return "RECHTSBERATUNG"
    if re.search(r"versicherung\b", combined):
        return "VERSICHERUNG"
    if re.search(r"mitgliedsbeitrag\b", combined) and not re.search(r"spende", combined):
        return "MITGLIEDSBEITRAEGE"
    if re.search(r"fortbildung|schulung|seminar|workshop\b", combined):
        return "SACH_FORTBILDUNG"
    if re.search(r"marketing|werbung|werbeanzeige|öffentlichkeitsarbeit|flyer|broschüre", combined):
        return "SACH_MARKETING"
    if re.search(r"veranstaltung|event\b|tagung", combined):
        return "SACH_VERANSTALTUNG"
    if re.search(r"bewirtung|verpflegung|catering", combined):
        return "SACH_BEWIRTUNG"
    if re.search(r"material|lernmaterial|bastelmaterial", combined):
        return "SACH_MATERIAL"
    if re.search(r"bürobedarf|büromaterial|papier|hygiene", combined):
        return "SACH_BUERO"

    if has("förder", "zuwendung"):
        return "EINNAHMEN_FOERDERUNG"

    return None
