"""/api/protected/pcm/* — Module PCM (Personal Cost Management) endpoints.

Isolated under a dedicated ``/pcm`` prefix so the module is a clean additive
overlay on the existing payroll surface:

  salary-tariffs (CRUD + /resolve + /{id}/levels)
  wochenstunden-zuweisungen (CRUD, Doppelförderungs guard)
  payroll/run · payroll/run-monat · payroll/{id}/detail-lines

Guarded by org session only (parity with the existing payroll/kostenstellen
routes). Domain errors flow through APIError → the {error, code} envelope.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.pcm.allocation_service import PayrollAllocationService
from app.services.pcm.audit_service import AuditService
from app.services.pcm.bonus_service import BonusService
from app.services.pcm.forecast_service import ForecastService
from app.services.pcm.leave_service import LeaveService
from app.services.pcm.payroll_import_service import PayrollImportService
from app.services.pcm.payroll_run_service import PcmPayrollService
from app.services.pcm.period_service import PayrollPeriodService
from app.services.pcm.promotion_service import run_promotions
from app.services.pcm.salary_tariff_service import SalaryTariffService
from app.services.pcm.scenario_service import ScenarioService
from app.services.pcm.settings_service import PcmSettingsService
from app.services.pcm.tariff_import_service import TariffImportService
from app.services.pcm.vwn_service import VwnService
from app.services.pcm.wochenstunden_service import WochenstundenService

_MAX_IMPORT_BYTES = 10 * 1024 * 1024  # 10 MB (DevGuide §10)


def _actor(ctx: OrgContext) -> str | None:
    """Best-effort actor identifier for the audit trail."""
    return getattr(ctx.user, "email", None) or getattr(ctx.user, "id", None)

router = APIRouter(prefix="/pcm", tags=["pcm"])


# ── salary tariffs ────────────────────────────────────────────────────────────
@router.get("/salary-tariffs")
def list_salary_tariffs(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": SalaryTariffService(db).list(ctx.org_id, dict(request.query_params))}


@router.post("/salary-tariffs", status_code=status.HTTP_201_CREATED)
async def create_salary_tariff(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": SalaryTariffService(db).create(ctx.org_id, body),
        "message": "Tarif-Eintrag wurde angelegt.",
    }


# Registered before /salary-tariffs/{id_} so "resolve" is not captured as an id.
@router.get("/salary-tariffs/resolve")
def resolve_salary_tariff(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": SalaryTariffService(db).resolve(ctx.org_id, dict(request.query_params))
    }


@router.get("/salary-tariffs/{id_}")
def get_salary_tariff(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": SalaryTariffService(db).get(ctx.org_id, id_)}


@router.patch("/salary-tariffs/{id_}")
async def update_salary_tariff(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": SalaryTariffService(db).update(ctx.org_id, id_, body),
        "message": "Tarif-Eintrag wurde gespeichert.",
    }


@router.delete("/salary-tariffs/{id_}")
def delete_salary_tariff(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=SalaryTariffService(db).delete(ctx.org_id, id_))


@router.get("/salary-tariffs/{id_}/levels")
def list_salary_levels(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": SalaryTariffService(db).list_levels(ctx.org_id, id_)}


@router.post("/salary-tariffs/{id_}/levels", status_code=status.HTTP_201_CREATED)
async def create_salary_level(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": SalaryTariffService(db).create_level(ctx.org_id, id_, body),
        "message": "Stufe wurde angelegt.",
    }


@router.patch("/salary-levels/{id_}")
async def update_salary_level(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": SalaryTariffService(db).update_level(ctx.org_id, id_, body),
        "message": "Stufe wurde gespeichert.",
    }


@router.delete("/salary-levels/{id_}")
def delete_salary_level(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=SalaryTariffService(db).delete_level(ctx.org_id, id_))


# ── tariff registry: codes, rows-by-code, overlap-check (D.1/D.2/D.3) ─────────
@router.get("/tariff-codes")
def list_tariff_codes(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    params = request.query_params
    return {
        "data": SalaryTariffService(db).tariff_codes(
            ctx.org_id,
            status=params.get("status"),
            search=params.get("search"),
        )
    }


@router.get("/tariff-rows/check-overlap")
def check_tariff_overlap(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": SalaryTariffService(db).check_overlap(
            ctx.org_id, dict(request.query_params)
        )
    }


@router.get("/tariff-codes/{tariff_code}/rows")
def list_tariff_rows_by_code(
    tariff_code: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": SalaryTariffService(db).rows_by_code(
            ctx.org_id, tariff_code, dict(request.query_params)
        )
    }


@router.get("/tariff-codes/{tariff_code}/levels")
def list_tariff_levels_by_code(
    tariff_code: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": SalaryTariffService(db).levels_by_code(
            ctx.org_id, tariff_code, request.query_params.get("salary_group")
        )
    }


# ── upcoming progressions (P-T) ───────────────────────────────────────────────
@router.get("/employees/progressions/upcoming")
def upcoming_progressions(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    try:
        months_ahead = int(request.query_params.get("months_ahead", "6"))
    except ValueError:
        months_ahead = 6
    return {
        "data": SalaryTariffService(db).progressions_upcoming(
            ctx.org_id,
            months_ahead=months_ahead,
            tariff_code=request.query_params.get("tariff_code"),
        )
    }


@router.post("/employees/promotions/run")
def run_promotion_job(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    result = run_promotions(db, ctx.org_id, changed_by=_actor(ctx))
    return {
        "data": result,
        "message": f"{result['promoted_count']} Stufenaufstiege durchgeführt.",
    }


# ── audit trail (Area O) ──────────────────────────────────────────────────────
@router.get("/audit-log")
def list_audit_log(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": AuditService(db).list(ctx.org_id, dict(request.query_params))}


@router.get("/audit-log/{id_}")
def get_audit_entry(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": AuditService(db).get(ctx.org_id, id_)}


# ── tariff import wizard (I-T) ────────────────────────────────────────────────
@router.post("/tariff-rows/import")
async def import_tariff_rows_preview(
    file: UploadFile = File(...),
    source: str = Form(...),
    tariff_code: str = Form(...),
    is_proposed: str = Form("false"),
    valid_from: str = Form(...),
    valid_to: str | None = Form(None),
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read()
    if len(content) > _MAX_IMPORT_BYTES:
        raise APIError(422, "IMPORT_TOO_LARGE", "Die Datei überschreitet 10 MB.")
    meta = {
        "source": source,
        "tariff_code": tariff_code,
        "is_proposed": is_proposed,
        "valid_from": valid_from,
        "valid_to": valid_to or None,
    }
    return {
        "data": TariffImportService(db).preview(
            ctx.org_id, content=content, filename=file.filename or "", meta=meta
        )
    }


@router.post("/tariff-rows/import/{import_id}/confirm")
async def import_tariff_rows_confirm(
    import_id: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": TariffImportService(db).confirm(ctx.org_id, body),
        "message": "Tarif-Import wurde übernommen.",
    }


# ── wochenstunden-zuweisungen ────────────────────────────────────────────────
@router.get("/stellenplan/matrix")
def stellenplan_matrix(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    as_of_raw = request.query_params.get("as_of")
    as_of = None
    if as_of_raw:
        try:
            as_of = date.fromisoformat(as_of_raw)
        except ValueError:
            as_of = None
    return {"data": WochenstundenService(db).matrix(ctx.org_id, as_of)}


@router.get("/wochenstunden-zuweisungen")
def list_wochenstunden(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    employee_id = request.query_params.get("employee_id")
    return {"data": WochenstundenService(db).list(ctx.org_id, employee_id)}


@router.post("/wochenstunden-zuweisungen", status_code=status.HTTP_201_CREATED)
async def create_wochenstunden(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": WochenstundenService(db).create(ctx.org_id, body),
        "message": "Wochenstunden-Zuweisung wurde angelegt.",
    }


@router.patch("/wochenstunden-zuweisungen/{id_}")
async def update_wochenstunden(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": WochenstundenService(db).update(ctx.org_id, id_, body),
        "message": "Wochenstunden-Zuweisung wurde gespeichert.",
    }


@router.delete("/wochenstunden-zuweisungen/{id_}")
def delete_wochenstunden(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=WochenstundenService(db).delete(ctx.org_id, id_))


# ── leave & absence (Area F) ──────────────────────────────────────────────────
@router.get("/leave-periods")
def list_leave_periods(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": LeaveService(db).list(ctx.org_id, dict(request.query_params))}


@router.post("/leave-periods", status_code=status.HTTP_201_CREATED)
async def create_leave_period(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": LeaveService(db).create(ctx.org_id, body, changed_by=_actor(ctx)),
        "message": "Abwesenheit wurde erfasst.",
    }


@router.get("/placeholder-employees")
def list_placeholder_employees(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": LeaveService(db).list_placeholders(ctx.org_id)}


@router.post("/placeholder-employees", status_code=status.HTTP_201_CREATED)
async def create_placeholder_employee(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": LeaveService(db).create_placeholder(ctx.org_id, body),
        "message": "Platzhalter-Mitarbeiter:in wurde angelegt.",
    }


@router.get("/leave-periods/{id_}")
def get_leave_period(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": LeaveService(db).get(ctx.org_id, id_)}


@router.patch("/leave-periods/{id_}")
async def update_leave_period(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": LeaveService(db).update(ctx.org_id, id_, body),
        "message": "Abwesenheit wurde gespeichert.",
    }


@router.post("/leave-periods/{id_}/return")
async def record_leave_return(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": LeaveService(db).record_return(
            ctx.org_id, id_, body, changed_by=_actor(ctx)
        ),
        "message": "Rückkehr wurde erfasst.",
    }


@router.post("/leave-periods/{id_}/notification-sent")
def mark_leave_notification_sent(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": LeaveService(db).mark_notification_sent(ctx.org_id, id_),
        "message": "Benachrichtigung als gesendet markiert.",
    }


# ── bonus templates (Area G) ──────────────────────────────────────────────────
@router.get("/bonus-templates")
def list_bonus_templates(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": BonusService(db).list_templates(ctx.org_id)}


@router.post("/bonus-templates", status_code=status.HTTP_201_CREATED)
async def create_bonus_template(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": BonusService(db).create_template(ctx.org_id, body),
        "message": "Bonusvorlage wurde angelegt.",
    }


@router.post("/bonus-templates/preview")
async def preview_bonus_template(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": BonusService(db).preview_eligibility(ctx.org_id, body)}


@router.get("/bonus-templates/{id_}")
def get_bonus_template(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": BonusService(db).get_template(ctx.org_id, id_)}


@router.patch("/bonus-templates/{id_}")
async def update_bonus_template(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": BonusService(db).update_template(ctx.org_id, id_, body),
        "message": "Bonusvorlage wurde gespeichert.",
    }


@router.delete("/bonus-templates/{id_}")
def delete_bonus_template(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=BonusService(db).delete_template(ctx.org_id, id_))


# ── per-employee bonuses + adjustments (Area H) ───────────────────────────────
@router.get("/bonus-payments")
def list_bonus_payments(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    employee_id = request.query_params.get("employee_id", "")
    return {"data": BonusService(db).list_payments(ctx.org_id, employee_id)}


@router.post("/bonus-payments", status_code=status.HTTP_201_CREATED)
async def create_bonus_payment(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": BonusService(db).create_payment(ctx.org_id, body),
        "message": "Bonus wurde angelegt.",
    }


@router.delete("/bonus-payments/{id_}")
def delete_bonus_payment(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=BonusService(db).delete_payment(ctx.org_id, id_))


@router.get("/salary-adjustments")
def list_salary_adjustments(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    employee_id = request.query_params.get("employee_id", "")
    return {"data": BonusService(db).list_adjustments(ctx.org_id, employee_id)}


@router.post("/salary-adjustments", status_code=status.HTTP_201_CREATED)
async def create_salary_adjustment(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": BonusService(db).create_adjustment(ctx.org_id, body),
        "message": "Anpassung wurde angelegt.",
    }


@router.delete("/salary-adjustments/{id_}")
def delete_salary_adjustment(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=BonusService(db).delete_adjustment(ctx.org_id, id_))


# ── cost forecast (Area K) ────────────────────────────────────────────────────
@router.post("/forecast/run")
async def run_forecast_endpoint(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    result = ForecastService(db).run(ctx.org_id, body)
    return {"data": result, "message": "Prognose wurde berechnet."}


@router.get("/forecast/dashboard")
def forecast_dashboard(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": ForecastService(db).dashboard(ctx.org_id, fy)}


@router.get("/forecast/matrix")
def forecast_matrix(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": ForecastService(db).matrix(ctx.org_id, fy)}


@router.get("/forecast/warnings")
def forecast_warnings(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": ForecastService(db).warnings(ctx.org_id, fy)}


@router.get("/forecast/detail")
def forecast_detail(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    employee_id = request.query_params.get("employee_id", "")
    return {
        "data": ForecastService(db).detail(ctx.org_id, employee_id, _qmonat(request))
    }


# ── payroll allocation views (Area N) ─────────────────────────────────────────
@router.get("/allocations/overview")
def allocations_overview(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {
        "data": PayrollAllocationService(db).overview(ctx.org_id, fy, _qmonat(request))
    }


@router.get("/allocations/per-grant")
def allocations_per_grant(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    fm = request.query_params.get("funding_measure_id", "")
    return {"data": PayrollAllocationService(db).per_grant(ctx.org_id, fy, fm)}


# ── VWN itemized report (Area M) ──────────────────────────────────────────────
def _qdate(request: Request, key: str) -> date:
    raw = request.query_params.get(key)
    if not raw:
        raise APIError(422, "VALIDATION_REQUIRED", f"{key} ist erforderlich.")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise APIError(  # noqa: B904
            422, "VALIDATION_DATE", f"{key} muss ein Datum (YYYY-MM-DD) sein."
        ) from exc


@router.get("/vwn/config")
def vwn_get_config(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fm = request.query_params.get("funding_measure_id", "")
    return {"data": VwnService(db).get_config(ctx.org_id, fm)}


@router.put("/vwn/config")
async def vwn_save_config(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": VwnService(db).save_config(ctx.org_id, body["funding_measure_id"], body),
        "message": "VWN-Konfiguration gespeichert.",
    }


@router.get("/vwn/preview")
def vwn_preview(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fm = request.query_params.get("funding_measure_id", "")
    return {
        "data": VwnService(db).preview(
            ctx.org_id, fm, _qdate(request, "from_month"), _qdate(request, "to_month")
        )
    }


@router.get("/vwn/export")
def vwn_export(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> Response:
    fm = request.query_params.get("funding_measure_id", "")
    filename, content = VwnService(db).export_csv(
        ctx.org_id, fm, _qdate(request, "from_month"), _qdate(request, "to_month")
    )
    return Response(
        content=content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Filename": filename,
        },
    )


# ── scenario planner (Area L) ─────────────────────────────────────────────────
@router.get("/scenarios")
def list_scenarios(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ScenarioService(db).list(ctx.org_id)}


@router.post("/scenarios", status_code=status.HTTP_201_CREATED)
async def create_scenario(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": ScenarioService(db).create(ctx.org_id, body),
        "message": "Szenario wurde angelegt.",
    }


@router.get("/scenarios/{id_}")
def get_scenario(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ScenarioService(db).get(ctx.org_id, id_)}


@router.patch("/scenarios/{id_}")
async def update_scenario(
    id_: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": ScenarioService(db).update(ctx.org_id, id_, body),
        "message": "Szenario wurde gespeichert.",
    }


@router.delete("/scenarios/{id_}")
def delete_scenario(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    return JSONResponse(content=ScenarioService(db).delete(ctx.org_id, id_))


@router.post("/scenarios/{id_}/compute")
def compute_scenario(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ScenarioService(db).compute(ctx.org_id, id_)}


@router.get("/scenarios/{id_}/results")
def scenario_results(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": ScenarioService(db).results(ctx.org_id, id_)}


@router.post("/scenarios/{id_}/promote")
def promote_scenario(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {
        "data": ScenarioService(db).promote(ctx.org_id, id_),
        "message": "Szenario wurde übernommen.",
    }


# ── PCM settings (Area A) ─────────────────────────────────────────────────────
@router.get("/settings/overview")
def settings_overview(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": PcmSettingsService(db).overview(ctx.org_id)}


@router.get("/settings/bav")
def settings_get_bav(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": PcmSettingsService(db).get_bav(ctx.org_id)}


@router.put("/settings/bav")
async def settings_set_bav(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": PcmSettingsService(db).set_bav(ctx.org_id, body),
        "message": "BAV-Satz gespeichert.",
    }


@router.get("/settings/external-ids")
def settings_external_ids(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": PcmSettingsService(db).external_ids(ctx.org_id)}


@router.put("/settings/external-ids/{employee_id}")
async def settings_set_external_id(
    employee_id: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": PcmSettingsService(db).set_external_id(ctx.org_id, employee_id, body),
        "message": "Externe ID gespeichert.",
    }


# ── external payroll import (Area J) ──────────────────────────────────────────
@router.get("/payroll-import/batches")
def payroll_import_batches(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": PayrollImportService(db).list(ctx.org_id)}


@router.post("/payroll-import/preview")
async def payroll_import_preview(
    file: UploadFile = File(...),
    source_type: str = Form(...),
    period_from: str = Form(...),
    period_to: str | None = Form(None),
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read()
    if len(content) > _MAX_IMPORT_BYTES:
        raise APIError(422, "IMPORT_TOO_LARGE", "Die Datei überschreitet 10 MB.")
    return {
        "data": PayrollImportService(db).preview(
            ctx.org_id, source=source_type, content=content,
            meta={"period_from": period_from, "period_to": period_to or None},
        )
    }


@router.post("/payroll-import/confirm")
async def payroll_import_confirm(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": PayrollImportService(db).confirm(ctx.org_id, body),
        "message": "Import wurde verarbeitet.",
    }


# ── Fristen integration (Area P) ──────────────────────────────────────────────
@router.get("/fristen/leave-tasks")
def fristen_leave_tasks(
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": LeaveService(db).fristen_tasks(ctx.org_id)}


# ── payroll periods (Area I) ──────────────────────────────────────────────────
def _qmonat(request: Request) -> date:
    raw = request.query_params.get("monat")
    if not raw:
        raise APIError(422, "VALIDATION_REQUIRED", "monat ist erforderlich.")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise APIError(  # noqa: B904
            422, "VALIDATION_DATE", "monat muss ein Datum (YYYY-MM-DD) sein."
        ) from exc


@router.get("/payroll/periods")
def payroll_periods_overview(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id")
    if not fy:
        raise APIError(422, "VALIDATION_REQUIRED", "fiscal_year_id ist erforderlich.")
    return {"data": PayrollPeriodService(db).overview(ctx.org_id, fy)}


@router.get("/payroll/periods/preflight")
def payroll_period_preflight(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": PayrollPeriodService(db).preflight(ctx.org_id, fy, _qmonat(request))}


@router.get("/payroll/periods/results")
def payroll_period_results(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": PayrollPeriodService(db).results(ctx.org_id, fy, _qmonat(request))}


@router.get("/payroll/periods/on-leave")
def payroll_period_on_leave(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    fy = request.query_params.get("fiscal_year_id", "")
    return {"data": PayrollPeriodService(db).on_leave(ctx.org_id, fy, _qmonat(request))}


@router.post("/payroll/periods/lock")
async def lock_payroll_period(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    monat = date.fromisoformat(body["monat"])
    return {
        "data": PayrollPeriodService(db).lock(
            ctx.org_id, body["fiscal_year_id"], monat, locked_by=_actor(ctx)
        ),
        "message": "Periode wurde gesperrt.",
    }


@router.post("/payroll/periods/reopen")
async def reopen_payroll_period(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    monat = date.fromisoformat(body["monat"])
    return {
        "data": PayrollPeriodService(db).reopen(ctx.org_id, body["fiscal_year_id"], monat),
        "message": "Periode wurde wieder geöffnet.",
    }


# ── payroll engine ────────────────────────────────────────────────────────────
@router.post("/payroll/run")
async def run_payroll(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": PcmPayrollService(db).run_one(ctx.org_id, body),
        "message": "PCM-Abrechnung wurde berechnet.",
    }


@router.post("/payroll/run-monat")
async def run_payroll_monat(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": PcmPayrollService(db).run_monat(ctx.org_id, body)}


@router.get("/payroll/{id_}/detail-lines")
def payroll_detail_lines(
    id_: str,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    return {"data": PcmPayrollService(db).detail_lines(ctx.org_id, id_)}
