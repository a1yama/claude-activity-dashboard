"""Parse Claude Code JSONL logs and ingest into SQLite."""

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def extract_project_name(dir_name: str) -> str:
    """Convert directory name like '-Users-a1yama-ghq-github-com-foo-bar' to readable name."""
    parts = dir_name.lstrip("-").split("-")
    # Skip user home prefix (Users/username)
    try:
        # Find ghq or work boundaries for cleaner names
        for marker in ["ghq", "work"]:
            if marker in parts:
                idx = parts.index(marker)
                result = "/".join(parts[idx:])
                # Restore domain-like patterns: github/com -> github.com
                result = re.sub(r"github/com/", "github.com/", result)
                return result
        # Skip Users/username prefix
        if parts[0] == "Users" and len(parts) > 2:
            return "/".join(parts[2:])
    except (ValueError, IndexError):
        pass
    return "/".join(parts)


def parse_message_content(content) -> str:
    """Extract text content from message content (string or list)."""
    if isinstance(content, str):
        # Strip XML tags from system/command messages
        clean = re.sub(r"<[^>]+>", "", content).strip()
        return clean if clean else ""
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
        return "\n".join(texts)
    return ""


def count_tool_uses(content) -> int:
    """Count tool_use blocks in assistant message content."""
    if not isinstance(content, list):
        return 0
    return sum(1 for b in content if isinstance(b, dict) and b.get("type") == "tool_use")


def extract_tool_names(content) -> str:
    """Extract tool names from assistant message content."""
    if not isinstance(content, list):
        return ""
    names = [
        b.get("name", "")
        for b in content
        if isinstance(b, dict) and b.get("type") == "tool_use"
    ]
    return json.dumps(names) if names else ""


TOOL_INPUT_KEYS = {
    "Read": "file_path",
    "Edit": "file_path",
    "Write": "file_path",
    "Bash": "command",
    "Grep": "pattern",
    "Glob": "pattern",
    "Agent": "prompt",
}


def extract_tool_details(content) -> str:
    """Extract tool names with key input info from assistant message content."""
    if not isinstance(content, list):
        return ""
    details = []
    for b in content:
        if not isinstance(b, dict) or b.get("type") != "tool_use":
            continue
        name = b.get("name", "")
        inp = b.get("input", {})
        key = TOOL_INPUT_KEYS.get(name)
        summary = inp.get(key, "")[:200] if key else ""
        details.append({"name": name, "input": summary})
    return json.dumps(details) if details else ""


def init_db(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project_dir TEXT NOT NULL,
            project_name TEXT NOT NULL,
            first_message_at TEXT,
            last_message_at TEXT,
            message_count INTEGER DEFAULT 0,
            user_message_count INTEGER DEFAULT 0,
            assistant_message_count INTEGER DEFAULT 0,
            tool_use_count INTEGER DEFAULT 0,
            claude_version TEXT
        );

        CREATE TABLE IF NOT EXISTS messages (
            uuid TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            type TEXT NOT NULL,
            subtype TEXT,
            timestamp TEXT NOT NULL,
            timestamp_jst TEXT NOT NULL,
            date_jst TEXT NOT NULL,
            hour_jst INTEGER NOT NULL,
            content_preview TEXT,
            tool_count INTEGER DEFAULT 0,
            tool_names TEXT,
            tool_details TEXT,
            is_meta INTEGER DEFAULT 0,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        );

        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date_jst);
        CREATE INDEX IF NOT EXISTS idx_messages_type ON messages(type);
        CREATE INDEX IF NOT EXISTS idx_sessions_project ON sessions(project_name);
    """)
    return conn


def ingest_session(conn: sqlite3.Connection, jsonl_path: Path, project_dir: str, project_name: str):
    session_id = jsonl_path.stem
    messages = []
    first_ts = None
    last_ts = None
    user_count = 0
    assistant_count = 0
    tool_count = 0
    version = None

    with open(jsonl_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            msg_type = record.get("type", "")
            if msg_type in ("file-history-snapshot", "progress"):
                continue

            timestamp = record.get("timestamp")
            if not timestamp:
                continue

            uuid = record.get("uuid")
            if not uuid:
                continue

            if not version and record.get("version"):
                version = record["version"]

            # Parse timestamp to JST
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except ValueError:
                continue
            dt_jst = dt.astimezone(JST)
            date_jst = dt_jst.strftime("%Y-%m-%d")
            hour_jst = dt_jst.hour
            timestamp_jst = dt_jst.isoformat()

            if first_ts is None or dt < first_ts:
                first_ts = dt
            if last_ts is None or dt > last_ts:
                last_ts = dt

            # Extract content
            content_preview = ""
            msg_tool_count = 0
            tool_names = ""
            tool_details = ""
            is_meta = 1 if record.get("isMeta") else 0

            if msg_type in ("user", "assistant"):
                msg = record.get("message", {})
                content = msg.get("content", "")
                content_preview = parse_message_content(content)
                if msg_type == "assistant":
                    msg_tool_count = count_tool_uses(content)
                    tool_names = extract_tool_names(content)
                    tool_details = extract_tool_details(content)
                    tool_count += msg_tool_count
                    assistant_count += 1
                elif not is_meta:
                    user_count += 1
            elif msg_type == "system":
                content_preview = parse_message_content(record.get("content", ""))

            messages.append((
                uuid, session_id, msg_type, record.get("subtype", ""),
                timestamp, timestamp_jst, date_jst, hour_jst,
                content_preview, msg_tool_count, tool_names, tool_details, is_meta,
            ))

    if not messages:
        return

    # Upsert session
    conn.execute("""
        INSERT OR REPLACE INTO sessions
        (session_id, project_dir, project_name, first_message_at, last_message_at,
         message_count, user_message_count, assistant_message_count, tool_use_count, claude_version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session_id, project_dir, project_name,
        first_ts.isoformat() if first_ts else None,
        last_ts.isoformat() if last_ts else None,
        len(messages), user_count, assistant_count, tool_count, version,
    ))

    # Upsert messages
    conn.executemany("""
        INSERT OR REPLACE INTO messages
        (uuid, session_id, type, subtype, timestamp, timestamp_jst, date_jst, hour_jst,
         content_preview, tool_count, tool_names, tool_details, is_meta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, messages)


def ingest_all(db_path: Path):
    if not CLAUDE_PROJECTS_DIR.exists():
        print(f"Error: {CLAUDE_PROJECTS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    conn = init_db(db_path)
    total_sessions = 0

    for project_dir in sorted(CLAUDE_PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        project_name = extract_project_name(project_dir.name)

        for jsonl_path in sorted(project_dir.glob("*.jsonl")):
            # Skip subagent logs
            if "subagents" in str(jsonl_path):
                continue
            ingest_session(conn, jsonl_path, project_dir.name, project_name)
            total_sessions += 1

    conn.commit()
    conn.close()
    print(f"Ingested {total_sessions} sessions into {db_path}")


def main():
    db_path = Path(__file__).parent / "data" / "claude_activity.db"
    db_path.parent.mkdir(exist_ok=True)
    ingest_all(db_path)


if __name__ == "__main__":
    main()
