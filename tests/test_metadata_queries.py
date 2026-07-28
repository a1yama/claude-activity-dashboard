import sqlite3
import textwrap
from pathlib import Path

import pytest

METADATA_PATH = Path(__file__).resolve().parent.parent / "metadata.yml"


def load_query(name: str) -> str:
    """Extract a Datasette canned query's SQL from metadata.yml.

    PyYAML は datasette の推移的依存として .venv にしか無く、品質ゲートは venv 外の
    pytest で走るため、stdlib だけで読める形にしている。
    """
    lines = METADATA_PATH.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() != f"{name}:":
            continue
        name_indent = len(line) - len(line.lstrip())
        for j in range(i + 1, len(lines)):
            body = lines[j]
            if body.strip() and len(body) - len(body.lstrip()) <= name_indent:
                break
            if body.strip() != "sql: |":
                continue
            sql_indent = len(body) - len(body.lstrip())
            sql = []
            for sql_line in lines[j + 1:]:
                if sql_line.strip() and len(sql_line) - len(sql_line.lstrip()) <= sql_indent:
                    break
                sql.append(sql_line)
            return textwrap.dedent("\n".join(sql))
        # クエリはあるのに読めない = ブロックスカラー以外の書き方に変わった
        raise ValueError(f"'{name}' has no 'sql: |' block; this reader only supports block scalars")
    raise KeyError(f"canned query not found in metadata.yml: {name}")


@pytest.fixture
def conn(tmp_path):
    from ingest import init_db

    conn = init_db(tmp_path / "test.db")
    yield conn
    conn.close()


def insert_commands(conn, commands, is_subagent=0):
    conn.executemany(
        """INSERT INTO messages
           (uuid, session_id, type, timestamp, timestamp_jst, date_jst, hour_jst,
            command_name, is_subagent)
           VALUES (?, 's1', 'user', '2026-03-01T00:00:00+09:00', '2026-03-01 00:00:00',
                   '2026-03-01', 0, ?, ?)""",
        [(f"u{i}-{is_subagent}", c, is_subagent) for i, c in enumerate(commands)],
    )


class TestLoadQuery:
    def test_extracts_sql_body(self):
        sql = load_query("command-usage")
        assert "FROM messages" in sql
        assert "LIMIT 30" in sql.strip().splitlines()[-1]

    def test_unknown_query(self):
        with pytest.raises(KeyError):
            load_query("no-such-query")


def run_command_usage(conn, known_commands=frozenset()):
    from ingest import classify_commands

    classify_commands(conn, set(known_commands))
    return [(r[0], r[1]) for r in conn.execute(load_query("command-usage"))]


class TestCommandUsage:
    def test_builtins_are_excluded(self, conn):
        # 追記漏れに気づけるよう、代表的なビルトインを一通り並べておく
        insert_commands(
            conn,
            [
                "/exit", "/exit", "/clear", "/compact", "/model", "/login",
                "/doctor", "/context", "/cost", "/resume", "/rewind", "/usage",
                "/agents", "/skills", "/plugin", "/tasks", "/stats", "/recap",
                "/goal", "/effort", "/insights", "/keybindings", "/pr-comments",
            ],
        )
        assert run_command_usage(conn) == []

    def test_custom_commands_are_ranked(self, conn):
        insert_commands(conn, ["/pipeline", "/pipeline", "/sod", "/exit", ""])
        assert run_command_usage(conn) == [("/pipeline", 2), ("/sod", 1)]

    def test_builtin_match_ignores_case_and_slash(self, conn):
        insert_commands(conn, ["/Clear", "compact"])
        assert run_command_usage(conn) == []

    def test_allowlisted_command_survives_a_builtin_name(self, conn):
        insert_commands(conn, ["/diff"])
        assert run_command_usage(conn, {"diff"}) == [("/diff", 1)]

    def test_subagent_messages_are_not_counted(self, conn):
        insert_commands(conn, ["/pipeline"])
        insert_commands(conn, ["/pipeline"], is_subagent=1)
        assert run_command_usage(conn) == [("/pipeline", 1)]
