"""/api/protected/foerdermassnahmen — FundingMeasure CRUD (domain core)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.foerdermassnahme_service import FoerdermassnahmeService
from app.services.foerdermassnahme_subresource_service import (
    FoerdermassnahmeSubresourceService,
)

router = APIRouter(tags=["foerdermassnahmen"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


@router.get("/foerdermassnahmen")
def list_measures(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    status_filter = request.query_params.get("status")
    funder_id = request.query_params.get("funder_id")
    return {"data": FoerdermassnahmeService(db).list(ctx.org_id, status_filter, funder_id)}


@router.post("/foerdermassnahmen", status_code=status.HTTP_201_CREATED)
async def create_measure(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    m = FoerdermassnahmeService(db).create(ctx.org_id, body)
    return {"data": m, "message": f'Fördermassnahme „{m["name"]}" wurde erfolgreich angelegt.'}


# ── Bescheid OCR import (Mistral) — registered before /foerdermassnahmen/{id_} ─
@router.post("/foerdermassnahmen/import-bescheid")
async def import_bescheid(
    request: Request,
    _ctx: OrgContext = Depends(get_org_context),
    _db: Session = Depends(get_db),
) -> dict[str, Any]:
    from fastapi.responses import JSONResponse

    from app.services.bescheid.ocr import OcrError, extrahiere_bescheid

    MAX = 10 * 1024 * 1024
    try:
        form = await request.form()
    except Exception:
        raise APIError(400, "INVALID_FORM", "Ungültige Formulardaten.")
    file = form.get("file")
    if file is None or isinstance(file, str) or not hasattr(file, "read"):
        raise APIError(400, "INVALID_FILE_TYPE", "Kein Datei-Upload gefunden.")
    if (file.content_type or "") != "application/pdf":
        raise APIError(400, "INVALID_FILE_TYPE", "Nur PDF-Dateien werden unterstützt.")
    content = await file.read()
    if len(content) > MAX:
        raise APIError(400, "FILE_TOO_LARGE", "Datei ist zu groß (max. 10 MB).")
    try:
        return {"data": extrahiere_bescheid(content)}
    except OcrError as err:
        if err.code == "OCR_TIMEOUT":
            return JSONResponse(
                status_code=504,
                content={
                    "error": "OCR-Verarbeitung hat zu lange gedauert. Bitte erneut versuchen.",
                    "code": "OCR_TIMEOUT",
                },
            )
        return JSONResponse(
            status_code=502,
            content={
                "error": "Mistral konnte den Bescheid nicht verarbeiten. Bitte in einer Minute erneut versuchen.",
                "code": "EXTRACTION_FAILED",
            },
        )


@router.get("/foerdermassnahmen/{id_}")
def get_measure(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": FoerdermassnahmeService(db).get(ctx.org_id, id_)}


@router.get("/foerdermassnahmen/{id_}/ampel")
def ampel(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from sqlalchemy import func, select

    from app.models.funding import FundingMeasure
    from app.models.master import CostCenter
    from app.models.transaction import FundAllocation, TransactionSplit
    from app.services.ampel import berechne_ampel
    from app.utils.serialization import decimal_str

    m = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if m is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    betrag_bewilligt = float(m.budget_gesamt)
    betrag_ist = float(
        db.execute(
            select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
            .where(FundAllocation.funding_measure_id == id_, FundAllocation.org_id == ctx.org_id)
        ).scalar_one() or 0
    )
    overhead_ist = float(
        db.execute(
            select(func.coalesce(func.sum(FundAllocation.betrag_foerderfahig * FundAllocation.prozent / 100), 0))
            .select_from(FundAllocation)
            .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
            .join(CostCenter, CostCenter.id == TransactionSplit.cost_center_id)
            .where(
                FundAllocation.funding_measure_id == id_,
                FundAllocation.org_id == ctx.org_id,
                CostCenter.typ == "OVERHEAD",
            )
        ).scalar_one() or 0
    )
    overhead_ist_prozent = (overhead_ist / betrag_ist * 100) if betrag_ist > 0 else 0
    result = berechne_ampel(
        betrag_bewilligt=betrag_bewilligt,
        betrag_ist=betrag_ist,
        laufzeit_von=m.laufzeit_von,
        laufzeit_bis=m.laufzeit_bis,
        overhead_limit_prozent=float(m.overhead_limit_prozent) if m.overhead_limit_prozent is not None else None,
        overhead_ist_prozent=overhead_ist_prozent,
    )
    return {
        "data": {
            "status": result.status,
            "ausschoepfung_prozent": result.ausschoepfung_prozent,
            "gruende": result.gruende,
            "betrag_ist": decimal_str(betrag_ist),
            "betrag_bewilligt": decimal_str(betrag_bewilligt),
        }
    }


@router.get("/foerdermassnahmen/{id_}/prognose")
def prognose(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.funding import FundingMeasure
    from app.models.transaction import FundAllocation, Transaction, TransactionSplit
    from app.services.jahresendprognose import berechne_jahresendprognose

    m = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if m is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    rows = db.execute(
        select(FundAllocation.betrag_foerderfahig, Transaction.datum)
        .select_from(FundAllocation)
        .join(TransactionSplit, FundAllocation.transaction_split_id == TransactionSplit.id)
        .join(Transaction, TransactionSplit.transaction_id == Transaction.id)
        .where(FundAllocation.funding_measure_id == id_, FundAllocation.org_id == ctx.org_id)
    ).all()
    allocations = [{"datum": datum, "betrag_foerderfahig": float(betrag)} for betrag, datum in rows]
    betrag_bewilligt = float(m.budget_gesamt)
    result = berechne_jahresendprognose(
        laufzeit_bis=m.laufzeit_bis, allocations=allocations, betrag_bewilligt=betrag_bewilligt
    )
    return {
        "data": {
            "monatsrate": result.monatsrate,
            "betrag_ist_gesamt": result.betrag_ist_gesamt,
            "prognose_gesamt": result.prognose_gesamt,
            "prognose_prozent": result.prognose_prozent,
            "days_remaining": result.days_remaining,
            "status": result.status,
            "betrag_bewilligt": f"{betrag_bewilligt:.2f}",
        }
    }


@router.get("/foerdermassnahmen/{id_}/preflight")
def preflight(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from datetime import date as _date
    from datetime import datetime as _dt

    from sqlalchemy import and_, exists, func, select
    from sqlalchemy.orm import selectinload

    from app.models.booking_rule import BookingRuleApplication
    from app.models.funding import FundingMeasure, FundingMeasureCostCenter
    from app.models.transaction import FundAllocation, Transaction, TransactionSplit
    from app.services.finanzplan_ist import aggregate_ist_by_finanzplan_position

    m = db.execute(
        select(FundingMeasure)
        .where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
        .options(
            selectinload(FundingMeasure.cost_centers),
            selectinload(FundingMeasure.finanzplan_positionen),
        )
    ).scalar_one_or_none()
    if m is None:
        raise APIError(404, "MEASURE_NOT_FOUND", "Fördermassnahme nicht gefunden.")
    kst_ids = [cc.cost_center_id for cc in m.cost_centers]

    zv = request.query_params.get("zeitraum_von")
    zb = request.query_params.get("zeitraum_bis")

    def _pd(v):
        try:
            return _date.fromisoformat(v[:10]) if v else None
        except ValueError:
            return None

    dvon, dbis = _pd(zv), _pd(zb)

    def _date_conds():
        c = []
        if dvon:
            c.append(Transaction.datum >= dvon)
        if dbis:
            c.append(Transaction.datum <= dbis)
        return c

    def _count(extra_split=None, orange=False):
        if not kst_ids:
            return 0
        split_inner = [
            TransactionSplit.transaction_id == Transaction.id,
            TransactionSplit.cost_center_id.in_(kst_ids),
        ]
        if extra_split is not None:
            split_inner.append(extra_split)
        conds = [Transaction.org_id == ctx.org_id, *_date_conds(), exists().where(and_(*split_inner))]
        if orange:
            conds.append(
                exists().where(
                    and_(
                        BookingRuleApplication.transaction_id == Transaction.id,
                        BookingRuleApplication.confidence == "ORANGE",
                    )
                )
            )
        return int(db.execute(select(func.count(Transaction.id)).where(and_(*conds))).scalar_one() or 0)

    alloc_exists = exists().where(
        and_(
            FundAllocation.transaction_split_id == TransactionSplit.id,
            FundAllocation.funding_measure_id == id_,
        )
    )
    total_tx = _count()
    tx_zugeordnet = _count(extra_split=alloc_exists)
    tx_unzugeordnet = _count(extra_split=~alloc_exists)
    tx_orange = _count(orange=True)

    ist_map = aggregate_ist_by_finanzplan_position(db, id_, ctx.org_id)
    positions_total = len(m.finanzplan_positionen)
    positions_with_ist = sum(1 for v in ist_map.values() if v > 0)
    positions_ohne_ist = positions_total - positions_with_ist

    drill_base = f"/dashboard/transaktionen?funding_measure_id={id_}"
    drill_orange = "/dashboard/transaktionen?confidence=ORANGE" + (f"&datum_von={zv}" if zv else "") + (f"&datum_bis={zb}" if zb else "")
    drill_unassigned = "/dashboard/transaktionen?has_massnahme=false" + (f"&datum_von={zv}" if zv else "") + (f"&datum_bis={zb}" if zb else "")

    return {
        "data": {
            "total_tx": total_tx,
            "tx_zugeordnet": tx_zugeordnet,
            "tx_unzugeordnet": tx_unzugeordnet,
            "tx_orange": tx_orange,
            "positions_total": positions_total,
            "positions_with_ist": positions_with_ist,
            "positions_ohne_ist": positions_ohne_ist,
            "ready": tx_unzugeordnet == 0 and tx_orange == 0 and positions_ohne_ist == 0,
            "drilldowns": {
                "zugeordnet": drill_base,
                "unzugeordnet": drill_unassigned,
                "orange": drill_orange,
            },
        }
    }


@router.get("/foerdermassnahmen/{id_}/fehlbedarf-status")
def fehlbedarf_status(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.fehlbedarf_compliance import get_fehlbedarf_status

    result = get_fehlbedarf_status(db, id_, ctx.org_id)
    if result is None:
        return {"data": {"status": {"active": False}}}
    return {
        "data": {
            "status": {
                "active": True,
                "hoechstbetrag": result["zuwendung_hoechstbetrag"],
                "abgerufen": result["zuwendung_abgerufen"],
                "drittmittel_ist": result["drittmittel_ist"],
                "eigenmittel_ist": result["eigenmittel_ist"],
                "eigenmittel_plan": result["eigenmittel_plan"],
                "verbleibend": result["verbleibend_abrufbar"],
                "status": result["status"],
            }
        }
    }


@router.get("/foerdermassnahmen/{id_}/compliance-status")
def compliance_status(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Full Fehlbedarf compliance result (FehlbedarfStatusResult) for the detail
    page banner + cross-financing widget, or null if not applicable."""
    from app.services.fehlbedarf_compliance import get_fehlbedarf_status

    return {"data": get_fehlbedarf_status(db, id_, ctx.org_id)}


