"""Datasette plugin: adds a /-/refresh endpoint to re-ingest JSONL logs."""

import subprocess
import sys
from pathlib import Path

from datasette import hookimpl
from datasette.utils.asgi import Response


INGEST_SCRIPT = Path(__file__).parent.parent / "ingest.py"


async def refresh_view(datasette, request):
    if request.method == "GET":
        html = """
        <html>
        <head><title>Refresh Data</title></head>
        <body style="font-family: system-ui; max-width: 600px; margin: 40px auto; padding: 0 20px;">
            <h2>データ更新</h2>
            <p>Claude Code のログを再取り込みしてDBを更新します。</p>
            <form method="POST">
                <button type="submit" style="padding: 10px 24px; font-size: 16px; cursor: pointer;">
                    更新実行
                </button>
            </form>
            <p><a href="/">← ダッシュボードに戻る</a></p>
        </body>
        </html>
        """
        return Response.html(html)

    # POST: run ingest
    try:
        result = subprocess.run(
            [sys.executable, str(INGEST_SCRIPT)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            msg = f"更新完了: {result.stdout.strip()}"
        else:
            msg = f"エラー: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        msg = "エラー: タイムアウト（120秒）"
    except OSError as e:
        msg = f"エラー: スクリプト実行失敗 - {e}"
    except Exception as e:
        msg = f"エラー: 予期しないエラー - {e}"

    html = f"""
    <html>
    <head><title>Refresh Data</title></head>
    <body style="font-family: system-ui; max-width: 600px; margin: 40px auto; padding: 0 20px;">
        <h2>データ更新</h2>
        <p>{msg}</p>
        <p><a href="/">← ダッシュボードに戻る</a></p>
        <p><a href="/-/refresh">もう一度更新する</a></p>
    </body>
    </html>
    """
    return Response.html(html)


@hookimpl
def register_routes():
    return [
        (r"^/-/refresh$", refresh_view),
    ]
