"""System-wide reference data seed (org_id IS NULL).

Ports two monolith seeds that the demo/pilot org seeds depend on:
  - Kostenbereiche (SKR42 catalogue) — `prisma/seed-kostenbereiche.ts` (33 rows)
  - TVöD-Bund/Kommunen 2025 tariff table — `prisma/seed.ts` (17×6 = 102 rows)

Idempotent: Kostenbereiche are upserted by `code`; tariff rows are inserted with
duplicate-skip on (tarifwerk, entgeltgruppe, stufe, jahr).

Run:  python -m app.seeds.system_data
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.enums import Tarifwerk
from app.models.master import Kostenbereich
from app.models.payroll import TarifTabelle

# ── Kostenbereich catalogue (4 top groups + 29 sub-categories) ─────────
# (code, bezeichnung, beschreibung, parent_code, ist_personal, ist_gemeinkosten,
#  foerderfahig_default, sort_order, skr42_von, skr42_bis)
_KB: list[dict] = [
    # Ebene 1: Obergruppen
    {"code": "PERSONAL", "bezeichnung": "Personalkosten", "ist_personal": True, "sort_order": 10},
    {"code": "SACHKOSTEN", "bezeichnung": "Sachkosten", "sort_order": 20},
    {"code": "GEMEINKOSTEN", "bezeichnung": "Gemeinkosten / Verwaltung", "ist_gemeinkosten": True, "sort_order": 30},
    {"code": "EINNAHMEN", "bezeichnung": "Einnahmen", "foerderfahig_default": False, "sort_order": 40},
    # Ebene 2: PERSONAL
    {"code": "PERSONAL_FESTANSTELLUNG", "bezeichnung": "Festangestellte", "parent": "PERSONAL", "ist_personal": True, "sort_order": 11, "von": "4000", "bis": "4199"},
    {"code": "PERSONAL_HONORARE", "bezeichnung": "Honorare / Werkverträge", "parent": "PERSONAL", "ist_personal": True, "sort_order": 12, "von": "6510", "bis": "6520"},
    {"code": "PERSONAL_EHRENAMT", "bezeichnung": "Ehrenamtspauschalen", "parent": "PERSONAL", "ist_personal": True, "sort_order": 13, "von": "4380"},
    # Ebene 2: SACHKOSTEN
    {"code": "SACH_BUERO", "bezeichnung": "Bürobedarf", "parent": "SACHKOSTEN", "sort_order": 21, "von": "6815"},
    {"code": "SACH_REISE", "bezeichnung": "Reisekosten", "parent": "SACHKOSTEN", "sort_order": 22, "von": "6660", "bis": "6680"},
    {"code": "SACH_BESCHAFFUNG", "bezeichnung": "Anschaffungen, Geräte", "parent": "SACHKOSTEN", "sort_order": 23, "von": "6700"},
    {"code": "SACH_MARKETING", "bezeichnung": "Werbung, Druck, Öffentlichkeitsarbeit", "parent": "SACHKOSTEN", "sort_order": 24, "von": "6600"},
    {"code": "SACH_DIENSTLEISTUNGEN", "bezeichnung": "Externe Dienstleister", "parent": "SACHKOSTEN", "sort_order": 25, "von": "6300"},
    {"code": "SACH_BEWIRTUNG", "bezeichnung": "Bewirtung, Verpflegung", "parent": "SACHKOSTEN", "foerderfahig_default": False, "sort_order": 26, "von": "6640"},
    {"code": "SACH_VERANSTALTUNG", "bezeichnung": "Veranstaltungen, Aktionen", "parent": "SACHKOSTEN", "sort_order": 27, "von": "6610"},
    {"code": "SACH_MATERIAL", "bezeichnung": "Programm-Material", "parent": "SACHKOSTEN", "sort_order": 28, "von": "6790"},
    {"code": "SACH_FORTBILDUNG", "bezeichnung": "Schulungen, Fortbildungen", "parent": "SACHKOSTEN", "sort_order": 29, "von": "6821"},
    # Ebene 2: GEMEINKOSTEN
    {"code": "MIETE", "bezeichnung": "Miete, Pacht, Hausgeld", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 31, "von": "6310"},
    {"code": "ENERGIE", "bezeichnung": "Strom, Gas, Heizung, Wasser", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 32, "von": "6320"},
    {"code": "REINIGUNG", "bezeichnung": "Raumreinigung, Reinigungsdienst", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 33, "von": "6330"},
    {"code": "RAUM_NEBENKOSTEN", "bezeichnung": "Sonstige Raumnebenkosten", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 34, "von": "6340"},
    {"code": "KOMMUNIKATION", "bezeichnung": "Telefon, Internet, Porto", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 35, "von": "6805"},
    {"code": "IT_SOFTWARE", "bezeichnung": "Software-Lizenzen, Wartung", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 36, "von": "6495"},
    {"code": "IT_INFRASTRUKTUR", "bezeichnung": "Server, Hardware, Hosting", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 37, "von": "6485"},
    {"code": "VERSICHERUNG", "bezeichnung": "Versicherungen", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 38, "von": "6400"},
    {"code": "RECHTSBERATUNG", "bezeichnung": "Anwalt, Steuerberater, Datenschutz, Notar", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 39, "von": "6825"},
    {"code": "KONTOFUEHRUNG", "bezeichnung": "Bankgebühren, Buchungsentgelte", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 40, "von": "6855"},
    {"code": "MITGLIEDSBEITRAEGE", "bezeichnung": "Mitgliedsbeiträge", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "foerderfahig_default": False, "sort_order": 41, "von": "6420"},
    {"code": "STEUERN_ABGABEN", "bezeichnung": "Steuern, Abgaben (Finanzamt)", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "foerderfahig_default": False, "sort_order": 42, "von": "7600", "bis": "7900"},
    {"code": "VERWALTUNG_SONSTIGE", "bezeichnung": "Sonstige Verwaltungskosten", "parent": "GEMEINKOSTEN", "ist_gemeinkosten": True, "sort_order": 43},
    # Ebene 2: EINNAHMEN
    {"code": "EINNAHMEN_FOERDERUNG", "bezeichnung": "Öffentliche Förderungen", "parent": "EINNAHMEN", "foerderfahig_default": False, "sort_order": 51, "von": "8200"},
    {"code": "EINNAHMEN_SPENDEN", "bezeichnung": "Spenden, Mitgliedsbeiträge (Einnahmen)", "parent": "EINNAHMEN", "foerderfahig_default": False, "sort_order": 52, "von": "8400"},
    {"code": "EINNAHMEN_PROJEKT", "bezeichnung": "Projekteinnahmen / Eigenmittel", "parent": "EINNAHMEN", "foerderfahig_default": False, "sort_order": 53, "von": "8100"},
    {"code": "EINNAHMEN_SONSTIGE", "bezeichnung": "Sonstige Einnahmen", "parent": "EINNAHMEN", "foerderfahig_default": False, "sort_order": 54, "von": "8900"},
    {"code": "EINNAHMEN_AAG_ERSTATTUNG", "bezeichnung": "AAG-Erstattung (Aufwendungsausgleichsgesetz)", "parent": "EINNAHMEN", "foerderfahig_default": False, "sort_order": 55, "von": "4170"},
]

# TVöD Bund/Kommunen 2025 — representative values (anchors E9a S1=3448, S6=4713).
_TVOEDD_2025: dict[str, list[int]] = {
    "E1": [2300, 2450, 2530, 2600, 2680, 2800],
    "E2": [2500, 2650, 2730, 2800, 2880, 2980],
    "E3": [2620, 2780, 2860, 2940, 3020, 3130],
    "E4": [2750, 2910, 2990, 3080, 3160, 3270],
    "E5": [2900, 3070, 3160, 3250, 3340, 3500],
    "E6": [3050, 3220, 3320, 3420, 3520, 3680],
    "E7": [3200, 3390, 3490, 3600, 3710, 3880],
    "E8": [3350, 3550, 3660, 3780, 3900, 4080],
    "E9a": [3448, 3650, 3780, 3920, 4080, 4713],
    "E9b": [3600, 3810, 3940, 4090, 4260, 4900],
    "E9c": [3750, 3970, 4110, 4270, 4450, 5100],
    "E10": [4100, 4340, 4490, 4660, 4850, 5560],
    "E11": [4500, 4760, 4930, 5120, 5330, 6100],
    "E12": [4900, 5190, 5380, 5590, 5820, 6650],
    "E13": [5000, 5490, 5710, 5960, 6230, 7000],
    "E14": [5500, 6040, 6290, 6580, 6890, 7700],
    "E15": [6000, 6590, 6870, 7200, 7550, 8400],
}


def seed_kostenbereiche(db: Session) -> int:
    """Upsert the SKR42 Kostenbereich catalogue by `code`. Returns row count."""
    parent_id: dict[str, str] = {}
    # Top groups first (so children can resolve parent_id).
    for item in sorted(_KB, key=lambda k: ("parent" in k, k["sort_order"])):
        row = db.execute(
            select(Kostenbereich).where(Kostenbereich.code == item["code"])
        ).scalar_one_or_none()
        values = dict(
            bezeichnung=item["bezeichnung"],
            beschreibung=item.get("beschreibung"),
            parent_id=parent_id.get(item.get("parent")) if item.get("parent") else None,
            org_id=None,
            skr42_konto_von=item.get("von"),
            skr42_konto_bis=item.get("bis"),
            ist_personal=item.get("ist_personal", False),
            ist_gemeinkosten=item.get("ist_gemeinkosten", False),
            belegpflicht_default=item.get("belegpflicht_default", True),
            foerderfahig_default=item.get("foerderfahig_default", True),
            sort_order=item.get("sort_order", 0),
        )
        if row:
            for k, v in values.items():
                setattr(row, k, v)
        else:
            row = Kostenbereich(code=item["code"], **values)
            db.add(row)
        db.flush()
        parent_id[item["code"]] = row.id
    return len(_KB)


def seed_tvoedd_2025(db: Session) -> int:
    """Insert TVöD-D 2025 tariff rows (skip existing). Returns rows added."""
    existing = {
        (eg, st)
        for eg, st in db.execute(
            select(TarifTabelle.entgeltgruppe, TarifTabelle.stufe).where(
                TarifTabelle.tarifwerk == Tarifwerk.TVOEDD, TarifTabelle.jahr == 2025
            )
        ).all()
    }
    added = 0
    for gruppe, stufen in _TVOEDD_2025.items():
        for idx, betrag in enumerate(stufen):
            stufe = idx + 1
            if (gruppe, stufe) in existing:
                continue
            db.add(
                TarifTabelle(
                    tarifwerk=Tarifwerk.TVOEDD,
                    entgeltgruppe=gruppe,
                    stufe=stufe,
                    jahr=2025,
                    betrag=Decimal(betrag),
                )
            )
            added += 1
    db.flush()
    return added


def seed(db: Session) -> None:
    n_kb = seed_kostenbereiche(db)
    n_tarif = seed_tvoedd_2025(db)
    db.commit()
    print(f"[seed] system data: {n_kb} Kostenbereiche, +{n_tarif} TVöD-D 2025 rows.")


def main() -> None:
    db = SessionLocal()
    try:
        seed(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
