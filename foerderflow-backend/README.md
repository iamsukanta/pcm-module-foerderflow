# FörderFlow Backend (FastAPI)

REST API backend for FörderFlow — a faithful, separated-architecture port of the
FörderFlow monolith (`../../foerderflow`). German funding/grant management domain.

## Stack
FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · PostgreSQL · JWT (magic-link) · pytest

## Architecture (clean architecture)
```
app/
├── api/            HTTP layer (routers). Thin — delegates downward.
│   └── routes/     one module per resource
├── core/           config, logging, security/JWT, errors
├── db/             engine, session, declarative base
├── models/         SQLAlchemy ORM entities (1:1 with Prisma models) + enums
├── schemas/        Pydantic v2 request/response DTOs
├── repositories/   data access (org-scoped queries; no business logic)
├── services/       domain logic ported from the monolith lib/**
├── use_cases/      application workflows (orchestration + Unit of Work)
├── dependencies/   FastAPI DI: db, current user, org context, RBAC
├── middleware/     rate limiting, logging, error mapping
├── permissions/    RBAC policy (OrgRole + super-admin)
├── utils/          decimal/date serialization, money math, German formatting
├── seeds/          demo + pilot org seeds (ported from scripts/seed-*.ts)
└── tests/          pytest unit/integration/API
```

## Local development
```bash
python -m venv .venv && source .venv/bin/activate   # (Windows: .venv\Scripts\activate)
pip install -e ".[dev]"
cp .env.example .env                                 # adjust DATABASE_URL
alembic upgrade head                                 # apply migrations
uvicorn app.main:app --reload --port 8000
```
OpenAPI docs: http://localhost:8000/docs · Health: http://localhost:8000/api/health

## Database migrations (Alembic)
```bash
alembic revision --autogenerate -m "describe change"
alembic upgrade head
alembic downgrade -1
```

## Tests / quality
```bash
pytest
ruff check app && black --check app && mypy app
```

## Migration status
Phase 0 (scaffold) done. Phase 1 (data layer: 46 models, 24 enums, initial
migration, seeds) in progress. See `../docs/02-migration-roadmap.md`.
