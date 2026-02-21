.PHONY: help install dev test lint format type-check docker-up docker-down clean frontend-install frontend-dev frontend-build frontend-lint

.DEFAULT_GOAL := help

help: ## Show available commands
	@echo "Available commands:"
	@echo "  make install           - Install production dependencies"
	@echo "  make dev               - Install production + dev dependencies, playwright, and pre-commit hooks"
	@echo "  make test              - Run pytest"
	@echo "  make lint              - Run ruff check"
	@echo "  make format            - Run ruff format"
	@echo "  make type-check        - Run type checking (placeholder)"
	@echo "  make docker-up         - Start Docker containers"
	@echo "  make docker-down       - Stop Docker containers"
	@echo "  make clean             - Remove cache and temp files"
	@echo "  make frontend-install  - Install frontend dependencies"
	@echo "  make frontend-dev      - Start frontend dev server"
	@echo "  make frontend-build    - Build frontend for production"
	@echo "  make frontend-lint     - Lint frontend code"

install: ## Install production dependencies
	python -m pip install -r requirements.txt

dev: ## Install production + dev dependencies, playwright, and pre-commit hooks
	python -m pip install -r requirements.txt
	python -m pip install -r requirements-dev.txt
	python -m playwright install
	python -m pre_commit install

test: ## Run pytest
	python -m pytest

lint: ## Run ruff check
	python -m ruff check .

format: ## Run ruff format
	python -m ruff format .

type-check: ## Run type checking (placeholder)
	@echo "Type checking is not yet configured. Consider adding mypy or pyright."

docker-up: ## Start Docker containers
	docker compose up -d --build

docker-down: ## Stop Docker containers
	docker compose down

clean: ## Remove cache and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -prune -o -type f -name "*.tmp" -print -exec rm -f {} + 2>/dev/null || true

frontend-install: ## Install frontend dependencies
	cd frontend && npm ci

frontend-dev: ## Start frontend dev server
	cd frontend && npm run dev

frontend-build: ## Build frontend for production
	cd frontend && npm run build

frontend-lint: ## Lint frontend code
	cd frontend && npm run lint
