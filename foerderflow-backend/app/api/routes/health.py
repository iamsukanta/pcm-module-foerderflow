"""Health & readiness probes (used by docker-compose healthchecks)."""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness — process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
def readiness(db: Session = Depends(get_db)) -> dict[str, str]:
    """Readiness — DB reachable."""
    db.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}
