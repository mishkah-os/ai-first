"""
QDML Engine V2 — SQL-Abstracted, JSON-Protocol, Production-Ready.
Supports: SQLite (dev) and PostgreSQL (production).
Zero external dependencies for SQLite mode.
"""
import sqlite3, json, time, os, hashlib, secrets
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path(__file__).parent / "qdml.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL, slug TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '', created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS module (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES project(id) ON DELETE CASCADE,
    name TEXT NOT NULL, slug TEXT NOT NULL,
    tier TEXT DEFAULT 'frontend', app TEXT DEFAULT 'main',
    sort_order INTEGER DEFAULT 0, assembler TEXT DEFAULT '',
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(project_id, slug)
);
CREATE TABLE IF NOT EXISTS component (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    module_id INTEGER NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name TEXT NOT NULL, slug TEXT NOT NULL,
    kind TEXT DEFAULT 'library', target TEXT DEFAULT 'mas-js',
    meta TEXT DEFAULT '{}', sort_order INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(module_id, slug)
);
CREATE TABLE IF NOT EXISTS pillar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    component_id INTEGER NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    kind TEXT NOT NULL, content TEXT DEFAULT '',
    lang TEXT DEFAULT 'javascript',
    bulk_name TEXT, bulk_order INTEGER DEFAULT 0,
    reveal TEXT DEFAULT '', depends TEXT DEFAULT '', exports TEXT DEFAULT '',
    overflow INTEGER DEFAULT 0, lines INTEGER DEFAULT 0, chars INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(component_id, kind, bulk_name)
);
CREATE TABLE IF NOT EXISTS bulk_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pillar_id INTEGER NOT NULL REFERENCES pillar(id) ON DELETE CASCADE,
    content TEXT NOT NULL, changed_by TEXT DEFAULT 'ai',
    reason TEXT DEFAULT '', ts TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS syntax_error (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pillar_id INTEGER, component_id INTEGER,
    error_type TEXT NOT NULL, message TEXT NOT NULL,
    line INTEGER, col INTEGER, severity TEXT DEFAULT 'error',
    resolved INTEGER DEFAULT 0, ts TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    operation TEXT NOT NULL, module TEXT DEFAULT '',
    tool TEXT DEFAULT '', model TEXT DEFAULT '',
    target_table TEXT DEFAULT '', target_id INTEGER,
    success INTEGER DEFAULT 1, error_msg TEXT DEFAULT '',
    duration_ms REAL DEFAULT 0,
    started_at TEXT, ended_at TEXT,
    details TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS project_artifact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER REFERENCES project(id),
    filename TEXT NOT NULL, path TEXT DEFAULT './',
    content TEXT DEFAULT '', category TEXT DEFAULT 'config',
    lines INTEGER DEFAULT 0, chars INTEGER DEFAULT 0, bytes INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS qdml_user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    role TEXT DEFAULT 'developer',
    lang TEXT DEFAULT 'en',
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS qdml_session (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES qdml_user(id) ON DELETE CASCADE,
    token TEXT UNIQUE NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
"""

MARKER_MAP = {
    "javascript": ("// m-bulk:{name}", "// m-end:{name}"),
    "css":        ("/* m-bulk:{name} */", "/* m-end:{name} */"),
    "html":       ("<!-- m-bulk:{name} -->", "<!-- m-end:{name} -->"),
    "markdown":   ("<!-- m-bulk:{name} -->", "<!-- m-end:{name} -->"),
    "python":     ("# m-bulk:{name}", "# m-end:{name}"),
}

class QDMLEngine:
    def __init__(self, db_path=None, driver="sqlite", pg_config=None):
        self.driver = driver
        if driver == "sqlite":
            self.db_path = db_path or DB_PATH
            self.conn = sqlite3.connect(str(self.db_path))
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
        elif driver == "pgsql":
            import psycopg2
            import psycopg2.extras
            self.conn = psycopg2.connect(**(pg_config or {}))
            self.conn.cursor_factory = psycopg2.extras.RealDictCursor
        self._init_schema()

    def _init_schema(self):
        schema = SCHEMA
        if self.driver == "pgsql":
            schema = schema.replace("AUTOINCREMENT", "")
            schema = schema.replace("INTEGER PRIMARY KEY", "SERIAL PRIMARY KEY")
            schema = schema.replace("datetime('now')", "NOW()")
        if self.driver == "sqlite":
            self.conn.executescript(schema)
        else:
            cur = self.conn.cursor()
            cur.execute(schema)
            self.conn.commit()
        self.conn.commit()

    def _q(self, sql, params=()):
        if self.driver == "pgsql":
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    def _fetch_one(self, sql, params=()):
        row = self._q(sql, params).fetchone()
        return dict(row) if row else None

    def _fetch_all(self, sql, params=()):
        return [dict(r) for r in self._q(sql, params).fetchall()]

    def _now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _log_op(self, op, module="", tool="", model="", table="", tid=0, success=True, error="", duration=0, details=None):
        self._q(
            "INSERT INTO operation_log (operation,module,tool,model,target_table,target_id,success,error_msg,duration_ms,started_at,ended_at,details) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (op, module, tool, model, table, tid, 1 if success else 0, error, duration,
             self._now(), self._now(), json.dumps(details or {}, ensure_ascii=False)))
        self.conn.commit()

    def _measure(self, op, module="", tool="qdml_engine", model="system"):
        engine = self
        class Timer:
            def __init__(t): t.start = time.perf_counter()
            def __enter__(t): return t
            def __exit__(t, exc_type, exc_val, exc_tb):
                dur = (time.perf_counter() - t.start) * 1000
                ok = exc_type is None
                err = str(exc_val) if exc_val else ""
                engine._log_op(op, module, tool, model, "", 0, ok, err, dur)
        return Timer()

    def _content_stats(self, content):
        lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
        return {"lines": lines, "chars": len(content), "bytes": len(content.encode('utf-8'))}

    def _marker(self, lang, name, kind="open"):
        tpl = MARKER_MAP.get(lang, MARKER_MAP["javascript"])
        return tpl[0 if kind == "open" else 1].format(name=name)

    def create_project(self, name, slug, description=""):
        with self._measure("create_project", slug):
            self._q("INSERT OR IGNORE INTO project (name,slug,description) VALUES (?,?,?)", (name,slug,description))
            self.conn.commit()
            return self._fetch_one("SELECT id FROM project WHERE slug=?", (slug,))["id"]

    def create_module(self, project_slug, name, slug, tier="frontend", app="main"):
        with self._measure("create_module", slug):
            pid = self._fetch_one("SELECT id FROM project WHERE slug=?", (project_slug,))["id"]
            self._q("INSERT OR IGNORE INTO module (project_id,name,slug,tier,app) VALUES (?,?,?,?,?)", (pid,name,slug,tier,app))
            self.conn.commit()
            return self._fetch_one("SELECT id FROM module WHERE project_id=? AND slug=?", (pid,slug))["id"]

    def create_component(self, module_slug, name, slug, kind="library", target="mas-js", meta=None):
        with self._measure("create_component", slug):
            mid = self._fetch_one("SELECT id FROM module WHERE slug=?", (module_slug,))["id"]
            self._q("INSERT OR IGNORE INTO component (module_id,name,slug,kind,target,meta) VALUES (?,?,?,?,?,?)",
                (mid,name,slug,kind,target,json.dumps(meta or {})))
            self.conn.commit()
            return self._fetch_one("SELECT id FROM component WHERE module_id=? AND slug=?", (mid,slug))["id"]

    def create_bulk(self, component_slug, bulk_name, content, lang="javascript",
                    bulk_order=0, reveal="", depends="", exports="", overflow=False):
        with self._measure("create_bulk", bulk_name):
            cid = self._fetch_one("SELECT id FROM component WHERE slug=?", (component_slug,))["id"]
            stats = self._content_stats(content)
            self._q(
                """INSERT OR REPLACE INTO pillar
                   (component_id,kind,content,lang,bulk_name,bulk_order,reveal,depends,exports,overflow,lines,chars,bytes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid,"bulk",content,lang,bulk_name,bulk_order,reveal,depends,exports,
                 1 if overflow else 0, stats["lines"], stats["chars"], stats["bytes"]))
            self.conn.commit()
            return self._fetch_one("SELECT id FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name))["id"]

    def create_artifact(self, project_slug, filename, content, path="./", category="config"):
        with self._measure("create_artifact", filename):
            pid = self._fetch_one("SELECT id FROM project WHERE slug=?", (project_slug,))["id"]
            stats = self._content_stats(content)
            self._q(
                """INSERT OR REPLACE INTO project_artifact
                   (project_id,filename,path,content,category,lines,chars,bytes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (pid,filename,path,content,category,stats["lines"],stats["chars"],stats["bytes"]))
            self.conn.commit()

    def mutate_bulk(self, component_slug, bulk_name, new_content, changed_by="ai", reason=""):
        with self._measure("mutate_bulk", bulk_name):
            cid = self._fetch_one("SELECT id FROM component WHERE slug=?", (component_slug,))["id"]
            row = self._fetch_one("SELECT id,content FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name))
            if row:
                self._q("INSERT INTO bulk_history (pillar_id,content,changed_by,reason) VALUES (?,?,?,?)",
                    (row["id"], row["content"], changed_by, reason))
            stats = self._content_stats(new_content)
            self._q("UPDATE pillar SET content=?,lines=?,chars=?,bytes=?,updated_at=? WHERE id=?",
                (new_content, stats["lines"], stats["chars"], stats["bytes"], self._now(), row["id"]))
            self.conn.commit()

    def compile_component(self, component_slug, inject_markers=False):
        with self._measure("compile", component_slug):
            cid = self._fetch_one("SELECT id FROM component WHERE slug=?", (component_slug,))["id"]
            bulks = self._fetch_all(
                "SELECT bulk_name,content,lang FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (cid,))
            parts = []
            for b in bulks:
                lang = b.get("lang", "javascript")
                if inject_markers:
                    parts.append(self._marker(lang, b["bulk_name"], "open"))
                parts.append(b["content"])
                if inject_markers:
                    parts.append(self._marker(lang, b["bulk_name"], "close"))
            return "\n".join(parts)

    def describe(self, project_slug=None):
        with self._measure("describe", project_slug or "all"):
            q = "SELECT * FROM project" + (" WHERE slug=?" if project_slug else "") + " ORDER BY id"
            args = (project_slug,) if project_slug else ()
            projects = self._fetch_all(q, args)
            result = []
            for p in projects:
                modules = self._fetch_all("SELECT * FROM module WHERE project_id=? ORDER BY tier,app,sort_order", (p["id"],))
                mod_list = []
                for m in modules:
                    comps = self._fetch_all("SELECT * FROM component WHERE module_id=? ORDER BY sort_order", (m["id"],))
                    comp_list = []
                    for c in comps:
                        bulks = self._fetch_all("SELECT bulk_name,lines,chars,exports,depends FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (c["id"],))
                        comp_list.append({"name":c["name"],"slug":c["slug"],"kind":c["kind"],"target":c["target"],
                            "bulks":[{"name":b["bulk_name"],"lines":b["lines"],"chars":b["chars"],"exports":b["exports"]} for b in bulks]})
                    mod_list.append({"name":m["name"],"slug":m["slug"],"tier":m["tier"],"app":m["app"],"components":comp_list})
                result.append({"name":p["name"],"slug":p["slug"],"modules":mod_list})
            return result

    def mini(self, project_slug, level=0):
        with self._measure("mini", project_slug):
            tree = self.describe(project_slug)
            if not tree: return "PROJECT NOT FOUND"
            p = tree[0]
            out = [f"PROJECT {p['name']}\n"]
            for m in p["modules"]:
                comps = m["components"]
                total_bulks = sum(len(c["bulks"]) for c in comps)
                total_lines = sum(sum(b["lines"] for b in c["bulks"]) for c in comps)
                comp_names = ",".join(c["slug"] for c in comps)
                out.append(f"[{m['tier'].upper()}] {m['app']}/{m['slug']}  {len(comps)}C [{comp_names}] | {total_bulks}B | {total_lines} lines")
                if level >= 1:
                    for c in comps:
                        bulk_info = " ".join(f"{b['name']}({b['lines']}L)" for b in c["bulks"])
                        out.append(f"    {c['slug']} [{c['kind']}]: {bulk_info}")
            total_c = sum(len(m["components"]) for m in p["modules"])
            total_b = sum(sum(len(c["bulks"]) for c in m["components"]) for m in p["modules"])
            total_l = sum(sum(sum(b["lines"] for b in c["bulks"]) for c in m["components"]) for m in p["modules"])
            out.append(f"\nTOTAL: {len(p['modules'])} modules | {total_c} components | {total_b} bulks | {total_l} lines")
            return "\n".join(out)

    def reveal(self, component_slug, bulk_name=None, level=3):
        with self._measure("reveal", component_slug):
            cid = self._fetch_one("SELECT id FROM component WHERE slug=?", (component_slug,))["id"]
            if bulk_name:
                row = self._fetch_one("SELECT * FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name))
                if not row: return None
                result = {"bulk_name":row["bulk_name"],"lines":row["lines"],"chars":row["chars"],
                          "exports":row["exports"],"depends":row["depends"],"reveal":row["reveal"],"overflow":bool(row["overflow"])}
                if level >= 2 and row["reveal"]:
                    content_lines = row["content"].split('\n')
                    shown = []
                    for part in row["reveal"].split(','):
                        if ':' in part:
                            a,b = part.split(':')
                            shown.extend(content_lines[int(a):int(b)+1])
                        else:
                            idx = int(part)
                            if idx < len(content_lines):
                                shown.append(content_lines[idx])
                    result["sample"] = '\n'.join(shown)
                if level >= 3:
                    result["content"] = row["content"]
                return result
            else:
                return self._fetch_all("SELECT bulk_name,lines,chars,exports,depends,overflow FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (cid,))

    def history(self, component_slug, bulk_name, limit=5):
        with self._measure("history", bulk_name):
            cid = self._fetch_one("SELECT id FROM component WHERE slug=?", (component_slug,))["id"]
            pid = self._fetch_one("SELECT id FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name))["id"]
            return self._fetch_all("SELECT content,changed_by,reason,ts FROM bulk_history WHERE pillar_id=? ORDER BY ts DESC LIMIT ?", (pid,limit))

    def metrics(self):
        return self._fetch_all("""
            SELECT operation, COUNT(*) as count,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail,
                   ROUND(AVG(duration_ms),2) as avg_ms,
                   ROUND(SUM(duration_ms),2) as total_ms
            FROM operation_log GROUP BY operation ORDER BY count DESC
        """)

    def recent_ops(self, limit=50):
        return self._fetch_all("SELECT operation,module,tool,model,success,error_msg,duration_ms,started_at FROM operation_log ORDER BY id DESC LIMIT ?", (limit,))

    def stats(self):
        p = self._fetch_one("SELECT COUNT(*) as c FROM project")["c"]
        m = self._fetch_one("SELECT COUNT(*) as c FROM module")["c"]
        co = self._fetch_one("SELECT COUNT(*) as c FROM component")["c"]
        b = self._fetch_one("SELECT COUNT(*) as c FROM pillar WHERE kind='bulk'")["c"]
        total_lines = self._fetch_one("SELECT COALESCE(SUM(lines),0) as c FROM pillar WHERE kind='bulk'")["c"]
        total_chars = self._fetch_one("SELECT COALESCE(SUM(chars),0) as c FROM pillar WHERE kind='bulk'")["c"]
        ops = self._fetch_one("SELECT COUNT(*) as c FROM operation_log")["c"]
        hist = self._fetch_one("SELECT COUNT(*) as c FROM bulk_history")["c"]
        db_size = os.path.getsize(self.db_path) if self.driver == "sqlite" else 0
        return {"projects":p,"modules":m,"components":co,"bulks":b,
                "total_lines":total_lines,"total_chars":total_chars,
                "operations":ops,"history_snapshots":hist,"db_size_kb":round(db_size/1024,1)}

    def create_user(self, username, password, display_name="", role="developer", lang="en"):
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        self._q("INSERT OR IGNORE INTO qdml_user (username,password_hash,display_name,role,lang) VALUES (?,?,?,?,?)",
            (username, pw_hash, display_name or username, role, lang))
        self.conn.commit()
        return self._fetch_one("SELECT id FROM qdml_user WHERE username=?", (username,))["id"]

    def login(self, username, password):
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        user = self._fetch_one("SELECT id,username,display_name,role,lang FROM qdml_user WHERE username=? AND password_hash=? AND active=1", (username, pw_hash))
        if not user:
            return None
        token = secrets.token_hex(32)
        expires = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ").replace(
            str(datetime.now(timezone.utc).year),
            str(datetime.now(timezone.utc).year + 1))
        self._q("INSERT INTO qdml_session (user_id,token,expires_at) VALUES (?,?,?)", (user["id"], token, expires))
        self.conn.commit()
        return {"token": token, "user": user}

    def verify_token(self, token):
        if not token: return None
        row = self._fetch_one(
            "SELECT s.user_id, u.username, u.display_name, u.role, u.lang FROM qdml_session s JOIN qdml_user u ON s.user_id=u.id WHERE s.token=? AND u.active=1", (token,))
        return row

    def logout(self, token):
        self._q("DELETE FROM qdml_session WHERE token=?", (token,))
        self.conn.commit()

    def execute_json(self, action_dict, user=None):
        a = action_dict.get("action", "")
        model = action_dict.get("model", user.get("username","system") if user else "system")
        try:
            if a == "mini":
                return {"ok": True, "data": self.mini(action_dict["project"], action_dict.get("level", 0))}
            elif a == "describe":
                return {"ok": True, "data": self.describe(action_dict.get("project"))}
            elif a == "reveal":
                data = self.reveal(action_dict["component"], action_dict.get("bulk"), action_dict.get("level", 3))
                return {"ok": True, "data": data}
            elif a == "create_bulk":
                pid = self.create_bulk(action_dict["component"], action_dict["bulk_name"],
                    action_dict["content"], action_dict.get("lang", "javascript"),
                    action_dict.get("order", 0), action_dict.get("reveal", ""),
                    action_dict.get("depends", ""), action_dict.get("exports", ""),
                    action_dict.get("overflow", False))
                return {"ok": True, "id": pid}
            elif a == "mutate_bulk":
                self.mutate_bulk(action_dict["component"], action_dict["bulk_name"],
                    action_dict["content"], model, action_dict.get("reason", ""))
                return {"ok": True}
            elif a == "compile":
                code = self.compile_component(action_dict["component"], action_dict.get("markers", False))
                return {"ok": True, "data": code, "lines": code.count('\n')+1, "chars": len(code)}
            elif a == "history":
                data = self.history(action_dict["component"], action_dict["bulk"], action_dict.get("limit", 5))
                return {"ok": True, "data": data}
            elif a == "metrics":
                return {"ok": True, "data": self.metrics()}
            elif a == "stats":
                return {"ok": True, "data": self.stats()}
            elif a == "recent_ops":
                return {"ok": True, "data": self.recent_ops(action_dict.get("limit", 50))}
            else:
                return {"ok": False, "error": f"Unknown action: {a}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def close(self):
        self.conn.close()
