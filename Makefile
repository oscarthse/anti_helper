# =============================================================================
# Antigravity Dev - Development Workflow
# =============================================================================

.PHONY: install dev up down db-upgrade db-revision db-reset test test-unit test-frontend test-all lint format check build push sync-schema help

# Default shell
SHELL := /bin/bash

# Configuration
PYTHON_VENV := .venv
PYTHON := $(PYTHON_VENV)/bin/python
PYTEST := $(PYTHON_VENV)/bin/pytest
ALEMBIC := $(PYTHON_VENV)/bin/alembic
UVICORN := $(PYTHON_VENV)/bin/uvicorn
DRAMATIQ := $(PYTHON_VENV)/bin/dramatiq

# =============================================================================
# Help
# =============================================================================

help: ## Show this help message
	@echo "Antigravity Dev - Management Commands"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# =============================================================================
# Development
# =============================================================================

install: ## Install all dependencies
	@echo "Installing dependencies..."
	uv pip install -e ".[dev]"
	cd frontend && npm install

dev: ## Start API + workers in development mode (requires 'make up' first)
	@echo "Starting API and Workers..."
	@# Use specific terminals or background processes in real usage
	@echo "Run 'make dev-api' and 'make dev-worker' in separate terminals"

dev-api: ## Start API server
	$(UVICORN) backend.app.main:app --host 0.0.0.0 --port 8000 --reload

dev-worker: ## Start Dramatiq workers
	$(DRAMATIQ) backend.app.workers --processes 2 --threads 4

up: ## Start infrastructure (PostgreSQL, Redis)
	docker-compose up -d postgres redis

down: ## Stop infrastructure
	docker-compose down

# =============================================================================
# Database
# =============================================================================

db-upgrade: ## Apply all migrations
	$(ALEMBIC) upgrade head

db-revision: ## Create new migration (usage: make db-revision MSG="message")
	@if [ -z "$(MSG)" ]; then echo "Error: MSG argument required"; exit 1; fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

db-reset: ## Reset database (DROP ALL DATA)
	docker-compose down -v
	docker-compose up -d postgres
	@echo "Waiting for Postgres..."
	@sleep 5
	$(ALEMBIC) upgrade head

# =============================================================================
# Testing
# =============================================================================

test: ## Run all Python tests
	$(PYTEST) tests/ -v

test-unit: ## Run Python unit tests only
	$(PYTEST) tests/unit/ -v

test-frontend: ## Run frontend Jest tests
	cd frontend && npm test

test-all: test test-frontend ## Run all tests (Python + Frontend)

# =============================================================================
# Code Quality
# =============================================================================

lint: ## Run linting (Ruff, Mypy)
	@echo "Running Ruff..."
	$(PYTHON_VENV)/bin/ruff check .
	@echo "Running Mypy..."
	$(PYTHON_VENV)/bin/mypy .

format: ## Format code (Ruff)
	$(PYTHON_VENV)/bin/ruff check --fix .
	$(PYTHON_VENV)/bin/ruff format .

check: lint test-all ## Run full CI check (lint + all tests)

# =============================================================================
# Schema Sync
# =============================================================================

sync-schema: ## Generate TypeScript types from Pydantic models
	@echo "Syncing Pydantic models to TypeScript..."
	$(PYTHON) -m backend.scripts.sync_schema

# =============================================================================
# Docker
# =============================================================================

build: ## Build Docker images
	docker-compose build

push: ## Push Docker images to registry (requires login)
	docker-compose push
