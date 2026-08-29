"""Tests for scripts/generate-proposals.py の純粋関数。

ハイフンを含むファイル名のため importlib で直接ロードする。
LLM(claude -p) や analyze.py のサブプロセス呼び出しは対象外（純粋関数のみ検証）。
"""

import importlib.util
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "generate_proposals",
    Path(__file__).resolve().parent.parent / "scripts" / "generate-proposals.py",
)
gp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(gp)

JST = timezone(timedelta(hours=9))


def make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    gp.ensure_table(conn)
    return conn


class TestShouldGenerate:
    def test_none_last_means_generate(self):
        assert gp.should_generate(None, datetime.now(JST)) is True

    def test_recent_within_window_skips(self):
        now = datetime(2026, 6, 20, 12, 0, tzinfo=JST)
        last = now - timedelta(days=3)
        assert gp.should_generate(last, now) is False

    def test_old_enough_generates(self):
        now = datetime(2026, 6, 20, 12, 0, tzinfo=JST)
        last = now - timedelta(days=8)
        assert gp.should_generate(last, now) is True

    def test_exact_boundary_generates(self):
        now = datetime(2026, 6, 20, 12, 0, tzinfo=JST)
        last = now - timedelta(days=7)
        assert gp.should_generate(last, now) is True


class TestParseProposals:
    def _valid_item(self, **over):
        base = {
            "category": "claude_md",
            "title": "T",
            "rationale": "R",
            "suggestion": "S",
            "target_file": "~/.claude/CLAUDE.md",
        }
        base.update(over)
        return base

    def test_clean_array(self):
        import json

        out = json.dumps([self._valid_item()], ensure_ascii=False)
        result = gp.parse_proposals(out)
        assert len(result) == 1
        assert result[0]["category"] == "claude_md"

    def test_json_code_fence_stripped(self):
        import json

        body = json.dumps([self._valid_item()], ensure_ascii=False)
        result = gp.parse_proposals(f"```json\n{body}\n```")
        assert len(result) == 1

    def test_surrounding_prose_tolerated(self):
        import json

        body = json.dumps([self._valid_item()], ensure_ascii=False)
        result = gp.parse_proposals(f"以下が提案です:\n{body}\nご確認ください")
        assert len(result) == 1

    def test_invalid_category_dropped(self):
        import json

        out = json.dumps([self._valid_item(category="other")], ensure_ascii=False)
        assert gp.parse_proposals(out) == []

    def test_missing_required_field_dropped(self):
        import json

        out = json.dumps([self._valid_item(title="")], ensure_ascii=False)
        assert gp.parse_proposals(out) == []

    def test_target_file_defaults_to_empty(self):
        import json

        item = self._valid_item(category="skill")
        del item["target_file"]
        result = gp.parse_proposals(json.dumps([item], ensure_ascii=False))
        assert result[0]["target_file"] == ""

    def test_non_array_returns_empty(self):
        assert gp.parse_proposals('{"category":"skill"}') == []

    def test_garbage_returns_empty(self):
        assert gp.parse_proposals("これは JSON ではありません") == []

    def test_empty_array(self):
        assert gp.parse_proposals("[]") == []


class TestDecisionsSurviveRegeneration:
    ITEM = {
        "category": "skill",
        "title": "T",
        "rationale": "R",
        "suggestion": "S",
        "target_file": "",
    }

    def _write(self, conn, ts):
        gp.write_proposals(conn, [self.ITEM], ts)

    def test_status_is_carried_over_for_the_same_proposal(self):
        conn = make_db()
        self._write(conn, datetime(2026, 6, 1, tzinfo=JST).isoformat())
        conn.execute(
            "UPDATE improvement_proposals SET status = 'adopted', decided_at = '2026-06-02'"
        )
        self._write(conn, datetime(2026, 6, 8, tzinfo=JST).isoformat())
        assert conn.execute(
            "SELECT status, decided_at FROM improvement_proposals"
        ).fetchone() == ("adopted", "2026-06-02")

    def test_new_proposal_starts_open(self):
        conn = make_db()
        self._write(conn, datetime(2026, 6, 1, tzinfo=JST).isoformat())
        conn.execute("UPDATE improvement_proposals SET status = 'rejected'")
        gp.write_proposals(
            conn, [{**self.ITEM, "title": "別の提案"}],
            datetime(2026, 6, 8, tzinfo=JST).isoformat(),
        )
        assert conn.execute(
            "SELECT title, status FROM improvement_proposals"
        ).fetchone() == ("別の提案", "open")


