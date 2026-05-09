"""
AI-First Core Engine — QDML Protocol Implementation
====================================================
The single gateway for all code operations against PostgreSQL.
Nothing touches the database except through this engine.

QDML Operations:
  create   — Insert modules, components, pillars, artifacts
  describe — Show the project tree
  reveal   — Read component content
  mutate   — Modify pillar content
  delete   — Remove with tombstone logging

Every write operation → change_log entry.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg


class CoreEngine:
    """
    The AI-First Core Engine.
    Connects to PostgreSQL. Implements the QDML protocol.
    This is the ONLY interface between the system and the database.
    """

    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: Optional[asyncpg.Pool] = None

    # ================================================================
    # CONNECTION
    # ================================================================

    async def connect(self) -> "CoreEngine":
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=10)
        return self

    async def close(self):
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def init_schema(self):
        """Execute schema.sql to create all tables."""
        sql = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(sql)

    # ================================================================
    # CHANGE LOG (internal — called on every write)
    # ================================================================

    async def _log(self, conn, table: str, row_id: int, op: str,
                   payload: dict = None, tombstone: bool = False):
        await conn.execute(
            """INSERT INTO change_log (table_name, row_id, operation, payload, tombstone)
               VALUES ($1, $2, $3, $4, $5)""",
            table, row_id, op,
            json.dumps(payload, ensure_ascii=False) if payload else None,
            tombstone
        )

    # ================================================================
    # QDML: CREATE — Modules
    # ================================================================

    async def create_module(self, name: str, slug: str, sort_order: int = 0) -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                "INSERT INTO module (name, slug, sort_order) VALUES ($1,$2,$3) RETURNING id",
                name, slug, sort_order)
            await self._log(conn, "module", rid, "INSERT", {"name": name, "slug": slug})
            return rid

    # ================================================================
    # QDML: CREATE — Components
    # ================================================================

    async def create_component(self, module_slug: str, name: str, slug: str,
                                kind: str = "screen", target: str = "mas-js") -> int:
        async with self.pool.acquire() as conn:
            mid = await conn.fetchval("SELECT id FROM module WHERE slug=$1", module_slug)
            if mid is None:
                raise ValueError(f"Module '{module_slug}' not found")
            rid = await conn.fetchval(
                """INSERT INTO component (module_id, name, slug, kind, target)
                   VALUES ($1,$2,$3,$4,$5) RETURNING id""",
                mid, name, slug, kind, target)
            await self._log(conn, "component", rid, "INSERT",
                          {"module": module_slug, "name": name, "slug": slug, "kind": kind, "target": target})
            return rid

    # ================================================================
    # QDML: CREATE — Pillars (upsert)
    # ================================================================

    async def set_pillar(self, component_id: int, kind: str, content: str,
                         lang: str = "javascript") -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                """INSERT INTO pillar (component_id, kind, content, lang)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT (component_id, kind)
                   DO UPDATE SET content=EXCLUDED.content, lang=EXCLUDED.lang, updated_at=now()
                   RETURNING id""",
                component_id, kind, content, lang)
            await self._log(conn, "pillar", rid, "INSERT",
                          {"component_id": component_id, "kind": kind, "lang": lang})
            return rid

    # ================================================================
    # QDML: CREATE — Shared Functions
    # ================================================================

    async def add_shared_function(self, name: str, content: str,
                                   lang: str = "javascript", description: str = "") -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                """INSERT INTO shared_function (name, content, lang, description)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT (name) DO UPDATE SET content=EXCLUDED.content, lang=EXCLUDED.lang
                   RETURNING id""",
                name, content, lang, description)
            await self._log(conn, "shared_function", rid, "INSERT", {"name": name, "lang": lang})
            return rid

    # ================================================================
    # QDML: CREATE — Global Variables
    # ================================================================

    async def add_global_var(self, key: str, value: str,
                              scope: str = "app", scope_ref: str = None) -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                """INSERT INTO global_var (key, value, scope, scope_ref)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value
                   RETURNING id""",
                key, value, scope, scope_ref)
            await self._log(conn, "global_var", rid, "INSERT", {"key": key, "scope": scope})
            return rid

    # ================================================================
    # QDML: CREATE — Design Tokens
    # ================================================================

    async def add_design_token(self, key: str, value: str, category: str = "color") -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                """INSERT INTO design_token (key, value, category)
                   VALUES ($1,$2,$3)
                   ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, category=EXCLUDED.category
                   RETURNING id""",
                key, value, category)
            await self._log(conn, "design_token", rid, "INSERT", {"key": key, "value": value})
            return rid

    # ================================================================
    # QDML: CREATE — i18n
    # ================================================================

    async def add_i18n(self, key: str, translations: dict, ns: str = "common") -> int:
        """Add an i18n key with translations. translations = {'en': 'Hello', 'ar': 'مرحبا'}"""
        async with self.pool.acquire() as conn:
            key_id = await conn.fetchval(
                """INSERT INTO i18n_key (key, ns) VALUES ($1,$2)
                   ON CONFLICT (key) DO UPDATE SET ns=EXCLUDED.ns RETURNING id""",
                key, ns)
            for lang, val in translations.items():
                await conn.execute(
                    """INSERT INTO i18n_value (key_id, lang, value) VALUES ($1,$2,$3)
                       ON CONFLICT (key_id, lang) DO UPDATE SET value=EXCLUDED.value""",
                    key_id, lang, val)
            await self._log(conn, "i18n_key", key_id, "INSERT",
                          {"key": key, "langs": list(translations.keys())})
            return key_id

    # ================================================================
    # QDML: CREATE — Project Artifacts
    # ================================================================

    async def add_artifact(self, filename: str, content: str,
                            path: str = "./", category: str = "config") -> int:
        async with self.pool.acquire() as conn:
            rid = await conn.fetchval(
                """INSERT INTO project_artifact (filename, content, path, category)
                   VALUES ($1,$2,$3,$4)
                   ON CONFLICT (path, filename) DO UPDATE
                   SET content=EXCLUDED.content, category=EXCLUDED.category, updated_at=now()
                   RETURNING id""",
                filename, content, path, category)
            await self._log(conn, "project_artifact", rid, "INSERT",
                          {"filename": filename, "path": path, "category": category})
            return rid

    # ================================================================
    # QDML: DESCRIBE
    # ================================================================

    async def describe(self, module_slug: str = None) -> list[dict]:
        """Return the full project tree: modules → components → pillar names."""
        async with self.pool.acquire() as conn:
            q = "SELECT id, name, slug FROM module"
            args = []
            if module_slug:
                q += " WHERE slug=$1"
                args.append(module_slug)
            q += " ORDER BY sort_order"
            modules = await conn.fetch(q, *args)

            result = []
            for m in modules:
                comps = await conn.fetch(
                    """SELECT c.id, c.name, c.slug, c.kind, c.target,
                              array_agg(p.kind ORDER BY p.kind)
                                FILTER (WHERE p.kind IS NOT NULL) AS pillars
                       FROM component c
                       LEFT JOIN pillar p ON p.component_id = c.id
                       WHERE c.module_id = $1
                       GROUP BY c.id ORDER BY c.sort_order""",
                    m["id"])
                result.append({
                    "module": m["name"], "slug": m["slug"],
                    "components": [{
                        "name": c["name"], "slug": c["slug"],
                        "kind": c["kind"], "target": c["target"],
                        "pillars": list(c["pillars"]) if c["pillars"] else []
                    } for c in comps]
                })
            return result

    # ================================================================
    # QDML: REVEAL
    # ================================================================

    async def reveal(self, component_slug: str, pillar_kind: str = None) -> dict:
        """Return a component with all (or one) pillar contents."""
        async with self.pool.acquire() as conn:
            comp = await conn.fetchrow(
                "SELECT id, name, slug, kind, target FROM component WHERE slug=$1",
                component_slug)
            if not comp:
                raise ValueError(f"Component '{component_slug}' not found")

            q = "SELECT kind, content, lang FROM pillar WHERE component_id=$1"
            args = [comp["id"]]
            if pillar_kind:
                q += " AND kind=$2"
                args.append(pillar_kind)
            q += " ORDER BY kind"
            pillars = await conn.fetch(q, *args)

            return {
                "name": comp["name"], "slug": comp["slug"],
                "kind": comp["kind"], "target": comp["target"],
                "pillars": {
                    p["kind"]: {"content": p["content"], "lang": p["lang"]}
                    for p in pillars
                }
            }

    # ================================================================
    # QDML: MUTATE
    # ================================================================

    async def mutate(self, component_slug: str, pillar_kind: str, new_content: str) -> bool:
        async with self.pool.acquire() as conn:
            comp_id = await conn.fetchval(
                "SELECT id FROM component WHERE slug=$1", component_slug)
            if not comp_id:
                raise ValueError(f"Component '{component_slug}' not found")
            result = await conn.execute(
                "UPDATE pillar SET content=$1, updated_at=now() WHERE component_id=$2 AND kind=$3",
                new_content, comp_id, pillar_kind)
            if result.split()[-1] == "0":
                raise ValueError(f"Pillar '{pillar_kind}' not found for '{component_slug}'")
            pid = await conn.fetchval(
                "SELECT id FROM pillar WHERE component_id=$1 AND kind=$2", comp_id, pillar_kind)
            await self._log(conn, "pillar", pid, "UPDATE",
                          {"component": component_slug, "kind": pillar_kind})
            return True

    # ================================================================
    # QDML: DELETE (with tombstone)
    # ================================================================

    async def delete_component(self, component_slug: str) -> bool:
        async with self.pool.acquire() as conn:
            comp = await conn.fetchrow(
                "SELECT id, name, slug FROM component WHERE slug=$1", component_slug)
            if not comp:
                raise ValueError(f"Component '{component_slug}' not found")
            await conn.execute("DELETE FROM component WHERE id=$1", comp["id"])
            await self._log(conn, "component", comp["id"], "DELETE",
                          {"slug": comp["slug"], "name": comp["name"]}, tombstone=True)
            return True

    # ================================================================
    # READ HELPERS (used by Compiler)
    # ================================================================

    async def read_all_modules(self) -> list[dict]:
        """Read all modules ordered."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, name, slug FROM module ORDER BY sort_order")
            return [dict(r) for r in rows]

    async def read_components(self, module_id: int) -> list[dict]:
        """Read all components for a module with their pillars."""
        async with self.pool.acquire() as conn:
            comps = await conn.fetch(
                "SELECT id, name, slug, kind, target FROM component WHERE module_id=$1 ORDER BY sort_order",
                module_id)
            result = []
            for c in comps:
                pillars = await conn.fetch(
                    "SELECT kind, content, lang FROM pillar WHERE component_id=$1 ORDER BY kind",
                    c["id"])
                result.append({
                    **dict(c),
                    "pillars": {p["kind"]: p["content"] for p in pillars}
                })
            return result

    async def read_shared_functions(self, lang: str = None) -> list[dict]:
        async with self.pool.acquire() as conn:
            q = "SELECT name, content, lang, description FROM shared_function"
            args = []
            if lang:
                q += " WHERE lang=$1"
                args.append(lang)
            q += " ORDER BY name"
            return [dict(r) for r in await conn.fetch(q, *args)]

    async def read_global_vars(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            return [dict(r) for r in await conn.fetch(
                "SELECT key, value, scope, scope_ref FROM global_var ORDER BY key")]

    async def read_design_tokens(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            return [dict(r) for r in await conn.fetch(
                "SELECT key, value, category FROM design_token ORDER BY category, key")]

    async def read_i18n(self) -> dict:
        """Returns {lang: {key: value, ...}, ...}"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """SELECT k.key, v.lang, v.value
                   FROM i18n_key k JOIN i18n_value v ON v.key_id = k.id
                   ORDER BY v.lang, k.key""")
            result = {}
            for r in rows:
                result.setdefault(r["lang"], {})[r["key"]] = r["value"]
            return result

    async def read_artifacts(self) -> list[dict]:
        async with self.pool.acquire() as conn:
            return [dict(r) for r in await conn.fetch(
                "SELECT filename, path, content, category FROM project_artifact ORDER BY path, filename")]

    # ================================================================
    # UTILITIES
    # ================================================================

    async def count(self) -> dict:
        async with self.pool.acquire() as conn:
            return {
                "modules": await conn.fetchval("SELECT COUNT(*) FROM module"),
                "components": await conn.fetchval("SELECT COUNT(*) FROM component"),
                "pillars": await conn.fetchval("SELECT COUNT(*) FROM pillar"),
                "shared_functions": await conn.fetchval("SELECT COUNT(*) FROM shared_function"),
                "artifacts": await conn.fetchval("SELECT COUNT(*) FROM project_artifact"),
                "changes": await conn.fetchval("SELECT COUNT(*) FROM change_log"),
            }

    async def changelog(self, limit: int = 20) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, table_name, row_id, operation, tombstone, ts FROM change_log ORDER BY ts DESC LIMIT $1",
                limit)
            return [{"id": r["id"], "table": r["table_name"], "row_id": r["row_id"],
                     "op": r["operation"], "tombstone": r["tombstone"],
                     "ts": r["ts"].isoformat()} for r in rows]

    async def wipe(self):
        """Delete ALL data. For testing only."""
        async with self.pool.acquire() as conn:
            for t in ["change_log", "pillar", "component", "module",
                       "shared_function", "global_var", "design_token",
                       "i18n_value", "i18n_key", "project_artifact"]:
                await conn.execute(f"DELETE FROM {t}")
