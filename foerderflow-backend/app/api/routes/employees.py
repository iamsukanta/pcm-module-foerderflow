"""/api/protected/employees (+contracts +components) — port of employees/*."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.personal.employee_service import EmployeeService

router = APIRouter(tags=["employees"])


@router.get("/employees")
def list_employees(ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": EmployeeService(db).list(ctx.org_id)}


@router.post("/employees", status_code=status.HTTP_201_CREATED)
async def create_employee(
    request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    e = EmployeeService(db).create(ctx.org_id, body)
    return {"data": e, "message": f"Mitarbeiter {e['vorname']} {e['nachname']} wurde angelegt."}


@router.get("/employees/{id_}")
def get_employee(id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": EmployeeService(db).get(ctx.org_id, id_)}


@router.patch("/employees/{id_}")
async def update_employee(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": EmployeeService(db).update(ctx.org_id, id_, body), "message": "Mitarbeiter aktualisiert."}


@router.get("/employees/{id_}/contracts")
def list_contracts(id_: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"data": EmployeeService(db).list_contracts(ctx.org_id, id_)}


@router.post("/employees/{id_}/contracts", status_code=status.HTTP_201_CREATED)
async def create_contract(
    id_: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return {"data": EmployeeService(db).create_contract(ctx.org_id, id_, body), "message": "Vertragsänderung gespeichert."}


@router.get("/employees/{id_}/contracts/{contract_id}/components")
def list_components(
    id_: str, contract_id: str, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    return {"data": EmployeeService(db).list_components(ctx.org_id, id_, contract_id)}


@router.post("/employees/{id_}/contracts/{contract_id}/components", status_code=status.HTTP_201_CREATED)
async def create_component(
    id_: str, contract_id: str, request: Request, ctx: OrgContext = Depends(get_org_context), db: Session = Depends(get_db)
) -> dict[str, Any]:
    body = await _json_body(request)
    return {
        "data": EmployeeService(db).create_component(ctx.org_id, id_, contract_id, body),
        "message": "Gehaltskomponente angelegt.",
    }


@router.patch("/employees/{id_}/contracts/{contract_id}/components")
def deactivate_component(
    id_: str,
    contract_id: str,
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> JSONResponse:
    from app.core.errors import APIError

    if request.query_params.get("action") != "deactivate":
        raise APIError(
            400, "INVALID_ACTION", "Ungültige Aktion. Erwartet: ?action=deactivate&componentId=xxx"
        )
    component_id = request.query_params.get("componentId")
    return JSONResponse(
        content=EmployeeService(db).deactivate_component(ctx.org_id, id_, contract_id, component_id)
    )
