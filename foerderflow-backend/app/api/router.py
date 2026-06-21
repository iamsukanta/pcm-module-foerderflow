"""Top-level API router. Domain routers are mounted here as Phase 3 progresses."""

from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    bank_accounts,
    belege,
    buchungsregeln,
    compliance,
    csv_profiles,
    employees,
    finanzplan_positionen,
    fristen,
    mittelabrufe,
    payroll,
    verwendungsnachweise,
    foerdermassnahmen,
    funder,
    haushaltsjahre,
    health,
    kostenbereiche,
    kostenstellen,
    me,
    misc,
    org_invite,
    pcm,
    transaktionen,
    umlage_source_scopes,
    verteilungsschluessel,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(me.router, prefix="/protected")
api_router.include_router(kostenstellen.router, prefix="/protected")
api_router.include_router(kostenbereiche.router, prefix="/protected")
api_router.include_router(funder.router, prefix="/protected")
api_router.include_router(haushaltsjahre.router, prefix="/protected")
api_router.include_router(bank_accounts.router, prefix="/protected")
api_router.include_router(foerdermassnahmen.router, prefix="/protected")
api_router.include_router(finanzplan_positionen.router, prefix="/protected")
api_router.include_router(verteilungsschluessel.router, prefix="/protected")
api_router.include_router(umlage_source_scopes.router, prefix="/protected")
api_router.include_router(transaktionen.router, prefix="/protected")
api_router.include_router(buchungsregeln.router, prefix="/protected")
api_router.include_router(belege.router, prefix="/protected")
api_router.include_router(csv_profiles.router, prefix="/protected")
api_router.include_router(mittelabrufe.router, prefix="/protected")
api_router.include_router(fristen.router, prefix="/protected")
api_router.include_router(compliance.router, prefix="/protected")
api_router.include_router(verwendungsnachweise.router, prefix="/protected")
api_router.include_router(employees.router, prefix="/protected")
api_router.include_router(payroll.router, prefix="/protected")
api_router.include_router(misc.router, prefix="/protected")
api_router.include_router(pcm.router, prefix="/protected")
api_router.include_router(org_invite.router, prefix="/protected")
api_router.include_router(org_invite.setup_router, prefix="/setup")
api_router.include_router(admin.router)

# Phase 3 domain routers mounted here incrementally (dependency order):
#   kostenstellen, kostenbereiche, funder, haushaltsjahre, bank-accounts,
#   foerdermassnahmen, verteilungsschluessel, transaktionen, buchungsregeln,
#   mittelabrufe, verwendungsnachweise, payroll, ... + /admin/* (super-admin).
