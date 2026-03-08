.PHONY: setup ingest serve serve-only dev dev-api dev-frontend build test-e2e

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DATASETTE := $(VENV)/bin/datasette
DB := data/claude_activity.db

setup:
	python3 -m venv $(VENV)
	$(PIP) install -e .
	cd frontend && npm install

ingest:
	$(PYTHON) ingest.py

# Development: run Datasette API + Vite dev server
dev: ingest
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765 &
	cd frontend && npm run dev

# Datasette API only (for dev)
dev-api: ingest
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765

# Frontend dev server only
dev-frontend:
	cd frontend && npm run dev

# Build frontend
build:
	cd frontend && npm run build

# Legacy: Datasette-only serve
serve: ingest
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765 --open

serve-only:
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765 --open

# E2E tests: create fixture DB and run Playwright
test-e2e:
	$(PYTHON) e2e/create-fixture-db.py
	cd frontend && npx playwright test --config ../e2e/playwright.config.ts
