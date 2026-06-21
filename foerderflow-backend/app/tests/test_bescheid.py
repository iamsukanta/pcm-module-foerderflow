"""Bescheid (Zuwendungsbescheid PDF) parity tests."""

from __future__ import annotations

import pytest

PDF = b"%PDF-1.4\n%fake pdf bytes\n"


@pytest.fixture
def measure(client):
    fid = client.post("/api/protected/funder", json={"name": "Funder", "typ": "STIFTUNG"}).json()["data"]["id"]
    return client.post(
        "/api/protected/foerdermassnahmen",
        json={
            "funder_id": fid, "name": "Maßnahme", "budget_gesamt": 100000, "foerderquote": 80,
            "laufzeit_von": "2026-01-01", "laufzeit_bis": "2026-03-31", "mittelabruf_verfahren": "ABRUF",
        },
    ).json()["data"]["id"]


def test_get_none(client, measure):
    r = client.get(f"/api/protected/foerdermassnahmen/{measure}/bescheid")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_upload_and_get(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("Bescheid ß.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["filename"] == "Bescheid ß.pdf"
    assert d["mime_type"] == "application/pdf"
    assert d["size_bytes"] == len(PDF)
    assert d["quelle"] == "MANUAL_UPLOAD"

    g = client.get(f"/api/protected/foerdermassnahmen/{measure}/bescheid")
    assert g.status_code == 200
    assert g.content == PDF
    assert g.headers["content-type"].startswith("application/pdf")
    assert "filename*=UTF-8''" in g.headers["content-disposition"]


def test_upload_quelle_ocr(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        data={"quelle": "OCR_IMPORT"},
        files={"file": ("b.pdf", PDF, "application/pdf")},
    )
    assert r.json()["data"]["quelle"] == "OCR_IMPORT"


def test_upload_invalid_quelle_falls_back(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        data={"quelle": "GARBAGE"},
        files={"file": ("b.pdf", PDF, "application/pdf")},
    )
    assert r.json()["data"]["quelle"] == "MANUAL_UPLOAD"


def test_upsert_replaces(client, measure):
    r1 = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    ).json()["data"]
    new = PDF + b"more"
    r2 = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("b.pdf", new, "application/pdf")},
    ).json()["data"]
    assert r2["id"] == r1["id"]
    assert r2["filename"] == "b.pdf"
    assert r2["size_bytes"] == len(new)
    assert client.get(f"/api/protected/foerdermassnahmen/{measure}/bescheid").content == new


def test_upload_wrong_mime(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("a.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"


def test_upload_no_file(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        data={"quelle": "MANUAL_UPLOAD"},
    )
    assert r.status_code == 400 and r.json()["code"] == "INVALID_FILE_TYPE"


def test_upload_empty(client, measure):
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("a.pdf", b"", "application/pdf")},
    )
    assert r.status_code == 400 and r.json()["code"] == "FILE_EMPTY"


def test_upload_too_large(client, measure):
    big = b"%PDF-1.4\n" + b"x" * (10 * 1024 * 1024 + 1)
    r = client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("a.pdf", big, "application/pdf")},
    )
    assert r.status_code == 400 and r.json()["code"] == "FILE_TOO_LARGE"


def test_upload_measure_not_found(client):
    r = client.post(
        "/api/protected/foerdermassnahmen/nope/bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"


def test_delete(client, measure):
    client.post(
        f"/api/protected/foerdermassnahmen/{measure}/bescheid",
        files={"file": ("a.pdf", PDF, "application/pdf")},
    )
    r = client.delete(f"/api/protected/foerdermassnahmen/{measure}/bescheid")
    assert r.status_code == 200, r.text
    assert "id" in r.json()["data"]
    assert client.get(f"/api/protected/foerdermassnahmen/{measure}/bescheid").status_code == 404


def test_delete_none(client, measure):
    r = client.delete(f"/api/protected/foerdermassnahmen/{measure}/bescheid")
    assert r.status_code == 404 and r.json()["code"] == "NOT_FOUND"
