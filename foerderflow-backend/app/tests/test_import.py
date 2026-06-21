"""CSV import system parity tests (detector, parser, persist, profiles, digest)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.master import FiscalYear
from app.models.transaction import Transaction
from app.services.csv_import.detector import auto_detect, tokenize_csv_line
from app.services.csv_import.heuristics import infer_kostenbereich_code
from app.services.csv_import.parser import parse_csv_with_profile


# ── pure unit tests ───────────────────────────────────────────────────────────
def test_tokenizer_quotes_and_delimiter():
    assert tokenize_csv_line('a;"b;c";d', ";") == ["a", "b;c", "d"]
    assert tokenize_csv_line('x,"q""q",z', ",") == ["x", 'q"q', "z"]


def test_auto_detect_semicolon_german():
    csv = "Datum;Name;Betrag\n01.03.2026;Spender;1.234,56\n02.03.2026;Miete;-500,00"
    d = auto_detect(csv)
    assert d["delimiter"] == ";"
    assert d["decimalSeparator"] == ","
    assert d["dateFormat"] == "dd.MM.yyyy"
    assert d["header"] == ["Datum", "Name", "Betrag"]


def test_parser_with_profile():
    csv = "Buchungsdatum,Auftraggeber/Empfänger,Verwendungszweck,Betrag\n01.03.2026,ACME,Rechnung,-100.50"
    config = {
        "delimiter": ",", "encoding": "utf-8", "quoteChar": '"',
        "decimalSeparator": ".", "thousandSeparator": None, "dateFormat": "dd.MM.yyyy",
        "headerRow": 1, "skipRows": 0,
        "columnMappings": {
            "datum": "Buchungsdatum", "auftraggeber": "Auftraggeber/Empfänger",
            "verwendungszweck": "Verwendungszweck", "betrag": "Betrag",
        },
    }
    result = parse_csv_with_profile(csv, config)
    assert len(result.rows) == 1
    assert result.rows[0].betrag == -100.5
    assert result.rows[0].datum == date(2026, 3, 1)
    assert result.rows[0].auftraggeber == "ACME"


def test_heuristics():
    assert infer_kostenbereich_code("Vattenfall", "Strom März") == "ENERGIE"
    assert infer_kostenbereich_code("Telekom Deutschland", None) == "KOMMUNIKATION"
    assert infer_kostenbereich_code("Spender", "Spende 2026") == "EINNAHMEN_SPENDEN"
    assert infer_kostenbereich_code("Random", "nichts") is None


# ── endpoint tests ────────────────────────────────────────────────────────────
@pytest.fixture
def fy(client, db_session, org):
    f = FiscalYear(org_id=org.id, jahr=2026, beginn=date(2026, 1, 1), ende=date(2026, 12, 31))
    db_session.add(f)
    db_session.commit()
    return f.id


def test_import_finom_autodetect(client, fy):
    csv = (
        "Buchungsdatum,Auftraggeber/Empfänger,Verwendungszweck,Betrag\n"
        "01.03.2026,Spender A,Spende,500.00\n"
        "05.03.2026,Vermieter,Miete,-250.00\n"
    )
    r = client.post(
        "/api/protected/transaktionen/import",
        data={"fiscal_year_id": fy},
        files={"file": ("finom.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["profile_used"] == "Finom (CSV Export)"
    assert d["anzahl_importiert"] == 2
    assert d["anzahl_duplikate"] == 0
    # re-import same file -> all duplicates
    r2 = client.post(
        "/api/protected/transaktionen/import",
        data={"fiscal_year_id": fy},
        files={"file": ("finom.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r2.json()["data"]["anzahl_duplikate"] == 2
    assert r2.json()["data"]["anzahl_importiert"] == 0


def test_import_unknown_format(client, fy):
    r = client.post(
        "/api/protected/transaktionen/import",
        data={"fiscal_year_id": fy},
        files={"file": ("x.csv", b"foo|bar|baz\n1|2|3", "text/csv")},
    )
    assert r.status_code == 400 and r.json()["code"] == "UNKNOWN_FORMAT"


def test_import_missing_fiscal_year(client):
    r = client.post(
        "/api/protected/transaktionen/import",
        files={"file": ("x.csv", b"a,b\n1,2", "text/csv")},
    )
    assert r.status_code == 400 and r.json()["code"] == "MISSING_FIELDS"


def test_import_preview(client, fy):
    csv = "Datum;Name;Betrag\n01.03.2026;Spender;1.234,56"
    r = client.put(
        "/api/protected/transaktionen/import",
        files={"file": ("x.csv", csv.encode("utf-8"), "text/csv")},
    )
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["detection"]["delimiter"] == ";"
    assert "preview_rows" in d


def test_csv_profiles(client):
    r = client.get("/api/protected/csv-profiles")
    assert r.status_code == 200  # empty until seeded
    r = client.post(
        "/api/protected/csv-profiles",
        json={"name": "Mein Profil", "delimiter": ";", "decimal_separator": ",",
              "date_format": "dd.MM.yyyy", "column_mappings": {"datum": "D", "betrag": "B", "auftraggeber": "A"}},
    )
    assert r.status_code == 201
    assert r.json()["data"]["name"] == "Mein Profil"
    assert r.json()["data"]["ist_systemweit"] is False


def test_digest(client, db_session, org, fy):
    db_session.add(
        Transaction(
            org_id=org.id, fiscal_year_id=fy, datum=date(2026, 3, 1),
            betrag=Decimal("100"), typ="EINNAHME", status="IMPORTIERT",
            created_at=datetime.now(timezone.utc),
        )
    )
    db_session.commit()
    r = client.get("/api/protected/transaktionen/digest")
    assert r.status_code == 200
    assert r.json()["data"]["total"] >= 1
    assert "ohneRegel" in r.json()["data"]
