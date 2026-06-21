"""/api/protected/transaktionen/[id]/belege(/[belegId]) — receipt upload/list/
download/soft-delete."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.beleg_service import BelegService

router = APIRouter(tags=["belege"])


def _uid(ctx: OrgContext) -> str | None:
    return ctx.user.id if ctx.user else None


@router.get("/transaktionen/{id_}/belege")
def list_belege(
    id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": BelegService(db).list(ctx.org_id, id_)}


@router.post("/transaktionen/{id_}/belege", status_code=status.HTTP_201_CREATED)
async def upload_beleg(
    id_: str,
    file: UploadFile | None = File(default=None),
    externe_referenz: str | None = Form(default=None),
    retention_years: str | None = Form(default=None),
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    svc = BelegService(db)
    if file is None and not externe_referenz:
        raise APIError(
            400, "VALIDATION_ERROR", "Entweder 'file' oder 'externe_referenz' ist Pflichtfeld"
        )
    if file is None:
        data = svc.create_external(ctx.org_id, _uid(ctx), id_, externe_referenz, retention_years)
    else:
        content = await file.read()
        data = svc.create_upload(
            ctx.org_id,
            _uid(ctx),
            id_,
            file.filename or "beleg",
            file.content_type or "application/octet-stream",
            content,
            retention_years,
        )
    return JSONResponse(content={"data": data}, status_code=status.HTTP_201_CREATED)


@router.get("/transaktionen/{id_}/belege/{beleg_id}")
def download_beleg(
    id_: str,
    beleg_id: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
):
    beleg = BelegService(db).get_for_download(ctx.org_id, id_, beleg_id)
    if beleg.externe_referenz and not beleg.datei_pfad:
        return JSONResponse(content={"data": {"externe_referenz": beleg.externe_referenz}})
    if not beleg.datei_pfad or not beleg.datei_typ:
        raise APIError(404, "NOT_FOUND", "Keine Datei verfügbar")
    path = Path(beleg.datei_pfad)
    if not path.exists():
        raise APIError(500, "IO_ERROR", "Datei konnte nicht gelesen werden")
    return FileResponse(
        path,
        media_type=beleg.datei_typ,
        filename=beleg.datei_name or "beleg",
        content_disposition_type="inline",
    )


@router.delete("/transaktionen/{id_}/belege/{beleg_id}")
def delete_beleg(
    id_: str,
    beleg_id: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=BelegService(db).soft_delete(ctx.org_id, id_, beleg_id))
