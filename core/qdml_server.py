"""
QDML Server — Zero-dependency HTTP server for QDML Admin.
Serves: JSON API + Static files (admin dashboard).
Usage: python qdml_server.py [--port 8800] [--init]
"""
import sys, os, io, json, mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
from qdml_engine import QDMLEngine

CORE_DIR = Path(__file__).parent
ADMIN_DIR = CORE_DIR.parent / "admin"
LIB_DIR = CORE_DIR.parent / "mas-front" / "_generated"
PORT = 8800

engine = None

def get_engine():
    global engine
    if engine is None:
        engine = QDMLEngine()
    return engine

def ensure_admin_user():
    q = get_engine()
    user = q._fetch_one("SELECT id FROM qdml_user WHERE username='admin'")
    if not user:
        q.create_user("admin", "admin", "Administrator", "admin", "en")
        print("[INIT] Created default admin user (admin/admin)")

def json_response(handler, data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", len(body))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
    handler.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
    handler.end_headers()
    handler.wfile.write(body)

def read_body(handler):
    length = int(handler.headers.get("Content-Length", 0))
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    return json.loads(raw.decode("utf-8"))

def get_token(handler):
    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None

def require_auth(handler):
    token = get_token(handler)
    if not token:
        json_response(handler, {"ok": False, "error": "No token"}, 401)
        return None
    user = get_engine().verify_token(token)
    if not user:
        json_response(handler, {"ok": False, "error": "Invalid token"}, 401)
        return None
    return user

MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".md": "text/markdown; charset=utf-8",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}

class QDMLHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        if path == "/api/qdml/prompt":
            prompt_path = CORE_DIR / "system_prompt.md"
            if prompt_path.exists():
                content = prompt_path.read_text(encoding="utf-8")
                q = get_engine()
                mini_text = q.mini("mas-front", level=1)
                content = content.replace("{{MINI_CODE}}", mini_text)
                content = content.replace("{{STATS}}", json.dumps(q.stats(), indent=2))
            else:
                content = "# System prompt not found"
            body = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/qdml/stats":
            json_response(self, {"ok": True, "data": get_engine().stats()})
            return

        if path == "" or path == "/":
            path = "/index.html"

        if path.startswith("/lib/"):
            lib_file = LIB_DIR / path[5:]
            if lib_file.exists() and lib_file.is_file():
                ext = lib_file.suffix.lower()
                mime = MIME_MAP.get(ext, "application/octet-stream")
                data = lib_file.read_bytes() if ext in (".png", ".ico", ".svg") else lib_file.read_text(encoding="utf-8").encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", len(data))
                self.end_headers()
                self.wfile.write(data)
                return

        file_path = ADMIN_DIR / path.lstrip("/")
        if file_path.exists() and file_path.is_file():
            ext = file_path.suffix.lower()
            mime = MIME_MAP.get(ext, "application/octet-stream")
            if ext in (".png", ".ico", ".svg"):
                data = file_path.read_bytes()
            else:
                data = file_path.read_text(encoding="utf-8").encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", len(data))
            self.end_headers()
            self.wfile.write(data)
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        if path == "/api/auth/login":
            body = read_body(self)
            result = get_engine().login(body.get("username",""), body.get("password",""))
            if result:
                json_response(self, {"ok": True, **result})
            else:
                json_response(self, {"ok": False, "error": "Invalid credentials"}, 401)
            return

        if path == "/api/auth/logout":
            token = get_token(self)
            if token:
                get_engine().logout(token)
            json_response(self, {"ok": True})
            return

        if path == "/api/auth/verify":
            user = require_auth(self)
            if user:
                json_response(self, {"ok": True, "user": user})
            return

        if path == "/api/qdml":
            user = require_auth(self)
            if not user:
                return
            body = read_body(self)
            result = get_engine().execute_json(body, user)
            status = 200 if result.get("ok") else 400
            json_response(self, result, status)
            return

        json_response(self, {"ok": False, "error": "Not found"}, 404)

def main():
    global PORT
    args = sys.argv[1:]
    if "--port" in args:
        PORT = int(args[args.index("--port") + 1])

    ensure_admin_user()

    if "--init" in args:
        print("[INIT] Running master build...")
        master = CORE_DIR / "qdml_master.py"
        if master.exists():
            os.system(f'python "{master}"')

    server = HTTPServer(("0.0.0.0", PORT), QDMLHandler)
    print(f"\n{'='*50}")
    print(f"QDML Server running on http://localhost:{PORT}")
    print(f"Admin:  http://localhost:{PORT}/")
    print(f"API:    http://localhost:{PORT}/api/qdml")
    print(f"Prompt: http://localhost:{PORT}/api/qdml/prompt")
    print(f"{'='*50}\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.server_close()
        if engine:
            engine.close()

if __name__ == "__main__":
    main()
