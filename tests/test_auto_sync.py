"""Tests for scripts/auto-sync.sh（SessionEnd ごとに本番へ押し戻さないこと）。

本番DBは 170MB を超える。SessionEnd のたびに同期すると1日で数GB送ることになるため、
最小間隔のガードが効いているかを実際にスクリプトを走らせて確かめる。

make sync は本物を呼ばず、呼ばれた回数を数えるだけの Makefile に差し替える。
"""

import os
import shutil
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "scripts" / "auto-sync.sh"

# sync が呼ばれた回数を数えるだけの Makefile
FAKE_MAKEFILE = """\
sync:
\t@echo ran >> $(MARKER)
"""


def build(tmp_path: Path) -> tuple[Path, dict, Path]:
    """偽リポジトリと偽 HOME を用意し、(スクリプト, 環境変数, マーカー) を返す。"""
    repo = tmp_path / "repo"
    (repo / "scripts").mkdir(parents=True)
    (repo / "data").mkdir()
    shutil.copy(HOOK, repo / "scripts" / "auto-sync.sh")

    marker = tmp_path / "sync-calls"
    (repo / "Makefile").write_text(FAKE_MAKEFILE.replace("$(MARKER)", str(marker)))

    home = tmp_path / "home"
    (home / ".claude" / "projects" / "p").mkdir(parents=True)
    (home / ".claude" / "projects" / "p" / "s.jsonl").write_text("{}\n")

    env = {**os.environ, "HOME": str(home)}
    env.pop("CLAUDE_CODE_DASHBOARD_SKIP_SYNC", None)
    return repo / "scripts" / "auto-sync.sh", env, marker


def run(script: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(script)], env=env, capture_output=True, text=True)


def calls(marker: Path) -> int:
    return len(marker.read_text().splitlines()) if marker.exists() else 0


def log_text(env: dict) -> str:
    path = Path(env["HOME"]) / ".claude" / "dashboard-sync.log"
    return path.read_text() if path.exists() else ""


class TestMinInterval:
    def test_first_run_syncs(self, tmp_path):
        script, env, marker = build(tmp_path)
        run(script, env)
        assert calls(marker) == 1

    def test_second_run_is_skipped(self, tmp_path):
        # 回帰: 間隔ガードが無いと SessionEnd のたびに 170MB を押し戻していた
        script, env, marker = build(tmp_path)
        run(script, env)
        run(script, env)
        assert calls(marker) == 1
        assert "synced within" in log_text(env)

    def test_interval_zero_disables_the_guard(self, tmp_path):
        script, env, marker = build(tmp_path)
        env["SYNC_MIN_INTERVAL_MIN"] = "0"
        run(script, env)
        run(script, env)
        # 間隔ガードは無効。2回目は「新しい活動なし」で止まる
        assert calls(marker) == 1
        assert "no new activity" in log_text(env)

    def test_new_activity_after_the_window_syncs_again(self, tmp_path):
        script, env, marker = build(tmp_path)
        env["SYNC_MIN_INTERVAL_MIN"] = "0"
        run(script, env)
        jsonl = Path(env["HOME"]) / ".claude" / "projects" / "p" / "s.jsonl"
        os.utime(jsonl, (jsonl.stat().st_atime + 60, jsonl.stat().st_mtime + 60))
        run(script, env)
        assert calls(marker) == 2

    def test_non_numeric_interval_falls_back_to_default(self, tmp_path):
        # 無効化のつもりの誤記で「常に同期」に倒れると転送量が戻ってしまう
        script, env, marker = build(tmp_path)
        env["SYNC_MIN_INTERVAL_MIN"] = "abc"
        run(script, env)
        run(script, env)
        assert calls(marker) == 1
        assert "synced within 30m" in log_text(env)


class TestGuards:
    def test_recursive_invocation_is_skipped(self, tmp_path):
        script, env, marker = build(tmp_path)
        env["CLAUDE_CODE_DASHBOARD_SKIP_SYNC"] = "1"
        run(script, env)
        assert calls(marker) == 0

    def test_missing_data_dir_is_recreated(self, tmp_path):
        # data/ は gitignore でクローン直後に存在しない。
        # 無いままロックを作れず「stale lock / already running」だけが出続けていた
        script, env, marker = build(tmp_path)
        shutil.rmtree(script.parent.parent / "data")

        run(script, env)

        assert calls(marker) == 1
        assert "already running" not in log_text(env)
