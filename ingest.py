"""Parse Claude Code JSONL logs and ingest into SQLite."""

import json
import re
import sqlite3
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
CLAUDE_HOME = Path.home() / ".claude"
CLAUDE_PROJECTS_DIR = CLAUDE_HOME / "projects"
CLAUDE_PLUGINS_DIR = CLAUDE_HOME / "plugins"

# プラグイン本体の置き場。ツリー全体を走査すると skills/<skill>/commands のような
# ネストをプラグインルートと誤認するため、実レイアウトを固定深さで列挙する
PLUGIN_ROOT_PATTERNS = (
    "marketplaces/*/plugins/*",
    "marketplaces/*/external_plugins/*",
    "cache/*/*/*",
    "repos/*/*",
)

# コマンド定義が見つからなかったときのフォールバック判定に使う。
# Claude Code 2.1.220 のバイナリからコマンド定義とエイリアスを抽出したもの。
# 新しいビルトインが増えると「未知＝カスタム」と誤判定してランキングに混ざるため、
# Claude Code を大きく更新したら以下で差分を確認して追記する:
#   BIN=~/.local/share/claude/versions/<version>
#   grep -aoE 'type:"(local|local-jsx|prompt)",name:"[a-z][a-z0-9:_-]{1,30}"' "$BIN" \
#     | sed -E 's/.*name:"([^"]+)"/\1/' | sort -u
#   grep -aoE 'name:"[a-z][a-z0-9:_-]{1,30}",aliases:\[[^]]*\]' "$BIN" | sort -u
BUILTIN_COMMANDS = frozenset({
    "add-dir", "advisor", "agents", "allowed-tools", "android", "app",
    "artifacts", "auto-mode-setup", "autocompact", "autofix-pr",
    "background", "bashes", "bg", "branch", "break-reminder", "breaks",
    "brief", "btw", "bug", "cd", "clear", "color", "compact", "config",
    "context", "copy", "cost", "daemon", "design", "design-consent",
    "design-login", "design-revoke", "desktop", "diff", "doctor",
    "downtime", "effort", "exit", "export", "extra-usage", "fast",
    "feedback", "focus", "fork", "goal", "heapdump", "help", "hooks", "ide",
    "import", "init", "insights", "install", "install-github-app",
    "install-slack-app", "ios", "keybindings", "login", "logout", "loop",
    "loops", "marketplace", "mcp", "memory", "memory-pause", "mobile",
    "model", "name", "output-style", "passes", "pause-memory",
    "permissions", "plan", "plugin", "plugins", "powerup", "pr-comments",
    "privacy-settings", "pro-trial-expired", "quit", "radio",
    "rate-limit-options", "rc", "recap", "release-notes", "reload-plugins",
    "reload-skills", "remote", "remote-control", "remote-env", "rename",
    "restart", "resume", "review", "rewind", "sandbox", "schedule",
    "scroll-speed", "security-review", "session", "settings",
    "setup-bedrock", "setup-vertex", "skill-doctor", "skills", "stats",
    "status", "statusline", "stickers", "stop", "subtask", "tasks",
    "team-onboarding", "teleport", "terminal-setup", "theme", "todos",
    "toggle-memory", "tp", "tui", "ultraplan", "ultrareview", "update",
    "upgrade", "usage", "usage-credits", "version", "vim", "voice",
    "web-setup", "wellbeing", "workflow-launch-exec", "workflows",
    "worktree",
})


def encode_project_dir(path: str) -> str:
    """Claude Code のログディレクトリ名（絶対パスの / と . を - に置換した形）を作る。"""
    return re.sub(r"[/.]", "-", path)


def resolve_project_path(cwd: str, project_dir: str) -> str | None:
    """cwd の祖先から、ログのディレクトリ名と一致するプロジェクトルートを探す。

    ディレクトリ名は区切り文字を潰していて一意に戻せない
    （-a-b が a/b とも a-b とも読める）ため、実パスと突き合わせて確定させる。
    """
    current = Path(cwd)
    for candidate in (current, *current.parents):
        if encode_project_dir(str(candidate)) == project_dir:
            return str(candidate)
    return None


def format_project_name(path: str, home: Path | None = None) -> str:
    """ホーム基準の短いパスにする（/Users/me/ghq/x/y → ghq/x/y）。"""
    home = home if home is not None else Path.home()
    target = Path(path)
    if target == home:
        return "~"
    if target.is_relative_to(home):
        return str(target.relative_to(home))
    return str(target).lstrip("/")


