"""Tests for ingest.py core functions."""

import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ingest import (
    count_tool_uses,
    extract_project_name,
    extract_tool_names,
    init_db,
    ingest_session,
    parse_message_content,
)


class TestExtractProjectName:
    def test_ghq_github_path(self):
        name = extract_project_name("-Users-a1yama-ghq-github-com-a1yama-my-repo")
        assert name == "ghq/github.com/a1yama/my/repo"

    def test_ghq_path_without_github(self):
        name = extract_project_name("-Users-a1yama-ghq-tig-gh")
        assert name == "ghq/tig/gh"

    def test_work_path(self):
        name = extract_project_name("-Users-a1yama-work-company-project")
        assert name == "work/company/project"

    def test_dotfiles(self):
        name = extract_project_name("-Users-a1yama-dotfiles")
        assert name == "dotfiles"

    def test_no_marker(self):
        name = extract_project_name("-Users-a1yama-some-project")
        assert name == "some/project"

    def test_empty_string(self):
        name = extract_project_name("")
        assert name == ""


class TestParseMessageContent:
    def test_plain_string(self):
        result = parse_message_content("hello world")
        assert result == "hello world"

    def test_string_with_xml_tags(self):
        result = parse_message_content("<system>some tag</system> visible text")
        assert result == "some tag visible text"

    def test_content_block_list(self):
        content = [
            {"type": "text", "text": "Hello"},
            {"type": "tool_use", "name": "Bash"},
            {"type": "text", "text": "World"},
        ]
        result = parse_message_content(content)
        assert result == "Hello\nWorld"

    def test_empty_list(self):
        result = parse_message_content([])
        assert result == ""

    def test_none_input(self):
        result = parse_message_content(None)
        assert result == ""

    def test_truncation(self):
        long_text = "x" * 1000
        result = parse_message_content(long_text)
        assert len(result) == 500


class TestCountToolUses:
    def test_with_tool_uses(self):
        content = [
            {"type": "text", "text": "Let me help"},
            {"type": "tool_use", "name": "Bash", "input": {}},
            {"type": "tool_use", "name": "Read", "input": {}},
        ]
        assert count_tool_uses(content) == 2

    def test_no_tool_uses(self):
        content = [{"type": "text", "text": "Hello"}]
        assert count_tool_uses(content) == 0

    def test_string_content(self):
        assert count_tool_uses("just a string") == 0

    def test_none_content(self):
        assert count_tool_uses(None) == 0

    def test_empty_list(self):
        assert count_tool_uses([]) == 0


class TestExtractToolNames:
    def test_multiple_tools(self):
        content = [
            {"type": "tool_use", "name": "Bash"},
            {"type": "text", "text": "result"},
            {"type": "tool_use", "name": "Read"},
        ]
        assert extract_tool_names(content) == "Bash,Read"

    def test_no_tools(self):
        assert extract_tool_names([{"type": "text", "text": "Hi"}]) == ""

    def test_non_list(self):
        assert extract_tool_names("string") == ""


class TestIngestSession:
    def _make_jsonl(self, tmp_path, records):
        path = tmp_path / "test-session.jsonl"
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return path

    def test_basic_ingest(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            {
                "uuid": "u1",
                "type": "user",
                "timestamp": "2026-03-08T10:00:00Z",
                "message": {"content": "Hello Claude"},
            },
            {
                "uuid": "u2",
                "type": "assistant",
                "timestamp": "2026-03-08T10:00:05Z",
                "message": {
                    "content": [
                        {"type": "text", "text": "Hi!"},
                        {"type": "tool_use", "name": "Bash", "input": {}},
                    ]
                },
            },
        ]
        jsonl_path = self._make_jsonl(tmp_path, records)
        ingest_session(conn, jsonl_path, "test-dir", "test/project")
        conn.commit()

        # Check session
        session = conn.execute("SELECT * FROM sessions").fetchone()
        assert session is not None
        assert session[2] == "test/project"  # project_name
        assert session[7] == 1  # assistant_message_count
        assert session[8] == 1  # tool_use_count

        # Check messages
        msgs = conn.execute("SELECT * FROM messages ORDER BY timestamp").fetchall()
        assert len(msgs) == 2

    def test_skips_invalid_records(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            {"uuid": "u1", "type": "user", "timestamp": "2026-03-08T10:00:00Z",
             "message": {"content": "valid"}},
            {"type": "user", "timestamp": "2026-03-08T10:00:01Z"},  # no uuid
            {"not": "valid json line"},  # no type/timestamp/uuid
        ]
        jsonl_path = self._make_jsonl(tmp_path, records)
        ingest_session(conn, jsonl_path, "test-dir", "test/project")
        conn.commit()

        msgs = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        assert msgs == 1

    def test_jst_conversion(self, tmp_path):
        db_path = tmp_path / "test.db"
        conn = init_db(db_path)

        records = [
            {
                "uuid": "u1",
                "type": "user",
                "timestamp": "2026-03-08T15:00:00Z",  # UTC 15:00 = JST 00:00 next day
                "message": {"content": "late night"},
            },
        ]
        jsonl_path = self._make_jsonl(tmp_path, records)
        ingest_session(conn, jsonl_path, "test-dir", "test/project")
        conn.commit()

        msg = conn.execute("SELECT date_jst, hour_jst FROM messages").fetchone()
        assert msg[0] == "2026-03-09"  # JST is next day
        assert msg[1] == 0  # midnight JST
