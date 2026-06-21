# FörderFlow — separated full-stack. Common dev/ops commands.
# Usage: make <target>

COMPOSE := docker compose
BACKEND := foerderflow-backend
FRONTEND := foerderflow-frontend

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

# ── Docker (full stack) ──────────────────────────────────────────────
.PHONY: up
up: ## Build + start all services (db, backend, frontend, mailpit)
	$(COMPOSE) up --build -d

.PHONY: down
down: ## Stop all services
	$(COMPOSE) down

.PHONY: logs
logs: ## Tail logs for all services
	$(COMPOSE) logs -f

.PHONY: ps
ps: ## Show service status
	$(COMPOSE) ps

.PHONY: clean
clean: ## Stop services and remove volumes (DESTROYS DB DATA)
	$(COMPOSE) down -v

# ── Database / migrations ────────────────────────────────────────────
.PHONY: migrate
migrate: ## Apply Alembic migrations (inside backend container)
	$(COMPOSE) exec backend alembic upgrade head

.PHONY: makemigration
makemigration: ## Autogenerate a migration: make makemigration m="message"
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

.PHONY: seed
seed: ## Seed demo data
	$(COMPOSE) exec backend python -m app.seeds.demo

# ── Backend (local) ──────────────────────────────────────────────────
.PHONY: backend-install
backend-install: ## Install backend deps (editable + dev)
	cd $(BACKEND) && pip install -e ".[dev]"

.PHONY: backend-dev
backend-dev: ## Run backend with reload
	cd $(BACKEND) && uvicorn app.main:app --reload --port 8000

.PHONY: backend-test
backend-test: ## Run backend tests
	cd $(BACKEND) && pytest

.PHONY: backend-lint
backend-lint: ## Lint + typecheck backend
	cd $(BACKEND) && ruff check app && black --check app && mypy app

# ── Frontend (local) ─────────────────────────────────────────────────
.PHONY: frontend-install
frontend-install: ## Install frontend deps
	cd $(FRONTEND) && npm install

.PHONY: frontend-dev
frontend-dev: ## Run frontend dev server
	cd $(FRONTEND) && npm run dev

.PHONY: frontend-test
frontend-test: ## Run frontend tests
	cd $(FRONTEND) && npm test

.PHONY: frontend-lint
frontend-lint: ## Lint + typecheck frontend
	cd $(FRONTEND) && npm run lint && npm run typecheck

# ── Aggregate ────────────────────────────────────────────────────────
.PHONY: test
test: backend-test frontend-test ## Run all tests

.PHONY: lint
lint: backend-lint frontend-lint ## Lint everything
