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

    def test_long_text_preserved(self):
        long_text = "x" * 1000
        result = parse_message_content(long_text)
        assert len(result) == 1000


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
        assert extract_tool_names(content) == '["Bash", "Read"]'

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


class TestExtractCommandName:
    def test_slash_command(self):
        from ingest import extract_command_name
        content = "<command-name>/model</command-name>\n<command-message>model</command-message>"
        assert extract_command_name(content) == "/model"

    def test_no_command(self):
        from ingest import extract_command_name
        assert extract_command_name("just text") == ""

    def test_non_string(self):
        from ingest import extract_command_name
        assert extract_command_name([{"type": "text", "text": "hi"}]) == ""


class TestResolveProjectPath:
    def test_hyphenated_repository_name(self):
        from ingest import resolve_project_path
        cwd = "/Users/a1yama/ghq/github.com/a1yama/claude-activity-dashboard"
        dir_name = "-Users-a1yama-ghq-github-com-a1yama-claude-activity-dashboard"
        assert resolve_project_path(cwd, dir_name) == cwd

    def test_subdirectory_walks_up_to_the_project_root(self):
        from ingest import resolve_project_path
        root = "/Users/a1yama/ghq/github.com/a1yama/media-pipeline"
        dir_name = "-Users-a1yama-ghq-github-com-a1yama-media-pipeline"
        assert resolve_project_path(f"{root}/frontend/src", dir_name) == root

    def test_unrelated_cwd(self):
        from ingest import resolve_project_path
        assert resolve_project_path("/tmp/other", "-Users-a1yama-foo") is None


class TestFormatProjectName:
    def test_relative_to_home(self):
        from ingest import format_project_name
        name = format_project_name(
            "/Users/a1yama/ghq/github.com/a1yama/claude-activity-dashboard",
            Path("/Users/a1yama"),
        )
        assert name == "ghq/github.com/a1yama/claude-activity-dashboard"

    def test_home_itself(self):
        from ingest import format_project_name
        assert format_project_name("/Users/a1yama", Path("/Users/a1yama")) == "~"

    def test_outside_home(self):
        from ingest import format_project_name
        assert format_project_name("/srv/app", Path("/Users/a1yama")) == "srv/app"


class TestBackfillProjectNames:
    def test_fixes_rows_whose_logs_are_gone(self, tmp_path):
        from ingest import backfill_project_names, build_project_path_index, init_db
        conn = init_db(tmp_path / "t.db")
        conn.execute(
            """INSERT INTO sessions (session_id, project_dir, project_name, project_path)
               VALUES ('s1', '-Users-me-work-my-app', 'work/my/app', '')"""
        )
        index = build_project_path_index(["/Users/me/work/my-app/src"])
        assert backfill_project_names(conn, index, home=Path("/Users/me")) == 1
        row = conn.execute(
            "SELECT project_name, project_path FROM sessions"
        ).fetchone()
        assert row == ("work/my-app", "/Users/me/work/my-app")
        conn.close()

    def test_leaves_unresolvable_rows_alone(self, tmp_path):
        from ingest import backfill_project_names, build_project_path_index, init_db
        conn = init_db(tmp_path / "t.db")
        conn.execute(
            """INSERT INTO sessions (session_id, project_dir, project_name, project_path)
               VALUES ('s1', '-gone-forever', 'gone/forever', '')"""
        )
        assert backfill_project_names(conn, build_project_path_index([])) == 0
        assert conn.execute("SELECT project_name FROM sessions").fetchone()[0] == "gone/forever"
        conn.close()


