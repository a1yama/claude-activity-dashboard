"""Create a fixture SQLite database for E2E tests with known data."""

import sys
from pathlib import Path

# Add project root to path so we can import init_db from ingest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ingest import init_db

FIXTURE_DB_PATH = Path(__file__).resolve().parent / "fixtures" / "claude_activity.db"

SESSION_1_ID = "e2e-test-session-001"
SESSION_2_ID = "e2e-test-session-002"


def create_fixture_db():
    FIXTURE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if FIXTURE_DB_PATH.exists():
        FIXTURE_DB_PATH.unlink()

    conn = init_db(FIXTURE_DB_PATH)

    # Session 1: a normal session with messages and tool uses
    conn.execute(
        """INSERT INTO sessions
        (session_id, project_dir, project_name, first_message_at, last_message_at,
         message_count, user_message_count, assistant_message_count, tool_use_count, claude_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            SESSION_1_ID,
            "/Users/test/ghq/github.com/test/my-project",
            "ghq/github.com/test/my-project",
            "2026-03-01 10:00:00",
            "2026-03-01 10:30:00",
            5,  # message_count
            2,  # user_message_count
            3,  # assistant_message_count
            4,  # tool_use_count
            "claude-sonnet-4-6",
        ),
    )

    # Session 2: another session
    conn.execute(
        """INSERT INTO sessions
        (session_id, project_dir, project_name, first_message_at, last_message_at,
         message_count, user_message_count, assistant_message_count, tool_use_count, claude_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            SESSION_2_ID,
            "/Users/test/ghq/github.com/test/other-project",
            "ghq/github.com/test/other-project",
            "2026-03-02 14:00:00",
            "2026-03-02 14:45:00",
            3,  # message_count
            1,  # user_message_count
            2,  # assistant_message_count
            2,  # tool_use_count
            "claude-opus-4-6",
        ),
    )

    # Messages for session 1
    messages_s1 = [
        (
            "msg-001",
            SESSION_1_ID,
            "user",
            None,
            "2026-03-01T10:00:00+09:00",
            "2026-03-01 10:00:00",
            "2026-03-01",
            10,
            "バグを修正してください",
            0,
            "",
            "",
            0,
        ),
        (
            "msg-002",
            SESSION_1_ID,
            "assistant",
            None,
            "2026-03-01T10:01:00+09:00",
            "2026-03-01 10:01:00",
            "2026-03-01",
            10,
            "ファイルを確認します",
            2,
            '["Read", "Grep"]',
            '[{"name": "Read", "input": "src/app.ts"}, {"name": "Grep", "input": "error"}]',
            0,
        ),
        (
            "msg-003",
            SESSION_1_ID,
            "user",
            None,
            "2026-03-01T10:05:00+09:00",
            "2026-03-01 10:05:00",
            "2026-03-01",
            10,
            "ありがとう、テストも追加してください",
            0,
            "",
            "",
            0,
        ),
        (
            "msg-004",
            SESSION_1_ID,
            "assistant",
            None,
            "2026-03-01T10:06:00+09:00",
            "2026-03-01 10:06:00",
            "2026-03-01",
            10,
            "テストを追加します",
            1,
            '["Write"]',
            '[{"name": "Write", "input": "src/app.test.ts"}]',
            0,
        ),
        (
            "msg-005",
            SESSION_1_ID,
            "assistant",
            None,
            "2026-03-01T10:10:00+09:00",
            "2026-03-01 10:10:00",
            "2026-03-01",
            10,
            "修正とテスト追加が完了しました",
            1,
            '["Bash"]',
            '[{"name": "Bash", "input": "npm test"}]',
            0,
        ),
    ]

    # Messages for session 2
    messages_s2 = [
        (
            "msg-006",
            SESSION_2_ID,
            "user",
            None,
            "2026-03-02T14:00:00+09:00",
            "2026-03-02 14:00:00",
            "2026-03-02",
            14,
            "READMEを更新してください",
            0,
            "",
            "",
            0,
        ),
        (
            "msg-007",
            SESSION_2_ID,
            "assistant",
            None,
            "2026-03-02T14:01:00+09:00",
            "2026-03-02 14:01:00",
            "2026-03-02",
            14,
            "READMEを確認して更新します",
            1,
            '["Read"]',
            '[{"name": "Read", "input": "README.md"}]',
            0,
        ),
        (
            "msg-008",
            SESSION_2_ID,
            "assistant",
            None,
            "2026-03-02T14:05:00+09:00",
            "2026-03-02 14:05:00",
            "2026-03-02",
            14,
            "README更新が完了しました",
            1,
            '["Edit"]',
            '[{"name": "Edit", "input": "README.md"}]',
            0,
        ),
    ]

    for msg in messages_s1 + messages_s2:
        conn.execute(
            """INSERT INTO messages
            (uuid, session_id, type, subtype, timestamp, timestamp_jst, date_jst, hour_jst,
             content_preview, tool_count, tool_names, tool_details, is_meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            msg,
        )

    conn.commit()
    conn.close()
    print(f"Created fixture DB: {FIXTURE_DB_PATH}")


if __name__ == "__main__":
    create_fixture_db()
