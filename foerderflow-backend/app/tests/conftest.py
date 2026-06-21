"""Shared pytest fixtures: in-memory DB + a TestClient with auth/org overridden.

Uses SQLite for fast, DB-less CI of service/route logic. Native PG enums render as
VARCHAR on SQLite (values still validated in Python), which is fine for behavior
tests; full Postgres-specific behavior is covered by the migration + model suite.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401  (register mappers)
from app.db.base import Base
from app.db.session import get_db
from app.dependencies.auth import OrgContext, get_org_context
from app.main import app
from app.models.enums import OrgRole, Rechtsform
from app.models.organization import Organization

@pytest.fixture
def db_session() -> Iterator[Session]:
    # JSONB columns use with_variant(JSON, "sqlite"), so the full metadata is
    # SQLite-creatable — no need to cherry-pick tables.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def org(db_session: Session) -> Organization:
    from decimal import Decimal

    o = Organization(
        name="Test Org",
        rechtsform=Rechtsform.EV,
        regelarbeitszeit_stunden=Decimal("39.00"),
    )
    db_session.add(o)
    db_session.commit()
    db_session.refresh(o)
    return o


@pytest.fixture
def super_user(db_session: Session) -> "User":
    from app.models.auth import User

    u = User(email="admin@test.de", name="Test Admin", is_super_admin=True)
    db_session.add(u)
    db_session.commit()
    db_session.refresh(u)
    return u


@pytest.fixture
def client(db_session: Session, org: Organization, super_user):
    from fastapi.testclient import TestClient

    from app.dependencies.auth import get_current_user, require_super_admin

    def _override_db() -> Iterator[Session]:
        yield db_session

    class _Stub:
        def __init__(self, role: OrgRole):
            self.role = role
            self.org_id = org.id

    def _override_ctx() -> OrgContext:
        return OrgContext(
            user=super_user,
            organization=org,
            membership=_Stub(OrgRole.ADMIN),  # type: ignore[arg-type]
        )

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_org_context] = _override_ctx
    app.dependency_overrides[get_current_user] = lambda: super_user
    app.dependency_overrides[require_super_admin] = lambda: super_user
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