def build_project_path_index(cwds) -> dict[str, str]:
    """ログの cwd 群から「ログディレクトリ名 → 実パス」の逆引き表を作る。"""
    index = {}
    for cwd in cwds:
        current = Path(cwd)
        for candidate in (current, *current.parents):
            index.setdefault(encode_project_dir(str(candidate)), str(candidate))
    return index


def backfill_project_names(
    conn: sqlite3.Connection, index: dict[str, str], home: Path | None = None
) -> int:
    """元ログが消えて再取り込みできない既存行のプロジェクト名を補正する。"""
    rows = conn.execute(
        "SELECT DISTINCT project_dir FROM sessions WHERE project_path = ''"
    ).fetchall()
    updates = [
        (index[project_dir], format_project_name(index[project_dir], home), project_dir)
        for (project_dir,) in rows
        if project_dir in index
    ]
    conn.executemany(
        "UPDATE sessions SET project_path = ?, project_name = ? WHERE project_dir = ?",
        updates,
    )
    return len(updates)


def extract_project_name(dir_name: str) -> str:
    """Convert directory name like '-Users-a1yama-ghq-github-com-foo-bar' to readable name.

    cwd が取れない古いログ向けのフォールバック。区切り文字を復元しきれず
    ハイフンを含むディレクトリ名は分割されてしまう。
    """
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


def extract_command_name(content) -> str:
    """Extract slash command name from user message content like <command-name>/foo</command-name>."""
    if not isinstance(content, str):
        return ""
    m = re.search(r"<command-name>([^<]+)</command-name>", content)
    return m.group(1).strip() if m else ""


def count_tool_errors(content) -> int:
    """Count tool_result blocks with is_error in user message content."""
    if not isinstance(content, list):
        return 0
    return sum(
        1
        for b in content
        if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("is_error")
    )


def normalize_command_name(name: str) -> str:
    return name.strip().lstrip("/").lower()


def split_command_names(base_dir: Path) -> tuple[set[str], set[str]]:
    """Collect (commands, skills) names from a commands/ + skills/ pair.

    commands/ のサブディレクトリは名前空間になる（commands/git/diff.md → /git:diff）。
    commands/ 直下の .md はすべてコマンド定義とみなす（README.md などは除く）。
    """
    commands = set()
    commands_dir = base_dir / "commands"
    for path in commands_dir.rglob("*.md"):
        if path.stem.upper() == "README":
            continue
        parts = path.relative_to(commands_dir).with_suffix("").parts
        commands.add(normalize_command_name(":".join(parts)))
    skills = {
        normalize_command_name(path.parent.name)
        for path in (base_dir / "skills").glob("*/SKILL.md")
    }
    return commands, skills


def collect_command_names(base_dir: Path) -> set[str]:
    commands, skills = split_command_names(base_dir)
    return commands | skills


def read_plugin_name(plugin_root: Path, plugins_dir: Path | None = None) -> str:
    """プラグイン名はディレクトリ名とは限らない（cache 配下はバージョン名になる）。"""
    manifest = plugin_root / ".claude-plugin" / "plugin.json"
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # 壊れた/非UTF-8の plugin.json で ingest 全体を落とさない
        data = None
    name = data.get("name") if isinstance(data, dict) else None
    if name:
        return name
    if plugins_dir is not None:
        # cache/<marketplace>/<plugin>/<version> は plugin.json が無いことがある
        try:
            parts = plugin_root.relative_to(plugins_dir).parts
        except ValueError:
            parts = ()
        if len(parts) == 4 and parts[0] == "cache":
            return parts[2]
    return plugin_root.name


def collect_plugin_command_names(plugins_dir: Path) -> set[str]:
    """Collect plugin command names.

    コマンドは /<plugin>:<name> で呼ばれるが、スキルはベア名でログに残ることがあるため
    両方の形式で登録する。
    """
    roots = {
        path
        for pattern in PLUGIN_ROOT_PATTERNS
        for path in plugins_dir.glob(pattern)
        if path.is_dir()
    }
    names = set()
    for root in roots:
        plugin = normalize_command_name(read_plugin_name(root, plugins_dir))
        commands, skills = split_command_names(root)
        names |= {f"{plugin}:{name}" for name in commands | skills}
        names |= skills
    return names


