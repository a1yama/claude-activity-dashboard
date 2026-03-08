# CLAUDE.md

## プロジェクト概要

Claude Code の活動ログを SQLite に取り込み、ブラウザで閲覧・分析するダッシュボード。

- バックエンド: Datasette (SQLite JSON API)
- フロントエンド: React + TypeScript + Tailwind CSS + Recharts

## 開発コマンド

```bash
make setup          # 初回セットアップ
make dev            # 開発サーバー起動（Datasette + Vite）
make ingest         # データ取り込み
make build          # フロントエンドビルド
```

## テスト

コード変更後は以下のテストを実行して確認すること。

```bash
# フロントエンドユニットテスト
cd frontend && npm test

# E2Eテスト（Playwright）
make test-e2e

# Python テスト
.venv/bin/pytest
```

### E2Eテストについて

- `make test-e2e` でPlaywright E2Eテストを実行する
- テスト用フィクスチャDBを自動生成し、専用ポート（8766/5174）で独立サーバーを起動する
- 実装変更後は必ずE2Eテストを実行し、主要なユーザーフローが壊れていないことを確認する
- テストファイルは `e2e/tests/` に配置されている
