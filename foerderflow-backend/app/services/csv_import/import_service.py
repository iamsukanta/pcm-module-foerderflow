"""Import orchestration — port of app/api/protected/transaktionen/import POST+PUT.

POST paths:
  1. explicit profile_id / custom_mapping → parse with that config
  2. auto-detect via builtin profile header pattern
  3. unknown → UNKNOWN_FORMAT (the legacy Finom path is covered by the Finom
     builtin profile in path 2)
PUT: auto-detect preview (no persistence).
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.models.master import FiscalYear
from app.models.transaction import CsvImportProfile, ImportBatch
from app.services.csv_import.builtin_profiles import find_builtin_profile
from app.services.csv_import.detector import auto_detect, strip_bom
from app.services.csv_import.field_hints import suggest_mapping
from app.services.csv_import.parser import parse_csv_with_profile
from app.services.csv_import.persist import check_saldo_consistency, persist_parsed_rows

MAX_FILE_SIZE = 10 * 1024 * 1024


def _profile_to_config(p: CsvImportProfile) -> dict[str, Any]:
    return {
        "delimiter": p.delimiter,
        "encoding": p.encoding,
        "quoteChar": p.quote_char,
        "decimalSeparator": p.decimal_separator,
        "thousandSeparator": p.thousand_separator,
        "dateFormat": p.date_format,
        "headerRow": p.header_row,
        "skipRows": p.skip_rows,
        "columnMappings": p.column_mappings,
    }


class ImportService:
    def __init__(self, db: Session):
        self.db = db

    def run_import(
        self,
        org_id: str,
        user_id: str,
        *,
        filename: str,
        size: int,
        content: str,
        fiscal_year_id: str | None,
        profile_id: str | None = None,
        custom_mapping_json: str | None = None,
        fallback_bank_account_id: str | None = None,
    ) -> dict[str, Any]:
        if not content or not fiscal_year_id:
            raise APIError(400, "MISSING_FIELDS", "Datei und Haushaltsjahr erforderlich.")
        if size > MAX_FILE_SIZE:
            raise APIError(
                400, "FILE_TOO_LARGE", f"Datei zu groß (max. {MAX_FILE_SIZE // 1024 // 1024} MB)."
            )
        fy = self.db.execute(
            select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.org_id == org_id)
        ).scalar_one_or_none()
        if fy is None:
            raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")
        if (fy.status.value if hasattr(fy.status, "value") else fy.status) == "GESCHLOSSEN":
            raise APIError(
                400, "FISCAL_YEAR_CLOSED", "Haushaltsjahr ist geschlossen — keine neuen Importe möglich."
            )

        content_no_bom, _ = strip_bom(content)
        first_line = content_no_bom.split("\n")[0].rstrip("\r")

        # ── Path 1: explicit profile / custom mapping ──
        if profile_id or custom_mapping_json:
            if profile_id:
                dbp = self.db.execute(
                    select(CsvImportProfile).where(
                        CsvImportProfile.id == profile_id,
                        (CsvImportProfile.ist_systemweit.is_(True))
                        | (CsvImportProfile.org_id == org_id),
                    )
                ).scalar_one_or_none()
                if dbp is None:
                    raise APIError(404, "PROFILE_NOT_FOUND", "CSV-Profil nicht gefunden.")
                config = _profile_to_config(dbp)
            else:
                try:
                    config = json.loads(custom_mapping_json)
                except (ValueError, TypeError):
                    raise APIError(  # noqa: B904
                        422, "INVALID_MAPPING", "Ungültige Mapping-Konfiguration (JSON)."
                    )

            result = parse_csv_with_profile(content, config)
            if not result.rows and result.errors:
                raise APIError(
                    422,
                    "PARSE_FAILED",
                    f"Parser-Fehler: {result.errors[0].get('message', 'unbekannt')}",
                    extra={"errors": result.errors[:10]},
                )
            persisted = persist_parsed_rows(
                self.db,
                result.rows,
                org_id=org_id,
                fiscal_year_id=fiscal_year_id,
                user_id=user_id,
                csv_import_profile_id=profile_id,
                fallback_bank_account_id=fallback_bank_account_id,
                dateiname=filename,
                format="GENERIC_CSV",
            )
            saldo = check_saldo_consistency(self.db, org_id, fiscal_year_id, result.rows)
            return {
                "data": {
                    "batch_id": persisted.batch_id,
                    "anzahl_importiert": persisted.anzahl_importiert,
                    "anzahl_duplikate": persisted.anzahl_duplikate,
                    "anzahl_fehler": len(result.errors),
                    "anzahl_auto_matched": persisted.anzahl_auto_matched,
                    "bank_accounts_neu": persisted.bank_accounts_neu,
                    "errors": result.errors[:50],
                    "saldo_check": saldo,
                }
            }

        # ── Path 2: auto-detect builtin profile ──
        builtin = find_builtin_profile(first_line)
        if builtin:
            result = parse_csv_with_profile(content, builtin["config"])
            persisted = persist_parsed_rows(
                self.db,
                result.rows,
                org_id=org_id,
                fiscal_year_id=fiscal_year_id,
                user_id=user_id,
                csv_import_profile_id=None,
                fallback_bank_account_id=fallback_bank_account_id,
                dateiname=filename,
                format="GENERIC_CSV",
            )
            saldo = check_saldo_consistency(self.db, org_id, fiscal_year_id, result.rows)
            # tag batch with systemwide profile id if present
            dbp = self.db.execute(
                select(CsvImportProfile.id).where(
                    CsvImportProfile.name == builtin["name"],
                    CsvImportProfile.ist_systemweit.is_(True),
                )
            ).scalar_one_or_none()
            if dbp:
                batch = self.db.get(ImportBatch, persisted.batch_id)
                if batch:
                    batch.csv_import_profile_id = dbp
                    self.db.commit()
            return {
                "data": {
                    "batch_id": persisted.batch_id,
                    "profile_used": builtin["name"],
                    "anzahl_importiert": persisted.anzahl_importiert,
                    "anzahl_duplikate": persisted.anzahl_duplikate,
                    "anzahl_fehler": len(result.errors),
                    "anzahl_auto_matched": persisted.anzahl_auto_matched,
                    "bank_accounts_neu": persisted.bank_accounts_neu,
                    "errors": result.errors[:50],
                    "saldo_check": saldo,
                }
            }

        # ── Path 3: unknown ──
        raise APIError(
            400,
            "UNKNOWN_FORMAT",
            "CSV-Format nicht automatisch erkannt. Bitte wähle ein Profil aus oder erstelle "
            "ein eigenes Spalten-Mapping.",
            extra={"first_line_sample": first_line[:200]},
        )

    def preview(self, content: str) -> dict[str, Any]:
        detection = auto_detect(content)
        first_line = strip_bom(content)[0].split("\n")[0].rstrip("\r")
        builtin = find_builtin_profile(first_line)
        suggested = suggest_mapping(detection["header"])
        return {
            "data": {
                "detection": detection,
                "builtin_profile": (
                    {"name": builtin["name"], "beschreibung": builtin["beschreibung"]}
                    if builtin
                    else None
                ),
                "suggested_mapping": suggested,
                "preview_rows": content.split("\n")[:5],
            }
        }