def discover_custom_commands(
    project_paths,
    claude_home: Path = CLAUDE_HOME,
    plugins_dir: Path | None = None,
    stop_at: Path | None = None,
) -> set[str]:
    """Build the allowlist of user-defined commands from the filesystem.

    プロジェクト単位ではなく全体の和集合で持つ。個人用ダッシュボードなので
    「そのコマンドを自分で定義したことがあるか」が分かれば足りる。
    stop_at は project_paths を遡るときの打ち切り境界（既定はホームディレクトリ）。
    """
    boundary = stop_at if stop_at is not None else claude_home.parent
    names = collect_command_names(claude_home)
    visited: set[Path] = set()
    for path in project_paths:
        # ログの cwd はサブディレクトリのこともあるので、境界まで遡って .claude を探す
        current = Path(path)
        while current not in visited:
            visited.add(current)
            names |= collect_command_names(current / ".claude")
            # 境界の外（ホーム外の作業ディレクトリなど）へは遡らない
            if current == current.parent or not current.parent.is_relative_to(boundary):
                break
            current = current.parent
    names |= collect_plugin_command_names(
        plugins_dir if plugins_dir is not None else claude_home / "plugins"
    )
    return names


def classify_commands(conn: sqlite3.Connection, known_commands: set[str]):
    """既存行も含めて分類し直す。元ログが消えたセッションの行も判定を保てる。"""
    names = [
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT command_name FROM messages WHERE command_name != ''"
        )
    ]
    conn.executemany(
        "UPDATE messages SET is_custom_command = ? WHERE command_name = ?",
        [(1 if is_custom_command(n, known_commands) else 0, n) for n in names],
    )


def is_custom_command(name: str, known_commands: set[str]) -> bool:
    """Classify a slash command, falling back to the builtin list when unresolved."""
    key = normalize_command_name(name)
    if not key:
        return False
    if key in known_commands:
        return True
    return key not in BUILTIN_COMMANDS


def extract_usage(message: dict) -> tuple[int, int, int, int]:
    """Extract (input, output, cache_creation, cache_read) token counts from assistant message."""
    u = message.get("usage") or {}
    return (
        u.get("input_tokens") or 0,
        u.get("output_tokens") or 0,
        u.get("cache_creation_input_tokens") or 0,
        u.get("cache_read_input_tokens") or 0,
    )


# 過去に ingest 済みの DB にも列を追加できるよう、CREATE TABLE とは別に管理する
SESSIONS_EXTRA_COLUMNS = {
    "project_path": "TEXT DEFAULT ''",
}

# 提案の採否は本番では記録できない（サーバの DB は読み取り専用マウント）ため、
# Mac 側で scripts/proposal-status.py が更新し make sync で反映する
PROPOSALS_EXTRA_COLUMNS = {
    "status": "TEXT DEFAULT 'open'",
    "decided_at": "TEXT DEFAULT ''",
}

