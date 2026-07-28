"""改善候補の採否を記録する。

本番の DB は読み取り専用マウントで、Mac から scp で上書きされる。
そのため採否はここ（Mac 側）で記録し、`make sync` でダッシュボードに反映する。

    make proposals-list
    make proposal-adopt ID=3
    make proposal-reject ID=3
    make proposal-reopen ID=3
"""

import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DB_PATH = REPO / "data" / "claude_activity.db"
JST = timezone(timedelta(hours=9))

STATUS_BY_COMMAND = {"adopt": "adopted", "reject": "rejected", "reopen": "open"}
STATUS_LABEL = {"open": "未対応", "adopted": "採用", "rejected": "却下"}


def list_proposals(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """SELECT id, status, category, title, decided_at
           FROM improvement_proposals
           ORDER BY status != 'open', id"""
    ).fetchall()
    if not rows:
        print("改善候補はまだありません（make proposals で生成されます）。")
        return
    for proposal_id, status, category, title, decided_at in rows:
        label = STATUS_LABEL.get(status, status)
        decided = f" ({decided_at[:10]})" if decided_at else ""
        print(f"#{proposal_id:<3} [{label}]{decided} {category}: {title}")


def set_status(conn: sqlite3.Connection, proposal_id: int, status: str, now: str) -> bool:
    decided_at = "" if status == "open" else now
    cursor = conn.execute(
        "UPDATE improvement_proposals SET status = ?, decided_at = ? WHERE id = ?",
        (status, decided_at, proposal_id),
    )
    conn.commit()
    return cursor.rowcount > 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] not in {"list", *STATUS_BY_COMMAND}:
        print(__doc__, file=sys.stderr)
        return 2
    if not DB_PATH.exists():
        print(f"DB がありません: {DB_PATH}（make ingest を先に実行）", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    try:
        command = argv[0]
        if command == "list":
            list_proposals(conn)
            return 0

        if len(argv) < 2 or not argv[1].lstrip("#").isdigit():
            print(f"ID を指定してください: proposal-status.py {command} 3", file=sys.stderr)
            return 2

        proposal_id = int(argv[1].lstrip("#"))
        status = STATUS_BY_COMMAND[command]
        now = datetime.now(JST).isoformat()
        if not set_status(conn, proposal_id, status, now):
            print(f"#{proposal_id} は見つかりません", file=sys.stderr)
            return 1
        print(f"#{proposal_id} を「{STATUS_LABEL[status]}」にしました（make sync で反映）")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
