"""
QDML Local Engine — SQLite-based, self-contained, production-ready.
Zero external dependencies. Tracks every operation with metrics.
"""
import sqlite3, json, time, os, hashlib
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
"""

class QDMLEngine:
    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()
        self._op_stack = []

    def _init_schema(self):
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def _now(self):
        return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    def _log_op(self, op, module="", tool="", model="", table="", tid=0, success=True, error="", duration=0, details=None):
        self.conn.execute(
            "INSERT INTO operation_log (operation,module,tool,model,target_table,target_id,success,error_msg,duration_ms,started_at,ended_at,details) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (op, module, tool, model, table, tid, 1 if success else 0, error, duration,
             self._now(), self._now(), json.dumps(details or {}, ensure_ascii=False)))
        self.conn.commit()

    def _measure(self, op, module="", tool="qdml_local", model="system"):
        class Timer:
            def __init__(t): t.start = time.perf_counter(); t.op=op; t.mod=module; t.tool=tool; t.model=model
            def __enter__(t): return t
            def __exit__(t, exc_type, exc_val, exc_tb):
                dur = (time.perf_counter() - t.start) * 1000
                ok = exc_type is None
                err = str(exc_val) if exc_val else ""
                self._log_op(op, module, tool, model, "", 0, ok, err, dur)
        return Timer()

    def _content_stats(self, content):
        lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
        return {"lines": lines, "chars": len(content), "bytes": len(content.encode('utf-8'))}

    # ═══════════════════ CREATE ═══════════════════
    def create_project(self, name, slug, description=""):
        with self._measure("create_project", slug):
            self.conn.execute("INSERT OR IGNORE INTO project (name,slug,description) VALUES (?,?,?)", (name,slug,description))
            self.conn.commit()
            return self.conn.execute("SELECT id FROM project WHERE slug=?", (slug,)).fetchone()["id"]

    def create_module(self, project_slug, name, slug, tier="frontend", app="main"):
        with self._measure("create_module", slug):
            pid = self.conn.execute("SELECT id FROM project WHERE slug=?", (project_slug,)).fetchone()["id"]
            self.conn.execute("INSERT OR IGNORE INTO module (project_id,name,slug,tier,app) VALUES (?,?,?,?,?)", (pid,name,slug,tier,app))
            self.conn.commit()
            return self.conn.execute("SELECT id FROM module WHERE project_id=? AND slug=?", (pid,slug)).fetchone()["id"]

    def create_component(self, module_slug, name, slug, kind="library", target="mas-js", meta=None):
        with self._measure("create_component", slug):
            mid = self.conn.execute("SELECT id FROM module WHERE slug=?", (module_slug,)).fetchone()["id"]
            self.conn.execute("INSERT OR IGNORE INTO component (module_id,name,slug,kind,target,meta) VALUES (?,?,?,?,?,?)",
                (mid,name,slug,kind,target,json.dumps(meta or {})))
            self.conn.commit()
            return self.conn.execute("SELECT id FROM component WHERE module_id=? AND slug=?", (mid,slug)).fetchone()["id"]

    def create_bulk(self, component_slug, bulk_name, content, lang="javascript",
                    bulk_order=0, reveal="", depends="", exports="", overflow=False):
        with self._measure("create_bulk", bulk_name):
            cid = self.conn.execute("SELECT id FROM component WHERE slug=?", (component_slug,)).fetchone()["id"]
            stats = self._content_stats(content)
            self.conn.execute(
                """INSERT OR REPLACE INTO pillar
                   (component_id,kind,content,lang,bulk_name,bulk_order,reveal,depends,exports,overflow,lines,chars,bytes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid,"bulk",content,lang,bulk_name,bulk_order,reveal,depends,exports,
                 1 if overflow else 0, stats["lines"], stats["chars"], stats["bytes"]))
            self.conn.commit()
            pid = self.conn.execute("SELECT id FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name)).fetchone()["id"]
            return pid

    def create_artifact(self, project_slug, filename, content, path="./", category="config"):
        with self._measure("create_artifact", filename):
            pid = self.conn.execute("SELECT id FROM project WHERE slug=?", (project_slug,)).fetchone()["id"]
            stats = self._content_stats(content)
            self.conn.execute(
                """INSERT OR REPLACE INTO project_artifact
                   (project_id,filename,path,content,category,lines,chars,bytes)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (pid,filename,path,content,category,stats["lines"],stats["chars"],stats["bytes"]))
            self.conn.commit()

    # ═══════════════════ MUTATE ═══════════════════
    def mutate_bulk(self, component_slug, bulk_name, new_content, changed_by="ai", reason=""):
        with self._measure("mutate_bulk", bulk_name):
            cid = self.conn.execute("SELECT id FROM component WHERE slug=?", (component_slug,)).fetchone()["id"]
            row = self.conn.execute("SELECT id,content FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name)).fetchone()
            if row:
                self.conn.execute("INSERT INTO bulk_history (pillar_id,content,changed_by,reason) VALUES (?,?,?,?)",
                    (row["id"], row["content"], changed_by, reason))
            stats = self._content_stats(new_content)
            self.conn.execute("UPDATE pillar SET content=?,lines=?,chars=?,bytes=?,updated_at=? WHERE id=?",
                (new_content, stats["lines"], stats["chars"], stats["bytes"], self._now(), row["id"]))
            self.conn.commit()

    # ═══════════════════ COMPILE ═══════════════════
    def compile_component(self, component_slug, inject_markers=False):
        with self._measure("compile", component_slug):
            cid = self.conn.execute("SELECT id FROM component WHERE slug=?", (component_slug,)).fetchone()["id"]
            bulks = self.conn.execute(
                "SELECT bulk_name,content FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order",
                (cid,)).fetchall()
            parts = []
            for b in bulks:
                if inject_markers:
                    parts.append(f"// m-bulk:{b['bulk_name']}")
                parts.append(b["content"])
                if inject_markers:
                    parts.append(f"// m-end:{b['bulk_name']}")
            return "\n".join(parts)

    # ═══════════════════ DESCRIBE ═══════════════════
    def describe(self, project_slug=None):
        with self._measure("describe", project_slug or "all"):
            q = "SELECT * FROM project" + (" WHERE slug=?" if project_slug else "") + " ORDER BY id"
            args = (project_slug,) if project_slug else ()
            projects = self.conn.execute(q, args).fetchall()
            result = []
            for p in projects:
                modules = self.conn.execute("SELECT * FROM module WHERE project_id=? ORDER BY tier,app,sort_order", (p["id"],)).fetchall()
                mod_list = []
                for m in modules:
                    comps = self.conn.execute("SELECT * FROM component WHERE module_id=? ORDER BY sort_order", (m["id"],)).fetchall()
                    comp_list = []
                    for c in comps:
                        bulks = self.conn.execute("SELECT bulk_name,lines,chars,exports,depends FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (c["id"],)).fetchall()
                        comp_list.append({"name":c["name"],"slug":c["slug"],"kind":c["kind"],"target":c["target"],
                            "bulks":[{"name":b["bulk_name"],"lines":b["lines"],"chars":b["chars"],"exports":b["exports"]} for b in bulks]})
                    mod_list.append({"name":m["name"],"slug":m["slug"],"tier":m["tier"],"app":m["app"],"components":comp_list})
                result.append({"name":p["name"],"slug":p["slug"],"modules":mod_list})
            return result

    # ═══════════════════ MINI ═══════════════════
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

    # ═══════════════════ REVEAL ═══════════════════
    def reveal(self, component_slug, bulk_name=None, level=3):
        with self._measure("reveal", component_slug):
            cid = self.conn.execute("SELECT id FROM component WHERE slug=?", (component_slug,)).fetchone()["id"]
            if bulk_name:
                row = self.conn.execute("SELECT * FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name)).fetchone()
                if not row: return None
                result = {"bulk_name":row["bulk_name"],"lines":row["lines"],"chars":row["chars"],
                          "exports":row["exports"],"depends":row["depends"],"reveal":row["reveal"],"overflow":bool(row["overflow"])}
                if level >= 2:
                    reveal_str = row["reveal"]
                    if reveal_str:
                        content_lines = row["content"].split('\n')
                        shown = []
                        for part in reveal_str.split(','):
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
                rows = self.conn.execute("SELECT bulk_name,lines,chars,exports,depends,overflow FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (cid,)).fetchall()
                return [{"bulk_name":r["bulk_name"],"lines":r["lines"],"chars":r["chars"],"exports":r["exports"],"depends":r["depends"]} for r in rows]

    def history(self, component_slug, bulk_name, limit=5):
        with self._measure("history", bulk_name):
            cid = self.conn.execute("SELECT id FROM component WHERE slug=?", (component_slug,)).fetchone()["id"]
            pid = self.conn.execute("SELECT id FROM pillar WHERE component_id=? AND bulk_name=?", (cid,bulk_name)).fetchone()["id"]
            rows = self.conn.execute("SELECT content,changed_by,reason,ts FROM bulk_history WHERE pillar_id=? ORDER BY ts DESC LIMIT ?", (pid,limit)).fetchall()
            return [dict(r) for r in rows]

    # ═══════════════════ METRICS ═══════════════════
    def metrics(self):
        rows = self.conn.execute("""
            SELECT operation, COUNT(*) as count,
                   SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN success=0 THEN 1 ELSE 0 END) as fail,
                   ROUND(AVG(duration_ms),2) as avg_ms,
                   ROUND(SUM(duration_ms),2) as total_ms
            FROM operation_log GROUP BY operation ORDER BY count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
