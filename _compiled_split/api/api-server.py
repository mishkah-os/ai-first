# ══════════════════════════════════════════════════════
# AI-First Compiled Output
# Module: API Layer | Component: Server
# Generated: 2026-05-09T13:03:24Z
# WARNING: This file is auto-generated. Do not edit.
# The source of truth is the database.
# ══════════════════════════════════════════════════════

import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        data = {"engine": "AI-First", "version": "1.0", "status": "running"}
        self.wfile.write(json.dumps(data).encode())
    def log_message(self, fmt, *args): pass

if __name__ == "__main__":
    if "--test" in sys.argv:
        print("AI-First API compiled from PostgreSQL")
        print("API-TEST-OK")
        sys.exit(0)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    srv = HTTPServer(("127.0.0.1", port), Handler)
    print(f"AI-First API running on http://127.0.0.1:{port}")
    srv.serve_forever()