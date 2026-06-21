"""/api/protected/payroll (+[id] +allocations +monat-uebersicht), employer-gross-
factors, tarif, personal/soll-ist — port of the payroll API surface."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.personal.payroll_service import (
    GrossFactorService,
    PayrollService,
    TarifService,
)

router = APIRouter(tags=["payroll"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


@router.get("/payroll")
def list_payroll(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": PayrollService(db).list(ctx.org_id, dict(request.query_params))}


@router.post("/payroll", status_code=status.HTTP_201_CREATED)
async def create_payroll(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    p = PayrollService(db).create(ctx.org_id, body)
    return {"data": p, "message": "Abrechnung wurde erfolgreich erfasst."}


@router.get("/payroll/monat-uebersicht")
def monat_uebersicht(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    monat = request.query_params.get("monat")
    fy = request.query_params.get("fiscal_year_id")
    return {"data": PayrollService(db).monat_uebersicht(ctx.org_id, monat, fy)}


# ── Lohnjournal CSV import (registered before /payroll/{id_}) ─────────────────
@router.post("/payroll/import")
async def import_payroll(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.core.errors import APIError
    from app.services.personal.payroll_io_service import PayrollIoService

    try:
        form = await request.form()
    except Exception:
        raise APIError(400, "FORM_PARSE_ERROR", "Fehler beim Lesen der Formulardaten.")
    file = form.get("file")
    fiscal_year_id = form.get("fiscal_year_id")
    spalten_mapping = form.get("spalten_mapping")
    if file is None or isinstance(file, str) or not hasattr(file, "read"):
        content = None
        size = None
    else:
        raw = await file.read()
        size = len(raw)
        content = raw.decode("utf-8-sig", errors="replace")
    return PayrollIoService(db).import_csv(
        ctx.org_id,
        content,
        size,
        fiscal_year_id if isinstance(fiscal_year_id, str) else None,
        spalten_mapping if isinstance(spalten_mapping, str) else None,
    )


# ── Lohnbüro CSV export (registered before /payroll/{id_}) ────────────────────
@router.get("/payroll/lohnbuero-export")
def lohnbuero_export(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
):
    from fastapi.responses import Response

    from app.services.personal.payroll_io_service import PayrollIoService

    p = request.query_params
    csv, filename = PayrollIoService(db).lohnbuero_export(
        ctx.org_id, p.get("monat"), p.get("fiscal_year_id"), p.get("spalten")
    )
    return Response(
        content=csv,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/payroll/{id_}")
def get_payroll(id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": PayrollService(db).get(ctx.org_id, id_)}


@router.patch("/payroll/{id_}")
async def update_payroll(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": PayrollService(db).update(ctx.org_id, id_, body), "message": "Abrechnung aktualisiert."}


@router.delete("/payroll/{id_}")
def delete_payroll(id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> JSONResponse:
    return JSONResponse(content=PayrollService(db).delete(ctx.org_id, id_))


@router.get("/payroll/{id_}/allocations")
def list_allocations(id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": PayrollService(db).list_allocations(ctx.org_id, id_)}


@router.post("/payroll/{id_}/allocations")
async def set_allocations(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> JSONResponse:
    body = await _json_body(request)
    return JSONResponse(content=PayrollService(db).set_allocations(ctx.org_id, _uid(ctx), id_, body))


# ── employer gross factors ──────────────────────────────────────────────────
@router.get("/employer-gross-factors")
def list_gross_factors(ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": GrossFactorService(db).list(ctx.org_id)}


@router.post("/employer-gross-factors", status_code=status.HTTP_201_CREATED)
async def create_gross_factor(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": GrossFactorService(db).create(ctx.org_id, body), "message": "AG-Faktor angelegt."}


# ── tarif ────────────────────────────────────────────────────────────────────
@router.get("/tarif")
def tarif_lookup(
    request: Request, _ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    p = request.query_params
    return {"data": TarifService(db).lookup(p.get("tarifwerk"), p.get("entgeltgruppe"), p.get("jahr"))}


# ── personal soll-ist ─────────────────────────────────────────────────────────
@router.get("/personal/soll-ist")
def personal_soll_ist(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    p = request.query_params
    return PayrollService(db).personal_soll_ist(ctx.org_id, p.get("funding_measure_id"), p.get("fiscal_year_id"))


# ── VZÄ-Übersicht ──────────────────────────────────────────────────────────────
@router.get("/personal/vzae-uebersicht")
def vzae_uebersicht(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    from app.services.personal.vzae_uebersicht_service import VzaeUebersichtService

    p = request.query_params
    return VzaeUebersichtService(db).uebersicht(
        ctx.org_id, p.get("funding_measure_id"), p.get("fiscal_year_id")
    )
