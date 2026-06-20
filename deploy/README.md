# deploy/ — 本番インフラ定義（IaC）

本番（さくらVPS, `ssh a1yama-pj`）の Datasette コンテナ定義をバージョン管理するディレクトリ。

| ファイル | 役割 | 本番への反映方法 |
|---|---|---|
| `docker-compose.yml` | Datasette / frontend-build サービス定義 | symlink（git pull で自動更新） |
| `docker/datasette.Dockerfile` | Datasette イメージ | symlink（git pull で自動更新） |
| `Caddyfile.dashboard.example` | リバースプロキシ設定の**テンプレート** | 手動（共有 Caddyfile + 認証ハッシュのため） |

## 本番ディレクトリ構成

```
/srv/apps/claude-dashboard/
├── docker-compose.yml -> repo/deploy/docker-compose.yml   # symlink
├── docker            -> repo/deploy/docker                # symlink
├── data/             # Mac から scp される SQLite（git管理外）
├── static/           # Vite ビルド出力（git管理外）
└── repo/             # このリポジトリの git clone
```

`docker-compose.yml` 内のパスは**親ディレクトリ基準**（`./data`, `./repo/metadata.yml`, `./static`）。
symlink で配置することで、相対パスを保ったまま実体を git 管理下に置ける。

## 初回 symlink 化（一度だけ・現行構成からの移行）

```bash
ssh a1yama-pj
cd /srv/apps/claude-dashboard

# 既存の手打ちファイルを退避
mv docker-compose.yml docker-compose.yml.bak
mv docker docker.bak

# repo 内の定義へ symlink
ln -s repo/deploy/docker-compose.yml docker-compose.yml
ln -s repo/deploy/docker docker

# 検証（実行中コンテナには影響しない。次の操作で初めて効く）
docker compose config >/dev/null && echo OK

# 反映（IaC 経路で再ビルド・再起動できることを確認）
docker compose --profile build run --rm frontend-build
docker compose up -d --build datasette
docker compose ps
```

問題なければ `*.bak` を削除。以降は `git pull` で compose / Dockerfile が更新される。

## Caddy（手動）

共有 `/srv/caddy/Caddyfile` の `dashboard.a1yama.com` ブロックが正。
変更時は `Caddyfile.dashboard.example` を編集 → 共有ファイルへ反映（ハッシュは伏せ字を実値に置換）→ `caddy reload`。