class TestDiscoverCustomCommands:
    def _make_claude_dir(self, base, commands=(), skills=()):
        for name in commands:
            path = base / ".claude" / "commands" / f"{name}.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("cmd")
        for name in skills:
            path = base / ".claude" / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("skill")
        return base / ".claude"

    def test_collects_commands_and_skills(self, tmp_path):
        from ingest import collect_command_names
        claude_dir = self._make_claude_dir(
            tmp_path, commands=["Pipeline"], skills=["analyze-usage"]
        )
        assert collect_command_names(claude_dir) == {"pipeline", "analyze-usage"}

    def test_missing_directory(self, tmp_path):
        from ingest import collect_command_names
        assert collect_command_names(tmp_path / "nope") == set()

    def test_nested_commands_are_namespaced(self, tmp_path):
        from ingest import collect_command_names
        path = tmp_path / ".claude" / "commands" / "git" / "diff.md"
        path.parent.mkdir(parents=True)
        path.write_text("cmd")
        assert collect_command_names(tmp_path / ".claude") == {"git:diff"}

    def test_plugin_commands_are_namespaced(self, tmp_path):
        from ingest import collect_plugin_command_names
        cmd = tmp_path / "marketplaces" / "mkt" / "plugins" / "codex" / "commands" / "rescue.md"
        cmd.parent.mkdir(parents=True)
        cmd.write_text("cmd")
        skill = tmp_path / "marketplaces" / "mkt" / "plugins" / "slack" / "skills" / "standup" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("skill")
        # スキルは <command-name>standup</command-name> のようにベア名でも記録される
        assert collect_plugin_command_names(tmp_path) == {
            "codex:rescue", "slack:standup", "standup",
        }

    def test_readme_is_not_a_command(self, tmp_path):
        from ingest import collect_command_names
        base = tmp_path / ".claude" / "commands"
        base.mkdir(parents=True)
        (base / "README.md").write_text("docs")
        (base / "deploy.md").write_text("cmd")
        assert collect_command_names(tmp_path / ".claude") == {"deploy"}

    def test_plugin_name_comes_from_the_manifest(self, tmp_path):
        import json
        from ingest import collect_plugin_command_names
        # cache 配下は <marketplace>/<plugin>/<version>/ でバージョンが親ディレクトリになる
        root = tmp_path / "cache" / "openai-codex" / "codex" / "1.0.3"
        (root / "commands").mkdir(parents=True)
        (root / "commands" / "rescue.md").write_text("cmd")
        (root / ".claude-plugin").mkdir()
        (root / ".claude-plugin" / "plugin.json").write_text(json.dumps({"name": "codex"}))
        assert collect_plugin_command_names(tmp_path) == {"codex:rescue"}

    def test_cached_plugin_without_manifest_uses_the_plugin_directory(self, tmp_path):
        from ingest import collect_plugin_command_names
        root = tmp_path / "cache" / "anthropic-agent-skills" / "example-skills" / "1f630fdf9259"
        (root / "skills" / "canvas-design").mkdir(parents=True)
        (root / "skills" / "canvas-design" / "SKILL.md").write_text("skill")
        assert collect_plugin_command_names(tmp_path) == {
            "example-skills:canvas-design", "canvas-design",
        }

    def test_plugin_name_falls_back_to_directory(self, tmp_path):
        from ingest import collect_plugin_command_names
        root = tmp_path / "repos" / "owner" / "myplugin"
        (root / "commands").mkdir(parents=True)
        (root / "commands" / "run.md").write_text("cmd")
        assert collect_plugin_command_names(tmp_path) == {"myplugin:run"}

    def test_nested_directories_are_not_plugin_roots(self, tmp_path):
        from ingest import collect_plugin_command_names
        # <plugin>/skills/<skill>/commands/ をプラグインルートと誤認しないこと
        root = tmp_path / "marketplaces" / "mkt" / "plugins" / "codex"
        nested = root / "skills" / "rescue" / "commands"
        nested.mkdir(parents=True)
        (nested / "inner.md").write_text("cmd")
        (root / "skills" / "rescue" / "SKILL.md").write_text("skill")
        assert collect_plugin_command_names(tmp_path) == {"codex:rescue", "rescue"}

    def test_walks_up_from_a_subdirectory(self, tmp_path):
        from ingest import discover_custom_commands
        home = tmp_path / "home"
        project = home / "work" / "proj"
        (project / "frontend").mkdir(parents=True)
        self._make_claude_dir(project, commands=["deploy"])
        names = discover_custom_commands(
            [str(project / "frontend")],
            claude_home=home / ".claude",
            plugins_dir=tmp_path / "no-plugins",
        )
        assert "deploy" in names

    def test_scans_a_path_outside_the_boundary_without_walking_up(self, tmp_path):
        from ingest import discover_custom_commands
        outside = tmp_path / "volume" / "proj"
        outside.mkdir(parents=True)
        self._make_claude_dir(outside, commands=["external"])
        self._make_claude_dir(tmp_path / "volume", commands=["parent-of-external"])
        names = discover_custom_commands(
            [str(outside)],
            claude_home=tmp_path / "home" / ".claude",
            plugins_dir=tmp_path / "no-plugins",
        )
        assert names == {"external"}

    def test_stops_walking_up_at_the_boundary(self, tmp_path):
        from ingest import discover_custom_commands
        home = tmp_path / "home"
        (home / "work").mkdir(parents=True)
        self._make_claude_dir(home, commands=["home-only"])
        names = discover_custom_commands(
            [str(home / "work")],
            claude_home=tmp_path / "empty" / ".claude",
            plugins_dir=tmp_path / "no-plugins",
            stop_at=home / "work",
        )
        assert names == set()


