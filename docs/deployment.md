# デプロイ / 本番運用

## 構成概要

ローカル Mac でログを ingest → SQLite を VPS に同期 → Datasette がブラウザに JSON API を提供する構成。

- **公開URL**: https://dashboard.a1yama.com/
- **認証**: Basic 認証（Caddy `basic_auth`）
  - User: `a1yama` / Password は 1Password 等で管理
- **VPS**: 153.126.204.83 (SSD, AlmaLinux 10)
- **リバースプロキシ**: Caddy (Let's Encrypt 自動更新)
- **ssh エントリ**: `ssh a1yama-pj`

```
[Mac] ~/.claude/projects/**/*.jsonl
          ↓ ingest.py
[Mac] data/claude_activity.db (SQLite)
          ↓ make sync (WAL checkpoint + scp + datasette restart)
          ※ Claude Code SessionEnd hook → scripts/auto-sync.sh が自動実行
[VPS] /srv/apps/claude-dashboard/data/claude_activity.db
          ↓
[Datasette コンテナ:8765] (--immutable で読み取り専用)
[Caddy]
  ├ /api/* → uri strip_prefix /api → claude-datasette:8765
  └ /     → file_server /srv/apps/claude-dashboard/static (Vite build 出力)
          ↓ HTTPS + Basic 認証
[Browser]
```

## サーバ側ディレクトリ構成

```
/srv/apps/claude-dashboard/
├── docker-compose.yml
├── docker/
│   └── datasette.Dockerfile
├── repo/                    # git clone した本リポジトリ
│   ├── metadata.yml         # Datasette のクエリ定義
│   ├── plugins/             # Datasette カスタムプラグイン
│   └── frontend/            # Vite + React ソース
├── data/
│   └── claude_activity.db   # Mac から定期 scp で更新
└── static/                  # Vite build 出力 (Caddy が配信)
```

## デプロイ (初回)

### 1. ベースライン
keiba (`docs/deployment.md`) と同じ AlmaLinux 10 の構築（Caddy 起動済み前提）。

### 2. Caddy 設定追加

共有 `/srv/caddy/Caddyfile` に [`deploy/Caddyfile.dashboard.example`](../deploy/Caddyfile.dashboard.example) のブロックを追記し、`<BCRYPT_HASH>` を実値に置換して `caddy reload`。
（Caddyfile は複数アプリ共有かつ認証ハッシュを含むためリポジトリにはテンプレートのみ置く。）

bcrypt ハッシュ:
```bash
docker exec caddy caddy hash-password --plaintext "<password>"
```

### 3. Deploy Key 設定

```bash
ssh-keygen -t ed25519 -f ~/.ssh/claude_dashboard_deploy -N ""
cat ~/.ssh/claude_dashboard_deploy.pub  # → GitHub Settings → Deploy keys に登録

cat >> ~/.ssh/config <<'EOF'

Host github-claude-dashboard
HostName github.com
User git
IdentityFile ~/.ssh/claude_dashboard_deploy
IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config
```

### 4. リポジトリ配置

```bash
mkdir -p /srv/apps/claude-dashboard/{data,docker,static}
cd /srv/apps/claude-dashboard
GIT_SSH_COMMAND="ssh -i ~/.ssh/claude_dashboard_deploy" \
    git clone git@github-claude-dashboard:a1yama/claude-activity-dashboard.git repo
```

### 5. Dockerfile / compose 配置

`docker-compose.yml` と `docker/datasette.Dockerfile` は**リポジトリの [`deploy/`](../deploy/) で管理**している（IaC 化済み）。本番では symlink で配置し、`git pull` で更新される。

```bash
cd /srv/apps/claude-dashboard
ln -s repo/deploy/docker-compose.yml docker-compose.yml
ln -s repo/deploy/docker docker
```

詳細・初回移行手順・パス設計は [`deploy/README.md`](../deploy/README.md) を参照。

### 6. 初回データ転送（Mac から）

```bash
cd ~/ghq/github.com/a1yama/claude-activity-dashboard
make ingest
scp data/claude_activity.db a1yama-pj:/srv/apps/claude-dashboard/data/
```

> SQLite が WAL モードで書かれている場合、サーバ側の `--immutable` で開けない。同期スクリプトで `PRAGMA wal_checkpoint(TRUNCATE)` を実行してから転送する（後述）。

### 7. ビルド・起動

```bash
ssh a1yama-pj
cd /srv/apps/claude-dashboard

# frontend ビルド (static/ に出力される)
docker compose --profile build run --rm frontend-build

# Datasette 起動
docker compose up -d datasette
docker compose logs -f datasette

# 内部疎通確認
docker exec caddy wget -qO- http://claude-datasette:8765/-/databases.json
```

DNS が向いていれば Caddy が Let's Encrypt 証明書を自動取得。

## Mac → サーバ同期

`make sync` で `ingest → WAL checkpoint → scp → Datasette restart` まで一気に走る。

```bash
cd ~/ghq/github.com/a1yama/claude-activity-dashboard
make sync
```

### 自動同期（SessionEnd hook）

Claude Code のセッション終了時に `~/.claude/settings.json` の SessionEnd hook が
`scripts/auto-sync.sh` をデタッチ起動し、`make sync` を自動実行する。

`scripts/auto-sync.sh` の挙動:

- **差分チェック**: 前回同期成功時（`data/.last_synced`）より新しい JSONL がなければスキップ
- **多重起動防止**: ロック（`data/.sync.lock`）取得中に再トリガーされた場合は再実行を予約し、実行中の同期完了後にもう一度同期する
- **失敗時リトライ**: 同期失敗時はマーカーを更新しないため、次のセッション終了時に自動リトライされる
- **ログ**: `~/.claude/dashboard-sync.log` に記録

Makefile 内のサーバ宛先は ssh エントリ `a1yama-pj` を前提にしている。サーバが変わった場合は `Makefile` の `SERVER` / `SERVER_DB_PATH` を書き換える。

### 「データ更新」ボタンについて (注意)

ダッシュボード右上の「データ更新」ボタンは `plugins/refresh.py` 経由で **コンテナ内** の `ingest.py` を叩く。サーバには `~/.claude/projects/` がないので、**サーバ環境では押すと空 DB になる**ため押さないこと。

将来的にはサーバビルドではボタンを非表示にするか、Mac 側の `make sync` をリモート起動する形に作り替える余地あり。

## 更新デプロイ (運用中)

ソースコード（`metadata.yml`, `plugins/`, `frontend/`, `deploy/`）の更新:

```bash
ssh a1yama-pj
cd /srv/apps/claude-dashboard/repo
GIT_SSH_COMMAND="ssh -i ~/.ssh/claude_dashboard_deploy" git pull
cd ..

# frontend が変わった場合
docker compose --profile build run --rm frontend-build

# Datasette 設定（metadata.yml / plugins / deploy の compose・Dockerfile）が変わった場合
docker compose up -d --build datasette
```

> `docker-compose.yml` / `Dockerfile` は `repo/deploy/` への symlink なので、`git pull` だけで実体が更新される（手編集不要）。compose 自体を変えた場合は `--build` 付きで再起動する。

## 監視 / トラブルシュート

| 確認したいこと | コマンド |
|---|---|
| Datasette 状態 | `docker compose ps`, `docker compose logs datasette` |
| データベース情報 | `docker exec caddy wget -qO- http://claude-datasette:8765/-/databases.json` |
| 最終同期日時 | サーバ上 `ls -lh /srv/apps/claude-dashboard/data/claude_activity.db` |
| Caddy ログ | `docker logs caddy --tail=50` |

### よくあるトラブル

#### Datasette が `unable to open database file` で起動失敗

SQLite が WAL モードのまま転送された場合、`--immutable` で開けない。Mac 側の同期スクリプトで `PRAGMA wal_checkpoint(TRUNCATE)` してから転送する（本ドキュメントのスクリプトで対応済み）。

手動で直す場合:
```bash
# Mac 側
sqlite3 ~/ghq/github.com/a1yama/claude-activity-dashboard/data/claude_activity.db \
    "PRAGMA wal_checkpoint(TRUNCATE);"
scp ~/ghq/github.com/a1yama/claude-activity-dashboard/data/claude_activity.db \
    a1yama-pj:/srv/apps/claude-dashboard/data/
ssh a1yama-pj 'cd /srv/apps/claude-dashboard && docker compose restart datasette'
```

#### frontend ビルドが `EACCES` で失敗

`./static` の所有者がコンテナの root になっている。 ホスト側で chown:
```bash
sudo chown -R alma:alma /srv/apps/claude-dashboard/static
```

#### React Router でリロードすると 404

Caddyfile の `try_files {path} /index.html` がないと SPA のサブパスがリロードで 404 になる。本ドキュメントの設定で対応済み。

## バックアップ

SQLite は Mac 側で生成されているので、Mac の Time Machine 等で間接的にバックアップされる。サーバ側のものは Mac の最新が常に上書きされるため、定期取得は不要。

## 削除 / 整理

```bash
ssh a1yama-pj
cd /srv/apps/claude-dashboard && docker compose --profile build down --rmi all --volumes
sudo rm -rf /srv/apps/claude-dashboard
rm ~/.ssh/claude_dashboard_deploy*
# /srv/caddy/Caddyfile から dashboard.a1yama.com ブロック削除 → caddy reload

# GitHub の Deploy key も削除
```