MESSAGES_EXTRA_COLUMNS = {
    "model": "TEXT DEFAULT ''",
    "stop_reason": "TEXT DEFAULT ''",
    "input_tokens": "INTEGER DEFAULT 0",
    "output_tokens": "INTEGER DEFAULT 0",
    "cache_creation_tokens": "INTEGER DEFAULT 0",
    "cache_read_tokens": "INTEGER DEFAULT 0",
    "command_name": "TEXT DEFAULT ''",
    "error_count": "INTEGER DEFAULT 0",
    "is_subagent": "INTEGER DEFAULT 0",
    "is_custom_command": "INTEGER DEFAULT 0",
}


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    for name, decl in columns.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {decl}")


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

        -- 系統B: 週次でLLMが生成する改善提案。ingest では触らず保持する
        CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            rationale TEXT NOT NULL,
            suggestion TEXT NOT NULL,
            target_file TEXT DEFAULT ''
        );
    """)
    _ensure_columns(conn, "sessions", SESSIONS_EXTRA_COLUMNS)
    _ensure_columns(conn, "messages", MESSAGES_EXTRA_COLUMNS)
    _ensure_columns(conn, "improvement_proposals", PROPOSALS_EXTRA_COLUMNS)
    # command_name は ALTER で後付けするため、列を追加してからインデックスを張る
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_messages_command ON messages(command_name)"
    )
    return conn


def ingest_session(
    conn: sqlite3.Connection,
    jsonl_path: Path,
    project_dir: str,
    project_name: str,
    session_id: str | None = None,
    is_subagent: bool = False,
    cwds: set[str] | None = None,
):
    # サブエージェントは親セッションの session_id に紐付けて messages のみ取り込み、
    # sessions の統計（メインスレッドの集計）は上書きしない
    if session_id is None:
        session_id = jsonl_path.stem
    messages = []
    session_cwd = None
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

            if record.get("cwd"):
                if cwds is not None:
                    cwds.add(record["cwd"])
                if session_cwd is None:
                    session_cwd = record["cwd"]

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
            model = ""
            stop_reason = ""
            input_tokens = output_tokens = cache_creation_tokens = cache_read_tokens = 0
            command_name = ""
            error_count = 0

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
                    model = msg.get("model") or ""
                    stop_reason = msg.get("stop_reason") or ""
                    (
                        input_tokens, output_tokens,
                        cache_creation_tokens, cache_read_tokens,
                    ) = extract_usage(msg)
                else:
                    command_name = extract_command_name(content)
                    error_count = count_tool_errors(content)
                    if not is_meta:
                        user_count += 1
            elif msg_type == "system":
                content_preview = parse_message_content(record.get("content", ""))

            messages.append((
                uuid, session_id, msg_type, record.get("subtype", ""),
                timestamp, timestamp_jst, date_jst, hour_jst,
                content_preview, msg_tool_count, tool_names, tool_details, is_meta,
                model, stop_reason,
                input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
                command_name, error_count, 1 if is_subagent else 0,
            ))

    if not messages:
        return

    # ディレクトリ名からの復元はハイフンを含む名前を壊すので、cwd が取れれば実パスを優先する
    project_path = resolve_project_path(session_cwd, project_dir) if session_cwd else None
    if project_path:
        project_name = format_project_name(project_path)

    if not is_subagent:
        # Upsert session
        conn.execute("""
            INSERT OR REPLACE INTO sessions
            (session_id, project_dir, project_name, project_path,
             first_message_at, last_message_at,
             message_count, user_message_count, assistant_message_count, tool_use_count, claude_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, project_dir, project_name, project_path or "",
            first_ts.isoformat() if first_ts else None,
            last_ts.isoformat() if last_ts else None,
            len(messages), user_count, assistant_count, tool_count, version,
        ))

    # Upsert messages
    conn.executemany("""
        INSERT OR REPLACE INTO messages
        (uuid, session_id, type, subtype, timestamp, timestamp_jst, date_jst, hour_jst,
         content_preview, tool_count, tool_names, tool_details, is_meta,
         model, stop_reason,
         input_tokens, output_tokens, cache_creation_tokens, cache_read_tokens,
         command_name, error_count, is_subagent)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, messages)


def ingest_all(db_path: Path):
    if not CLAUDE_PROJECTS_DIR.exists():
        print(f"Error: {CLAUDE_PROJECTS_DIR} not found", file=sys.stderr)
        sys.exit(1)

    conn = init_db(db_path)
    total_sessions = 0
    cwds: set[str] = set()

    for project_dir in sorted(CLAUDE_PROJECTS_DIR.iterdir()):
        if not project_dir.is_dir():
            continue
        project_name = extract_project_name(project_dir.name)

        for jsonl_path in sorted(project_dir.glob("*.jsonl")):
            # Skip subagent logs
            if "subagents" in str(jsonl_path):
                continue
            ingest_session(conn, jsonl_path, project_dir.name, project_name, cwds=cwds)
            total_sessions += 1

            # サブエージェントログ (<session_id>/subagents/*.jsonl) を親セッションに紐付けて取り込む
            subagents_dir = project_dir / jsonl_path.stem / "subagents"
            for sub_path in sorted(subagents_dir.glob("*.jsonl")):
                ingest_session(
                    conn, sub_path, project_dir.name, project_name,
                    session_id=jsonl_path.stem, is_subagent=True, cwds=cwds,
                )

    classify_commands(conn, discover_custom_commands(cwds))
    backfill_project_names(conn, build_project_path_index(cwds))
    conn.commit()
    conn.close()
    print(f"Ingested {total_sessions} sessions into {db_path}")


def main():
    db_path = Path(__file__).parent / "data" / "claude_activity.db"
    db_path.parent.mkdir(exist_ok=True)
    ingest_all(db_path)


if __name__ == "__main__":
    main()
