# jltg-mapper — developer environment
#
# Common entry points for backend (uv) + frontend (pnpm) + local Postgres (Docker).
# Run `make help` for a summary of available targets.

.DEFAULT_GOAL := help

# Tools
UV    ?= uv
PNPM  ?= pnpm
COMPOSE ?= docker compose

# Directories
BACKEND_DIR  := backend
FRONTEND_DIR := frontend

# Ports / URLs (informational)
BACKEND_PORT  := 8000
FRONTEND_PORT := 5173

.PHONY: help install dev backend frontend db-up db-down migrate test lint build data

help: ## Show this help
	@echo "jltg-mapper — make targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| sort \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Install backend (uv sync) and frontend (pnpm install) dependencies
	cd $(BACKEND_DIR) && $(UV) sync
	cd $(FRONTEND_DIR) && $(PNPM) install

dev: ## Run backend + frontend dev servers together (Ctrl-C stops both)
	@echo "Starting backend (:$(BACKEND_PORT)) and frontend (:$(FRONTEND_PORT))..."
	@echo "Tip: 'make backend' / 'make frontend' run them individually."
	@trap 'kill 0' INT TERM EXIT; \
		( cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload ) & \
		( cd $(FRONTEND_DIR) && $(PNPM) dev ) & \
		wait

backend: ## Run the backend dev server (uvicorn --reload)
	cd $(BACKEND_DIR) && $(UV) run uvicorn app.main:app --reload

frontend: ## Run the frontend dev server (vite)
	cd $(FRONTEND_DIR) && $(PNPM) dev

db-up: ## Start local Postgres in Docker (idempotent)
	$(COMPOSE) up -d postgres

db-down: ## Stop local Postgres (keeps the data volume)
	$(COMPOSE) stop postgres

migrate: ## Apply database migrations (alembic) if configured
	@if [ -f $(BACKEND_DIR)/alembic.ini ]; then \
		cd $(BACKEND_DIR) && $(UV) run alembic upgrade head; \
	else \
		echo "No $(BACKEND_DIR)/alembic.ini yet — migrations not configured. Skipping."; \
	fi

test: ## Run backend tests (pytest)
	cd $(BACKEND_DIR) && $(UV) run python -m pytest

lint: ## Lint backend (ruff) and frontend (eslint)
	cd $(BACKEND_DIR) && $(UV) run ruff check .
	cd $(FRONTEND_DIR) && $(PNPM) lint

build: ## Build the frontend production bundle
	cd $(FRONTEND_DIR) && $(PNPM) build

data: ## Build geo-data assets from data/ (runs scripts/ build, if present)
	@if ls scripts/build_*.py scripts/build_*.sh >/dev/null 2>&1; then \
		echo "Running geo-data build scripts..."; \
		root=$$(pwd); \
		for s in scripts/build_*.py; do \
			[ -f "$$s" ] && ( cd $(BACKEND_DIR) && $(UV) run python "$$root/$$s" ); \
		done; \
		for s in scripts/build_*.sh; do \
			[ -f "$$s" ] && bash "$$s"; \
		done; \
	else \
		echo "No scripts/build_* scripts yet — geo-data pipeline not implemented. Skipping."; \
	fi
