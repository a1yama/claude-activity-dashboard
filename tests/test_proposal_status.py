"""Tests for scripts/proposal-status.py（採否記録CLIの純粋部分）。"""

import importlib.util
import sqlite3
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "proposal_status",
    Path(__file__).resolve().parent.parent / "scripts" / "proposal-status.py",
)
ps = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(ps)

NOW = "2026-07-28T13:00:00+09:00"


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        """CREATE TABLE improvement_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT, title TEXT,
            status TEXT DEFAULT 'open', decided_at TEXT DEFAULT ''
        )"""
    )
    conn.execute("INSERT INTO improvement_proposals (category, title) VALUES ('skill', 'T')")
    return conn


class TestSetStatus:
    def test_adopt_records_the_decision_time(self):
        conn = make_db()
        assert ps.set_status(conn, 1, "adopted", NOW) is True
        assert conn.execute(
            "SELECT status, decided_at FROM improvement_proposals"
        ).fetchone() == ("adopted", NOW)

    def test_reopen_clears_the_decision_time(self):
        conn = make_db()
        ps.set_status(conn, 1, "rejected", NOW)
        ps.set_status(conn, 1, "open", NOW)
        assert conn.execute(
            "SELECT status, decided_at FROM improvement_proposals"
        ).fetchone() == ("open", "")

    def test_unknown_id(self):
        assert ps.set_status(make_db(), 99, "adopted", NOW) is False


class TestMain:
    def test_rejects_unknown_command(self):
        assert ps.main(["bogus"]) == 2

    def test_requires_an_id(self):
        assert ps.main(["adopt"]) == 2
