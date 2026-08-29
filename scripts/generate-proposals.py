"""系統B: 活動ログを直近N日で分析し、LLM(claude -p)で改善提案を生成して DB に保存する。

`make sync` の ingest 後に呼ばれる前提。週次スロットルで、前回生成から
MIN_INTERVAL_DAYS 未満なら何もせず終了する（毎回の同期で安全に呼べる）。

提案生成は別途 API キーを使わず、認証済みの Claude Code CLI (`claude -p`) を叩く。
その子プロセスには CLAUDE_CODE_DASHBOARD_SKIP_SYNC=1 を渡し、headless セッション終了時の
SessionEnd hook → auto-sync の再帰実行を止める（スロットルと合わせた二重ガード）。
"""

import json
import os
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from ingest import PROPOSALS_EXTRA_COLUMNS  # noqa: E402

DB_PATH = REPO / "data" / "claude_activity.db"
ANALYZE_PY = REPO / "analyze.py"

PERIOD_DAYS = 7
MIN_INTERVAL_DAYS = 7
JST = timezone(timedelta(hours=9))

VALID_CATEGORIES = {"claude_md", "skill", "prompt"}
# 1回の analyze 出力に含まれる全ユーザーメッセージ。トークン肥大を避けプロンプトから除外する
PROMPT_DROP_KEYS = {"b2_user_messages"}


def ensure_table(conn: sqlite3.Connection) -> None:
    """ingest 前の単独実行でもテーブルが無いことで落ちないようにする(定義は ingest.py と同一)。"""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS improvement_proposals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            rationale TEXT NOT NULL,
            suggestion TEXT NOT NULL,
            target_file TEXT DEFAULT ''
        )"""
    )
    existing = {row[1] for row in conn.execute("PRAGMA table_info(improvement_proposals)")}
    for name, decl in PROPOSALS_EXTRA_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE improvement_proposals ADD COLUMN {name} {decl}")


def last_generated_at(conn: sqlite3.Connection) -> datetime | None:
    row = conn.execute(
        "SELECT MAX(generated_at) FROM improvement_proposals"
    ).fetchone()
    if not row or not row[0]:
        return None
    try:
        return datetime.fromisoformat(row[0])
    except ValueError:
        return None


def should_generate(
    last: datetime | None, now: datetime, min_interval_days: int = MIN_INTERVAL_DAYS
) -> bool:
    """前回生成から min_interval_days 以上経過していれば True。"""
    if last is None:
        return True
    return (now - last) >= timedelta(days=min_interval_days)


def build_prompt(analyze_data: dict, period_days: int = PERIOD_DAYS) -> str:
    compact = {k: v for k, v in analyze_data.items() if k not in PROMPT_DROP_KEYS}
    data_json = json.dumps(compact, ensure_ascii=False, indent=2)
    return f"""あなたは Claude Code の利用ログ分析アシスタントです。
以下は直近{period_days}日間の活動ログ分析結果(JSON)です。

{data_json}

このデータから、ワークフロー改善提案を生成してください。提案は以下3カテゴリのいずれか:
- "claude_md": ~/.claude/CLAUDE.md または プロジェクトの .claude/CLAUDE.md に追記すべきルール
- "skill": スキル化/コマンド化すべき繰り返し操作
- "prompt": Claude 側の振る舞いルール(否定形指示の言い換え確認、着手前の要件確認 等)

制約:
- データに根拠がある提案だけを出す。根拠が弱いものは出さない(0件でも可)。
- 最大5件。重要度順。
- 出力は JSON配列のみ。前後に説明文やコードフェンスを付けない。
- 各要素は次のキーを持つ: category, title, rationale, suggestion, target_file
  - rationale: データ上の根拠(どの指標が何回 等)を具体的に
  - suggestion: 追記すべき具体テキスト or スキル概要
  - target_file: claude_md/prompt の場合は対象ファイルパス。skill では空文字で可

