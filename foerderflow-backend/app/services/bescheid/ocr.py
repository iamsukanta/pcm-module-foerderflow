"""Mistral OCR + extraction for Förderbescheide — port of lib/bescheid/ocr.ts.

Two-step: (1) Mistral OCR (PDF → markdown), (2) Mistral Small (markdown → structured
JSON via EXTRACTION_PROMPT). 180s timeout each. Raises OcrError(code) on failure.
"""

from __future__ import annotations

import base64
import json
from typing import Any

import httpx

from app.core.config import settings
from app.services.bescheid.extraction_prompt import EXTRACTION_PROMPT, normalize_extraktion

OCR_TIMEOUT_SECONDS = 180.0
OCR_URL = "https://api.mistral.ai/v1/ocr"
CHAT_URL = "https://api.mistral.ai/v1/chat/completions"


class OcrError(Exception):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        self.code = code  # "OCR_TIMEOUT" | "EXTRACTION_FAILED"


def extrahiere_bescheid(pdf_bytes: bytes) -> dict[str, Any]:
    api_key = settings.mistral_api_key
    if not api_key:
        raise OcrError("MISTRAL_API_KEY nicht konfiguriert.", "EXTRACTION_FAILED")

    data_url = f"data:application/pdf;base64,{base64.b64encode(pdf_bytes).decode('ascii')}"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}

    # ── Call 1: Mistral OCR ────────────────────────────────────────────────────
    try:
        ocr_res = httpx.post(
            OCR_URL,
            headers=headers,
            json={
                "model": "mistral-ocr-latest",
                "document": {"type": "document_url", "document_url": data_url},
                "include_image_base64": False,
            },
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise OcrError("Mistral OCR Timeout (180s überschritten).", "OCR_TIMEOUT")
    except httpx.HTTPError as err:
        raise OcrError(f"OCR-Anfrage fehlgeschlagen: {err}", "EXTRACTION_FAILED")

    if ocr_res.status_code >= 400:
        raise OcrError(
            f"Mistral OCR API Fehler {ocr_res.status_code}: {ocr_res.text}", "EXTRACTION_FAILED"
        )
    ocr_data = ocr_res.json()
    ocr_text = "\n\n".join(p.get("markdown", "") for p in (ocr_data.get("pages") or []))

    # ── Call 2: Mistral Small (Extraktion) ─────────────────────────────────────
    try:
        extract_res = httpx.post(
            CHAT_URL,
            headers=headers,
            json={
                "model": "mistral-small-latest",
                "messages": [
                    {"role": "system", "content": EXTRACTION_PROMPT},
                    {"role": "user", "content": ocr_text},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            timeout=OCR_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        raise OcrError("Mistral Extraktion Timeout (180s überschritten).", "OCR_TIMEOUT")
    except httpx.HTTPError as err:
        raise OcrError(f"Extraktion fehlgeschlagen: {err}", "EXTRACTION_FAILED")

    if extract_res.status_code >= 400:
        raise OcrError(
            f"Mistral Extraktion API Fehler {extract_res.status_code}: {extract_res.text}",
            "EXTRACTION_FAILED",
        )

    try:
        extract_data = extract_res.json()
        content = (extract_data.get("choices") or [{}])[0].get("message", {}).get("content") or "{}"
        parsed = json.loads(content)
    except (ValueError, KeyError, IndexError, TypeError) as err:
        raise OcrError(f"Extraktion fehlgeschlagen: {err}", "EXTRACTION_FAILED")

    return normalize_extraktion(parsed)
