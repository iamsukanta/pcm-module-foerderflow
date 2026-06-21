"""import-bescheid (Mistral OCR) parity tests — validation + error mapping +
normalization. The live Mistral calls are monkeypatched."""

from __future__ import annotations

PDF = b"%PDF-1.4\n%fake\n"


def test_no_file(client):
    r = client.post("/api/protected/foerdermassnahmen/import-bescheid", data={"x": "1"})
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"


def test_wrong_mime(client):
    r = client.post(
        "/api/protected/foerdermassnahmen/import-bescheid",
        files={"file": ("a.txt", b"hi", "text/plain")},
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"


def test_too_large(client):
    big = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024 + 1)
    r = client.post(
        "/api/protected/foerdermassnahmen/import-bescheid",
        files={"file": ("a.pdf", big, "application/pdf")},
    )
    assert r.status_code == 400 and r.json()["code"] == "FILE_TOO_LARGE"


def test_no_api_key_extraction_failed(client):
    # default settings.mistral_api_key == "" → OcrError EXTRACTION_FAILED → 502
    r = client.post(
        "/api/protected/foerdermassnahmen/import-bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 502 and r.json()["code"] == "EXTRACTION_FAILED"


def test_success_monkeypatched(client, monkeypatch):
    import app.services.bescheid.ocr as ocr

    def _fake(pdf_bytes):
        return ocr.normalize_extraktion(
            {
                "name": "Projekt X",
                "funder_name": "Stiftung Y",
                "foerderquote": 80,
                "budget_gesamt": 50000.0,
                "finanzplan_positionen": [
                    {"positionscode": "1", "bezeichnung": "Personal", "betrag_bewilligt": 30000}
                ],
            }
        )

    monkeypatch.setattr(ocr, "extrahiere_bescheid", _fake)
    r = client.post(
        "/api/protected/foerdermassnahmen/import-bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["name"] == "Projekt X"
    assert d["foerderquote"] == 80
    assert d["mwst_nicht_foerderfahig"] is False
    assert d["confidence"] == "LOW"
    assert d["rules"] == []
    assert d["finanzplan_positionen"][0]["ist_pauschale"] is False


def test_timeout_monkeypatched(client, monkeypatch):
    import app.services.bescheid.ocr as ocr

    def _fake(pdf_bytes):
        raise ocr.OcrError("timeout", "OCR_TIMEOUT")

    monkeypatch.setattr(ocr, "extrahiere_bescheid", _fake)
    r = client.post(
        "/api/protected/foerdermassnahmen/import-bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 504 and r.json()["code"] == "OCR_TIMEOUT"


def test_normalize_defaults():
    from app.services.bescheid.extraction_prompt import normalize_extraktion

    out = normalize_extraktion({})
    assert out["name"] is None
    assert out["mwst_nicht_foerderfahig"] is False
    assert out["finanzplan_positionen"] == []
    assert out["rules"] == []
    assert out["raw_hinweise"] == []
    assert out["confidence"] == "LOW"
    assert out["foerderquote"] is None


def test_normalize_position_coercion():
    from app.services.bescheid.extraction_prompt import normalize_extraktion

    out = normalize_extraktion(
        {
            "finanzplan_positionen": [
                {
                    "positionscode": 5,
                    "betrag_bewilligt": "not-a-number",
                    "ist_pauschale": True,
                    "pauschale_typ": "GARBAGE",
                },
            ]
        }
    )
    p = out["finanzplan_positionen"][0]
    assert p["positionscode"] == "5"
    assert p["betrag_bewilligt"] == 0  # non-number → 0
    assert p["ist_pauschale"] is True
    assert p["pauschale_typ"] is None  # invalid enum → None
