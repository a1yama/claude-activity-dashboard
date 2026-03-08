.PHONY: setup ingest serve

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip
DATASETTE := $(VENV)/bin/datasette
DB := data/claude_activity.db

setup:
	python3 -m venv $(VENV)
	$(PIP) install -e .

ingest:
	$(PYTHON) ingest.py

serve: ingest
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765 --open

serve-only:
	$(DATASETTE) serve $(DB) --metadata metadata.yml --plugins-dir plugins/ --port 8765 --open
