"""Loopback-only static/API server for the synthetic portfolio application."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from portfolio_demo.engine import analyze_property, bootstrap


ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
FILES = {
    "/": (ROOT / "index.html", "text/html; charset=utf-8"),
    "/index.html": (ROOT / "index.html", "text/html; charset=utf-8"),
    "/assets/app.css": (ASSETS / "app.css", "text/css; charset=utf-8"),
    "/assets/app.js": (ASSETS / "app.js", "text/javascript; charset=utf-8"),
}


class Handler(BaseHTTPRequestHandler):
    server_version = "PropertyPortfolioDemo/1.0"

    def _send(self, status, body, content_type):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/api/bootstrap":
            return self._send(200, json.dumps(bootstrap()).encode(), "application/json; charset=utf-8")
        if path not in FILES:
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        file_path, content_type = FILES[path]
        return self._send(200, file_path.read_bytes(), content_type)

    def do_POST(self):
        if urlsplit(self.path).path != "/api/analyze":
            return self._send(404, "Not found", "text/plain; charset=utf-8")
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 64_000:
                raise ValueError("Analysis request size is invalid")
            payload = json.loads(self.rfile.read(length))
            result = analyze_property(payload)
        except (ValueError, json.JSONDecodeError) as exc:
            return self._send(400, json.dumps({"error": str(exc)}), "application/json; charset=utf-8")
        return self._send(200, json.dumps(result, separators=(",", ":"), allow_nan=False), "application/json; charset=utf-8")

    def log_message(self, _fmt, *_args):
        return


def main():
    parser = argparse.ArgumentParser(description="Run the fictional property portfolio demo on loopback")
    parser.add_argument("--port", type=int, default=8790)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Synthetic Property Intelligence demo: http://127.0.0.1:{args.port}/")
    print("Loopback only · no credentials · no provider calls · Ctrl-C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