class TestIsCustomCommand:
    def test_builtin_is_not_custom(self):
        from ingest import is_custom_command
        assert is_custom_command("/exit", set()) is False

    def test_unknown_command_falls_back_to_custom(self):
        from ingest import is_custom_command
        # 元ログもコマンド定義も残っていない過去データを取りこぼさない
        assert is_custom_command("/pipeline", set()) is True

    def test_allowlist_wins_over_builtin_name(self):
        from ingest import is_custom_command
        assert is_custom_command("/diff", {"diff"}) is True

    def test_empty_name(self):
        from ingest import is_custom_command
        assert is_custom_command("", {"diff"}) is False


class TestClassifyCommands:
    def test_updates_existing_rows(self, tmp_path):
        from ingest import classify_commands, init_db
        conn = init_db(tmp_path / "t.db")
        rows = [("m1", "/exit"), ("m2", "/pipeline"), ("m3", "/diff")]
        conn.executemany(
            """INSERT INTO messages
               (uuid, session_id, type, timestamp, timestamp_jst, date_jst, hour_jst, command_name)
               VALUES (?, 's1', 'user', '2026-03-01T00:00:00+09:00', '2026-03-01 00:00:00',
                       '2026-03-01', 0, ?)""",
            rows,
        )
        classify_commands(conn, {"diff"})
        result = dict(
            conn.execute("SELECT command_name, is_custom_command FROM messages")
        )
        assert result == {"/exit": 0, "/pipeline": 1, "/diff": 1}
        conn.close()


class TestCountToolErrors:
    def test_with_errors(self):
        from ingest import count_tool_errors
        content = [
            {"type": "tool_result", "is_error": True, "content": "boom"},
            {"type": "tool_result", "content": "ok"},
            {"type": "tool_result", "is_error": True, "content": "boom2"},
        ]
        assert count_tool_errors(content) == 2

    def test_no_errors(self):
        from ingest import count_tool_errors
        assert count_tool_errors([{"type": "tool_result", "content": "ok"}]) == 0

    def test_string_content(self):
        from ingest import count_tool_errors
        assert count_tool_errors("text") == 0


class TestExtractUsage:
    def test_full_usage(self):
        from ingest import extract_usage
        msg = {"usage": {
            "input_tokens": 10, "output_tokens": 20,
            "cache_creation_input_tokens": 30, "cache_read_input_tokens": 40,
        }}
        assert extract_usage(msg) == (10, 20, 30, 40)

    def test_missing_usage(self):
        from ingest import extract_usage
        assert extract_usage({}) == (0, 0, 0, 0)

    def test_null_values(self):
        from ingest import extract_usage
        assert extract_usage({"usage": {"input_tokens": None}}) == (0, 0, 0, 0)


