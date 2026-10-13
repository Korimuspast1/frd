#!/usr/bin/env python3
"""
Локальный сервер KVS Studio: раздаёт плеер и примеры .kvs.

    python3 viewer/server.py [порт]

Маршруты:
    /                     -> viewer/index.html
    /static/<file>        -> файлы плеера (viewer/*)
    /samples/manifest.json-> список примеров из examples/*.kvs
    /samples/<name>.kvs   -> сам файл примера
"""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(ROOT, "viewer")
EXAMPLES = os.path.join(ROOT, "examples")
sys.path.insert(0, ROOT)

from kvs.container import read_header          # noqa: E402

MIME = {
    ".html": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".kvs": "application/octet-stream",
    ".png": "image/png",
}


def manifest() -> list:
    out = []
    if not os.path.isdir(EXAMPLES):
        return out
    for name in sorted(os.listdir(EXAMPLES)):
        if not name.endswith(".kvs"):
            continue
        path = os.path.join(EXAMPLES, name)
        try:
            h = read_header(path)
        except Exception:
            continue
        out.append({
            "file": name,
            "name": name[:-4],
            "width": h["width"],
            "height": h["height"],
            "frames": h["frames"],
            "fps": h["fps"],
            "size": os.path.getsize(path),
        })
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):      # тише
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in ("/", "/index.html"):
            return self._file(os.path.join(VIEWER, "index.html"))
        if path.startswith("/static/"):
            return self._file(os.path.join(VIEWER, path[len("/static/"):]))
        if path == "/samples/manifest.json":
            data = json.dumps(manifest(), ensure_ascii=False).encode("utf-8")
            return self._send(200, data, MIME[".json"])
        if path.startswith("/samples/"):
            name = os.path.basename(path)
            if name.endswith(".kvs"):
                return self._file(os.path.join(EXAMPLES, name))
        return self._send(404, b"not found", "text/plain")

    def _file(self, path: str):
        path = os.path.realpath(path)
        if not (path.startswith(os.path.realpath(VIEWER)) or
                path.startswith(os.path.realpath(EXAMPLES))):
            return self._send(403, b"forbidden", "text/plain")
        if not os.path.isfile(path):
            return self._send(404, b"not found", "text/plain")
        ext = os.path.splitext(path)[1].lower()
        with open(path, "rb") as fh:
            body = fh.read()
        return self._send(200, body, MIME.get(ext, "application/octet-stream"))


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"KVS Studio: http://0.0.0.0:{port}/  (Ctrl-C для остановки)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
