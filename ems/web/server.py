"""Serve the frontend and a precomputed, read-only test dataset using stdlib."""
import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

from ems.paths import ROOT

WEB_ROOT = ROOT / "web"
DATASET = ROOT / "outputs/web/dataset.json"


def read_dataset(path=DATASET):
    raw = Path(path).read_bytes()
    value = json.loads(raw)
    if value.get("schemaVersion") != 1 or not value.get("rows"):
        raise ValueError("Invalid dataset schema")
    return raw


class Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, web_root=WEB_ROOT, dataset=DATASET, **kwargs):
        self.web_root = Path(web_root).resolve()
        self.dataset = Path(dataset)
        super().__init__(*args, **kwargs)

    def respond(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'self'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        route = unquote(urlsplit(self.path).path)
        if route == "/health":
            try:
                read_dataset(self.dataset)
            except (OSError, ValueError):
                return self.respond(503, b'{"status":"dataset unavailable"}', "application/json")
            return self.respond(200, b'{"status":"ok"}', "application/json")
        if route == "/api/dataset":
            try:
                body = read_dataset(self.dataset)
            except (OSError, ValueError):
                return self.respond(503, b'{"error":"Run python -m ems.web.export to prepare the demo dataset."}', "application/json")
            return self.respond(200, body, "application/json; charset=utf-8")
        target = (self.web_root / ("index.html" if route == "/" else route.lstrip("/"))).resolve()
        if not target.is_relative_to(self.web_root) or not target.is_file():
            return self.respond(404, b"Not found", "text/plain")
        content_types = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                         ".mjs": "text/javascript; charset=utf-8", ".woff2": "font/woff2",
                         ".svg": "image/svg+xml"}
        if target.suffix not in content_types:
            return self.respond(404, b"Not found", "text/plain")
        self.respond(200, target.read_bytes(), content_types[target.suffix])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), partial(Handler))
    print(f"EMSForecast: http://{args.host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