class TestWriteAndRead:
    def test_write_then_last_generated_at(self):
        conn = make_db()
        ts = datetime(2026, 6, 20, 12, 0, tzinfo=JST).isoformat()
        gp.write_proposals(
            conn,
            [
                {
                    "category": "skill",
                    "title": "T",
                    "rationale": "R",
                    "suggestion": "S",
                    "target_file": "",
                }
            ],
            ts,
        )
        assert gp.last_generated_at(conn) == datetime.fromisoformat(ts)

    def test_write_replaces_previous_snapshot(self):
        conn = make_db()
        old = datetime(2026, 6, 1, tzinfo=JST).isoformat()
        new = datetime(2026, 6, 20, tzinfo=JST).isoformat()
        item = {
            "category": "skill",
            "title": "T",
            "rationale": "R",
            "suggestion": "S",
            "target_file": "",
        }
        gp.write_proposals(conn, [item, item], old)
        gp.write_proposals(conn, [item], new)
        rows = conn.execute("SELECT generated_at FROM improvement_proposals").fetchall()
        assert len(rows) == 1
        assert rows[0][0] == new

    def test_last_generated_at_empty_is_none(self):
        assert gp.last_generated_at(make_db()) is None


class TestBuildPrompt:
    def test_drops_bulky_user_messages(self):
        data = {
            "basic_stats": {"total_sessions": 3},
            "b2_user_messages": [{"content_preview": "x" * 100}] * 500,
        }
        prompt = gp.build_prompt(data)
        assert "b2_user_messages" not in prompt
        assert "total_sessions" in prompt


class TestEmptyParseDoesNotWipe:
    """回帰: パース失敗で既存の提案と採否の記録が消える経路を塞ぐ。

    対話用フックが headless の提案生成にも注入され、出力に散文が混ざると
    parse_proposals が 0 件を返す。以前はそのまま全削除だけが走っていた。
    """

    def test_existing_proposals_survive_an_empty_result(self):
        conn = make_db()
        gp.write_proposals(
            conn,
            [{"category": "skill", "title": "既存", "rationale": "r",
              "suggestion": "s", "target_file": ""}],
            "2026-08-25",
        )
        gp.write_proposals(conn, [], "2026-08-30")
        assert conn.execute("SELECT COUNT(*) FROM improvement_proposals").fetchone()[0] == 1

    def test_adoption_record_survives(self):
        conn = make_db()
        gp.write_proposals(
            conn,
            [{"category": "skill", "title": "既存", "rationale": "r",
              "suggestion": "s", "target_file": ""}],
            "2026-08-25",
        )
        conn.execute("UPDATE improvement_proposals SET status='adopted', decided_at='2026-08-26'")
        gp.write_proposals(conn, [], "2026-08-30")
        assert conn.execute(
            "SELECT status, decided_at FROM improvement_proposals"
        ).fetchone() == ("adopted", "2026-08-26")

    def test_prose_before_the_array_yields_nothing(self):
        # フックが注入する前提節を模した出力。角括弧が JSON より前に出ると取り出せない
        stdout = '⚖️ **前提**\n- 目的: [提案の生成]\n[{"category":"skill","title":"t","suggestion":"s"}]'
        assert gp.parse_proposals(stdout) == []

    def test_normal_output_still_replaces(self):
        conn = make_db()
        gp.write_proposals(
            conn,
            [{"category": "skill", "title": "旧", "rationale": "r",
              "suggestion": "s", "target_file": ""}],
            "2026-08-25",
        )
        gp.write_proposals(
            conn,
            [{"category": "hook", "title": "新", "rationale": "r",
              "suggestion": "s", "target_file": ""}],
            "2026-08-30",
        )
        rows = conn.execute("SELECT title FROM improvement_proposals").fetchall()
        assert rows == [("新",)]
