# FörderFlow — Structured Full-Stack

A modern, **fully separated** rewrite of the FörderFlow monolith (`../foerderflow`):
an independent **FastAPI backend** and **Next.js frontend** communicating only over
REST. Goal: **100% functional parity** with the monolith (the single source of truth).

> Domain: Fördermittelverwaltung für soziale Träger (German non-profit funding/grant
> management) — funding measures, bank transactions, salary recording, rule-based
> allocations, compliance, reporting.

## Repository layout
```
new-structured-foerderflow/
├── foerderflow-backend/    FastAPI · SQLAlchemy 2 · Alembic · Pydantic v2 · JWT
├── foerderflow-frontend/   Next.js · TS · Tailwind · TanStack Query · Axios
├── docker-compose.yml      db · backend · frontend · mailpit (healthchecks)
├── .env.example            root env (cascades into both apps)
├── Makefile                dev/ops commands (make help)
├── README.md               this file
└── docs/                   analysis, roadmap, decisions, endpoint inventory
```

## Quick start (Docker)
```bash
cp .env.example .env          # set AUTH_SECRET, POSTGRES_PASSWORD
make up                       # build + start everything
make migrate                  # apply DB schema
make seed                     # (optional) demo data
```
- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- Mailpit (magic-link inbox): http://localhost:8025

## Local development (without Docker)
```bash
make backend-install && make backend-dev      # :8000
make frontend-install && make frontend-dev    # :3000
```

## Architecture decisions (confirmed)
- **Auth:** passwordless magic-link → JWT issued after email verification (no passwords).
- **Frontend data:** SSR-via-BFF — Server Components call the REST API; TanStack Query
  for client-side mutations/lists.


