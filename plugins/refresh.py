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
            resp = Response.json({"ok": True, "message": result.stdout.strip()})
        else:
            resp = Response.json({"ok": False, "message": result.stderr.strip()}, status=500)
    except subprocess.TimeoutExpired:
        resp = Response.json({"ok": False, "message": "タイムアウト（120秒）"}, status=500)
    except Exception as e:
        resp = Response.json({"ok": False, "message": str(e)}, status=500)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@hookimpl
def register_routes():
    return [
        (r"^/-/refresh$", refresh_view),
        (r"^/refresh$", refresh_view),
    ]
