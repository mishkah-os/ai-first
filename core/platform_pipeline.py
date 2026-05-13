"""
AI-First platform pipeline helpers.

This module keeps deployment/runtime concerns protocol-shaped instead of
scattering ad-hoc nginx, port, preview, and context logic through route files.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import html
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


APP_ROOT = Path(__file__).resolve().parents[1]
NGINX_SITES = Path("/etc/nginx/sites-available")
DOMAIN_RE = re.compile(r"server_name\s+([^;]+);")
FENCE_RE = re.compile(r"^\s*```[a-zA-Z0-9_-]*\s*\n(?P<body>.*?)(?:\n\s*```\s*)$", re.S)


def slugify(value: str, fallback: str = "project") -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or fallback


def strip_code_fence(content: str) -> str:
    content = content or ""
    match = FENCE_RE.match(content)
    if match:
        return match.group("body").strip()
    stripped = content.lstrip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        return "\n".join(lines).strip()
    return content


def public_suffix_base(host: str) -> str:
    parts = [p for p in host.split(".") if p]
    if len(parts) <= 2:
        return host
    if parts[-2:] == ["com", "eg"] and len(parts) >= 3:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


def discover_nginx_domains() -> dict[str, Any]:
    hosts: set[str] = set()
    bases: set[str] = set()
    if NGINX_SITES.exists():
        for path in NGINX_SITES.iterdir():
            if not path.is_file():
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for match in DOMAIN_RE.finditer(text):
                for raw in match.group(1).split():
                    host = raw.strip()
                    if not host or host == "_" or "$" in host or "*" in host:
                        continue
                    hosts.add(host)
                    bases.add(public_suffix_base(host))
    return {
        "hosts": sorted(hosts),
        "base_domains": sorted(bases),
        "source": str(NGINX_SITES),
    }


async def ensure_platform_schema(pool, schema: str) -> None:
    """Idempotently align DB tables with the current AI-First protocol."""
    statements = [
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS icon TEXT DEFAULT 'project'",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS logo_url TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS base_domain TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS subdomain TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS port INT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS service_name TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS service_type TEXT DEFAULT 'node'",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS nginx_domain TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS test_url TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS docs_en_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS docs_ar_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS test_credentials JSONB DEFAULT '{{}}'::jsonb",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS playwright_script TEXT",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS curl_tests JSONB DEFAULT '[]'::jsonb",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS ai_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS system_prompt_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.project ADD COLUMN IF NOT EXISTS planner_prompt_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.component ADD COLUMN IF NOT EXISTS classification TEXT DEFAULT 'custom'",
        f"ALTER TABLE {schema}.component ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.component ADD COLUMN IF NOT EXISTS ai_category TEXT DEFAULT 'frontend'",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS description TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS human_summary TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS parent_pillar_id UUID REFERENCES {schema}.pillar(id) ON DELETE SET NULL",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS node_path TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS line_start INT DEFAULT 1",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS line_end INT",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS classification TEXT DEFAULT 'custom'",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS ai_md TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS human_md_en TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS human_md_ar TEXT DEFAULT ''",
        f"ALTER TABLE {schema}.pillar ADD COLUMN IF NOT EXISTS role TEXT DEFAULT 'source'",
        f"""CREATE TABLE IF NOT EXISTS {schema}.component_endpoint (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            component_id UUID NOT NULL REFERENCES {schema}.component(id) ON DELETE CASCADE,
            endpoint_type TEXT NOT NULL DEFAULT 'preview',
            subdomain TEXT,
            path TEXT NOT NULL DEFAULT '/',
            port INT,
            url TEXT NOT NULL,
            health_url TEXT,
            is_primary BOOLEAN DEFAULT false,
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(component_id, endpoint_type, path)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.project_page (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES {schema}.project(id) ON DELETE CASCADE,
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            route_path TEXT NOT NULL DEFAULT '/',
            runtime_url TEXT NOT NULL,
            subdomain TEXT,
            url TEXT NOT NULL,
            page_type TEXT NOT NULL DEFAULT 'screen',
            source_component_slug TEXT,
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(project_id, slug)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.service_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            component_id UUID NOT NULL REFERENCES {schema}.component(id) ON DELETE CASCADE,
            port INT,
            env_vars JSONB DEFAULT '{{}}'::jsonb,
            health_check TEXT,
            startup_cmd TEXT,
            test_routes JSONB DEFAULT '[]'::jsonb,
            UNIQUE(component_id)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.test_suite (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            component_id UUID NOT NULL REFERENCES {schema}.component(id) ON DELETE CASCADE,
            test_name TEXT NOT NULL,
            test_type TEXT NOT NULL,
            test_code TEXT,
            curl_config JSONB,
            assertions JSONB,
            last_run TIMESTAMPTZ,
            last_result JSONB,
            UNIQUE(component_id, test_name)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.project_tree_node (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES {schema}.project(id) ON DELETE CASCADE,
            parent_id UUID REFERENCES {schema}.project_tree_node(id) ON DELETE CASCADE,
            node_type TEXT NOT NULL,
            slug TEXT NOT NULL,
            title TEXT NOT NULL,
            ref_table TEXT,
            ref_id UUID,
            node_path TEXT NOT NULL,
            classification TEXT DEFAULT 'custom',
            ai_md TEXT DEFAULT '',
            human_md_en TEXT DEFAULT '',
            human_md_ar TEXT DEFAULT '',
            meta JSONB DEFAULT '{{}}'::jsonb,
            sort_order INT DEFAULT 0,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(project_id, node_path)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.classification_instruction (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            classification TEXT NOT NULL,
            code_kind TEXT NOT NULL DEFAULT 'code',
            agent_slug TEXT,
            ai_md TEXT NOT NULL DEFAULT '',
            human_md_en TEXT NOT NULL DEFAULT '',
            human_md_ar TEXT NOT NULL DEFAULT '',
            schema_md TEXT NOT NULL DEFAULT '',
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(classification, code_kind)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.agent_profile (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            agent_role TEXT NOT NULL,
            owns_classifications TEXT[] DEFAULT '{{}}',
            system_md TEXT NOT NULL DEFAULT '',
            tools JSONB DEFAULT '[]'::jsonb,
            can_edit_core BOOLEAN DEFAULT false,
            can_execute_tests BOOLEAN DEFAULT true,
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.auth_script (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES {schema}.project(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            script_type TEXT NOT NULL DEFAULT 'playwright',
            username TEXT DEFAULT '',
            password_ref TEXT DEFAULT '',
            credentials JSONB DEFAULT '{{}}'::jsonb,
            script TEXT NOT NULL DEFAULT '',
            is_default BOOLEAN DEFAULT false,
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(project_id, slug)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.test_case (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID NOT NULL REFERENCES {schema}.project(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            slug TEXT NOT NULL,
            runner_type TEXT NOT NULL,
            target_kind TEXT NOT NULL DEFAULT 'project',
            target_slug TEXT NOT NULL DEFAULT '',
            url TEXT DEFAULT '',
            auth_script_id UUID REFERENCES {schema}.auth_script(id) ON DELETE SET NULL,
            script TEXT DEFAULT '',
            curl_config JSONB DEFAULT '{{}}'::jsonb,
            assertions JSONB DEFAULT '[]'::jsonb,
            timeout_ms INT DEFAULT 30000,
            enabled BOOLEAN DEFAULT true,
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now(),
            UNIQUE(project_id, slug)
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.test_run (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID REFERENCES {schema}.project(id) ON DELETE SET NULL,
            test_case_id UUID REFERENCES {schema}.test_case(id) ON DELETE SET NULL,
            runner_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            request JSONB DEFAULT '{{}}'::jsonb,
            result JSONB DEFAULT '{{}}'::jsonb,
            stdout TEXT DEFAULT '',
            stderr TEXT DEFAULT '',
            artifact_path TEXT DEFAULT '',
            started_at TIMESTAMPTZ DEFAULT now(),
            finished_at TIMESTAMPTZ
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.planner_run (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID REFERENCES {schema}.project(id) ON DELETE SET NULL,
            execution_mode TEXT NOT NULL DEFAULT 'planner',
            user_prompt TEXT NOT NULL DEFAULT '',
            selection JSONB DEFAULT '[]'::jsonb,
            prompt_packet JSONB DEFAULT '{{}}'::jsonb,
            plan JSONB DEFAULT '{{}}'::jsonb,
            status TEXT NOT NULL DEFAULT 'simulated',
            meta JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
        f"""CREATE TABLE IF NOT EXISTS {schema}.agent_task_assignment (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            planner_run_id UUID NOT NULL REFERENCES {schema}.planner_run(id) ON DELETE CASCADE,
            project_id UUID REFERENCES {schema}.project(id) ON DELETE SET NULL,
            agent_slug TEXT REFERENCES {schema}.agent_profile(slug) ON DELETE SET NULL,
            classification TEXT NOT NULL DEFAULT 'custom',
            title TEXT NOT NULL,
            prompt TEXT NOT NULL DEFAULT '',
            selection JSONB DEFAULT '[]'::jsonb,
            input_refs JSONB DEFAULT '[]'::jsonb,
            status TEXT NOT NULL DEFAULT 'planned',
            sort_order INT DEFAULT 0,
            result JSONB DEFAULT '{{}}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )""",
    ]
    async with pool.acquire() as conn:
        for sql in statements:
            await conn.execute(sql)
        await conn.execute(
            f"""
            UPDATE {schema}.pillar pi
            SET
                line_start=COALESCE(NULLIF(pi.line_start,0),1),
                line_end=COALESCE(pi.line_end, pi.lines),
                node_path=COALESCE(NULLIF(pi.node_path,''), c.slug || '/' || COALESCE(pi.bulk_name,'source')),
                classification=COALESCE(NULLIF(pi.classification,''), c.classification, 'custom'),
                ai_md=COALESCE(NULLIF(pi.ai_md,''), pi.human_summary, ''),
                human_md_en=COALESCE(NULLIF(pi.human_md_en,''), pi.human_summary, ''),
                human_md_ar=COALESCE(NULLIF(pi.human_md_ar,''), pi.human_summary, '')
            FROM {schema}.component c
            WHERE c.id=pi.component_id
            """
        )
    await seed_vibe_protocol(pool, schema)


async def next_project_port(pool, schema: str, base_port: int = 9000) -> int:
    current = await pool.fetchval(
        f"SELECT COALESCE(MAX(port), $1) FROM {schema}.project WHERE port IS NOT NULL",
        base_port,
    )
    return int(current) + 1


async def seed_vibe_protocol(pool, schema: str) -> None:
    """Install baseline agents/instructions used by the planner prompt packet."""
    agents = [
        {
            "slug": "planner",
            "name": "Planner / Orchestrator",
            "agent_role": "planner",
            "owns": ["architecture", "orchestration", "context"],
            "can_edit_core": False,
            "md": "You are the planning agent. Never edit code directly. Classify the request, remove unrelated noise, select the smallest useful context, assign micro-tasks to specialist agents, and define verification scripts.",
        },
        {
            "slug": "mas-ui",
            "name": "MAS UI Specialist",
            "agent_role": "worker",
            "owns": ["frontend", "mas-ui", "screen", "component"],
            "can_edit_core": False,
            "md": "Own MAS Core V2/QDML UI code. Preserve gkeys, emit a gkey contract for logic agents, avoid pure HTML screens, and keep page-level behavior testable.",
        },
        {
            "slug": "mas-store",
            "name": "MAS Store/Data Specialist",
            "agent_role": "worker",
            "owns": ["mas-store", "frontend-data", "ws3", "state"],
            "can_edit_core": False,
            "md": "Own MAS Store, live data, auth/session scoping, watchers, cache rules, and data contracts between UI and services.",
        },
        {
            "slug": "backend-api",
            "name": "Backend/API Specialist",
            "agent_role": "worker",
            "owns": ["backend", "api", "service"],
            "can_edit_core": False,
            "md": "Own HTTP APIs, service health, auth boundaries, curl-verifiable contracts, and integration behavior.",
        },
        {
            "slug": "postgres",
            "name": "PostgreSQL Specialist",
            "agent_role": "worker",
            "owns": ["sql", "postgres", "schema", "procedure"],
            "can_edit_core": False,
            "md": "Own schema, SQL, migrations, functions/procedures, indexes, and data integrity tests.",
        },
        {
            "slug": "quantum-core",
            "name": "Quantum/Core Specialist",
            "agent_role": "worker",
            "owns": ["quantum", "core", "runtime", "protocol"],
            "can_edit_core": True,
            "md": "Own platform/runtime core, QDML mutation protocol, AI-first orchestration, deploy pipeline, and cross-project structural changes.",
        },
        {
            "slug": "qa-browser",
            "name": "Browser QA Specialist",
            "agent_role": "reviewer",
            "owns": ["playwright", "curl", "qa", "verification"],
            "can_edit_core": False,
            "md": "Own Playwright and curl verification. Produce executable scripts, run them, summarize failures with selectors, console errors, screenshots, and HTTP status.",
        },
    ]
    instructions = [
        ("frontend", "javascript", "mas-ui", "Use MAS Core V2/QDML structures. No standalone pure HTML screen. Preserve gkeys and route-level preview behavior.", "Frontend UI code and page composition.", "كود واجهة؛ يجب أن يحافظ على MAS/QDML و gkeys."),
        ("mas-ui", "javascript", "mas-ui", "Describe D/MAS nodes, route state, gkeys, and expected events. UI changes must include a gkey contract.", "MAS UI specialist context.", "تعليمات واجهة MAS."),
        ("mas-store", "javascript", "mas-store", "Describe tables, filters, session/auth scope, WS3 watchers, cache invalidation, and save/load/remove behavior.", "MAS Store and frontend data layer.", "تعليمات طبقة MAS Store والبيانات."),
        ("backend", "javascript", "backend-api", "Describe routes, input/output contracts, auth, service health, and curl tests.", "Backend/API code.", "تعليمات الباك والـ API."),
        ("sql", "sql", "postgres", "Describe tables, indexes, migrations, procedures, integrity constraints, and rollback risks.", "PostgreSQL code.", "تعليمات SQL و PostgreSQL."),
        ("quantum", "python", "quantum-core", "Describe QDML protocol, tree nodes, AI prompt packets, deploy/test runners, and cross-project side effects.", "Platform/core code.", "تعليمات النواة والبروتوكول."),
        ("test", "javascript", "qa-browser", "Tests must be executable. Prefer Playwright for UI and curl for APIs. Include auth script requirements and expected assertions.", "Test code.", "تعليمات الاختبارات."),
        ("service", "config", "backend-api", "Describe runtime service, domain, port, health URL, systemd/nginx/cloudflare state, and the curl verification needed before UI work is accepted.", "Runtime service context.", "تعليمات الخدمة والدومين والفحص."),
        ("orchestration", "plan", "planner", "Split the request into agent-owned micro-tasks. State attention scope, excluded noise, required tests, and when a direct specialist can bypass the planner.", "Planner/A2A protocol context.", "تعليمات المخطط وبروتوكول الوكلاء."),
        ("custom", "code", "planner", "Classify first. Include only relevant bulks. Ask for missing context through the protocol rather than dumping the whole project.", "Generic code.", "تعليمات عامة."),
    ]
    async with pool.acquire() as conn:
        for agent in agents:
            await conn.execute(
                f"""
                INSERT INTO {schema}.agent_profile
                    (slug, name, agent_role, owns_classifications, system_md, tools, can_edit_core, can_execute_tests, meta)
                VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,true,$8::jsonb)
                ON CONFLICT (slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    agent_role=EXCLUDED.agent_role,
                    owns_classifications=EXCLUDED.owns_classifications,
                    system_md=EXCLUDED.system_md,
                    tools=EXCLUDED.tools,
                    can_edit_core=EXCLUDED.can_edit_core,
                    updated_at=now()
                """,
                agent["slug"],
                agent["name"],
                agent["agent_role"],
                agent["owns"],
                agent["md"],
                json.dumps(["prompt-packet", "mini-code", "full-code", "playwright", "curl", "syntax"]),
                agent["can_edit_core"],
                json.dumps({"seed": "vibe-protocol"}),
            )
        for classification, kind, agent_slug, ai_md, en, ar in instructions:
            await conn.execute(
                f"""
                INSERT INTO {schema}.classification_instruction
                    (classification, code_kind, agent_slug, ai_md, human_md_en, human_md_ar, schema_md, meta)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8::jsonb)
                ON CONFLICT (classification, code_kind) DO UPDATE SET
                    agent_slug=EXCLUDED.agent_slug,
                    ai_md=EXCLUDED.ai_md,
                    human_md_en=EXCLUDED.human_md_en,
                    human_md_ar=EXCLUDED.human_md_ar,
                    schema_md=EXCLUDED.schema_md,
                    updated_at=now()
                """,
                classification,
                kind,
                agent_slug,
                ai_md,
                en,
                ar,
                "Use project_tree_node and selected bulks as the contract. Do not infer hidden files when QDML already has the source.",
                json.dumps({"seed": "vibe-protocol"}),
            )


async def upsert_project_profile(pool, schema: str, payload: dict[str, Any]) -> dict[str, Any]:
    name = payload.get("name") or payload.get("slug") or "New Project"
    slug = slugify(payload.get("slug") or name)
    base_domain = payload.get("base_domain") or payload.get("domain") or "test.localhost"
    subdomain = payload.get("subdomain") or f"{slug}.{base_domain}"
    port = int(payload.get("port") or await next_project_port(pool, schema))
    service_name = payload.get("service_name") or f"qdml-{slug}"
    test_url = payload.get("test_url") or f"http://{subdomain}"
    docs_en = payload.get("docs_en_md") or payload.get("docs_en") or ""
    docs_ar = payload.get("docs_ar_md") or payload.get("docs_ar") or ""
    stack = payload.get("stack") or {}
    icon = payload.get("icon") or "[]"
    description = payload.get("description") or ""
    service_type = payload.get("service_type") or stack.get("service_type") or "node"

    row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.project
            (name, slug, description, icon, base_domain, subdomain, port, service_name,
             service_type, nginx_domain, test_url, docs_en_md, docs_ar_md, status)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$6,$10,$11,$12,'active')
        ON CONFLICT (slug) DO UPDATE SET
            name=EXCLUDED.name,
            description=EXCLUDED.description,
            icon=EXCLUDED.icon,
            base_domain=EXCLUDED.base_domain,
            subdomain=EXCLUDED.subdomain,
            port=EXCLUDED.port,
            service_name=EXCLUDED.service_name,
            service_type=EXCLUDED.service_type,
            nginx_domain=EXCLUDED.nginx_domain,
            test_url=EXCLUDED.test_url,
            docs_en_md=EXCLUDED.docs_en_md,
            docs_ar_md=EXCLUDED.docs_ar_md
        RETURNING *
        """,
        name,
        slug,
        description,
        icon,
        base_domain,
        subdomain,
        port,
        service_name,
        service_type,
        test_url,
        docs_en,
        docs_ar,
    )

    await pool.execute(
        f"""
        INSERT INTO {schema}.service_registry (project_id, name, url, port, protocol, health_url, status, meta)
        VALUES ($1,$2,$3,$4,'http',$5,'active',$6::jsonb)
        ON CONFLICT (name, port) DO UPDATE SET
            url=EXCLUDED.url,
            health_url=EXCLUDED.health_url,
            status=EXCLUDED.status,
            meta=EXCLUDED.meta
        """,
        row["id"],
        service_name,
        f"http://127.0.0.1:{port}",
        port,
        f"http://127.0.0.1:{port}/health",
        json.dumps({"subdomain": subdomain, "service_type": service_type}),
    )

    return dict(row)


async def project_tree(pool, schema: str, project_slug: str | None = None) -> list[dict[str, Any]]:
    args = []
    where = ""
    if project_slug:
        where = "WHERE p.slug=$1"
        args.append(project_slug)
    rows = await pool.fetch(
        f"""
        SELECT
            p.id as project_id, p.name as project_name, p.slug as project_slug,
            p.subdomain, p.base_domain, p.port, p.test_url, p.service_name,
            p.docs_en_md, p.docs_ar_md, p.ai_md, p.system_prompt_md, p.planner_prompt_md,
            m.id as module_id, m.name as module_name, m.slug as module_slug, m.tier, m.app,
            c.id as component_id, c.name as component_name, c.slug as component_slug,
            c.kind, c.target, c.classification, c.meta,
            COALESCE(SUM(pi.lines),0) as lines,
            COUNT(pi.id) FILTER (WHERE pi.kind='bulk') as bulks
        FROM {schema}.project p
        LEFT JOIN {schema}.module m ON m.project_id=p.id
        LEFT JOIN {schema}.component c ON c.module_id=m.id
        LEFT JOIN {schema}.pillar pi ON pi.component_id=c.id AND pi.kind='bulk'
        {where}
        GROUP BY p.id,m.id,c.id
        ORDER BY p.slug,m.tier,m.sort_order,c.sort_order,c.slug
        """,
        *args,
    )
    projects: dict[str, dict[str, Any]] = {}
    for row in rows:
        p = projects.setdefault(
            row["project_slug"],
            {
                "id": str(row["project_id"]),
                "name": row["project_name"],
                "slug": row["project_slug"],
                "subdomain": row["subdomain"],
                "base_domain": row["base_domain"],
                "port": row["port"],
                "service_name": row["service_name"],
                "test_url": row["test_url"],
                "docs_en_md": row["docs_en_md"],
                "docs_ar_md": row["docs_ar_md"],
                "ai_md": row["ai_md"],
                "system_prompt_md": row["system_prompt_md"],
                "planner_prompt_md": row["planner_prompt_md"],
                "modules": {},
            },
        )
        if not row["module_id"]:
            continue
        m = p["modules"].setdefault(
            row["module_slug"],
            {
                "id": str(row["module_id"]),
                "name": row["module_name"],
                "slug": row["module_slug"],
                "tier": row["tier"],
                "app": row["app"],
                "components": [],
            },
        )
        if row["component_id"]:
            m["components"].append(
                {
                    "id": str(row["component_id"]),
                    "name": row["component_name"],
                    "slug": row["component_slug"],
                    "kind": row["kind"],
                    "target": row["target"],
                    "classification": row["classification"],
                    "lines": int(row["lines"] or 0),
                    "bulks": int(row["bulks"] or 0),
                    "preview_url": f"/preview/{row['project_slug']}/{row['component_slug']}",
                    "full_code_url": f"/api/platform/projects/{row['project_slug']}/components/{row['component_slug']}/code?mode=full",
                    "mini_code_url": f"/api/platform/projects/{row['project_slug']}/components/{row['component_slug']}/code?mode=mini",
                }
            )
    out = []
    for p in projects.values():
        p["modules"] = list(p["modules"].values())
        out.append(p)
    return out


async def component_parts(pool, schema: str, project_slug: str, component_slug: str) -> dict[str, Any] | None:
    comp = await pool.fetchrow(
        f"""
        SELECT c.*, m.slug as module_slug, p.slug as project_slug, p.name as project_name
        FROM {schema}.component c
        JOIN {schema}.module m ON c.module_id=m.id
        JOIN {schema}.project p ON m.project_id=p.id
        WHERE p.slug=$1 AND c.slug=$2
        """,
        project_slug,
        component_slug,
    )
    if not comp:
        return None
    rows = await pool.fetch(
        f"""
        SELECT id, bulk_name, content, lang, lines, chars, exports, depends,
               line_start, line_end, parent_pillar_id, node_path, classification,
               ai_md, human_md_en, human_md_ar, role
        FROM {schema}.pillar
        WHERE component_id=$1 AND kind='bulk'
        ORDER BY bulk_order, bulk_name
        """,
        comp["id"],
    )
    parts: dict[str, list[str]] = {"javascript": [], "css": [], "html": [], "python": [], "sql": [], "other": []}
    bulks = []
    for row in rows:
        lang = (row["lang"] or "javascript").lower()
        content = strip_code_fence(row["content"] or "")
        key = lang if lang in parts else "other"
        parts[key].append(content)
        bulks.append({**dict(row), "content": content})
    return {"component": dict(comp), "parts": parts, "bulks": bulks}


def project_runtime_base(project_slug: str) -> str:
    return {
        "erp": "https://ai-auto.cloud",
        "mostamal-hawaa": "https://mostamal.ai-auto.cloud",
        "mostamal-hawaa-admin": "https://mostamal-admin.ai-auto.cloud",
    }.get(project_slug, f"/api/platform/projects/{project_slug}/inventory")


def component_route_hash(project_slug: str, component_slug: str) -> str:
    slug = component_slug or ""
    if project_slug == "mostamal-hawaa-admin":
        for key, route in [
            ("classifieds", "#/classifieds"),
            ("reels", "#/reels"),
            ("comments", "#/comments"),
            ("users", "#/users"),
            ("messages", "#/messages"),
            ("packages", "#/packages"),
            ("settings", "#/settings"),
        ]:
            if key in slug:
                return route
        return "#/overview"
    if project_slug == "mostamal-hawaa":
        for key, route in [
            ("features-reels", "#/route/reels"),
            ("feature-reels", "#/route/reels"),
            ("features-inbox", "#/route/inbox"),
            ("feature-inbox", "#/route/inbox"),
            ("features-profile", "#/route/profile"),
            ("feature-profile", "#/route/profile"),
            ("features-catalog", "#/route/classifieds"),
            ("feature-catalog", "#/route/classifieds"),
            ("features-feed", "#/route/classifieds"),
            ("feature-feed", "#/route/classifieds"),
            ("features-cart", "#/route/cart"),
            ("feature-cart", "#/route/cart"),
        ]:
            if key in slug:
                return route
    return ""


def known_project_pages(project_slug: str) -> list[dict[str, Any]]:
    if project_slug == "erp":
        return [
            {"slug": "home", "title": "AI-Auto ERP Home", "route_path": "/", "hash": "/", "source_component_slug": "front-index-html"},
            {"slug": "sales-invoice", "title": "Sales Invoice Document", "route_path": "/document-host.html?head_table=sales_invoice_hd&mode=preview", "hash": "/document-host.html?head_table=sales_invoice_hd&mode=preview", "source_component_slug": "front-ui-modules-documents-sales-invoice-index-js"},
            {"slug": "platform-admin", "title": "AI-Auto Platform Admin", "route_path": "/platform-admin.html", "hash": "/platform-admin.html", "source_component_slug": "front-ui-platform-admin-main-js"},
            {"slug": "dashboard", "title": "ERP Dashboard", "route_path": "/dashboard.html", "hash": "/dashboard.html", "source_component_slug": "front-ui-dashboard-main-js"},
            {"slug": "reports", "title": "ERP Report Host", "route_path": "/report-host.html", "hash": "/report-host.html", "source_component_slug": "front-report-host-html"},
        ]
    if project_slug == "mostamal-hawaa":
        return [
            {"slug": "home", "title": "Mostamal Hawaa Home", "route_path": "/", "hash": "", "source_component_slug": "src-app"},
            {"slug": "classifieds", "title": "Classifieds Feed", "route_path": "/route/classifieds", "hash": "#/route/classifieds", "source_component_slug": "src-features-catalog-ui"},
            {"slug": "reels", "title": "Reels Screen", "route_path": "/route/reels", "hash": "#/route/reels", "source_component_slug": "src-features-reels-ui"},
            {"slug": "inbox", "title": "Inbox Screen", "route_path": "/route/inbox", "hash": "#/route/inbox", "source_component_slug": "src-features-inbox-ui"},
            {"slug": "profile", "title": "Profile Screen", "route_path": "/route/profile", "hash": "#/route/profile", "source_component_slug": "src-features-profile-ui"},
            {"slug": "cart", "title": "Cart Screen", "route_path": "/route/cart", "hash": "#/route/cart", "source_component_slug": "src-features-cart-ui"},
        ]
    if project_slug == "mostamal-hawaa-admin":
        return [
            {"slug": "overview", "title": "Admin Overview", "route_path": "/overview", "hash": "#/overview", "source_component_slug": "src-app"},
            {"slug": "classifieds", "title": "Admin Classifieds", "route_path": "/classifieds", "hash": "#/classifieds", "source_component_slug": "src-shared-ui"},
            {"slug": "reels", "title": "Admin Reels", "route_path": "/reels", "hash": "#/reels", "source_component_slug": "src-shared-ui"},
            {"slug": "comments", "title": "Admin Comments", "route_path": "/comments", "hash": "#/comments", "source_component_slug": "src-shared-ui"},
            {"slug": "users", "title": "Admin Users", "route_path": "/users", "hash": "#/users", "source_component_slug": "src-shared-ui"},
            {"slug": "messages", "title": "Admin Messages", "route_path": "/messages", "hash": "#/messages", "source_component_slug": "src-shared-ui"},
            {"slug": "packages", "title": "Admin Packages", "route_path": "/packages", "hash": "#/packages", "source_component_slug": "src-shared-ui"},
            {"slug": "settings", "title": "Admin Settings", "route_path": "/settings", "hash": "#/settings", "source_component_slug": "src-shared-ui"},
        ]
    return []


async def ensure_project_pages(pool, schema: str, project_slug: str) -> list[dict[str, Any]]:
    project = await pool.fetchrow(
        f"SELECT id, slug, base_domain FROM {schema}.project WHERE slug=$1",
        project_slug,
    )
    if not project:
        return []
    pages = known_project_pages(project_slug)
    base_domain = project["base_domain"] or "test.localhost"
    runtime_base = project_runtime_base(project_slug)
    out: list[dict[str, Any]] = []
    for page in pages:
        runtime_url = page.get("runtime_url") or runtime_base.rstrip("/") + page.get("hash", "")
        platform_preview_url = f"/page/{project_slug}/{page['slug']}"
        row = await pool.fetchrow(
            f"""
            INSERT INTO {schema}.project_page
                (project_id, slug, title, route_path, runtime_url, subdomain, url,
                 page_type, source_component_slug, meta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,'screen',$8,$9::jsonb)
            ON CONFLICT (project_id, slug) DO UPDATE SET
                title=EXCLUDED.title,
                route_path=EXCLUDED.route_path,
                runtime_url=EXCLUDED.runtime_url,
                subdomain=EXCLUDED.subdomain,
                url=EXCLUDED.url,
                page_type=EXCLUDED.page_type,
                source_component_slug=EXCLUDED.source_component_slug,
                meta=EXCLUDED.meta,
                updated_at=now()
            RETURNING *
            """,
            project["id"],
            page["slug"],
            page["title"],
            page["route_path"],
            runtime_url,
            None,
            runtime_url,
            page.get("source_component_slug"),
            json.dumps({
                "runtime_base": runtime_base,
                "hash": page.get("hash", ""),
                "base_domain": base_domain,
                "platform_preview_url": platform_preview_url,
                "route_protocol": "project-domain-route",
            }),
        )
        out.append(_record(row))
    return out


async def project_pages(pool, schema: str, project_slug: str) -> list[dict[str, Any]]:
    await ensure_project_pages(pool, schema, project_slug)
    rows = await pool.fetch(
        f"""
        SELECT pp.*
        FROM {schema}.project_page pp
        JOIN {schema}.project p ON p.id=pp.project_id
        WHERE p.slug=$1
        ORDER BY pp.created_at, pp.slug
        """,
        project_slug,
    )
    return [_record(row) for row in rows]


async def page_parts(pool, schema: str, project_slug: str, page_slug: str) -> dict[str, Any] | None:
    pages = await project_pages(pool, schema, project_slug)
    page = next((p for p in pages if p["slug"] == page_slug), None)
    if not page:
        return None
    source = page.get("source_component_slug")
    related = []
    if source:
        source_parts = await component_parts(pool, schema, project_slug, source)
        if source_parts:
            related.append(source_parts)
    if not related:
        rows = await pool.fetch(
            f"""
            SELECT c.slug
            FROM {schema}.component c
            JOIN {schema}.module m ON m.id=c.module_id
            JOIN {schema}.project p ON p.id=m.project_id
            WHERE p.slug=$1 AND c.slug ILIKE $2
            ORDER BY c.slug
            LIMIT 8
            """,
            project_slug,
            f"%{page_slug}%",
        )
        for row in rows:
            cp = await component_parts(pool, schema, project_slug, row["slug"])
            if cp:
                related.append(cp)
    bulks: list[dict[str, Any]] = []
    for item in related:
        component_slug = item["component"]["slug"]
        for bulk in item["bulks"]:
            bulks.append({**bulk, "component_slug": component_slug})
    return {"page": page, "related": related, "bulks": bulks}


def mini_text(content: str, head: int = 18, tail: int = 6) -> str:
    lines = (content or "").splitlines()
    if len(lines) <= head + tail + 4:
        return content or ""
    hidden = len(lines) - head - tail
    return "\n".join(lines[:head] + [f"// ... {hidden} lines hidden ..."] + lines[-tail:])


def numbered_code(content: str, start_line: int = 1, mode: str = "mini", head: int = 18, tail: int = 6) -> str:
    lines = (content or "").splitlines()
    indexed = list(enumerate(lines, start=1))
    if mode == "mini" and len(indexed) > head + tail + 4:
        visible = indexed[:head] + [(0, f"// ... {len(indexed) - head - tail} lines hidden ...")] + indexed[-tail:]
    else:
        visible = indexed
    out = []
    for rel, line in visible:
        if rel == 0:
            out.append(f"   ... |   ... | {line}")
        else:
            absolute = max(1, int(start_line or 1)) + rel - 1
            out.append(f"{rel:6d} | {absolute:6d} | {line}")
    return "\n".join(out)


def selector_is_project_root(selector: dict[str, Any]) -> bool:
    return bool(selector.get("project")) and not any(
        selector.get(key) for key in ("page", "module", "component", "bulk", "service")
    )


def normalize_selections(selections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse parent/child multi-select noise before code expansion."""
    project_roots = {
        selector["project"]
        for selector in selections
        if isinstance(selector, dict) and selector_is_project_root(selector)
    }
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in selections:
        if not isinstance(raw, dict):
            continue
        selector = {key: value for key, value in raw.items() if value not in (None, "")}
        project = selector.get("project")
        if not project:
            continue
        if project in project_roots and not selector_is_project_root(selector):
            continue
        key = json.dumps(selector, ensure_ascii=False, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(selector)
    return normalized


def selector_depth(selector: dict[str, Any]) -> str:
    for key in ("bulk", "component", "page", "module", "service"):
        if selector.get(key):
            return key
    return "project"


def matches_search_rules(row: dict[str, Any], content: str, query: str) -> bool:
    query = (query or "").strip()
    if not query:
        return True
    haystacks = {
        "content": content.lower(),
        "component": str(row.get("component") or "").lower(),
        "bulk": str(row.get("bulk") or row.get("bulk_name") or "").lower(),
        "lang": str(row.get("lang") or "").lower(),
        "class": str(row.get("classification") or "").lower(),
        "label": f"{row.get('project','')}/{row.get('component','')}/{row.get('bulk','')}".lower(),
    }
    groups = [g.strip() for g in re.split(r"[,;\n]+", query) if g.strip()]
    if not groups:
        groups = [query]
    for group in groups:
        terms = [t.strip().lower() for t in group.split() if t.strip()]
        for term in terms:
            if ":" in term:
                key, value = term.split(":", 1)
                target = haystacks.get(key)
                if target is None or value not in target:
                    return False
            elif not any(term in value for value in haystacks.values()):
                return False
    return True


async def selected_bulk_payload(
    pool,
    schema: str,
    selections: list[dict[str, Any]],
    mode: str = "mini",
    max_chars: int = 60000,
    content_query: str = "",
) -> dict[str, Any]:
    normalized = normalize_selections(selections)
    packet = {
        "items": [],
        "excluded": [],
        "chars": 0,
        "mode": mode,
        "max_chars": max_chars,
        "selection_count": len(normalized),
        "original_selection_count": len(selections or []),
        "selection_normalized": normalized,
    }
    query = (content_query or "").strip().lower()
    seen_rows: set[tuple[str, str, str]] = set()
    for selector in normalized:
        project = selector.get("project")
        if not project:
            continue
        rows = []
        if selector.get("service") and not any(selector.get(key) for key in ("page", "module", "component", "bulk")):
            service_project = await pool.fetchrow(
                f"""
                SELECT slug AS project, service_name, service_type, port, subdomain,
                       test_url, nginx_domain
                FROM {schema}.project
                WHERE slug=$1
                """,
                project,
            )
            if service_project:
                service_payload = _record(service_project)
                rows.append({
                    "project": project,
                    "component": "service",
                    "bulk": selector.get("service") or "runtime",
                    "lang": "text",
                    "content": json.dumps(service_payload, ensure_ascii=False, indent=2),
                    "classification": "service",
                    "lines": 1,
                    "line_start": 1,
                    "line_end": 1,
                })
        elif selector.get("page"):
            parts = await page_parts(pool, schema, project, selector["page"])
            if not parts:
                packet["excluded"].append({"selector": selector, "reason": "page_not_found"})
                continue
            for bulk in parts["bulks"]:
                rows.append({
                    "project": project,
                    "component": bulk.get("component_slug") or parts["page"].get("source_component_slug") or "",
                    "bulk": bulk.get("bulk_name"),
                    "lang": bulk.get("lang"),
                    "content": bulk.get("content") or "",
                    "classification": "screen",
                    "lines": bulk.get("lines") or 0,
                    "line_start": bulk.get("line_start") or 1,
                    "line_end": bulk.get("line_end"),
                })
        else:
            args = [project]
            where = ["p.slug=$1", "pi.kind='bulk'"]
            if selector.get("module"):
                args.append(selector["module"])
                where.append(f"m.slug=${len(args)}")
            if selector.get("component"):
                args.append(selector["component"])
                where.append(f"c.slug=${len(args)}")
            if selector.get("bulk"):
                args.append(selector["bulk"])
                where.append(f"pi.bulk_name=${len(args)}")
            db_rows = await pool.fetch(
                f"""
                SELECT p.slug AS project, m.slug AS module, c.slug AS component,
                       COALESCE(pi.classification,c.classification,'custom') AS classification,
                       pi.bulk_name AS bulk, pi.lang, pi.content, pi.lines,
                       pi.line_start, pi.line_end, pi.node_path, pi.role, pi.ai_md, pi.human_md_en, pi.human_md_ar
                FROM {schema}.pillar pi
                JOIN {schema}.component c ON c.id=pi.component_id
                JOIN {schema}.module m ON m.id=c.module_id
                JOIN {schema}.project p ON p.id=m.project_id
                WHERE {' AND '.join(where)}
                ORDER BY m.sort_order, c.sort_order, pi.bulk_order, pi.bulk_name
                """,
                *args,
            )
            rows = [_record(row) for row in db_rows]
        for row in rows:
            content = strip_code_fence(row.get("content") or "")
            if not matches_search_rules(row, content, query):
                continue
            identity = (row.get("project") or project, row.get("component") or "", row.get("bulk") or "")
            if identity in seen_rows:
                packet["excluded"].append({"selector": selector, "label": "/".join(identity), "reason": "duplicate_parent_child_selection"})
                continue
            seen_rows.add(identity)
            rendered = numbered_code(content, row.get("line_start") or 1, "full" if mode == "full" or selector.get("full") else "mini")
            label = f"{row.get('project')}/{row.get('component')}/{row.get('bulk')}"
            if packet["chars"] + len(rendered) > max_chars:
                packet["excluded"].append({"selector": selector, "label": label, "reason": "context_budget", "chars": len(rendered)})
                continue
            packet["items"].append({
                "selector": selector,
                "label": label,
                "project": row.get("project") or project,
                "component": row.get("component") or "",
                "bulk": row.get("bulk") or "",
                "lang": row.get("lang") or "",
                "classification": row.get("classification") or "custom",
                "lines": int(row.get("lines") or 0),
                "content": rendered,
                "chars": len(rendered),
                "selection_depth": selector_depth(selector),
            })
            packet["chars"] += len(rendered)
    packet["ok"] = True
    return packet


async def project_protocol_tree(pool, schema: str, project_slug: str | None = None, content_query: str = "") -> dict[str, Any]:
    projects = await project_tree(pool, schema, project_slug)
    out_projects = []
    for project in projects:
        pages = await project_pages(pool, schema, project["slug"])
        service = service_runtime_health(project)
        page_nodes = [
            {
                "id": f"page:{project['slug']}:{page['slug']}",
                "type": "page",
                "slug": page["slug"],
                "title": page["title"],
                "select": {"project": project["slug"], "page": page["slug"]},
                "url": page["runtime_url"],
                "workbench_url": page.get("meta", {}).get("platform_preview_url") if isinstance(page.get("meta"), dict) else f"/page/{project['slug']}/{page['slug']}",
                "children": [],
                "md": {
                    "ai": f"Screen route {page['route_path']} in project {project['slug']}. Runtime URL: {page['runtime_url']}.",
                    "human_en": page["title"],
                    "human_ar": page["title"],
                },
            }
            for page in pages
        ]
        module_nodes = []
        for module in project.get("modules", []):
            comp_nodes = []
            for comp in module.get("components", []):
                bulk_rows = await pool.fetch(
                    f"""
                    SELECT id, bulk_name, lang, lines, chars, human_summary,
                           line_start, line_end, node_path, classification,
                           ai_md, human_md_en, human_md_ar, role, parent_pillar_id
                    FROM {schema}.pillar
                    WHERE component_id=$1 AND kind='bulk'
                    ORDER BY bulk_order, bulk_name
                    """,
                    comp["id"],
                )
                bulk_nodes_by_id: dict[str, dict[str, Any]] = {}
                for row in bulk_rows:
                    row_id = str(row["id"])
                    bulk_nodes_by_id[row_id] = {
                        "id": f"bulk:{project['slug']}:{comp['slug']}:{row['bulk_name']}",
                        "type": "bulk",
                        "slug": row["bulk_name"],
                        "title": row["bulk_name"],
                        "select": {"project": project["slug"], "component": comp["slug"], "bulk": row["bulk_name"]},
                        "lang": row["lang"],
                        "lines": int(row["lines"] or 0),
                        "chars": int(row["chars"] or 0),
                        "line_start": int(row["line_start"] or 1),
                        "line_end": int(row["line_end"] or 0) or None,
                        "node_path": row["node_path"] or "",
                        "classification": row["classification"] or comp.get("classification") or "custom",
                        "role": row["role"] or "source",
                        "parent_pillar_id": str(row["parent_pillar_id"]) if row["parent_pillar_id"] else None,
                        "md": {
                            "ai": row["ai_md"] or row["human_summary"] or f"{row['lang']} bulk with {row['lines']} lines.",
                            "human_en": row["human_md_en"] or row["human_summary"] or "",
                            "human_ar": row["human_md_ar"] or row["human_summary"] or "",
                        },
                        "children": [],
                    }
                bulk_nodes = []
                for node in bulk_nodes_by_id.values():
                    parent_id = node.get("parent_pillar_id")
                    if parent_id and parent_id in bulk_nodes_by_id:
                        bulk_nodes_by_id[parent_id]["children"].append(node)
                    else:
                        bulk_nodes.append(node)
                comp_nodes.append({
                    "id": f"component:{project['slug']}:{comp['slug']}",
                    "type": "component",
                    "slug": comp["slug"],
                    "title": comp["name"],
                    "classification": comp.get("classification") or "custom",
                    "select": {"project": project["slug"], "component": comp["slug"]},
                    "preview_url": comp["preview_url"],
                    "mini_code_url": comp["mini_code_url"],
                    "full_code_url": comp["full_code_url"],
                    "lines": comp["lines"],
                    "bulks": comp["bulks"],
                    "md": {
                        "ai": f"{comp.get('classification') or 'custom'} component. Target: {comp.get('target')}.",
                        "human_en": comp.get("name") or comp["slug"],
                        "human_ar": comp.get("name") or comp["slug"],
                    },
                    "children": bulk_nodes,
                })
            module_nodes.append({
                "id": f"module:{project['slug']}:{module['slug']}",
                "type": "module",
                "slug": module["slug"],
                "title": module["name"],
                "tier": module.get("tier"),
                "select": {"project": project["slug"], "module": module["slug"]},
                "children": comp_nodes,
                "md": {
                    "ai": f"Module {module['slug']} in tier {module.get('tier')}.",
                    "human_en": module["name"],
                    "human_ar": module["name"],
                },
            })
        out_projects.append({
            "id": f"project:{project['slug']}",
            "type": "project",
            "slug": project["slug"],
            "title": project["name"],
            "select": {"project": project["slug"]},
            "url": project.get("test_url"),
            "service": service,
            "md": {
                "ai": project.get("ai_md") or project.get("docs_en_md") or "",
                "human_en": project.get("docs_en_md") or "",
                "human_ar": project.get("docs_ar_md") or "",
            },
            "children": [
                {"id": f"service:{project['slug']}:runtime", "type": "service", "slug": "runtime", "title": project.get("service_name") or "runtime", "select": {"project": project["slug"], "service": "runtime"}, "children": [], "service": service},
                {"id": f"pages:{project['slug']}", "type": "group", "slug": "pages", "title": "Pages", "children": page_nodes},
                {"id": f"modules:{project['slug']}", "type": "group", "slug": "modules", "title": "Modules", "children": module_nodes},
            ],
        })
    return {"ok": True, "projects": out_projects, "content_query": content_query}


async def build_vibe_prompt_packet(pool, schema: str, body: dict[str, Any]) -> dict[str, Any]:
    selections = body.get("selection") or []
    mode = body.get("mode") or "mini"
    max_chars = int(body.get("max_chars") or 80000)
    user_prompt = body.get("prompt") or body.get("user_prompt") or ""
    execution_mode = body.get("execution_mode") or "planner"
    content_query = body.get("content_query") or ""
    context = await selected_bulk_payload(pool, schema, selections, mode=mode, max_chars=max_chars, content_query=content_query)
    project_slugs = sorted({item.get("project") for item in selections if item.get("project")})
    projects = []
    if project_slugs:
        rows = await pool.fetch(
            f"""
            SELECT slug, name, description, test_url, service_name, docs_en_md, docs_ar_md,
                   ai_md, system_prompt_md, planner_prompt_md
            FROM {schema}.project
            WHERE slug = ANY($1::text[])
            ORDER BY slug
            """,
            project_slugs,
        )
        projects = [_record(row) for row in rows]
    agents = [_record(row) for row in await pool.fetch(f"SELECT * FROM {schema}.agent_profile ORDER BY agent_role, slug")]
    classifications = sorted({item.get("classification") or "custom" for item in context["items"]})
    instruction_rows = await pool.fetch(
        f"""
        SELECT *
        FROM {schema}.classification_instruction
        WHERE classification = ANY($1::text[]) OR classification='custom'
        ORDER BY classification, code_kind
        """,
        classifications,
    )
    instructions = [_record(row) for row in instruction_rows]
    system_lines = [
        "# AI-First Vibe Coding System Instructions",
        "The planner is always the first receiver unless execution_mode is direct.",
        "Use project subdomains only for project/microservice runtime. Pages/components are routes, not subdomains.",
        "Use QDML selections and bulk ids as the mutation contract. Do not request the whole filesystem when selected bulks are enough.",
        "Available tools in this platform protocol: mini/full code context, bulk edit, syntax check, Playwright browser run, curl/API run, Bedrock health, service health.",
        "For UI work, preserve MAS Core V2/QDML, gkeys, and page-level previews. Pure standalone HTML screens are not allowed for app modules.",
    ]
    if execution_mode == "direct":
        agent_slug = body.get("agent_slug") or "quantum-core"
        agent = next((a for a in agents if a["slug"] == agent_slug), None)
        if agent:
            system_lines.append(f"\n# Direct Agent\n{agent['name']}\n{agent['system_md']}")
    else:
        planner = next((a for a in agents if a["slug"] == "planner"), None)
        if planner:
            system_lines.append(f"\n# Planner\n{planner['system_md']}")
        system_lines.append("\n# Available Agents\n" + "\n".join(f"- {a['slug']}: {a['name']} ({', '.join(a.get('owns_classifications') or [])})" for a in agents))
    project_lines = ["# Project Profiles"]
    for project in projects:
        project_lines.append(
            f"## {project['slug']} - {project['name']}\n"
            f"Runtime: {project.get('test_url') or ''}\n"
            f"Service: {project.get('service_name') or ''}\n"
            f"AI MD:\n{project.get('ai_md') or project.get('docs_en_md') or project.get('description') or ''}\n"
            f"Project System Prompt:\n{project.get('system_prompt_md') or ''}\n"
            f"Planner Prompt:\n{project.get('planner_prompt_md') or ''}"
        )
    instruction_lines = ["# Classification Instructions"]
    for item in instructions:
        instruction_lines.append(f"## {item['classification']} / {item['code_kind']} -> {item.get('agent_slug') or 'planner'}\n{item['ai_md']}\nSchema:\n{item.get('schema_md') or ''}")
    code_lines = ["# Selected Code Context"]
    for item in context["items"]:
        code_lines.append(f"## {item['label']} | {item['classification']} | {item['lang']} | {item['lines']} lines\n```{item['lang'] or 'text'}\n{item['content']}\n```")
    raw_prompt = "\n\n".join([
        "\n".join(system_lines),
        "\n\n".join(project_lines),
        "\n\n".join(instruction_lines),
        "\n\n".join(code_lines),
        "# User Request\n" + user_prompt,
    ])
    return {
        "ok": True,
        "execution_mode": execution_mode,
        "system_prompt": "\n".join(system_lines),
        "project_prompt": "\n\n".join(project_lines),
        "classification_prompt": "\n\n".join(instruction_lines),
        "code_context": context,
        "user_prompt": user_prompt,
        "raw_prompt": raw_prompt,
        "chars": len(raw_prompt),
        "agents": agents,
        "instructions": instructions,
    }


def agent_for_classification(agents: list[dict[str, Any]], classification: str) -> dict[str, Any] | None:
    classification = classification or "custom"
    for agent in agents:
        owns = agent.get("owns_classifications") or []
        if classification in owns:
            return agent
    for agent in agents:
        if agent.get("slug") == "planner":
            return agent
    return agents[0] if agents else None


async def simulate_planner_run(pool, schema: str, body: dict[str, Any]) -> dict[str, Any]:
    """Persist a deterministic planner/A2A dry run from the same prompt packet."""
    packet = await build_vibe_prompt_packet(pool, schema, {**body, "execution_mode": body.get("execution_mode") or "planner"})
    selections = packet["code_context"].get("selection_normalized") or body.get("selection") or []
    project_slugs = sorted({item.get("project") for item in selections if item.get("project")})
    primary_project = None
    if project_slugs:
        primary_project = await pool.fetchrow(f"SELECT id, slug FROM {schema}.project WHERE slug=$1", project_slugs[0])
    agents = packet.get("agents") or []
    items = packet["code_context"].get("items") or []
    grouped: dict[str, dict[str, Any]] = {}
    for item in items:
        classification = item.get("classification") or "custom"
        agent = agent_for_classification(agents, classification)
        agent_slug = (agent or {}).get("slug") or "planner"
        group = grouped.setdefault(
            agent_slug,
            {
                "agent_slug": agent_slug,
                "agent_name": (agent or {}).get("name") or agent_slug,
                "classifications": set(),
                "items": [],
            },
        )
        group["classifications"].add(classification)
        group["items"].append(item)

    micro_tasks = []
    for index, group in enumerate(grouped.values(), start=1):
        labels = [item["label"] for item in group["items"]]
        classifications = sorted(group["classifications"])
        task_selection = normalize_selections([item["selector"] for item in group["items"]])
        micro_tasks.append({
            "order": index,
            "agent_slug": group["agent_slug"],
            "title": f"{group['agent_name']}: study and patch {', '.join(classifications)}",
            "classification": classifications[0] if classifications else "custom",
            "classifications": classifications,
            "input_refs": labels,
            "selection": task_selection,
            "prompt": (
                "Read only the listed input_refs first. Report unrelated/noisy bulks. "
                "If editing is needed, return bulk-level mutations and required Playwright/curl checks."
            ),
        })

    gaps = []
    if not items:
        gaps.append("no_code_context_selected")
    if packet["code_context"].get("excluded"):
        gaps.append("some_selected_context_was_excluded")
    if any(selector_is_project_root(selector) for selector in selections) and packet["code_context"].get("chars", 0) > 60000:
        gaps.append("whole_project_selection_needs_search_or_smaller_budget")
    for slug in project_slugs:
        count = await pool.fetchval(
            f"""
            SELECT COUNT(*)
            FROM {schema}.test_case tc
            JOIN {schema}.project p ON p.id=tc.project_id
            WHERE p.slug=$1 AND tc.enabled=true
            """,
            slug,
        )
        if not count:
            gaps.append(f"{slug}:missing_playwright_or_curl_tests")

    plan = {
        "protocol": "ai-first-a2a-v1",
        "status": "simulated",
        "execution_mode": packet["execution_mode"],
        "attention_scope": {
            "projects": project_slugs,
            "selection_count": packet["code_context"].get("selection_count", 0),
            "original_selection_count": packet["code_context"].get("original_selection_count", 0),
            "included_bulks": len(items),
            "excluded": packet["code_context"].get("excluded", []),
        },
        "noise_policy": "normalized_parent_selection_and_deduped_bulk_labels",
        "micro_tasks": micro_tasks,
        "verification": {
            "required": True,
            "browser": "Run Playwright tests for changed screens with project auth_script first.",
            "api": "Run curl tests for touched service/API contracts.",
            "syntax": "Run syntax_report for every edited project before finalizing.",
        },
        "gaps": sorted(set(gaps)),
    }

    run_row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.planner_run
            (project_id, execution_mode, user_prompt, selection, prompt_packet, plan, status, meta)
        VALUES ($1,$2,$3,$4::jsonb,$5::jsonb,$6::jsonb,'simulated',$7::jsonb)
        RETURNING *
        """,
        primary_project["id"] if primary_project else None,
        packet["execution_mode"],
        packet.get("user_prompt") or "",
        json.dumps(selections, ensure_ascii=False),
        json.dumps(packet, ensure_ascii=False),
        json.dumps(plan, ensure_ascii=False),
        json.dumps({"simulator": "deterministic-planner", "bedrock_used": False}),
    )
    task_rows = []
    for task in micro_tasks:
        row = await pool.fetchrow(
            f"""
            INSERT INTO {schema}.agent_task_assignment
                (planner_run_id, project_id, agent_slug, classification, title, prompt,
                 selection, input_refs, status, sort_order)
            VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8::jsonb,'planned',$9)
            RETURNING *
            """,
            run_row["id"],
            primary_project["id"] if primary_project else None,
            task["agent_slug"],
            task["classification"],
            task["title"],
            task["prompt"],
            json.dumps(task["selection"], ensure_ascii=False),
            json.dumps(task["input_refs"], ensure_ascii=False),
            task["order"],
        )
        task_rows.append(_record(row))

    return {
        "ok": True,
        "planner_run": _record(run_row),
        "plan": plan,
        "tasks": task_rows,
        "prompt_packet": packet,
    }


def default_auth_script(project_slug: str) -> str:
    if project_slug == "erp":
        return """
const url = api.test.url || api.project.test_url || "https://ai-auto.cloud/document-host.html?head_table=sales_invoice_hd&mode=preview";
const session = (api.auth || {}).session || {
    user_name: "preview",
    company_name: "Preview Company",
    company_id: 1,
    branch_id: 1,
    branch_name: "الفرع الرئيسي",
    user_id: 1,
    login_mode: "preview",
    lang: "ar"
};
const headers = {};
if ((api.auth || {}).static_token) {
  headers.Authorization = `Bearer ${api.auth.static_token}`;
}
if ((api.auth || {}).bridge_token) {
  headers["X-AI5-Bridge-Token"] = api.auth.bridge_token;
}
if (Object.keys(headers).length) {
  await api.page.route("**/api/platform-admin/**", (route) => {
    route.continue({ headers: { ...route.request().headers(), ...headers } });
  });
}
await api.context.addInitScript((session) => {
  localStorage.setItem("ai-auto.demo.session", JSON.stringify(session));
  localStorage.setItem("appLang", session.lang || "ar");
}, session);
await api.goto(url);
await api.wait(1200);
"""
    if project_slug == "mostamal-hawaa-admin":
        return """
const url = api.test.url || api.project.test_url || "https://mostamal-admin.ai-auto.cloud";
await api.goto(url);
await api.fill('[data-action="form.login"][data-field="phone"], input[placeholder*="الهاتف"], input[type="tel"]', api.auth.phone || "+201000000999").catch(() => {});
await api.fill('[data-action="form.login"][data-field="password"], input[type="password"]', api.auth.password || "SbnTest@2026").catch(() => {});
await api.click('[data-action="auth.login"], button:has-text("دخول")').catch(() => {});
await api.page.waitForLoadState("domcontentloaded").catch(() => {});
await api.wait(1200);
"""
    if project_slug == "mostamal-hawaa":
        return """
const url = api.test.url || api.project.test_url || "https://mostamal.ai-auto.cloud";
await api.goto(url);
await api.page.evaluate((auth) => {
  const user = auth.user || { user_id: "usr_test_seif", id: "usr_test_seif", username: "usr_test_seif", full_name: "Seif Test", phone: "+201000000999", roles: ["user"] };
  const token = auth.token || "dev-playwright-token";
  localStorage.setItem("sbn_token", token);
  localStorage.setItem("auth_token", token);
  localStorage.setItem("mostamal_hawaa_token", token);
  localStorage.setItem("sbn_user", JSON.stringify(user));
  localStorage.setItem("auth_user", JSON.stringify(user));
  localStorage.setItem("mostamal_hawaa_user", JSON.stringify(user));
}, api.auth || {});
await api.goto(url);
await api.wait(800);
"""
    return """
await api.goto(api.test.url || api.project.test_url);
"""


def default_playwright_script(project_slug: str, page_slug: str = "home") -> str:
    if project_slug == "mostamal-hawaa-admin":
        return """
await api.expectVisible("body");
api.log("admin route", api.page.url());
"""
    if page_slug == "reels":
        return """
await api.expectVisible("body");
await api.page.locator('[data-reel-id], .reels-viewport, body').first().waitFor({ state: "visible", timeout: 8000 });
api.log("reels screen ready", api.page.url());
"""
    return """
await api.expectVisible("body");
api.log("page ready", api.page.url());
"""


async def ensure_project_test_protocol(pool, schema: str, project_slug: str) -> dict[str, Any]:
    project = await pool.fetchrow(f"SELECT id, slug, name, test_url FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    pages = await project_pages(pool, schema, project_slug)
    auth = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.auth_script
            (project_id, name, slug, script_type, username, password_ref, credentials, script, is_default, meta)
        VALUES ($1,'Default project auth','default','playwright',$2,'project:test-password',$3::jsonb,$4,true,$5::jsonb)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            username=EXCLUDED.username,
            credentials=EXCLUDED.credentials,
            script=EXCLUDED.script,
            is_default=true,
            updated_at=now()
        RETURNING *
        """,
        project["id"],
        "+201000000999" if project_slug in {"mostamal-hawaa", "mostamal-hawaa-admin"} else "",
        json.dumps({"phone": "+201000000999", "password": "SbnTest@2026", "user_id": "usr_test_seif"} if project_slug in {"mostamal-hawaa", "mostamal-hawaa-admin"} else {}),
        default_auth_script(project_slug),
        json.dumps({"purpose": "auth bootstrap for browser tests"}),
    )
    test_count = 0
    for page in pages:
        slug = f"page-{page['slug']}-smoke"
        await pool.execute(
            f"""
            INSERT INTO {schema}.test_case
                (project_id, name, slug, runner_type, target_kind, target_slug, url, auth_script_id,
                 script, curl_config, assertions, timeout_ms, enabled, meta)
            VALUES ($1,$2,$3,'playwright','page',$4,$5,$6,$7,$8::jsonb,$9::jsonb,30000,true,$10::jsonb)
            ON CONFLICT (project_id, slug) DO UPDATE SET
                name=EXCLUDED.name,
                target_kind=EXCLUDED.target_kind,
                target_slug=EXCLUDED.target_slug,
                url=EXCLUDED.url,
                auth_script_id=EXCLUDED.auth_script_id,
                script=EXCLUDED.script,
                updated_at=now()
            """,
            project["id"],
            f"{page['title']} smoke",
            slug,
            page["slug"],
            page["runtime_url"],
            auth["id"],
            default_playwright_script(project_slug, page["slug"]),
            json.dumps({}),
            json.dumps([{"type": "visible", "selector": "body"}]),
            json.dumps({"seed": "vibe-protocol", "route_protocol": "project-domain-route"}),
        )
        test_count += 1
    if project_slug == "erp":
        health_url = "https://ai-auto.cloud/health"
    elif project_slug == "mostamal-hawaa":
        health_url = "http://127.0.0.1:9001/health"
    elif project_slug == "mostamal-hawaa-admin":
        health_url = "http://127.0.0.1:9002/health"
    else:
        health_url = (project["test_url"] or "http://127.0.0.1:8001").rstrip("/") + "/health"
    await pool.execute(
        f"""
        INSERT INTO {schema}.test_case
            (project_id, name, slug, runner_type, target_kind, target_slug, url, curl_config, assertions, timeout_ms, enabled, meta)
        VALUES ($1,'Runtime health curl','runtime-health','curl','service','runtime',$2,$3::jsonb,$4::jsonb,15000,true,$5::jsonb)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            url=EXCLUDED.url,
            curl_config=EXCLUDED.curl_config,
            assertions=EXCLUDED.assertions,
            updated_at=now()
        """,
        project["id"],
        health_url,
        json.dumps({"method": "GET"}),
        json.dumps([{"status": 200}]),
        json.dumps({"seed": "vibe-protocol"}),
    )
    test_count += 1
    if project_slug == "erp":
        erp_curl_tests = [
            (
                "sales-invoice-profile",
                "Sales invoice document profile",
                "api",
                "document-profile",
                "https://ai-auto.cloud/api/document-profile?head_table=sales_invoice_hd",
                {"method": "GET"},
                [{"status": 200}, {"contains": '"Success":true'}],
            ),
            (
                "sales-invoice-defaults",
                "Sales invoice defaults",
                "api",
                "document-defaults",
                "https://ai-auto.cloud/api/document-defaults?head_table=sales_invoice_hd",
                {"method": "GET"},
                [{"status": 200}, {"contains": '"defaults"'}],
            ),
            (
                "sales-invoice-v7-schema",
                "Sales invoice /API/v7 schema",
                "api",
                "api-v7",
                "https://ai-auto.cloud/API/v7",
                {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": {"Action": "schema", "Name": "sales_invoice_hd"}},
                [{"status": 200}, {"contains": '"sales_invoice_hd"'}],
            ),
        ]
        for slug, name, kind, target, url, curl_config, assertions in erp_curl_tests:
            await pool.execute(
                f"""
                INSERT INTO {schema}.test_case
                    (project_id, name, slug, runner_type, target_kind, target_slug, url,
                     curl_config, assertions, timeout_ms, enabled, meta)
                VALUES ($1,$2,$3,'curl',$4,$5,$6,$7::jsonb,$8::jsonb,20000,true,$9::jsonb)
                ON CONFLICT (project_id, slug) DO UPDATE SET
                    name=EXCLUDED.name,
                    target_kind=EXCLUDED.target_kind,
                    target_slug=EXCLUDED.target_slug,
                    url=EXCLUDED.url,
                    curl_config=EXCLUDED.curl_config,
                    assertions=EXCLUDED.assertions,
                    updated_at=now()
                """,
                project["id"],
                name,
                slug,
                kind,
                target,
                url,
                json.dumps(curl_config),
                json.dumps(assertions),
                json.dumps({"seed": "ai-auto-real-erp", "document": "sales_invoice_hd"}),
            )
            test_count += 1
    return {"ok": True, "project": project_slug, "auth_script": _record(auth), "tests": test_count}


async def list_project_tests(pool, schema: str, project_slug: str) -> dict[str, Any]:
    project = await pool.fetchrow(f"SELECT id FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        return {"ok": False, "error": "project_not_found"}
    auth = await pool.fetch(f"SELECT * FROM {schema}.auth_script WHERE project_id=$1 ORDER BY is_default DESC, slug", project["id"])
    tests = await pool.fetch(
        f"""
        SELECT tc.*, a.slug AS auth_slug
        FROM {schema}.test_case tc
        LEFT JOIN {schema}.auth_script a ON a.id=tc.auth_script_id
        WHERE tc.project_id=$1
        ORDER BY tc.runner_type, tc.target_kind, tc.slug
        """,
        project["id"],
    )
    return {"ok": True, "auth_scripts": [_record(row) for row in auth], "tests": [_record(row) for row in tests]}


def run_curl_payload(config: dict[str, Any]) -> dict[str, Any]:
    url = config.get("url")
    if not url:
        return {"ok": False, "error": "url_required"}
    method = (config.get("method") or "GET").upper()
    timeout = str(int(config.get("timeout") or config.get("timeout_ms") or 15000) / 1000)
    cmd = ["curl", "-sS", "-L", "--max-time", timeout, "-X", method]
    headers = config.get("headers") or {}
    if isinstance(headers, dict):
        for key, value in headers.items():
            cmd.extend(["-H", f"{key}: {value}"])
    elif isinstance(headers, list):
        for header in headers:
            cmd.extend(["-H", str(header)])
    body = config.get("body")
    if body is not None:
        cmd.extend(["--data", body if isinstance(body, str) else json.dumps(body)])
    cmd.extend(["-w", "\n__AI_FIRST_CURL_META__%{http_code} %{url_effective} %{time_total}", url])
    started = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=float(timeout) + 5)
    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    stdout = proc.stdout or ""
    meta = ""
    if "__AI_FIRST_CURL_META__" in stdout:
        stdout, meta = stdout.rsplit("__AI_FIRST_CURL_META__", 1)
    parts = meta.strip().split()
    status = int(parts[0]) if parts and parts[0].isdigit() else 0
    effective_url = parts[1] if len(parts) > 1 else url
    assertion_results = []
    assertions_ok = True
    for assertion in config.get("assertions") or []:
        if not isinstance(assertion, dict):
            continue
        if "status" in assertion:
            expected = int(assertion["status"])
            passed = status == expected
            assertion_results.append({"type": "status", "expected": expected, "actual": status, "ok": passed})
            assertions_ok = assertions_ok and passed
        if "contains" in assertion:
            needle = str(assertion["contains"])
            passed = needle in stdout
            assertion_results.append({"type": "contains", "expected": needle, "ok": passed})
            assertions_ok = assertions_ok and passed
    return {
        "ok": proc.returncode == 0 and 200 <= status < 400 and assertions_ok,
        "status": status,
        "effective_url": effective_url,
        "duration_ms": duration_ms,
        "stdout": stdout[:20000],
        "stderr": (proc.stderr or "")[:8000],
        "returncode": proc.returncode,
        "assertions": assertion_results,
    }


def run_playwright_payload(payload: dict[str, Any]) -> dict[str, Any]:
    run_id = payload.get("run_id") or str(uuid.uuid4())
    artifact_dir = APP_ROOT / "runtime" / "test-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(payload)
    payload.setdefault("screenshot_path", str(artifact_dir / f"{run_id}.png"))
    runner = Path(__file__).parent / "test_runners" / "playwright_runner.js"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        payload_path = handle.name
    try:
        proc = subprocess.run(
            ["node", str(runner), payload_path],
            capture_output=True,
            text=True,
            timeout=max(10, int(payload.get("timeout_ms") or 30000) // 1000 + 10),
            cwd=str(Path(__file__).parent),
        )
        raw = (proc.stdout or "").strip()
        result = json.loads(raw) if raw else {"ok": False, "error": {"message": "empty runner output"}}
        result["returncode"] = proc.returncode
        result["stderr"] = (proc.stderr or "")[:8000]
        result.setdefault("screenshot_path", payload.get("screenshot_path"))
        return result
    except Exception as exc:
        return {"ok": False, "error": {"message": str(exc)}, "screenshot_path": payload.get("screenshot_path")}
    finally:
        try:
            Path(payload_path).unlink()
        except OSError:
            pass


def read_env_secret(env_file: str, key: str) -> str:
    path = Path(env_file)
    if not path.exists() or not key:
        return ""
    try:
        for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name.strip() == key:
                return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


def base64url_json(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def sign_ai5_bridge_token(secret: str, payload: dict[str, Any]) -> str:
    encoded = base64url_json(payload)
    digest = hmac.new(secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).digest()
    signature = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return f"{encoded}.{signature}"


def resolve_auth_secret_refs(credentials: dict[str, Any]) -> dict[str, Any]:
    resolved = dict(credentials or {})
    static_ref = resolved.get("static_token_ref")
    if isinstance(static_ref, dict):
        token = read_env_secret(static_ref.get("env_file") or "", static_ref.get("key") or "")
        if token:
            resolved["static_token"] = token
        resolved.pop("static_token_ref", None)
    bridge_ref = resolved.get("bridge_token_ref")
    if isinstance(bridge_ref, dict):
        secret = read_env_secret(bridge_ref.get("env_file") or "", bridge_ref.get("key") or "")
        if secret:
            ttl_ms = int(bridge_ref.get("ttl_seconds") or 3600) * 1000
            payload = {
                "user": bridge_ref.get("user") or "ai-first-playwright",
                "role": bridge_ref.get("role") or "super_admin",
                "jti": str(uuid.uuid4()),
                "exp": int(time.time() * 1000) + ttl_ms,
            }
            resolved["bridge_token"] = sign_ai5_bridge_token(secret, payload)
        resolved.pop("bridge_token_ref", None)
    return resolved


async def execute_test_payload(pool, schema: str, body: dict[str, Any]) -> dict[str, Any]:
    project_slug = body.get("project")
    test_id = body.get("test_id")
    runner_type = body.get("runner_type") or body.get("runner") or "playwright"
    project = None
    test = None
    auth = None
    if test_id:
        test = await pool.fetchrow(
            f"""
            SELECT tc.*, p.slug AS project_slug, p.name AS project_name, p.test_url AS project_url,
                   a.script AS auth_script, a.credentials AS auth_credentials
            FROM {schema}.test_case tc
            JOIN {schema}.project p ON p.id=tc.project_id
            LEFT JOIN {schema}.auth_script a ON a.id=tc.auth_script_id
            WHERE tc.id=$1
            """,
            test_id,
        )
        if not test:
            return {"ok": False, "error": "test_not_found"}
        runner_type = test["runner_type"]
        project_slug = test["project_slug"]
    if project_slug:
        project = await pool.fetchrow(f"SELECT * FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        return {"ok": False, "error": "project_required"}
    run_row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.test_run (project_id, test_case_id, runner_type, status, request)
        VALUES ($1,$2,$3,'running',$4::jsonb)
        RETURNING id
        """,
        project["id"],
        test["id"] if test else None,
        runner_type,
        json.dumps(body),
    )
    run_id = str(run_row["id"])
    if runner_type == "curl":
        config = dict(json_value(test["curl_config"], {}) or {}) if test else {}
        config.update(body.get("curl_config") or {})
        config.setdefault("url", body.get("url") or (test["url"] if test else None) or project["test_url"])
        assertions = body.get("assertions")
        if assertions is None and test:
            assertions = json_value(test["assertions"], [])
        if assertions is not None:
            config["assertions"] = assertions
        result = run_curl_payload(config)
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
    else:
        if body.get("auth_script_id") and not test:
            auth = await pool.fetchrow(f"SELECT * FROM {schema}.auth_script WHERE id=$1", body["auth_script_id"])
        auth_script = body.get("auth_script") or (test["auth_script"] if test else "") or (auth["script"] if auth else "")
        auth_credentials = body.get("auth") or (json_value(test["auth_credentials"], {}) if test else {}) or (json_value(auth["credentials"], {}) if auth else {}) or {}
        auth_credentials = resolve_auth_secret_refs(auth_credentials)
        script = body.get("script") or (test["script"] if test else "") or default_playwright_script(project_slug or "")
        url = body.get("url") or (test["url"] if test else None) or project["test_url"]
        result = run_playwright_payload({
            "run_id": run_id,
            "project": _record(project),
            "test": {"url": url, "slug": test["slug"] if test else body.get("slug", "ad-hoc")},
            "auth": auth_credentials,
            "auth_script": auth_script,
            "script": script,
            "timeout_ms": body.get("timeout_ms") or (test["timeout_ms"] if test else 30000),
            "headless": body.get("headless", True),
        })
        stdout = json.dumps(result.get("events") or [], ensure_ascii=False)
        stderr = result.get("stderr", "")
    await pool.execute(
        f"""
        UPDATE {schema}.test_run
        SET status=$2, result=$3::jsonb, stdout=$4, stderr=$5, artifact_path=$6, finished_at=now()
        WHERE id=$1
        """,
        run_id,
        "passed" if result.get("ok") else "failed",
        json.dumps(result, ensure_ascii=False),
        stdout,
        stderr,
        result.get("screenshot_path") or "",
    )
    return {"ok": bool(result.get("ok")), "run_id": run_id, "result": result}


def code_modes(bulks: list[dict[str, Any]], mode: str = "mini") -> str:
    chunks = []
    for bulk in bulks:
        content = bulk.get("content") or ""
        rendered = numbered_code(content, bulk.get("line_start") or 1, "full" if mode == "full" else "mini", head=22, tail=8)
        chunks.append(
            f"// bulk:{bulk.get('bulk_name')} lang:{bulk.get('lang')} "
            f"lines:{bulk.get('lines')} line_start:{bulk.get('line_start') or 1}\n{rendered}"
        )
    return "\n\n".join(chunks)


def render_preview_shell(
    project_slug: str,
    subject_slug: str,
    subject_kind: str,
    title: str,
    runtime_url: str,
    mini_code: str,
    full_code: str,
    bulk_name: str = "source",
    edit_component_slug: str | None = None,
) -> str:
    def js_json(value: Any) -> str:
        return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} preview</title>
<script src="/core-assets/mas.core.v2.js"></script>
<style>
body{{margin:0;font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f7fb;color:#162033}}
button,textarea{{font:inherit}}
.shell{{min-height:100vh;display:grid;grid-template-columns:280px minmax(0,1fr)}}
.rail{{border-right:1px solid #dbe2ee;background:#fff;padding:16px;display:flex;flex-direction:column;gap:16px}}
.brand h1{{font-size:15px;line-height:1.35;margin:0 0 6px;word-break:break-word}}
.brand p{{font-size:12px;line-height:1.45;margin:0;color:#667085}}
.tabs{{display:grid;gap:8px}}
.tabs button{{min-height:38px;border:1px solid #dbe2ee;border-radius:8px;background:#fff;color:#344054;text-align:left;padding:8px 10px;cursor:pointer}}
.tabs button.active{{border-color:#2563eb;background:#eff6ff;color:#1d4ed8;font-weight:700}}
.meta{{font-size:12px;color:#667085;line-height:1.5;border-top:1px solid #eef2f7;padding-top:12px}}
.stage{{min-width:0;display:flex;flex-direction:column;min-height:100vh}}
.toolbar{{min-height:56px;border-bottom:1px solid #dbe2ee;background:#fff;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px}}
.toolbar a,.toolbar button{{border:1px solid #dbe2ee;background:#fff;border-radius:8px;color:#1d4ed8;text-decoration:none;min-height:36px;padding:8px 10px;display:inline-flex;align-items:center;gap:8px}}
.panel{{min-height:0;flex:1;padding:14px}}
.runtime{{width:100%;height:calc(100vh - 88px);border:1px solid #dbe2ee;border-radius:8px;background:white}}
pre{{margin:0;white-space:pre-wrap;word-break:break-word;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:#101827;color:#e5edf8;border-radius:8px;padding:14px;min-height:calc(100vh - 88px);overflow:auto}}
textarea{{width:100%;min-height:calc(100vh - 150px);resize:vertical;border:1px solid #cbd5e1;border-radius:8px;padding:12px;font:12px/1.55 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color:#102033;background:#fff}}
.status{{font-size:12px;color:#667085}}
.status.ok{{color:#047857}}.status.error{{color:#b42318}}
@media(max-width:860px){{.shell{{grid-template-columns:1fr}}.rail{{border-right:0;border-bottom:1px solid #dbe2ee}}.tabs{{grid-template-columns:repeat(4,minmax(0,1fr))}}.runtime,pre{{min-height:60vh;height:60vh}}}}
</style>
</head>
<body>
<div id="preview-app"></div>
<script>
var payload={{
  project:{js_json(project_slug)},
  subject:{js_json(subject_slug)},
  subjectKind:{js_json(subject_kind)},
  editComponent:{js_json(edit_component_slug or "")},
  bulk:{js_json(bulk_name)},
  title:{js_json(title)},
  runtimeUrl:{js_json(runtime_url)},
  mini:{js_json(mini_code)},
  full:{js_json(full_code)}
}};
function body(db,D){{
  function tab(name,label){{return D.button({{class:db.tab===name?'active':'',gkey:'tab.'+name}},label);}}
  var content;
  if(db.tab==='preview') content=D.iframe({{class:'runtime',src:db.runtimeUrl,title:'runtime preview'}},[]);
  else if(db.tab==='mini') content=D.pre({{}},db.mini);
  else if(db.tab==='full') content=D.pre({{}},db.full);
  else content=D.div({{}},[
    D.textarea({{gkey:'edit.input',value:db.edit,'aria-label':'edit source'}},[]),
    D.div({{class:'toolbar'}},[
      D.span({{class:'status '+(db.error?'error':db.saved?'ok':'')}},db.error||db.saved||'editing '+db.bulk),
      D.button({{gkey:'edit.save'}},db.saving?'Saving...':'Save bulk')
    ])
  ]);
  return D.div({{class:'shell'}},[
    D.aside({{class:'rail'}},[
      D.div({{class:'brand'}},[D.h1({{}},db.title),D.p({{}},'QDML full-page runtime preview and code editor')]),
      D.div({{class:'tabs'}},[tab('preview','Preview'),tab('mini','Mini Code'),tab('full','Full Code'),tab('edit','Edit')]),
      D.div({{class:'meta'}},['project: '+db.project,D.br(), db.subjectKind+': '+db.subject,D.br(), 'bulk: '+db.bulk])
    ]),
    D.main({{class:'stage'}},[
      D.div({{class:'toolbar'}},[
        D.span({{}},db.tab==='preview'?'Runtime service':'Code view'),
        D.a({{href:db.runtimeUrl,target:'_blank',rel:'noreferrer'}},'Open runtime')
      ]),
      D.section({{class:'panel'}},[content])
    ])
  ]);
}}
var app=MAS.app(body,Object.assign({{tab:'preview',edit:payload.full,saving:false,saved:'',error:''}},payload),{{
  'tab.preview':function(e,ctx){{ctx.set({{tab:'preview',saved:'',error:''}});}},
  'tab.mini':function(e,ctx){{ctx.set({{tab:'mini',saved:'',error:''}});}},
  'tab.full':function(e,ctx){{ctx.set({{tab:'full',saved:'',error:''}});}},
  'tab.edit':function(e,ctx){{ctx.set({{tab:'edit',saved:'',error:''}});}},
  'edit.input':{{on:'input',do:function(e,ctx){{ctx.set({{edit:e.target.value,saved:'',error:''}});}}}},
  'edit.save':async function(e,ctx){{
    var state=ctx.getState();
    ctx.set({{saving:true,saved:'',error:''}});
    try{{
      if(!state.editComponent) throw new Error('No editable source component is mapped to this page yet');
      var res=await fetch('/api/platform/projects/'+encodeURIComponent(state.project)+'/components/'+encodeURIComponent(state.editComponent)+'/bulks/'+encodeURIComponent(state.bulk),{{
        method:'POST',
        headers:{{'Content-Type':'application/json'}},
        body:JSON.stringify({{content:state.edit,changed_by:'human',reason:'preview editor'}})
      }});
      if(!res.ok) throw new Error(await res.text());
      ctx.set({{saving:false,full:state.edit,saved:'saved'}});
    }}catch(err){{ctx.set({{saving:false,error:err.message||String(err)}});}}
  }}
}});
app.mount('#preview-app');
</script>
</body>
</html>"""


def render_preview_html(project_slug: str, component_slug: str, parts: dict[str, list[str]], bulks: list[dict[str, Any]]) -> str:
    title = f"{project_slug}/{component_slug}"
    bulk_name = (bulks[0].get("bulk_name") if bulks else "source") or "source"
    runtime_url = project_runtime_base(project_slug) + component_route_hash(project_slug, component_slug)
    return render_preview_shell(
        project_slug=project_slug,
        subject_slug=component_slug,
        subject_kind="component",
        title=title,
        runtime_url=runtime_url,
        mini_code=code_modes(bulks, "mini"),
        full_code=code_modes(bulks, "full"),
        bulk_name=bulk_name,
        edit_component_slug=component_slug,
    )


def render_page_preview_html(project_slug: str, page: dict[str, Any], bulks: list[dict[str, Any]]) -> str:
    title = f"{project_slug}/{page['slug']} page"
    bulk_name = (bulks[0].get("bulk_name") if bulks else "page") or "page"
    edit_component_slug = (bulks[0].get("component_slug") if bulks else None) or page.get("source_component_slug")
    return render_preview_shell(
        project_slug=project_slug,
        subject_slug=page["slug"],
        subject_kind="page",
        title=title,
        runtime_url=page["runtime_url"],
        mini_code=code_modes(bulks, "mini") if bulks else "// No source bulks mapped to this page yet.",
        full_code=code_modes(bulks, "full") if bulks else "// No source bulks mapped to this page yet.",
        bulk_name=bulk_name,
        edit_component_slug=edit_component_slug,
    )


def _record(row) -> dict[str, Any]:
    data = dict(row)
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif key in {"meta", "credentials", "curl_config", "assertions", "request", "result", "tools", "selection", "prompt_packet", "plan", "input_refs"} and isinstance(value, str):
            try:
                data[key] = json.loads(value)
            except Exception:
                data[key] = value
        elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            data[key] = str(value)
    return data


def json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def service_runtime_health(project: dict[str, Any]) -> dict[str, Any]:
    slug = project.get("slug")
    port = project.get("port")
    service = project.get("service_name")
    result: dict[str, Any] = {"project": slug, "service_name": service, "port": port, "ok": False}
    if service and shutil.which("systemctl"):
        proc = subprocess.run(["systemctl", "is-active", service], capture_output=True, text=True, timeout=5)
        result["systemd_status"] = (proc.stdout or proc.stderr or "").strip()
    if port:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=4) as resp:
                result["health_url"] = f"http://127.0.0.1:{port}/health"
                result["health_http_status"] = resp.status
                result["ok"] = 200 <= resp.status < 300
        except Exception as exc:
            result["health_url"] = f"http://127.0.0.1:{port}/health"
            result["health_error"] = str(exc)
    return result


def _read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def ai_auto_domain_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    """Call the production ai-auto domain pipeline without exposing secrets to UI."""
    env = _read_env_file(Path("/srv/apps/ai-auto/.env"))
    api_key = os.environ.get("AI_AUTO_PIPELINE_KEY") or env.get("AI_AUTO_PIPELINE_KEY")
    if not api_key:
        keys_json = env.get("PLATFORM_API_KEYS_JSON") or "[]"
        try:
            keys = json.loads(keys_json)
            api_key = (keys[0] or {}).get("key") if keys else None
        except Exception:
            api_key = None
    if not api_key:
        return {"ok": False, "status": "missing_api_key"}

    credentials_path = Path("/srv/apps/ai-auto/data/platform-admin-cloudflare.json")
    credential_id = payload.get("credential_id")
    zone_name = payload.get("zone_name") or public_suffix_base(payload.get("full_domain", "ai-auto.cloud"))
    if not credential_id and credentials_path.exists():
        try:
            loaded = json.loads(credentials_path.read_text(encoding="utf-8"))
            creds = loaded.get("credentials", []) if isinstance(loaded, dict) else loaded
            for cred in creds:
                if cred.get("zone_name") == zone_name:
                    credential_id = cred.get("id")
                    break
        except Exception:
            credential_id = None
    if not credential_id:
        return {"ok": False, "status": "missing_cloudflare_credential", "zone_name": zone_name}

    body = {
        "credential_id": credential_id,
        "zone_name": zone_name,
        "full_domain": payload["full_domain"],
        "listen_port": int(payload["listen_port"]),
        "service_name": payload.get("service_name") or "",
        "acme_email": payload.get("acme_email") or "admin@ai-auto.cloud",
        "proxied": bool(payload.get("proxied", False)),
        "dry_run": bool(payload.get("dry_run", True)),
    }
    data = json.dumps(body).encode("utf-8")
    url = os.environ.get("AI_AUTO_PIPELINE_URL") or "http://127.0.0.1:3011/api/platform/pipeline/domain"
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", "X-API-KEY": api_key},
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            result = json.loads(raw) if raw else {}
            result.pop("api_key", None)
            return {"ok": 200 <= resp.status < 300, "http_status": resp.status, "result": result}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        return {"ok": False, "http_status": exc.code, "error": raw[:2000]}
    except Exception as exc:
        return {"ok": False, "status": "error", "error": str(exc)}


@dataclass
class SyntaxResult:
    name: str
    lang: str
    ok: bool
    message: str = ""


def check_syntax(name: str, lang: str, content: str) -> SyntaxResult:
    content = strip_code_fence(content)
    lang = (lang or "").lower()
    if lang in {"javascript", "js", "mas-js", "node"}:
        proc = subprocess.run(
            ["node", "--check", "--input-type=module", "-"],
            input=content,
            text=True,
            capture_output=True,
            timeout=10,
        )
        return SyntaxResult(name, lang, proc.returncode == 0, (proc.stderr or proc.stdout).strip())
    if lang in {"python", "py"}:
        py = "import ast,sys\nast.parse(sys.stdin.read())\n"
        proc = subprocess.run(
            ["python3", "-c", py],
            input=content,
            text=True,
            capture_output=True,
            timeout=10,
        )
        return SyntaxResult(name, lang, proc.returncode == 0, (proc.stderr or proc.stdout).strip())
    if lang == "css":
        ok = content.count("{") == content.count("}")
        return SyntaxResult(name, lang, ok, "" if ok else "CSS brace count mismatch")
    if lang in {"html", "markdown", "sql", "json"}:
        return SyntaxResult(name, lang, True, "syntax checker is structural only")
    return SyntaxResult(name, lang or "unknown", True, "no checker configured")


async def syntax_report(pool, schema: str, project_slug: str) -> dict[str, Any]:
    rows = await pool.fetch(
        f"""
        SELECT c.slug as component, c.target, pi.bulk_name, pi.lang, pi.content, pi.bulk_order
        FROM {schema}.pillar pi
        JOIN {schema}.component c ON pi.component_id=c.id
        JOIN {schema}.module m ON c.module_id=m.id
        JOIN {schema}.project p ON m.project_id=p.id
        WHERE p.slug=$1 AND pi.kind='bulk'
        ORDER BY c.slug, pi.bulk_order
        """,
        project_slug,
    )
    started = time.perf_counter()
    components: dict[str, dict[str, Any]] = {}
    for row in rows:
        item = components.setdefault(
            row["component"],
            {"component": row["component"], "target": row["target"], "langs": [], "parts": [], "bulks": 0},
        )
        item["langs"].append((row["lang"] or "").lower())
        item["parts"].append(row["content"] or "")
        item["bulks"] += 1
    checks = []
    for component in components.values():
        langs = [lang for lang in component["langs"] if lang]
        lang = langs[0] if langs and all(item == langs[0] for item in langs) else "text"
        content = "\n".join(strip_code_fence(part) for part in component["parts"])
        result = check_syntax(component["component"], lang, content)
        data = result.__dict__
        data["bulks"] = component["bulks"]
        data["target"] = component["target"]
        checks.append(data)
    return {
        "project": project_slug,
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "duration_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def dependency_health() -> list[dict[str, Any]]:
    checks = []
    for name, cmd, required in [
        ("nginx-service", ["systemctl", "is-active", "nginx"], True),
        ("certbot", ["certbot", "--version"], True),
        ("systemctl", ["systemctl", "--version"], True),
        ("node", ["node", "--version"], True),
        ("python3", ["python3", "--version"], True),
        ("psql", ["psql", "--version"], True),
        ("cloudflared", ["cloudflared", "--version"], False),
        ("wrangler", ["wrangler", "--version"], False),
    ]:
        if not shutil.which(cmd[0]):
            checks.append({"name": name, "ok": False, "status": "missing", "required": required})
            continue
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
            combined = (proc.stdout or "") + (proc.stderr or "")
            ok = proc.returncode == 0 or (name == "nginx" and "test is successful" in combined)
            checks.append({
                "name": name,
                "ok": ok,
                "status": "ok" if ok else "error",
                "required": required,
                "output": combined.splitlines()[0] if combined else "",
            })
        except Exception as exc:
            checks.append({"name": name, "ok": False, "status": "error", "required": required, "output": str(exc)})
    for name, host, port in [
        ("ai-first-api-port", "127.0.0.1", 8001),
    ]:
        try:
            with socket.create_connection((host, port), timeout=2):
                checks.append({"name": name, "ok": True, "status": "ok", "required": True, "host": host, "port": port})
        except Exception as exc:
            checks.append({"name": name, "ok": False, "status": "error", "required": True, "host": host, "port": port, "output": str(exc)})
    for name, url in [
        ("bedrock-gateway-service", "http://127.0.0.1:8011/health"),
        ("ai-auto-domain-pipeline", "http://127.0.0.1:3011/health"),
        ("ant-swarm-api", "http://127.0.0.1:9060/openapi.json"),
        ("mostamal-hawaa-service", "http://127.0.0.1:9001/health"),
        ("mostamal-hawaa-admin-service", "http://127.0.0.1:9002/health"),
    ]:
        try:
            with urllib.request.urlopen(url, timeout=5) as resp:
                ok = 200 <= resp.status < 300
                checks.append({"name": name, "ok": ok, "status": "ok" if ok else "error", "required": True, "url": url, "http_status": resp.status})
        except urllib.error.HTTPError as exc:
            checks.append({"name": name, "ok": False, "status": "error", "required": True, "url": url, "http_status": exc.code})
        except Exception as exc:
            checks.append({"name": name, "ok": False, "status": "error", "required": True, "url": url, "output": str(exc)})
    return checks
