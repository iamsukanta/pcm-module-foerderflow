"""/api/protected/compliance — dismiss a compliance banner (audit-logged)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.routes.kostenstellen import _json_body
from app.core.errors import APIError
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.services.audit_service import log_audit

router = APIRouter(tags=["compliance"])


@router.post("/compliance/dismiss")
async def dismiss(
    request: Request,
    ctx: OrgContext = Depends(get_org_context),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    body = await _json_body(request)
    alert_hash = body.get("alertHash")
    if not isinstance(alert_hash, str) or not alert_hash:
        raise APIError(422, "VALIDATION_ALERT_HASH", "alertHash fehlt.")
    log_audit(
        db,
        org_id=ctx.org_id,
        user_id=ctx.user.id if ctx.user else None,
        aktion="COMPLIANCE_ALERT_DISMISSED",
        entitaet="ComplianceAlert",
        entitaet_id=alert_hash,
        nachher={"dismissedAt": datetime.now(timezone.utc).isoformat()},
    )
    return {"ok": True}
