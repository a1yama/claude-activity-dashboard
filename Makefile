.PHONY: setup ingest serve serve-only dev dev-api dev-frontend build test test-py test-front test-e2e sync proposals proposals-list proposal-adopt proposal-reject proposal-reopen

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DATASETTE := $(VENV)/bin/datasette
DB := data/claude_activity.db
SERVER := a1yama-pj
SERVER_DB_PATH := /srv/apps/claude-dashboard/data/claude_activity.db

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

# Unit tests (Python + frontend)
test: test-py test-front

test-py:
	$(VENV)/bin/pytest

test-front:
	cd frontend && npm test

# E2E tests: create fixture DB and run Playwright
test-e2e:
	$(PYTHON) e2e/create-fixture-db.py
	cd frontend && npx playwright test --config ../e2e/playwright.config.ts

# 系統B: 週次スロットル付きの改善提案生成(claude -p)。毎回呼んでも内部で間引く
proposals:
	$(PYTHON) scripts/generate-proposals.py

# 改善候補の採否記録。本番DBは読み取り専用なので Mac 側で記録し make sync で反映する
proposals-list:
	@$(PYTHON) scripts/proposal-status.py list

proposal-adopt:
	@$(PYTHON) scripts/proposal-status.py adopt $(ID)

proposal-reject:
	@$(PYTHON) scripts/proposal-status.py reject $(ID)

proposal-reopen:
	@$(PYTHON) scripts/proposal-status.py reopen $(ID)

# 本番サーバへ手動同期: ingest → 提案生成 → WAL checkpoint → scp → datasette restart
# 転送は別名で行い mv で差し替える。稼働中の datasette は DB を開いたままなので、
# 同じ inode を上書きすると転送中の中途半端な内容を読んで malformed になる
sync: ingest proposals
	$(PYTHON) -c "import sqlite3; c=sqlite3.connect('$(DB)'); c.execute('PRAGMA wal_checkpoint(TRUNCATE);'); c.close()"
	scp -q $(DB) $(SERVER):$(SERVER_DB_PATH).new
	ssh $(SERVER) 'mv $(SERVER_DB_PATH).new $(SERVER_DB_PATH) && cd /srv/apps/claude-dashboard && sudo docker compose restart datasette'
	@echo "✓ sync done -> https://dashboard.a1yama.com/"
