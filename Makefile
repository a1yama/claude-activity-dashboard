.PHONY: setup ingest serve serve-only dev dev-api dev-frontend build test test-py test-front test-e2e sync merge-remote proposals proposals-list proposal-adopt proposal-reject proposal-reopen

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DATASETTE := $(VENV)/bin/datasette
DB := data/claude_activity.db
SERVER := a1yama-pj
SERVER_DB_PATH := /srv/apps/claude-dashboard/data/claude_activity.db

# data/ は gitignore なのでクローン直後は存在しない。
# 無いまま auto-sync.sh が走るとロックを作れず、失敗と見分けのつかないログだけが出続ける
setup:
	mkdir -p data
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

# 本番サーバへ同期: ingest → (本番を取得して併合) → 提案生成 → checkpoint → scp → restart
# 併合を挟むのは、複数の Mac から同期しても互いのセッションを消さないため。
# 手順の本体は scripts/sync-remote.sh(サーバ側ロックで区間全体を排他する)
sync: ingest
	SYNC_PYTHON=$(abspath $(PYTHON)) SYNC_SERVER=$(SERVER) SYNC_SERVER_DB=$(SERVER_DB_PATH) \
		scripts/sync-remote.sh

# 本番を取得してローカルへ併合するだけ(押し戻さない)。同期前の確認用
merge-remote:
	scp -q $(SERVER):$(SERVER_DB_PATH) data/.remote.db
	$(PYTHON) scripts/db_merge.py data/.remote.db $(DB)
	rm -f data/.remote.db
