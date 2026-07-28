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
make test           # ユニットテスト（Python + フロントエンド）
make test-py        # Python のみ
make test-front     # フロントエンドのみ
make test-e2e       # E2Eテスト（Playwright）
```

Python テストは venv 外の `pytest` でも実行される（Stop hook の品質ゲート）ため、
テストコードは標準ライブラリだけで動くようにする。

### E2Eテストについて

- `make test-e2e` でPlaywright E2Eテストを実行する
- テスト用フィクスチャDBを自動生成し、専用ポート（8766/5174）で独立サーバーを起動する
- 実装変更後は必ずE2Eテストを実行し、主要なユーザーフローが壊れていないことを確認する
- テストファイルは `e2e/tests/` に配置されている
