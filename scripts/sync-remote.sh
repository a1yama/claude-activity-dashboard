#!/bin/bash
# make sync の本体: 本番DBを取得 → ローカルへ併合 → 提案生成 → 押し戻す。
#
# 以前は ingest 済みのローカルDBを本番へ scp で丸ごと上書きしていた。
# ingest.py が読むのは実行マシンの ~/.claude/projects だけなので、2台目の Mac が
# 同期すると本番から1台目のセッションが消えていた(そして次に1台目が同期すると逆が起きる)。
# 取得してから併合することで、どちらから同期しても消えない。
#
# 提案生成(proposals)を併合の後に置くのは、生成の入力を全マシン分にするため。
# 併合前に生成すると、そのマシンの作業しか見ていない提案が出る。
#
# ロックはサーバ側に置く。2台が同時に sync すると、取得〜押し戻しの間に相手が
# 押し戻した内容を上書きしてしまうため、この区間全体を排他する。
# 落ちたプロセスのロックが残ると同期が永久に止まるので、古いものは時間で回収する。
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
DB="$REPO/data/claude_activity.db"
REMOTE_COPY="$REPO/data/.remote.db"
# 前回 push した直後に観測した本番DBの mtime。取得を省けるかの判定に使う
SEEN_MTIME="$REPO/data/.remote_mtime"
PYTHON="${SYNC_PYTHON:-$REPO/.venv/bin/python}"

SERVER="${SYNC_SERVER:-a1yama-pj}"
SERVER_DIR="${SYNC_SERVER_DIR:-/srv/apps/claude-dashboard}"
SERVER_DB="${SYNC_SERVER_DB:-$SERVER_DIR/data/claude_activity.db}"
REMOTE_LOCK="${SYNC_REMOTE_LOCK:-$SERVER_DIR/data/.sync.lock}"
STALE_MIN="${SYNC_LOCK_STALE_MIN:-30}"

die() { echo "[sync] $*" >&2; exit 1; }

[ -f "$DB" ] || die "ローカルDBがありません: $DB (make ingest を先に実行)"
[ -x "$PYTHON" ] || die "python がありません: $PYTHON (make setup を先に実行)"

# ロック取得。既にあっても STALE_MIN 分より古ければ回収する。
# パスと閾値はこちら側の設定なので、クライアント側で展開させるのが意図どおり(SC2029)
# shellcheck disable=SC2029
if ! ssh "$SERVER" "mkdir '$REMOTE_LOCK' 2>/dev/null || {
      [ -n \"\$(find '$REMOTE_LOCK' -maxdepth 0 -mmin +$STALE_MIN 2>/dev/null)\" ] &&
      rm -rf '$REMOTE_LOCK' && mkdir '$REMOTE_LOCK'; }"; then
  die "他のマシンが同期中です。終わってから再実行してください (残り続ける場合は $SERVER:$REMOTE_LOCK を削除)"
fi
trap 'ssh "$SERVER" "rm -rf '"'$REMOTE_LOCK'"'" >/dev/null 2>&1' EXIT

# 本番DBを取得して併合する。ただし DB は 150MB を超えるので、取りに行く必要が
# あるときだけ取る。前回こちらが push した直後の mtime と一致していれば、それ以降
# 誰も push していない = ローカルが既に上位集合なので取得を丸ごと省ける。
# (毎 SessionEnd で往復すると 300MB 超になる)
# shellcheck disable=SC2029  # SERVER_DB はこちら側の設定。クライアント展開が意図どおり
remote_mtime=$(ssh "$SERVER" "stat -c %Y '$SERVER_DB' 2>/dev/null" || true)
seen_mtime=$(cat "$SEEN_MTIME" 2>/dev/null || true)

rm -f "$REMOTE_COPY"
if [ -z "$remote_mtime" ]; then
  echo "[sync] 本番DBが無いため併合を飛ばします(初回同期とみなします)"
elif [ -n "$seen_mtime" ] && [ "$remote_mtime" = "$seen_mtime" ]; then
  echo "[sync] 前回の同期以降に他マシンの更新なし。取得を省きます"
elif scp -q "$SERVER:$SERVER_DB" "$REMOTE_COPY"; then
  "$PYTHON" "$REPO/scripts/db_merge.py" "$REMOTE_COPY" "$DB" || die "併合に失敗しました"
  rm -f "$REMOTE_COPY"
else
  die "本番DBの取得に失敗しました"
fi

# 提案生成は併合後。全マシン分のデータを入力にする(内部で週次に間引かれる)
"$PYTHON" "$REPO/scripts/generate-proposals.py" || die "提案生成に失敗しました"

"$PYTHON" -c "import sqlite3; c=sqlite3.connect('$DB'); c.execute('PRAGMA wal_checkpoint(TRUNCATE);'); c.close()"

scp -q "$DB" "$SERVER:$SERVER_DB" || die "本番への転送に失敗しました"

# 押し戻した直後の mtime を控える。次回これと一致していれば他マシンの更新が無いので
# 150MB の取得を丸ごと省ける。記録に失敗しても取得を挟むだけなので同期は続行する
# shellcheck disable=SC2029  # SERVER_DB はこちら側の設定。クライアント展開が意図どおり
ssh "$SERVER" "stat -c %Y '$SERVER_DB'" > "$SEEN_MTIME" 2>/dev/null || rm -f "$SEEN_MTIME"
# shellcheck disable=SC2029  # SERVER_DIR はこちら側の設定。クライアント展開が意図どおり
ssh "$SERVER" "cd '$SERVER_DIR' && sudo docker compose restart datasette" || die "datasette の再起動に失敗しました"

echo "✓ sync done -> https://dashboard.a1yama.com/"
