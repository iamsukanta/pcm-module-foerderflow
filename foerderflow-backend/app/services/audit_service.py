"""Fire-and-forget audit log — port of lib/audit.ts.

Best-effort: a failure must never block or poison the caller's transaction (the
monolith calls this un-awaited after the main operation). Errors are logged,
never raised.

Implementation: the audit row is written inside a SAVEPOINT on the caller's
session AFTER its main commit, so a failure rolls back only the audit insert and
no external connection is opened (important for tests / offline DBs).
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)

AuditAktion = str  # open union, values must match the monolith


def log_audit(
    db: Session,
    *,
    org_id: str,
    aktion: str,
    entitaet: str,
    entitaet_id: str,
    user_id: str | None = None,
    vorher: dict[str, Any] | None = None,
    nachher: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    try:
        with db.begin_nested():
            db.add(
                AuditLog(
                    org_id=org_id,
                    user_id=user_id,
                    aktion=aktion,
                    entitaet=entitaet,
                    entitaet_id=entitaet_id,
                    vorher=vorher,
                    nachher=nachher,
                    ip=ip,
                )
            )
        db.commit()
    except Exception:  # noqa: BLE001 - fire-and-forget
        logger.warning("[AuditLog] Fehler beim Schreiben", exc_info=True)
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