@router.get("/foerdermassnahmen/{id_}/bescheid/meta")
def bescheid_meta(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    """Bescheid document metadata (no bytes) for the detail page's Bescheid tab."""
    from app.services.bescheid_service import BescheidService

    try:
        dok = BescheidService(db).get(ctx.org_id, id_)
    except APIError:
        return {"data": None}
    return {
        "data": {
            "id": dok.id,
            "filename": dok.filename,
            "size_bytes": dok.size_bytes,
            "uploaded_at": dok.uploaded_at.isoformat() if dok.uploaded_at else None,
            "quelle": dok.quelle.value if hasattr(dok.quelle, "value") else dok.quelle,
        }
    }


@router.patch("/foerdermassnahmen/{id_}")
async def update_measure(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    m = FoerdermassnahmeService(db).update(ctx.org_id, id_, body)
    return {"data": m, "message": f'Fördermassnahme „{m["name"]}" wurde aktualisiert.'}


@router.delete("/foerdermassnahmen/{id_}")
def delete_measure(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    hard = request.query_params.get("hard") == "true"
    return JSONResponse(content=FoerdermassnahmeService(db).delete(ctx.org_id, id_, hard))


# ── bescheid (PDF in DB) ─────────────────────────────────────────────────────
@router.get("/foerdermassnahmen/{id_}/bescheid")
def get_bescheid(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
):
    from urllib.parse import quote

    from fastapi.responses import Response

    from app.services.bescheid_service import BescheidService

    dok = BescheidService(db).get(ctx.org_id, id_)
    safe = quote(dok.filename)
    return Response(
        content=bytes(dok.bytes),
        media_type=dok.mime_type,
        headers={
            "Content-Disposition": f"inline; filename*=UTF-8''{safe}",
            "Cache-Control": "private, no-store",
        },
    )


@router.post("/foerdermassnahmen/{id_}/bescheid")
async def upload_bescheid(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.bescheid_service import BescheidService

    svc = BescheidService(db)
    svc.ensure_uploadable(ctx.org_id, id_)
    try:
        form = await request.form()
    except Exception:
        raise APIError(400, "INVALID_FORM", "Ungültige Formulardaten.")
    file = form.get("file")
    # A real upload is an UploadFile (has .read / .filename); plain fields are str.
    if file is None or isinstance(file, str) or not hasattr(file, "read"):
        raise APIError(400, "INVALID_FILE_TYPE", "Kein Datei-Upload gefunden.")
    content = await file.read()
    quelle = form.get("quelle")
    return svc.upsert(
        ctx.org_id, id_, file.filename or "bescheid.pdf",
        file.content_type or "application/octet-stream", content,
        quelle if isinstance(quelle, str) else None,
    )


@router.delete("/foerdermassnahmen/{id_}/bescheid")
def delete_bescheid(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.bescheid_service import BescheidService

    return BescheidService(db).delete(ctx.org_id, id_)


# ── umlage drilldown preview ─────────────────────────────────────────────────
@router.get(
    "/foerdermassnahmen/{id_}/finanzplan-positionen/{pos_id}/umlage-preview"
)
def umlage_preview(
    id_: str,
    pos_id: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    from app.services.umlage_preview_service import UmlagePreviewService

    return UmlagePreviewService(db).preview(ctx.org_id, id_, pos_id)


# ── finanzplan grid ──────────────────────────────────────────────────────────
@router.get("/foerdermassnahmen/{id_}/finanzplan")
def get_finanzplan(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.finanzplan_grid import FinanzplanGridService

    data = FinanzplanGridService(db).load(ctx.org_id, id_)
    if data is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    return {"data": data}


@router.post("/foerdermassnahmen/{id_}/finanzplan")
async def post_finanzplan(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.finanzplan_grid import FinanzplanGridService

    body = await _json_body(request)
    return FinanzplanGridService(db).batch_upsert(ctx.org_id, id_, body)


@router.delete("/foerdermassnahmen/{id_}/finanzplan")
def delete_finanzplan(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.finanzplan_grid import FinanzplanGridService

    return FinanzplanGridService(db).delete(ctx.org_id, id_, request.query_params.get("quelle"))


@router.post("/foerdermassnahmen/{id_}/finanzplan/personalmodul")
def finanzplan_personalmodul(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.funding import FundingMeasure

    # Deliberate stub (parity): mapping UI not implemented → always KST_MAPPING_REQUIRED.
    m = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if m is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    if (m.status.value if hasattr(m.status, "value") else m.status) == "WIDERRUFEN":
        raise APIError(422, "MEASURE_REVOKED", "Massnahme ist widerrufen — keine Änderungen möglich.")
    raise APIError(
        422,
        "KST_MAPPING_REQUIRED",
        "Bitte konfiguriere zuerst die Kostenstellen-Zuordnung für diese Massnahme, "
        "bevor du Personalkosten übernimmst.",
    )


# ── reporting sub-resources ──────────────────────────────────────────────────
@router.get("/foerdermassnahmen/{id_}/soll-ist-position")
def soll_ist_position(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.models.funding import FundingMeasure
    from app.services.soll_ist_position import load_soll_ist_position

    if db.execute(
        select(FundingMeasure.id).where(
            FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id
        )
    ).scalar_one_or_none() is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    return {"data": load_soll_ist_position(db, id_, ctx.org_id)}


@router.get("/foerdermassnahmen/{id_}/verwendungsnachweis/preview")
def verwendungsnachweis_preview(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.verwendungsnachweis_service import VerwendungsnachweisService

    return VerwendungsnachweisService(db).preview(ctx.org_id, id_)


@router.get("/foerdermassnahmen/{id_}/verwendungsnachweis")
def verwendungsnachweis_report(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    """Verwendungsnachweis-Paket als ZIP — port of the monolith route.

    Bundles the Excel report, an optional DOCX rendered from a NachweisTemplate,
    and every linked Beleg file under a ``belege/`` folder.
    """
    import io
    import os
    import re
    import zipfile

    from fastapi.responses import Response
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.funding import FundingMeasure, NachweisTemplate
    from app.models.master import FiscalYear
    from app.models.transaction import FundAllocation, Transaction, TransactionSplit
    from app.services.nachweis.aggregator import build_nachweis_data
    from app.services.nachweis.docx_filler import fill_docx_template
    from app.services.nachweis.excel_generator import generate_excel

    def _slugify(value: str) -> str:
        s = value.lower()
        s = re.sub(r"\s+", "_", s)
        s = re.sub(r"[^a-z0-9_\-]", "", s)
        return s[:60]

    fiscal_year_id = request.query_params.get("fiscal_year_id")
    if not fiscal_year_id:
        raise APIError(400, "MISSING_PARAM", "Query-Parameter 'fiscal_year_id' ist erforderlich.")
    measure = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if measure is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    fy = db.execute(
        select(FiscalYear).where(FiscalYear.id == fiscal_year_id, FiscalYear.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if fy is None:
        raise APIError(404, "NOT_FOUND", "Haushaltsjahr nicht gefunden.")

    data = build_nachweis_data(db, id_, fiscal_year_id, ctx.org_id)
    excel = generate_excel(data)
    slug = _slugify(data["massnahme"]["name"])
    jahr = data["fiscal_year"]["jahr"]

    # Optional DOCX from a configured NachweisTemplate (docx only).
    docx_bytes: bytes | None = None
    template = db.execute(
        select(NachweisTemplate).where(
            NachweisTemplate.funding_measure_id == id_,
            NachweisTemplate.org_id == ctx.org_id,
        )
    ).scalar_one_or_none()
    if template and template.datei_typ == "docx" and template.datei_pfad:
        try:
            with open(template.datei_pfad, "rb") as fh:
                tpl_bytes = fh.read()
            docx_bytes = fill_docx_template(tpl_bytes, data, template.feld_mappings or {})
        except Exception:
            # Template processing failed — continue without DOCX (parity).
            docx_bytes = None

    # All transactions in this fiscal year linked to the measure, with their belege.
    txs = (
        db.execute(
            select(Transaction)
            .where(
                Transaction.org_id == ctx.org_id,
                Transaction.fiscal_year_id == fiscal_year_id,
                Transaction.id.in_(
                    select(TransactionSplit.transaction_id)
                    .join(
                        FundAllocation,
                        FundAllocation.transaction_split_id == TransactionSplit.id,
                    )
                    .where(FundAllocation.funding_measure_id == id_)
                ),
            )
            .options(selectinload(Transaction.belege))
        )
        .scalars()
        .all()
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"verwendungsnachweis_{slug}_{jahr}.xlsx", excel)
        if docx_bytes:
            zf.writestr(f"verwendungsnachweis_{slug}_{jahr}.docx", docx_bytes)
        # Always present, even when empty (mirrors JSZip's zip.folder("belege")).
        zf.writestr(zipfile.ZipInfo("belege/"), "")
        for tx in txs:
            for beleg in tx.belege:
                if beleg.geloescht_am is not None or not beleg.datei_pfad:
                    continue
                try:
                    with open(beleg.datei_pfad, "rb") as fh:
                        file_data = fh.read()
                except OSError:
                    # File missing on disk — skip silently (parity).
                    continue
                file_name = beleg.datei_name or os.path.basename(beleg.datei_pfad)
                zf.writestr(f"belege/{beleg.id}_{file_name}", file_data)

    zip_name = f"verwendungsnachweis_{slug}_{jahr}.zip"
    return Response(
        content=buf.getvalue(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "X-Filename": zip_name,
        },
    )


@router.get("/foerdermassnahmen/{id_}/stundennachweis")
def stundennachweis_report(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    import re

    from fastapi.responses import Response
    from sqlalchemy import select

    from app.models.funding import FundingMeasure
    from app.services.nachweis.stundennachweis_generator import generate_stundennachweis

    fiscal_year_id = request.query_params.get("fiscal_year_id")
    if not fiscal_year_id:
        raise APIError(400, "MISSING_PARAMS", "fiscal_year_id ist erforderlich.")
    measure = db.execute(
        select(FundingMeasure).where(FundingMeasure.id == id_, FundingMeasure.org_id == ctx.org_id)
    ).scalar_one_or_none()
    if measure is None:
        raise APIError(404, "NOT_FOUND", "Fördermassnahme nicht gefunden.")
    buf = generate_stundennachweis(
        db, funding_measure_id=id_, fiscal_year_id=fiscal_year_id, org_id=ctx.org_id
    )
    # ASCII-safe filename for the (latin-1) Content-Disposition header.
    safe = re.sub(r"[^a-zA-Z0-9\-_. ]", "", measure.name).replace(" ", "-") or "export"
    return Response(
        content=buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="stundennachweis-{safe}.xlsx"'},
    )


# ── sub-resources: funding rules ─────────────────────────────────────────────
@router.get("/foerdermassnahmen/{id_}/regeln")
def list_rules(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": FoerdermassnahmeSubresourceService(db).list_rules(ctx.org_id, id_)}


@router.post("/foerdermassnahmen/{id_}/regeln", status_code=status.HTTP_201_CREATED)
async def create_rule(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    rule = FoerdermassnahmeSubresourceService(db).create_rule(
        ctx.org_id, _uid(ctx), id_, body
    )
    return {"data": rule, "message": "Regel wurde hinzugefügt."}


@router.delete("/foerdermassnahmen/{id_}/regeln/{rule_id}")
def delete_rule(
    id_: str,
    rule_id: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(
        content=FoerdermassnahmeSubresourceService(db).delete_rule(
            ctx.org_id, _uid(ctx), id_, rule_id
        )
    )


# ── sub-resources: cost-center links ─────────────────────────────────────────
@router.post(
    "/foerdermassnahmen/{id_}/kostenstellen", status_code=status.HTTP_201_CREATED
)
async def add_cost_center(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return FoerdermassnahmeSubresourceService(db).add_cost_center(ctx.org_id, id_, body)


@router.delete("/foerdermassnahmen/{id_}/kostenstellen")
async def remove_cost_center(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(
        content=FoerdermassnahmeSubresourceService(db).remove_cost_center(
            ctx.org_id, id_, body
        )
    )
