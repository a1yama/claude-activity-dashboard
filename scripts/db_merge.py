"""別マシンの DB を取り込んで1つに併合する。

これまで `make sync` はローカル DB を本番へ scp で丸ごと上書きしていた。
ingest.py が読むのは実行マシンの ~/.claude/projects だけなので、2台目の Mac が
同期すると本番から1台目のセッションが消える(そして次に1台目が同期すると逆が起きる)。

そこで「本番を取得 → ローカルへ併合 → 押し戻す」に変え、その併合部分をここに置く。
副作用を持たない関数にしてあるので、テストはインメモリ DB 2つで全分岐を踏める。

テーブルごとに同一性の決め方が違う。

  sessions  session_id (UUID) が主キー。1つのセッションは1台のマシンでしか伸びないが、
            他マシンのセッションは本番側が新しいことがある。last_message_at が
            後のものを採る。
  messages  uuid が主キーで内容は不変。既にあれば触らない。
  improvement_proposals
            generate-proposals.py が毎回 DELETE してから全件入れ直す
            スナップショット方式。行単位で混ぜると別世代の提案が混在するので、
            generated_at が新しい側のスナップショットを丸ごと採る。
            ただし採否(status/decided_at)は人間の判断なので、どちらの側で
            記録されたものも (category, title) で引き継ぐ
            (generate-proposals.py:154 と同じキー)。
"""

import sqlite3
import sys
from pathlib import Path

SNAPSHOT_TABLE = "improvement_proposals"


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def _shared_columns(src: sqlite3.Connection, dst: sqlite3.Connection, table: str) -> list[str]:
    """両方に存在する列だけを対象にする。

    本番 DB は Mac 側より古いスキーマのことがある(_ensure_columns で列が増えるため)。
    src 基準で列を組むと、本番に無い列を INSERT しようとして落ちる。
    """
    dst_cols = set(_columns(dst, table))
    return [c for c in _columns(src, table) if c in dst_cols]


def merge_sessions(src: sqlite3.Connection, dst: sqlite3.Connection) -> int:
    """src のセッションを dst へ。新規は追加、既存は last_message_at が後なら差し替える。"""
    cols = _shared_columns(src, dst, "sessions")
    if not cols:
        return 0

    known = {
        row[0]: (row[1] or "")
        for row in dst.execute("SELECT session_id, last_message_at FROM sessions")
    }
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(cols)
    sid = cols.index("session_id")
    last = cols.index("last_message_at") if "last_message_at" in cols else None

    rows = []
    for row in src.execute(f"SELECT {col_list} FROM sessions"):
        if row[sid] in known:
            # 同じセッションが両側にある = 元は同じマシン発。取りこぼしを避けるため
            # 新しい方を残す。last_message_at が無いスキーマでは既存を優先する
            if last is None:
                continue
            if (row[last] or "") <= known[row[sid]]:
                continue
        rows.append(row)

    if rows:
        dst.executemany(
            f"INSERT OR REPLACE INTO sessions ({col_list}) VALUES ({placeholders})", rows
        )
    return len(rows)


def merge_messages(src: sqlite3.Connection, dst: sqlite3.Connection) -> int:
    """src のメッセージを dst へ。内容は不変なので既存には触らない。"""
    cols = _shared_columns(src, dst, "messages")
    if not cols:
        return 0

    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    known = {row[0] for row in dst.execute("SELECT uuid FROM messages")}
    uid = cols.index("uuid")

    rows = [row for row in src.execute(f"SELECT {col_list} FROM messages") if row[uid] not in known]
    if rows:
        dst.executemany(
            f"INSERT OR IGNORE INTO messages ({col_list}) VALUES ({placeholders})", rows
        )
    return len(rows)


def _decisions(conn: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str]]:
    """採否が記録済みの提案を (category, title) で引く。"""
    if SNAPSHOT_TABLE not in _tables(conn):
        return {}
    return {
        (category, title): (status, decided_at or "")
        for category, title, status, decided_at in conn.execute(
            f"SELECT category, title, status, decided_at FROM {SNAPSHOT_TABLE}"
            " WHERE status != 'open'"
        )
    }


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _latest_generated_at(conn: sqlite3.Connection) -> str:
    if SNAPSHOT_TABLE not in _tables(conn):
        return ""
    row = conn.execute(f"SELECT MAX(generated_at) FROM {SNAPSHOT_TABLE}").fetchone()
    return (row[0] or "") if row else ""


def merge_proposals(src: sqlite3.Connection, dst: sqlite3.Connection) -> int:
    """新しい世代のスナップショットを採り、採否は両側から引き継ぐ。

    採否の引き継ぎを先に集めてから入れ替える。順序を逆にすると、負けた側の
    スナップショットと一緒に人間が下した判断まで消える。
    """
    decided = {**_decisions(src), **_decisions(dst)}

    src_gen = _latest_generated_at(src)
    dst_gen = _latest_generated_at(dst)
    replaced = 0

    if src_gen > dst_gen:
        cols = _shared_columns(src, dst, SNAPSHOT_TABLE)
        # id は AUTOINCREMENT の使い捨てで、世代ごとに振り直される。
        # 持ち込むと本番側の連番と衝突するので落とし、挿入先で採番させる
        cols = [c for c in cols if c != "id"]
        if not cols:
            return 0
        col_list = ", ".join(cols)
        placeholders = ", ".join("?" for _ in cols)
        rows = list(src.execute(f"SELECT {col_list} FROM {SNAPSHOT_TABLE}"))
        dst.execute(f"DELETE FROM {SNAPSHOT_TABLE}")
        if rows:
            dst.executemany(
                f"INSERT INTO {SNAPSHOT_TABLE} ({col_list}) VALUES ({placeholders})", rows
            )
        replaced = len(rows)

    if decided and SNAPSHOT_TABLE in _tables(dst):
        dst.executemany(
            f"UPDATE {SNAPSHOT_TABLE} SET status = ?, decided_at = ?"
            " WHERE category = ? AND title = ?",
            [(status, at, category, title) for (category, title), (status, at) in decided.items()],
        )
    return replaced


def merge_db(src: sqlite3.Connection, dst: sqlite3.Connection) -> dict[str, int]:
    """src を dst へ併合する。dst 側が正になる。"""
    stats = {
        "sessions": merge_sessions(src, dst),
        "messages": merge_messages(src, dst),
        "proposals": merge_proposals(src, dst),
    }
    dst.commit()
    return stats


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: db_merge.py SRC_DB DST_DB", file=sys.stderr)
        return 2
    src_path, dst_path = Path(argv[0]), Path(argv[1])
    if not src_path.exists():
        print(f"src が見つかりません: {src_path}", file=sys.stderr)
        return 1
    if not dst_path.exists():
        print(f"dst が見つかりません: {dst_path}", file=sys.stderr)
        return 1

    src = sqlite3.connect(str(src_path))
    dst = sqlite3.connect(str(dst_path))
    try:
        stats = merge_db(src, dst)
    finally:
        src.close()
        dst.close()
    print(
        f"merged: sessions +{stats['sessions']}, messages +{stats['messages']}, "
        f"proposals {stats['proposals']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
