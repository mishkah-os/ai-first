"""
Small local Bedrock gateway for AI-First.

The platform API imports the same client directly, but a systemd-visible
gateway makes Bedrock operational status explicit in service health checks.
"""
from __future__ import annotations

import asyncio
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from bedrock_client import get_bedrock_client


HOST = "127.0.0.1"
PORT = 8011


def run(coro):
    return asyncio.run(coro)


class Handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path != "/health":
            self._json(404, {"ok": False, "error": "not_found"})
            return
        qs = parse_qs(parsed.query)
        live = (qs.get("live", ["0"])[0] in {"1", "true", "yes"})
        status = run(get_bedrock_client().health(live=live))
        self._json(200 if status.get("ok") else 503, status)

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != "/invoke":
            self._json(404, {"ok": False, "error": "not_found"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        try:
            text = run(get_bedrock_client().invoke(
                body.get("prompt") or "",
                system=body.get("system") or "",
                model=body.get("model") or "us.anthropic.claude-opus-4-6-v1",
                max_tokens=int(body.get("max_tokens") or 4096),
                temperature=float(body.get("temperature", 0.4)),
            ))
            self._json(200, {"ok": True, "text": text})
        except Exception as exc:
            self._json(503, {"ok": False, "error": str(exc)[:1000]})

    def log_message(self, fmt, *args):
        return


if __name__ == "__main__":
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"[bedrock-gateway] http://{HOST}:{PORT}")
    server.serve_forever()
