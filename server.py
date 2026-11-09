"""
HUMO PLASTIK — lokal server (kompyuterda sinash uchun).

Vercel'da bu fayl ishlatilmaydi: u yerda sayt `public/` dan, API esa `api/index.py` dan ishlaydi.
Lokal ishga tushirish:  python server.py   →  http://localhost:8000
"""

import importlib.util
import mimetypes
import os
import sys
import threading
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

BASE = Path(__file__).resolve().parent
PUBLIC = BASE / "public"

# api/index.py ni modul sifatida yuklaymiz — Vercel bilan bir xil kod
spec = importlib.util.spec_from_file_location("humo_api", BASE / "api" / "index.py")
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)

mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("application/manifest+json", ".webmanifest")


class Handler(api.handler):
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/api/"):
            return super().do_GET()
        if path == "/":
            path = "/index.html"
        file = (PUBLIC / path.lstrip("/")).resolve()
        if not file.is_file() or PUBLIC not in file.parents:
            if "." in path.rsplit("/", 1)[-1]:
                return self.send_error(404)
            file = PUBLIC / "index.html"
        ctype = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if ctype.startswith("text/") or ctype == "application/javascript":
            ctype += "; charset=utf-8"
        data = file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400" if "/img/" in path else "no-cache")
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8000"))
    threading.Thread(target=api.bot_polling, daemon=True).start()
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"[web] Sayt ishga tushdi: http://localhost:{port}  (saqlash: {api.store.kind})")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nTo'xtatildi.")
