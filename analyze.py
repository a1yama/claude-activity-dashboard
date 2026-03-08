"""Analyze Claude Code activity logs and output structured report as JSON."""

import json
import sqlite3
import sys
from pathlib import Path


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def build_filter(args: list[str]) -> dict:
    """Parse CLI arguments into SQL filter clauses."""
    if not args:
        return {"messages": "", "sessions": "", "sessions_and": ""}

    arg = " ".join(args)

    # Period filter: "直近N日" or "last N days"
    import re
    m = re.search(r"(?:直近|last)\s*(\d+)\s*(?:日|days?)", arg, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        return {
            "messages": f"AND m.date_jst >= date('now', '-{n} days')",
            "sessions": f"WHERE date(s.first_message_at) >= date('now', '-{n} days')",
            "sessions_and": f"AND date(s.first_message_at) >= date('now', '-{n} days')",
        }

    # Project filter
    return {
        "messages": f"AND m.session_id IN (SELECT session_id FROM sessions WHERE project_name LIKE '%{arg}%')",
        "sessions": f"WHERE s.project_name LIKE '%{arg}%'",
        "sessions_and": f"AND s.project_name LIKE '%{arg}%'",
    }


def query_basic_stats(conn: sqlite3.Connection, f: dict) -> dict:
    sql = f"""
        SELECT
            COUNT(DISTINCT s.session_id) AS total_sessions,
            COALESCE(SUM(s.user_message_count), 0) AS total_user_messages,
            COALESCE(SUM(s.assistant_message_count), 0) AS total_assistant_messages,
            COALESCE(SUM(s.tool_use_count), 0) AS total_tool_uses,
            COUNT(DISTINCT s.project_name) AS total_projects,
            MIN(s.first_message_at) AS earliest,
            MAX(s.last_message_at) AS latest
        FROM sessions s
        {f['sessions']}
    """
    row = conn.execute(sql).fetchone()
    return dict(row) if row else {}


def query_a1_bash_alternatives(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            CASE
                WHEN input LIKE 'cat %' OR input LIKE 'head %' OR input LIKE 'tail %' THEN 'Read代替可能'
                WHEN input LIKE 'grep %' OR input LIKE 'rg %' THEN 'Grep代替可能'
                WHEN input LIKE 'find %' OR input LIKE 'ls %' THEN 'Glob代替可能'
                WHEN input LIKE 'sed %' OR input LIKE 'awk %' THEN 'Edit代替可能'
                WHEN input LIKE 'echo %>>%' OR input LIKE 'echo %>%' OR input LIKE 'cat <<%' THEN 'Write代替可能'
                ELSE 'other'
            END AS pattern,
            COUNT(*) AS count,
            SUBSTR(GROUP_CONCAT(input, ' | '), 1, 300) AS examples
        FROM (
            SELECT json_extract(je.value, '$.input') AS input
            FROM messages m, json_each(m.tool_details) AS je
            WHERE m.is_meta = 0
                AND m.type = 'assistant'
                AND m.tool_details <> ''
                AND json_extract(je.value, '$.name') = 'Bash'
                {f['messages']}
        )
        WHERE pattern <> 'other'
        GROUP BY pattern
        ORDER BY count DESC
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_a2_consecutive_tools(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            tool_name AS consecutive_tool,
            COUNT(*) AS consecutive_count
        FROM (
            SELECT
                json_extract(je.value, '$.name') AS tool_name,
                LAG(json_extract(je.value, '$.name')) OVER (
                    PARTITION BY m.session_id ORDER BY m.timestamp
                ) AS prev_tool
            FROM messages m, json_each(m.tool_details) AS je
            WHERE m.is_meta = 0
                AND m.type = 'assistant'
                AND m.tool_details <> ''
                {f['messages']}
        )
        WHERE tool_name = prev_tool
        GROUP BY tool_name
        ORDER BY consecutive_count DESC
        LIMIT 10
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_a3_tool_frequency(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            json_extract(je.value, '$.name') AS tool_name,
            COUNT(*) AS use_count
        FROM messages m, json_each(m.tool_details) AS je
        WHERE m.is_meta = 0
            AND m.type = 'assistant'
            AND m.tool_details <> ''
            {f['messages']}
        GROUP BY tool_name
        ORDER BY use_count DESC
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_b1_repeated_instructions(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            SUBSTR(content_preview, 1, 100) AS instruction,
            COUNT(*) AS repeat_count
        FROM messages m
        WHERE m.is_meta = 0
            AND m.type = 'user'
            AND m.content_preview <> ''
            AND LENGTH(m.content_preview) > 10
            {f['messages']}
        GROUP BY SUBSTR(content_preview, 1, 100)
        HAVING COUNT(*) >= 3
        ORDER BY repeat_count DESC
        LIMIT 20
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_b2_user_messages(conn: sqlite3.Connection, f: dict) -> list[dict]:
    """Return user messages for AI-driven keyword extraction."""
    sql = f"""
        SELECT content_preview
        FROM messages m
        WHERE m.is_meta = 0
            AND m.type = 'user'
            AND m.content_preview <> ''
            AND LENGTH(m.content_preview) > 5
            {f['messages']}
        LIMIT 5000
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_c1_fix_patterns(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            SUBSTR(m.content_preview, 1, 150) AS message,
            m.date_jst,
            s.project_name
        FROM messages m
        JOIN sessions s ON m.session_id = s.session_id
        WHERE m.is_meta = 0
            AND m.type = 'user'
            AND (
                m.content_preview LIKE '%修正%'
                OR m.content_preview LIKE '%やり直%'
                OR m.content_preview LIKE '%間違%'
                OR m.content_preview LIKE '%違う%'
                OR m.content_preview LIKE '%正しく%'
                OR m.content_preview LIKE '%fix%'
                OR m.content_preview LIKE '%wrong%'
                OR m.content_preview LIKE '%incorrect%'
                OR m.content_preview LIKE '%instead%'
                OR m.content_preview LIKE '%undo%'
                OR m.content_preview LIKE '%revert%'
                OR m.content_preview LIKE '%戻して%'
                OR m.content_preview LIKE '%元に戻%'
                OR m.content_preview LIKE '%ダメ%'
                OR m.content_preview LIKE '%だめ%'
            )
            {f['messages']}
        ORDER BY m.timestamp DESC
        LIMIT 30
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_c2_intent_mismatch(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            SUBSTR(m.content_preview, 1, 150) AS message,
            m.date_jst,
            s.project_name
        FROM messages m
        JOIN sessions s ON m.session_id = s.session_id
        WHERE m.is_meta = 0
            AND m.type = 'user'
            AND (
                m.content_preview LIKE '%ではなく%'
                OR m.content_preview LIKE '%じゃなくて%'
                OR m.content_preview LIKE '%じゃなく%'
                OR m.content_preview LIKE '%ないで%'
                OR m.content_preview LIKE '%しないで%'
                OR m.content_preview LIKE '%not %'
                OR m.content_preview LIKE '%don''t%'
                OR m.content_preview LIKE '%do not%'
                OR m.content_preview LIKE '%instead of%'
                OR m.content_preview LIKE '%rather than%'
                OR m.content_preview LIKE '%そうじゃない%'
                OR m.content_preview LIKE '%そうではない%'
                OR m.content_preview LIKE '%思ってたのと%'
            )
            {f['messages']}
        ORDER BY m.timestamp DESC
        LIMIT 30
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_d1_project_efficiency(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            s.project_name,
            COUNT(DISTINCT s.session_id) AS sessions,
            SUM(s.user_message_count) AS user_msgs,
            SUM(s.tool_use_count) AS tool_uses,
            CASE WHEN SUM(s.user_message_count) > 0
                THEN ROUND(CAST(SUM(s.tool_use_count) AS FLOAT) / SUM(s.user_message_count), 1)
                ELSE 0
            END AS tools_per_user_msg
        FROM sessions s
        {f['sessions']}
        GROUP BY s.project_name
        ORDER BY sessions DESC
        LIMIT 20
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_e1_long_sessions(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            s.session_id,
            s.project_name,
            s.first_message_at,
            s.message_count,
            s.tool_use_count,
            ROUND(
                (julianday(s.last_message_at) - julianday(s.first_message_at)) * 24 * 60, 1
            ) AS duration_minutes
        FROM sessions s
        WHERE s.first_message_at IS NOT NULL
            AND s.last_message_at IS NOT NULL
            {f['sessions_and']}
        ORDER BY duration_minutes DESC
        LIMIT 10
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def query_e2_hourly_activity(conn: sqlite3.Connection, f: dict) -> list[dict]:
    sql = f"""
        SELECT
            m.hour_jst,
            COUNT(*) AS message_count,
            SUM(m.tool_count) AS tool_count
        FROM messages m
        WHERE m.is_meta = 0
            {f['messages']}
        GROUP BY m.hour_jst
        ORDER BY m.hour_jst
    """
    return [dict(r) for r in conn.execute(sql).fetchall()]


def main():
    db_path = Path(__file__).parent / "data" / "claude_activity.db"
    if not db_path.exists():
        print(json.dumps({"error": f"DB not found: {db_path}"}))
        sys.exit(1)

    f = build_filter(sys.argv[1:])
    conn = get_connection(db_path)

    report = {
        "filter_args": sys.argv[1:] if len(sys.argv) > 1 else None,
        "basic_stats": query_basic_stats(conn, f),
        "a1_bash_alternatives": query_a1_bash_alternatives(conn, f),
        "a2_consecutive_tools": query_a2_consecutive_tools(conn, f),
        "a3_tool_frequency": query_a3_tool_frequency(conn, f),
        "b1_repeated_instructions": query_b1_repeated_instructions(conn, f),
        "b2_user_messages": query_b2_user_messages(conn, f),
        "c1_fix_patterns": query_c1_fix_patterns(conn, f),
        "c2_intent_mismatch": query_c2_intent_mismatch(conn, f),
        "d1_project_efficiency": query_d1_project_efficiency(conn, f),
        "e1_long_sessions": query_e1_long_sessions(conn, f),
        "e2_hourly_activity": query_e2_hourly_activity(conn, f),
    }

    conn.close()
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
