#!/bin/bash
# Claude Code の SessionEnd hook から起動され、make sync を実行する。
# hook 側は即座に制御を返すため、このスクリプトは nohup でデタッチ起動される前提。
set -u

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PROJECTS_DIR="$HOME/.claude/projects"
STATE="$REPO/data/.last_synced"      # 前回同期成功時点のマーカー（mtime 比較用）
LOCK="$REPO/data/.sync.lock"
RERUN="$REPO/data/.sync.rerun"       # 実行中に再トリガーされた印
LOG="$HOME/.claude/dashboard-sync.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG"; }

# mkdir によるアトミックなロック取得。プロセス死亡で残った古いロックは回収する
acquire_lock() {
  if mkdir "$LOCK" 2>/dev/null; then
    echo $$ > "$LOCK/pid"
    return 0
  fi
  local pid
  pid=$(cat "$LOCK/pid" 2>/dev/null || true)
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    return 1
  fi
  log "stale lock detected (pid=${pid:-unknown}); reclaiming"
  rm -rf "$LOCK"
  mkdir "$LOCK" 2>/dev/null && echo $$ > "$LOCK/pid"
}

if ! acquire_lock; then
  # 実行中の同期が取り込めない差分を残す可能性があるため、終了後の再実行を予約する
  touch "$RERUN"
  log "sync already running; scheduled rerun"
  exit 0
fi
trap 'rm -rf "$LOCK"' EXIT

while :; do
  rm -f "$RERUN"

  if [ -f "$STATE" ] && \
     [ -z "$(find "$PROJECTS_DIR" -name '*.jsonl' -not -path '*subagents*' -newer "$STATE" -print -quit 2>/dev/null)" ]; then
    log "no new activity; skip"
  else
    # マーカーは ingest 開始前の時刻で作り、成功時のみ確定する。
    # 失敗時は古いマーカーが残るので次回トリガーで自動リトライになる
    touch "$STATE.tmp"
    if make -C "$REPO" sync >> "$LOG" 2>&1; then
      mv "$STATE.tmp" "$STATE"
      log "sync done"
    else
      rm -f "$STATE.tmp"
      log "sync FAILED (will retry on next session end)"
    fi
  fi

  [ -f "$RERUN" ] || break
  log "rerun requested; syncing again"
done