class TestNewMessageFields:
    def _make_jsonl(self, tmp_path, records, name="test-session.jsonl"):
        path = tmp_path / name
        with open(path, "w") as f:
            for r in records:
                f.write(json.dumps(r) + "\n")
        return path

    def test_model_usage_stop_reason_stored(self, tmp_path):
        conn = init_db(tmp_path / "test.db")
        records = [
            {
                "uuid": "a1", "type": "assistant",
                "timestamp": "2026-03-08T10:00:00Z",
                "message": {
                    "content": [{"type": "text", "text": "Hi"}],
                    "model": "claude-fable-5",
                    "stop_reason": "end_turn",
                    "usage": {
                        "input_tokens": 100, "output_tokens": 50,
                        "cache_creation_input_tokens": 10, "cache_read_input_tokens": 5000,
                    },
                },
            },
        ]
        ingest_session(conn, self._make_jsonl(tmp_path, records), "d", "p")
        conn.commit()
        row = conn.execute(
            "SELECT model, stop_reason, input_tokens, output_tokens,"
            " cache_creation_tokens, cache_read_tokens FROM messages"
        ).fetchone()
        assert row == ("claude-fable-5", "end_turn", 100, 50, 10, 5000)

    def test_command_and_error_stored(self, tmp_path):
        conn = init_db(tmp_path / "test.db")
        records = [
            {
                "uuid": "u1", "type": "user",
                "timestamp": "2026-03-08T10:00:00Z",
                "message": {"content": "<command-name>/loop</command-name>"},
            },
            {
                "uuid": "u2", "type": "user",
                "timestamp": "2026-03-08T10:01:00Z",
                "message": {"content": [
                    {"type": "tool_result", "is_error": True, "content": "err"},
                ]},
            },
        ]
        ingest_session(conn, self._make_jsonl(tmp_path, records), "d", "p")
        conn.commit()
        rows = conn.execute(
            "SELECT uuid, command_name, error_count FROM messages ORDER BY uuid"
        ).fetchall()
        assert rows[0] == ("u1", "/loop", 0)
        assert rows[1] == ("u2", "", 1)

    def test_subagent_ingest_does_not_touch_sessions(self, tmp_path):
        conn = init_db(tmp_path / "test.db")
        main_records = [
            {"uuid": "m1", "type": "user", "timestamp": "2026-03-08T10:00:00Z",
             "message": {"content": "main"}},
        ]
        main_path = self._make_jsonl(tmp_path, main_records, "parent-session.jsonl")
        ingest_session(conn, main_path, "d", "p")

        sub_records = [
            {"uuid": "s1", "type": "assistant", "timestamp": "2026-03-08T10:05:00Z",
             "message": {"content": [{"type": "text", "text": "sub"}],
                          "model": "claude-haiku-4-5",
                          "usage": {"input_tokens": 1, "output_tokens": 2}}},
        ]
        sub_path = self._make_jsonl(tmp_path, sub_records, "agent-001.jsonl")
        ingest_session(conn, sub_path, "d", "p",
                       session_id="parent-session", is_subagent=True)
        conn.commit()

        # sessions はメインの1行のみ・統計は上書きされない
        sessions = conn.execute("SELECT session_id, message_count FROM sessions").fetchall()
        assert sessions == [("parent-session", 1)]
        # サブエージェントメッセージは親 session_id + is_subagent=1 で格納
        sub = conn.execute(
            "SELECT session_id, is_subagent, model FROM messages WHERE uuid = 's1'"
        ).fetchone()
        assert sub == ("parent-session", 1, "claude-haiku-4-5")


class TestSchemaMigration:
    def test_old_db_gains_new_columns(self, tmp_path):
        # 旧スキーマ（新列なし）の DB を作って init_db でマイグレーションされること
        db_path = tmp_path / "old.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("""
            CREATE TABLE messages (
                uuid TEXT PRIMARY KEY, session_id TEXT NOT NULL, type TEXT NOT NULL,
                subtype TEXT, timestamp TEXT NOT NULL, timestamp_jst TEXT NOT NULL,
                date_jst TEXT NOT NULL, hour_jst INTEGER NOT NULL,
                content_preview TEXT, tool_count INTEGER DEFAULT 0,
                tool_names TEXT, tool_details TEXT, is_meta INTEGER DEFAULT 0
            )
        """)
        conn.execute(
            "INSERT INTO messages (uuid, session_id, type, timestamp, timestamp_jst,"
            " date_jst, hour_jst) VALUES ('old1', 's', 'user', 't', 't', '2026-01-01', 0)"
        )
        conn.commit()
        conn.close()

        conn = init_db(db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(messages)")}
        assert {"model", "input_tokens", "command_name", "is_subagent"} <= cols
        # 既存行はデフォルト値で読める
        row = conn.execute(
            "SELECT is_subagent, input_tokens FROM messages WHERE uuid = 'old1'"
        ).fetchone()
        assert row == (0, 0)
