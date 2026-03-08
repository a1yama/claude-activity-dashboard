# claude-activity-dashboard

Claude Code の活動ログ（`~/.claude/projects/` 内の JSONL）を SQLite に取り込み、ブラウザで閲覧・分析するダッシュボード。

## アーキテクチャ

```
~/.claude/projects/**/*.jsonl
        │
        ▼
   ingest.py ──► SQLite (data/claude_activity.db)
        │
        ▼
   Datasette (JSON API, port 8765)
        │
        ▼
   React + Vite (フロントエンド)
```

- **バックエンド**: Datasette が SQLite を JSON API として公開
- **フロントエンド**: React + TypeScript + Tailwind CSS + Recharts

## セットアップ

```bash
make setup
```

Python 3.11+ と Node.js が必要です。

## 起動

### 開発モード（API + フロントエンド）

```bash
make dev
```

- Datasette API: http://localhost:8765
- Vite dev server: http://localhost:5173 （API は Datasette にプロキシ）

### Datasette のみ

```bash
make serve
```

http://localhost:8765 でダッシュボードが開きます。

## データ更新

```bash
make ingest
```

`~/.claude/projects/` 配下の全 JSONL ファイルを読み取り、SQLite に取り込みます。

ブラウザからは `/-/refresh` にアクセスして「更新実行」ボタンでも実行できます。

## ダッシュボード機能

### 概要画面 (`/`)

- **統計カード**: 総セッション数、メッセージ数、ツール使用回数、アクティブプロジェクト数
- **日別アクティビティチャート**: 日ごとのセッション数・メッセージ数の推移
- **時間帯別分布チャート**: 何時に Claude Code を使っているか
- **ツール使用ランキング**: どのツール（Bash, Read, Edit 等）が多く使われているか
- **プロジェクト別サマリー**: プロジェクトごとの利用状況
- **最近のセッション一覧**: 直近のセッションへのリンク

### セッション詳細画面 (`/#/sessions/:id`)

- セッションのメタ情報（プロジェクト名、開始/終了時刻、メッセージ数、ツール使用回数）
- メッセージ一覧（ユーザー / アシスタントの全文表示）
- ツール使用の詳細（ツール名 + 入力パラメータ）

## テスト

```bash
# Python テスト
make setup  # 初回のみ
.venv/bin/pytest

# フロントエンドテスト
cd frontend && npm test
```

## プロジェクト構成

```
├── ingest.py           # JSONL → SQLite 取り込みスクリプト
├── metadata.yml        # Datasette 設定（SQL クエリ定義）
├── plugins/
│   └── refresh.py      # Datasette プラグイン（ブラウザからデータ更新）
├── frontend/
│   └── src/
│       ├── pages/          # Dashboard, SessionDetail
│       ├── components/     # チャート、テーブル等のコンポーネント
│       ├── hooks/          # useQuery（Datasette API 呼び出し）
│       └── types/          # TypeScript 型定義
├── tests/              # Python テスト
├── data/               # SQLite DB（生成物）
└── Makefile
```
