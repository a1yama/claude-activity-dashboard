"""Tests for scripts/db_merge.py（2台の Mac から同期しても消し合わないこと）。"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import db_merge  # noqa: E402

SCHEMA = """
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    project_name TEXT,
    last_message_at TEXT,
    message_count INTEGER DEFAULT 0
);
CREATE TABLE messages (
    uuid TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    type TEXT NOT NULL,
    content_preview TEXT
);
CREATE TABLE improvement_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'open',
    decided_at TEXT DEFAULT ''
);
"""


def make_db(extra_sql: str = "") -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.executescript(SCHEMA)
    if extra_sql:
        conn.executescript(extra_sql)
    return conn


def add_session(conn, sid, last, count=1):
    conn.execute(
        "INSERT OR REPLACE INTO sessions (session_id, project_name, last_message_at, message_count)"
        " VALUES (?, 'p', ?, ?)",
        (sid, last, count),
    )


def add_message(conn, uuid, sid="s1"):
    conn.execute(
        "INSERT OR REPLACE INTO messages (uuid, session_id, type, content_preview)"
        " VALUES (?, ?, 'user', 'x')",
        (uuid, sid),
    )


def add_proposal(conn, generated_at, category, title, status="open", decided_at=""):
    conn.execute(
        "INSERT INTO improvement_proposals (generated_at, category, title, status, decided_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (generated_at, category, title, status, decided_at),
    )


def sessions_of(conn):
    return {
        row[0]: row[1]
        for row in conn.execute("SELECT session_id, last_message_at FROM sessions")
    }


def proposals_of(conn):
    return [
        (row[0], row[1], row[2], row[3], row[4])
        for row in conn.execute(
            "SELECT generated_at, category, title, status, decided_at"
            " FROM improvement_proposals ORDER BY category, title"
        )
    ]


class TestMergeSessions:
    def test_other_machine_sessions_are_added(self):
        # 本丸の回帰テスト。従来の scp 上書きでは相手のセッションが消えていた
        src, dst = make_db(), make_db()
        add_session(src, "remote-1", "2026-08-20T10:00")
        add_session(dst, "local-1", "2026-08-21T10:00")

        db_merge.merge_db(src, dst)

        assert set(sessions_of(dst)) == {"remote-1", "local-1"}

    def test_newer_copy_wins(self):
        src, dst = make_db(), make_db()
        add_session(src, "s1", "2026-08-22T10:00", count=50)
        add_session(dst, "s1", "2026-08-20T10:00", count=10)

        db_merge.merge_db(src, dst)

        assert sessions_of(dst)["s1"] == "2026-08-22T10:00"
        assert dst.execute("SELECT message_count FROM sessions").fetchone()[0] == 50

    def test_local_copy_is_kept_when_it_is_newer(self):
        src, dst = make_db(), make_db()
        add_session(src, "s1", "2026-08-20T10:00", count=10)
        add_session(dst, "s1", "2026-08-22T10:00", count=50)

        db_merge.merge_db(src, dst)

        assert dst.execute("SELECT message_count FROM sessions").fetchone()[0] == 50

    def test_identical_timestamps_do_not_duplicate(self):
        src, dst = make_db(), make_db()
        add_session(src, "s1", "2026-08-20T10:00")
        add_session(dst, "s1", "2026-08-20T10:00")

        db_merge.merge_db(src, dst)

        assert dst.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1

    def test_null_last_message_at_does_not_crash(self):
        src, dst = make_db(), make_db()
        add_session(src, "s1", None)
        add_session(dst, "s1", None)

        db_merge.merge_db(src, dst)

        assert dst.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1

    def test_empty_source(self):
        src, dst = make_db(), make_db()
        add_session(dst, "local-1", "2026-08-21T10:00")

        assert db_merge.merge_db(src, dst)["sessions"] == 0
        assert set(sessions_of(dst)) == {"local-1"}


class TestMergeMessages:
    def test_new_messages_are_added(self):
        src, dst = make_db(), make_db()
        add_message(src, "m-remote")
        add_message(dst, "m-local")

        db_merge.merge_db(src, dst)

        assert dst.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 2

    def test_existing_messages_are_untouched(self):
        src, dst = make_db(), make_db()
        add_message(src, "m1")
        dst.execute(
            "INSERT INTO messages (uuid, session_id, type, content_preview)"
            " VALUES ('m1', 's1', 'user', 'ローカルの内容')"
        )

        assert db_merge.merge_db(src, dst)["messages"] == 0
        assert (
            dst.execute("SELECT content_preview FROM messages").fetchone()[0] == "ローカルの内容"
        )


class TestMergeProposals:
    def test_newer_snapshot_replaces_the_older_one(self):
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-25", "skill", "新しい提案")
        add_proposal(dst, "2026-08-18", "hook", "古い提案")

        db_merge.merge_db(src, dst)

        assert [(p[1], p[2]) for p in proposals_of(dst)] == [("skill", "新しい提案")]

    def test_older_snapshot_does_not_overwrite(self):
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-18", "hook", "古い提案")
        add_proposal(dst, "2026-08-25", "skill", "新しい提案")

        db_merge.merge_db(src, dst)

        assert [(p[1], p[2]) for p in proposals_of(dst)] == [("skill", "新しい提案")]

    def test_decision_made_on_the_other_machine_survives(self):
        # 相手側で採用した判断が、こちらの新しいスナップショットに引き継がれること
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-18", "skill", "同じ提案", "adopted", "2026-08-19")
        add_proposal(dst, "2026-08-25", "skill", "同じ提案")

        db_merge.merge_db(src, dst)

        assert proposals_of(dst) == [("2026-08-25", "skill", "同じ提案", "adopted", "2026-08-19")]

    def test_local_decision_survives_a_newer_remote_snapshot(self):
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-25", "skill", "同じ提案")
        add_proposal(dst, "2026-08-18", "skill", "同じ提案", "rejected", "2026-08-19")

        db_merge.merge_db(src, dst)

        assert proposals_of(dst) == [("2026-08-25", "skill", "同じ提案", "rejected", "2026-08-19")]

    def test_open_status_is_not_carried_over(self):
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-18", "skill", "同じ提案", "open", "")
        add_proposal(dst, "2026-08-25", "skill", "同じ提案", "adopted", "2026-08-26")

        db_merge.merge_db(src, dst)

        assert proposals_of(dst)[0][3] == "adopted"

    def test_ids_are_reassigned_not_carried(self):
        # id は世代ごとに振り直される使い捨て。持ち込むと本番側の連番と衝突する
        src, dst = make_db(), make_db()
        add_proposal(src, "2026-08-25", "skill", "A")
        add_proposal(src, "2026-08-25", "skill", "B")
        add_proposal(dst, "2026-08-18", "hook", "旧")

        db_merge.merge_db(src, dst)

        ids = [row[0] for row in dst.execute("SELECT id FROM improvement_proposals")]
        assert len(ids) == len(set(ids)) == 2

    def test_empty_proposals_on_both_sides(self):
        src, dst = make_db(), make_db()
        assert db_merge.merge_db(src, dst)["proposals"] == 0


class TestSchemaDrift:
    def test_columns_missing_on_one_side_are_skipped(self):
        # 本番 DB は Mac 側より古いスキーマのことがある。src 基準で列を組むと落ちる
        src = make_db()
        src.execute("ALTER TABLE sessions ADD COLUMN claude_version TEXT DEFAULT ''")
        add_session(src, "remote-1", "2026-08-20T10:00")
        dst = make_db()

        db_merge.merge_db(src, dst)

        assert set(sessions_of(dst)) == {"remote-1"}

    def test_missing_proposals_table_on_source(self):
        src = sqlite3.connect(":memory:")
        src.executescript(
            "CREATE TABLE sessions (session_id TEXT PRIMARY KEY, project_name TEXT,"
            " last_message_at TEXT, message_count INTEGER);"
            "CREATE TABLE messages (uuid TEXT PRIMARY KEY, session_id TEXT,"
            " type TEXT, content_preview TEXT);"
        )
        add_session(src, "remote-1", "2026-08-20T10:00")
        dst = make_db()
        add_proposal(dst, "2026-08-25", "skill", "残る提案")

        db_merge.merge_db(src, dst)

        assert set(sessions_of(dst)) == {"remote-1"}
        assert [(p[1], p[2]) for p in proposals_of(dst)] == [("skill", "残る提案")]


class TestMain:
    def test_missing_paths_are_reported(self, tmp_path):
        assert db_merge.main([str(tmp_path / "nope.db"), str(tmp_path / "also.db")]) == 1

    def test_wrong_argument_count(self):
        assert db_merge.main(["only-one"]) == 2

    def test_merges_two_files(self, tmp_path):
        src_path, dst_path = tmp_path / "src.db", tmp_path / "dst.db"
        for path, sid in ((src_path, "remote-1"), (dst_path, "local-1")):
            conn = sqlite3.connect(str(path))
            conn.executescript(SCHEMA)
            add_session(conn, sid, "2026-08-20T10:00")
            conn.commit()
            conn.close()

        assert db_merge.main([str(src_path), str(dst_path)]) == 0

        conn = sqlite3.connect(str(dst_path))
        assert set(sessions_of(conn)) == {"remote-1", "local-1"}
        conn.close()
