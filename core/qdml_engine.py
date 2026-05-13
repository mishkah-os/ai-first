"""
QDML Engine V3 — PostgreSQL-Native, Async, Microservices-Ready.
All code lives in the database. Files are compiled artifacts only.
"""
import json, time, hashlib, secrets
from datetime import datetime, timezone, timedelta
from platform_pipeline import strip_code_fence

MARKER_MAP = {
    "javascript": ("// m-bulk:{name}", "// m-end:{name}"),
    "css":        ("/* m-bulk:{name} */", "/* m-end:{name} */"),
    "html":       ("<!-- m-bulk:{name} -->", "<!-- m-end:{name} -->"),
    "markdown":   ("<!-- m-bulk:{name} -->", "<!-- m-end:{name} -->"),
    "python":     ("# m-bulk:{name}", "# m-end:{name}"),
    "sql":        ("-- m-bulk:{name}", "-- m-end:{name}"),
    "cpp":        ("// m-bulk:{name}", "// m-end:{name}"),
}


class QDMLEngine:
    def __init__(self, pool, schema="qdml"):
        self.pool = pool
        self.schema = schema

    async def _fetch_one(self, sql, *args):
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(sql, *args)
            return dict(row) if row else None

    async def _fetch_all(self, sql, *args):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            return [dict(r) for r in rows]

    async def _execute(self, sql, *args):
        async with self.pool.acquire() as conn:
            return await conn.execute(sql, *args)

    async def _execute_returning(self, sql, *args):
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(sql, *args)

    def _now(self):
        return datetime.now(timezone.utc)

    def _marker(self, lang, name, kind="open"):
        tpl = MARKER_MAP.get(lang, MARKER_MAP["javascript"])
        return tpl[0 if kind == "open" else 1].format(name=name)

    async def _log_op(self, operation, project_id=None, service="qdml", actor="system", success=True, duration_ms=0, details=None):
        await self._execute(
            f"INSERT INTO {self.schema}.operation_log (project_id, operation, service, actor, success, duration_ms, details) VALUES ($1,$2,$3,$4,$5,$6,$7)",
            project_id, operation, service, actor, success, round(duration_ms, 2), json.dumps(details or {})
        )

    # ─────────────────────────────────────────
    # PROJECT / MODULE / COMPONENT / BULK CRUD
    # ─────────────────────────────────────────

    async def create_project(self, name, slug, description=""):
        t0 = time.perf_counter()
        row = await self._execute_returning(
            f"INSERT INTO {self.schema}.project (name, slug, description) VALUES ($1,$2,$3) ON CONFLICT (slug) DO NOTHING RETURNING id",
            name, slug, description
        )
        if not row:
            row = await self._fetch_one(f"SELECT id FROM {self.schema}.project WHERE slug=$1", slug)
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("create_project", row["id"], duration_ms=dur)
        return row["id"]

    async def create_module(self, project_slug, name, slug, tier="frontend", app="main", assembler="concat"):
        t0 = time.perf_counter()
        pid = (await self._fetch_one(f"SELECT id FROM {self.schema}.project WHERE slug=$1", project_slug))["id"]
        row = await self._execute_returning(
            f"INSERT INTO {self.schema}.module (project_id, name, slug, tier, app, assembler) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (project_id, slug) DO NOTHING RETURNING id",
            pid, name, slug, tier, app, assembler
        )
        if not row:
            row = await self._fetch_one(f"SELECT id FROM {self.schema}.module WHERE project_id=$1 AND slug=$2", pid, slug)
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("create_module", pid, duration_ms=dur)
        return row["id"]

    async def create_component(self, module_slug, name, slug, kind="library", target="mas-js", meta=None, project_slug=None):
        t0 = time.perf_counter()
        if project_slug:
            mid_row = await self._fetch_one(
                f"SELECT m.id, m.project_id FROM {self.schema}.module m JOIN {self.schema}.project p ON m.project_id=p.id WHERE p.slug=$1 AND m.slug=$2",
                project_slug, module_slug
            )
        else:
            mid_row = await self._fetch_one(f"SELECT id, project_id FROM {self.schema}.module WHERE slug=$1", module_slug)
        mid = mid_row["id"]
        row = await self._execute_returning(
            f"INSERT INTO {self.schema}.component (module_id, name, slug, kind, target, meta) VALUES ($1,$2,$3,$4,$5,$6) ON CONFLICT (module_id, slug) DO NOTHING RETURNING id",
            mid, name, slug, kind, target, json.dumps(meta or {})
        )
        if not row:
            row = await self._fetch_one(f"SELECT id FROM {self.schema}.component WHERE module_id=$1 AND slug=$2", mid, slug)
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("create_component", mid_row["project_id"], duration_ms=dur)
        return row["id"]

    async def create_bulk(self, component_slug, bulk_name, content, lang="javascript",
                          bulk_order=0, reveal="", depends="", exports="", overflow=False, project_slug=None):
        t0 = time.perf_counter()
        content = strip_code_fence(content)
        if project_slug:
            cid_row = await self._fetch_one(
                f"""SELECT c.id, p.id as project_id FROM {self.schema}.component c
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project p ON m.project_id=p.id
                    WHERE p.slug=$1 AND c.slug=$2""",
                project_slug, component_slug
            )
        else:
            cid_row = await self._fetch_one(
                f"""SELECT c.id, p.id as project_id FROM {self.schema}.component c
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project p ON m.project_id=p.id
                    WHERE c.slug=$1""",
                component_slug
            )
        cid = cid_row["id"]
        row = await self._execute_returning(
            f"""INSERT INTO {self.schema}.pillar (component_id, kind, content, lang, bulk_name, bulk_order, reveal, depends, exports, overflow)
                VALUES ($1,'bulk',$2,$3,$4,$5,$6,$7,$8,$9)
                ON CONFLICT (component_id, bulk_name) DO UPDATE SET content=$2, lang=$3, bulk_order=$5, reveal=$6, depends=$7, exports=$8, overflow=$9, updated_at=now()
                RETURNING id""",
            cid, content, lang, bulk_name, bulk_order, reveal, depends, exports, overflow
        )
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("create_bulk", cid_row["project_id"], duration_ms=dur, details={"bulk": bulk_name, "lines": content.count('\n') + 1})
        return row["id"]

    async def mutate_bulk(self, component_slug, bulk_name, new_content, changed_by="ai", reason="", project_slug=None):
        t0 = time.perf_counter()
        new_content = strip_code_fence(new_content)
        if project_slug:
            row = await self._fetch_one(
                f"""SELECT p2.id, p2.content, pr.id as project_id FROM {self.schema}.pillar p2
                    JOIN {self.schema}.component c ON p2.component_id=c.id
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project pr ON m.project_id=pr.id
                    WHERE pr.slug=$1 AND c.slug=$2 AND p2.bulk_name=$3""",
                project_slug, component_slug, bulk_name
            )
        else:
            row = await self._fetch_one(
                f"""SELECT p2.id, p2.content, pr.id as project_id FROM {self.schema}.pillar p2
                    JOIN {self.schema}.component c ON p2.component_id=c.id
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project pr ON m.project_id=pr.id
                    WHERE c.slug=$1 AND p2.bulk_name=$2""",
                component_slug, bulk_name
            )
        if not row:
            return {"ok": False, "error": f"Bulk not found: {component_slug}/{bulk_name}"}

        await self._execute(
            f"INSERT INTO {self.schema}.bulk_history (pillar_id, content, changed_by, reason) VALUES ($1,$2,$3,$4)",
            row["id"], row["content"], changed_by, reason
        )
        await self._execute(
            f"UPDATE {self.schema}.pillar SET content=$1, updated_at=now() WHERE id=$2",
            new_content, row["id"]
        )
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("mutate_bulk", row["project_id"], actor=changed_by, duration_ms=dur, details={"bulk": bulk_name, "reason": reason})
        return {"ok": True}

    # ─────────────────────────────────────────
    # COMPILE
    # ─────────────────────────────────────────

    async def compile_component(self, component_slug, inject_markers=False, project_slug=None):
        t0 = time.perf_counter()
        if project_slug:
            cid_row = await self._fetch_one(
                f"""SELECT c.id FROM {self.schema}.component c
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project p ON m.project_id=p.id
                    WHERE p.slug=$1 AND c.slug=$2""",
                project_slug, component_slug
            )
        else:
            cid_row = await self._fetch_one(f"SELECT id FROM {self.schema}.component WHERE slug=$1", component_slug)
        if not cid_row:
            return None

        bulks = await self._fetch_all(
            f"SELECT bulk_name, content, lang FROM {self.schema}.pillar WHERE component_id=$1 AND kind='bulk' ORDER BY bulk_order",
            cid_row["id"]
        )
        parts = []
        for b in bulks:
            lang = b.get("lang", "javascript")
            if inject_markers:
                parts.append(self._marker(lang, b["bulk_name"], "open"))
            parts.append(b["content"])
            if inject_markers:
                parts.append(self._marker(lang, b["bulk_name"], "close"))
        dur = (time.perf_counter() - t0) * 1000
        code = "\n".join(parts)
        await self._log_op("compile", duration_ms=dur, details={"component": component_slug, "lines": code.count('\n') + 1})
        return code

    # ─────────────────────────────────────────
    # DESCRIBE / MINI / REVEAL
    # ─────────────────────────────────────────

    async def describe(self, project_slug=None):
        t0 = time.perf_counter()
        if project_slug:
            projects = await self._fetch_all(f"SELECT * FROM {self.schema}.project WHERE slug=$1", project_slug)
        else:
            projects = await self._fetch_all(f"SELECT * FROM {self.schema}.project ORDER BY created_at")

        result = []
        for p in projects:
            modules = await self._fetch_all(
                f"SELECT * FROM {self.schema}.module WHERE project_id=$1 ORDER BY tier, app, sort_order", p["id"]
            )
            mod_list = []
            for m in modules:
                comps = await self._fetch_all(
                    f"SELECT * FROM {self.schema}.component WHERE module_id=$1 ORDER BY sort_order", m["id"]
                )
                comp_list = []
                for c in comps:
                    bulks = await self._fetch_all(
                        f"SELECT bulk_name, lines, chars, exports, depends FROM {self.schema}.pillar WHERE component_id=$1 AND kind='bulk' ORDER BY bulk_order",
                        c["id"]
                    )
                    comp_list.append({
                        "name": c["name"], "slug": c["slug"], "kind": c["kind"], "target": c["target"],
                        "bulks": [{"name": b["bulk_name"], "lines": b["lines"], "chars": b["chars"], "exports": b["exports"]} for b in bulks]
                    })
                mod_list.append({"name": m["name"], "slug": m["slug"], "tier": m["tier"], "app": m["app"], "components": comp_list})
            result.append({"name": p["name"], "slug": p["slug"], "modules": mod_list})

        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("describe", duration_ms=dur)
        return result

    async def mini(self, project_slug, level=0):
        t0 = time.perf_counter()
        tree = await self.describe(project_slug)
        if not tree:
            return "PROJECT NOT FOUND"
        p = tree[0]
        out = [f"PROJECT {p['name']}\n"]
        for m in p["modules"]:
            comps = m["components"]
            total_bulks = sum(len(c["bulks"]) for c in comps)
            total_lines = sum(sum(b["lines"] or 0 for b in c["bulks"]) for c in comps)
            comp_names = ",".join(c["slug"] for c in comps)
            out.append(f"[{m['tier'].upper()}] {m['app']}/{m['slug']}  {len(comps)}C [{comp_names}] | {total_bulks}B | {total_lines} lines")
            if level >= 1:
                for c in comps:
                    bulk_info = " ".join(f"{b['name']}({b['lines']}L)" for b in c["bulks"])
                    out.append(f"    {c['slug']} [{c['kind']}]: {bulk_info}")
        total_c = sum(len(m["components"]) for m in p["modules"])
        total_b = sum(sum(len(c["bulks"]) for c in m["components"]) for m in p["modules"])
        total_l = sum(sum(sum(b["lines"] or 0 for b in c["bulks"]) for c in m["components"]) for m in p["modules"])
        out.append(f"\nTOTAL: {len(p['modules'])} modules | {total_c} components | {total_b} bulks | {total_l} lines")
        dur = (time.perf_counter() - t0) * 1000
        await self._log_op("mini", duration_ms=dur)
        return "\n".join(out)

    async def reveal(self, component_slug, bulk_name=None, level=3, project_slug=None):
        t0 = time.perf_counter()
        if project_slug:
            cid_row = await self._fetch_one(
                f"""SELECT c.id FROM {self.schema}.component c
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project p ON m.project_id=p.id
                    WHERE p.slug=$1 AND c.slug=$2""",
                project_slug, component_slug
            )
        else:
            cid_row = await self._fetch_one(f"SELECT id FROM {self.schema}.component WHERE slug=$1", component_slug)
        if not cid_row:
            return None

        cid = cid_row["id"]
        if bulk_name:
            row = await self._fetch_one(
                f"SELECT * FROM {self.schema}.pillar WHERE component_id=$1 AND bulk_name=$2", cid, bulk_name
            )
            if not row:
                return None
            result = {
                "bulk_name": row["bulk_name"], "lines": row["lines"], "chars": row["chars"],
                "exports": row["exports"], "depends": row["depends"], "reveal": row["reveal"],
                "overflow": row["overflow"]
            }
            if level >= 2 and row["reveal"]:
                content_lines = row["content"].split('\n')
                shown = []
                for part in row["reveal"].split(','):
                    if ':' in part:
                        a, b = part.split(':')
                        shown.extend(content_lines[int(a):int(b)+1])
                    else:
                        idx = int(part)
                        if idx < len(content_lines):
                            shown.append(content_lines[idx])
                result["sample"] = '\n'.join(shown)
            if level >= 3:
                result["content"] = row["content"]
            dur = (time.perf_counter() - t0) * 1000
            await self._log_op("reveal", duration_ms=dur, details={"bulk": bulk_name})
            return result
        else:
            rows = await self._fetch_all(
                f"SELECT bulk_name, lines, chars, exports, depends, overflow FROM {self.schema}.pillar WHERE component_id=$1 AND kind='bulk' ORDER BY bulk_order",
                cid
            )
            dur = (time.perf_counter() - t0) * 1000
            await self._log_op("reveal", duration_ms=dur, details={"component": component_slug})
            return rows

    async def history(self, component_slug, bulk_name, limit=5, project_slug=None):
        if project_slug:
            pid_row = await self._fetch_one(
                f"""SELECT p2.id FROM {self.schema}.pillar p2
                    JOIN {self.schema}.component c ON p2.component_id=c.id
                    JOIN {self.schema}.module m ON c.module_id=m.id
                    JOIN {self.schema}.project pr ON m.project_id=pr.id
                    WHERE pr.slug=$1 AND c.slug=$2 AND p2.bulk_name=$3""",
                project_slug, component_slug, bulk_name
            )
        else:
            cid = (await self._fetch_one(f"SELECT id FROM {self.schema}.component WHERE slug=$1", component_slug))["id"]
            pid_row = await self._fetch_one(
                f"SELECT id FROM {self.schema}.pillar WHERE component_id=$1 AND bulk_name=$2", cid, bulk_name
            )
        if not pid_row:
            return []
        return await self._fetch_all(
            f"SELECT content, changed_by, reason, ts FROM {self.schema}.bulk_history WHERE pillar_id=$1 ORDER BY ts DESC LIMIT $2",
            pid_row["id"], limit
        )

    # ─────────────────────────────────────────
    # STATS / METRICS
    # ─────────────────────────────────────────

    async def stats(self):
        s = self.schema
        p = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.project"))["c"]
        m = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.module"))["c"]
        co = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.component"))["c"]
        b = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.pillar WHERE kind='bulk'"))["c"]
        total_lines = (await self._fetch_one(f"SELECT COALESCE(SUM(lines),0) as c FROM {s}.pillar WHERE kind='bulk'"))["c"]
        total_chars = (await self._fetch_one(f"SELECT COALESCE(SUM(chars),0) as c FROM {s}.pillar WHERE kind='bulk'"))["c"]
        ops = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.operation_log"))["c"]
        hist = (await self._fetch_one(f"SELECT COUNT(*) as c FROM {s}.bulk_history"))["c"]
        db_size = (await self._fetch_one("SELECT pg_database_size(current_database()) as c"))["c"]
        return {
            "projects": p, "modules": m, "components": co, "bulks": b,
            "total_lines": total_lines, "total_chars": total_chars,
            "operations": ops, "history_snapshots": hist,
            "db_size_mb": round(db_size / (1024*1024), 2)
        }

    async def metrics(self):
        return await self._fetch_all(f"""
            SELECT operation, COUNT(*) as count,
                   SUM(CASE WHEN success THEN 1 ELSE 0 END) as ok,
                   SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as fail,
                   ROUND(AVG(duration_ms)::numeric, 2) as avg_ms,
                   ROUND(SUM(duration_ms)::numeric, 2) as total_ms
            FROM {self.schema}.operation_log GROUP BY operation ORDER BY count DESC
        """)

    async def recent_ops(self, limit=50):
        return await self._fetch_all(
            f"SELECT operation, service, actor, success, duration_ms, details, ts FROM {self.schema}.operation_log ORDER BY id DESC LIMIT $1",
            limit
        )

    # ─────────────────────────────────────────
    # AUTH
    # ─────────────────────────────────────────

    async def create_user(self, username, password, display_name="", role="developer"):
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        row = await self._execute_returning(
            f"INSERT INTO {self.schema}.platform_user (username, password_hash, display_name, role) VALUES ($1,$2,$3,$4) ON CONFLICT (username) DO NOTHING RETURNING id",
            username, pw_hash, display_name or username, role
        )
        if not row:
            row = await self._fetch_one(f"SELECT id FROM {self.schema}.platform_user WHERE username=$1", username)
        return row["id"]

    async def login(self, username, password):
        pw_hash = hashlib.sha256(password.encode()).hexdigest()
        user = await self._fetch_one(
            f"SELECT id, username, display_name, role FROM {self.schema}.platform_user WHERE username=$1 AND password_hash=$2 AND is_active=true",
            username, pw_hash
        )
        if not user:
            return None
        token = secrets.token_hex(32)
        expires = self._now() + timedelta(hours=72)
        await self._execute(
            f"INSERT INTO {self.schema}.platform_session (user_id, token, expires_at) VALUES ($1,$2,$3)",
            user["id"], token, expires
        )
        return {"token": token, "user": dict(user)}

    async def verify_token(self, token):
        if not token:
            return None
        row = await self._fetch_one(
            f"""SELECT u.id as user_id, u.username, u.display_name, u.role
                FROM {self.schema}.platform_session s
                JOIN {self.schema}.platform_user u ON s.user_id=u.id
                WHERE s.token=$1 AND u.is_active=true AND s.expires_at > now()""",
            token
        )
        return dict(row) if row else None

    async def logout(self, token):
        await self._execute(f"DELETE FROM {self.schema}.platform_session WHERE token=$1", token)

    # ─────────────────────────────────────────
    # ARTIFACTS
    # ─────────────────────────────────────────

    async def create_artifact(self, project_slug, filename, content, path="./", category="config"):
        pid = (await self._fetch_one(f"SELECT id FROM {self.schema}.project WHERE slug=$1", project_slug))["id"]
        await self._execute(
            f"""INSERT INTO {self.schema}.project_artifact (project_id, filename, path, content, category)
                VALUES ($1,$2,$3,$4,$5)
                ON CONFLICT (project_id, path, filename) DO UPDATE SET content=$4, category=$5, updated_at=now()""",
            pid, filename, path, content, category
        )

    # ─────────────────────────────────────────
    # JSON PROTOCOL (unified entry point)
    # ─────────────────────────────────────────

    async def execute_json(self, action_dict, user=None):
        a = action_dict.get("action", "")
        actor = user.get("username", "system") if user else "system"
        project = action_dict.get("project")
        try:
            if a == "mini":
                return {"ok": True, "data": await self.mini(action_dict["project"], action_dict.get("level", 0))}
            elif a == "describe":
                return {"ok": True, "data": await self.describe(action_dict.get("project"))}
            elif a == "reveal":
                data = await self.reveal(action_dict["component"], action_dict.get("bulk"), action_dict.get("level", 3), project)
                return {"ok": True, "data": data}
            elif a == "create_bulk":
                pid = await self.create_bulk(
                    action_dict["component"], action_dict["bulk_name"],
                    action_dict["content"], action_dict.get("lang", "javascript"),
                    action_dict.get("order", 0), action_dict.get("reveal", ""),
                    action_dict.get("depends", ""), action_dict.get("exports", ""),
                    action_dict.get("overflow", False), project
                )
                return {"ok": True, "id": str(pid)}
            elif a == "mutate_bulk":
                result = await self.mutate_bulk(
                    action_dict["component"], action_dict["bulk_name"],
                    action_dict["content"], actor, action_dict.get("reason", ""), project
                )
                return result
            elif a == "compile":
                code = await self.compile_component(action_dict["component"], action_dict.get("markers", False), project)
                if code is None:
                    return {"ok": False, "error": "Component not found"}
                return {"ok": True, "data": code, "lines": code.count('\n') + 1, "chars": len(code)}
            elif a == "history":
                data = await self.history(action_dict["component"], action_dict["bulk"], action_dict.get("limit", 5), project)
                return {"ok": True, "data": data}
            elif a == "metrics":
                return {"ok": True, "data": await self.metrics()}
            elif a == "stats":
                return {"ok": True, "data": await self.stats()}
            elif a == "recent_ops":
                return {"ok": True, "data": await self.recent_ops(action_dict.get("limit", 50))}
            else:
                return {"ok": False, "error": f"Unknown action: {a}"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