例: [{{"category":"claude_md","title":"...","rationale":"...","suggestion":"...","target_file":"~/.claude/CLAUDE.md"}}]"""


def parse_proposals(stdout: str) -> list[dict]:
    """claude -p の出力から提案 JSON配列を抽出・検証する。

    コードフェンスや前後の余計なテキストに耐性を持たせる。検証に通らない要素は捨てる。
    """
    text = stdout.strip()
    # ```json ... ``` のフェンスを除去
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    # 最初の [ から最後の ] までを配列とみなす
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1 or end < start:
        return []
    try:
        items = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        if not isinstance(item, dict):
            continue
        category = item.get("category", "")
        title = item.get("title", "")
        rationale = item.get("rationale", "")
        suggestion = item.get("suggestion", "")
        if category not in VALID_CATEGORIES or not title or not suggestion:
            continue
        result.append(
            {
                "category": category,
                "title": str(title),
                "rationale": str(rationale),
                "suggestion": str(suggestion),
                "target_file": str(item.get("target_file", "")),
            }
        )
    return result


def write_proposals(
    conn: sqlite3.Connection,
    proposals: list[dict],
    generated_at: str,
    period_days: int = PERIOD_DAYS,
) -> None:
    """最新スナップショットに置き換える(全削除→挿入)。ダッシュボードは常に最新だけ見る。

    同じ提案が再生成されたときに採否の記録が消えないよう、(category, title) で引き継ぐ。

    空リストのときは何もしない。LLM の出力形式が崩れて parse_proposals が 0 件を返すと、
    全削除だけが走って既存の提案と採否の記録が消える。
    「提案が無い」と「取り出せなかった」を出力から区別できない以上、
    古い提案を残す側に倒す(消えたものは復元できない)。
    """
    if not proposals:
        return
    decided = {
        (category, title): (status, decided_at)
        for category, title, status, decided_at in conn.execute(
            "SELECT category, title, status, decided_at FROM improvement_proposals"
            " WHERE status != 'open'"
        )
    }
    conn.execute("DELETE FROM improvement_proposals")
    conn.executemany(
        """INSERT INTO improvement_proposals
           (generated_at, period_days, category, title, rationale, suggestion, target_file,
            status, decided_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                generated_at,
                period_days,
                p["category"],
                p["title"],
                p["rationale"],
                p["suggestion"],
                p["target_file"],
                *decided.get((p["category"], p["title"]), ("open", "")),
            )
            for p in proposals
        ],
    )
    conn.commit()


def run_analyze() -> dict:
    proc = subprocess.run(
        [sys.executable, str(ANALYZE_PY), f"直近{PERIOD_DAYS}日"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    proc.check_returncode()
    return json.loads(proc.stdout)


def run_claude(prompt: str) -> str:
    # headless セッション終了時の auto-sync 再帰を止める。
    #
    # あわせてユーザー側の対話用フックを黙らせる。プロンプトには transcript の抜粋が
    # 埋め込まれるため、過去の会話に含まれる「ダメ」「間違い」「80%」といった語が
    # 前提チェックのシグナルに当たり、「直前の成果物が間違っていた」等の無関係な指示が
    # 注入される。指示に従って散文が増えると出力が JSON 配列だけでなくなり、
    # parse_proposals が 0 件を返して既存の提案が消える経路がある。
    env = {
        **os.environ,
        "CLAUDE_CODE_DASHBOARD_SKIP_SYNC": "1",
        "CLAUDE_PREMISE_CHECK_OFF": "1",
        "CLAUDE_FRAME_CHECK_OFF": "1",
    }
    proc = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )
    proc.check_returncode()
    return proc.stdout


def main() -> int:
    if not DB_PATH.exists():
        print(f"[generate-proposals] DB not found: {DB_PATH}", file=sys.stderr)
        return 0  # 同期フローを止めない

    conn = sqlite3.connect(str(DB_PATH))
    try:
        ensure_table(conn)
        now = datetime.now(JST)
        if not should_generate(last_generated_at(conn), now):
            print("[generate-proposals] within throttle window; skip")
            return 0

        analyze_data = run_analyze()
        stdout = run_claude(build_prompt(analyze_data))
        proposals = parse_proposals(stdout)
        write_proposals(conn, proposals, now.isoformat())
        if not proposals:
            # 黙って素通りさせない。出力形式の崩れはここでしか気づけない
            print("[generate-proposals] 提案を取り出せませんでした。既存の提案を残します")
            return 0
        print(f"[generate-proposals] wrote {len(proposals)} proposals")
        return 0
    except Exception as e:  # 同期フロー(scp)を止めないため握りつぶしてログのみ
        print(f"[generate-proposals] failed: {e}", file=sys.stderr)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
