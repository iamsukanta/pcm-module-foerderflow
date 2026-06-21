"""Engine, session factory, and FastAPI request-scoped DB dependency."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=settings.debug and settings.environment == "development",
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine, autoflush=False, autocommit=False, expire_on_commit=False
)


def get_db() -> Generator[Session, None, None]:
    """Request-scoped session. Commit/rollback handled by use-case/service layer
    (Unit of Work); this dependency guarantees the session is always closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
