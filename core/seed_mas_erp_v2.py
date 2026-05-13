#!/usr/bin/env python3
"""Register MAS ERP V2 as a real AI-First/QDML project."""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import asyncpg

from config import DATABASE_URL, QDML_SCHEMA
from platform_pipeline import ensure_platform_schema


ROOT = Path("/srv/apps/ai-first/mas-erp/_generated")
DOC = Path("/srv/apps/ai-first/doc/MAS_ERP_V2_PROTOCOL.md")
PROJECT = "mas-erp"
PUBLIC_URL = "https://test.mas-erp.com"
LOCAL_URL = "http://127.0.0.1:9010"


FILES = [
    ("Runtime Service", "runtime-service", "backend", "server", "server", "server.js", "javascript", "service"),
    ("MAS Store V3", "mas-store-v3", "frontend", "mas-store", "mas-store", "mas-store-v3.js", "javascript", "library"),
    ("Dashboard Kit V2", "dashboard-kit-v2", "frontend", "mas-ui", "dashboard-kit", "dashboard-kit-v2.js", "javascript", "library"),
    ("ERP Application", "erp-application", "frontend", "mas-ui", "erp-app", "erp-app.js", "javascript", "screen"),
    ("ERP Styles", "erp-styles", "frontend", "mas-ui", "styles", "styles.css", "css", "config"),
    ("HTML Shell", "html-shell", "frontend", "frontend", "index-shell", "index.html", "html", "config"),
    ("MAS ERP V2 Protocol", "protocol-docs", "shared", "orchestration", "mas-erp-v2-protocol", str(DOC), "markdown", "config"),
]


PAGES = [
    ("home", "MAS ERP Home", "/", f"{PUBLIC_URL}/"),
    ("dashboard", "ERP Dashboard", "/#/dashboard", f"{PUBLIC_URL}/#/dashboard"),
    ("masters", "Master Data CRUD", "/#/masters", f"{PUBLIC_URL}/#/masters"),
    ("sales", "Sales Invoice", "/#/sales", f"{PUBLIC_URL}/#/sales"),
    ("purchase", "Purchase Invoice", "/#/purchase", f"{PUBLIC_URL}/#/purchase"),
    ("inventory", "Inventory Reports", "/#/inventory", f"{PUBLIC_URL}/#/inventory"),
    ("finance", "Financial Reports", "/#/finance", f"{PUBLIC_URL}/#/finance"),
]


def slugify(value: str) -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "item"


def read_text(path_text: str) -> str:
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    return path.read_text(encoding="utf-8", errors="ignore")


def line_count(text: str) -> int:
    return max(1, len(text.splitlines()))


async def upsert_project(conn) -> str:
    docs_en = DOC.read_text(encoding="utf-8", errors="ignore")
    docs_ar = """# MAS ERP V2

إعادة بناء فعلية لـ AI-Auto ERP فوق MAS Core V2 و MasStore V3 و Quantum.
الدومين للمشروع فقط: `test.mas-erp.com`. الشاشات routes داخل التطبيق.

النظام يختبر: CRUD الحسابات والأصناف والمخازن، فاتورة بيع وشراء header/detail،
تقارير مخزنية ومالية، وحفظ مسودة فاتورة حقيقي عبر Quantum.
"""
    ai_md = """MAS ERP V2 is the rebuilt ERP runtime for AI-First WF.
Do not copy old ai-auto UI. Use MAS Core V2, MasStore V3, dashboard-kit-v2,
and Quantum APIs. Project domain is test.mas-erp.com; pages are hash routes.
The critical cycle is chart of accounts, items, warehouses, sales/purchase
documents, inventory reports, financial reports, and document draft/finalize."""
    system_prompt = """Project invariants:
- No pure HTML app screens; index.html is only a loader shell.
- All data goes through MasStore V3.
- Runtime service proxies Quantum safely through /api/*.
- One project subdomain: test.mas-erp.com. Screens are routes.
- Draft save must work for sales_invoice_hd and purch_invoice_hd."""
    planner_prompt = """Planner split:
1. mas-store agent for data/proc/func/document contracts.
2. mas-ui agent for ERP routes, gkeys, invoice UI, dashboard kit.
3. backend-api agent for server.js, proxy, service health.
4. postgres/quantum agent for document-service and SQL/report gaps.
5. qa-browser agent for Playwright and curl verification."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO {QDML_SCHEMA}.project
            (name, slug, description, icon, base_domain, subdomain, port, service_name,
             service_type, nginx_domain, test_url, docs_en_md, docs_ar_md,
             ai_md, system_prompt_md, planner_prompt_md, status, curl_tests)
        VALUES
            ('MAS ERP V2', $1, $2, 'database', 'mas-erp.com', 'test.mas-erp.com',
             9010, 'mas-erp-v2', 'node', 'test.mas-erp.com', $3, $4, $5,
             $6, $7, $8, 'active', $9::jsonb)
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
            docs_ar_md=EXCLUDED.docs_ar_md,
            ai_md=EXCLUDED.ai_md,
            system_prompt_md=EXCLUDED.system_prompt_md,
            planner_prompt_md=EXCLUDED.planner_prompt_md,
            curl_tests=EXCLUDED.curl_tests,
            status='active'
        RETURNING id
        """,
        PROJECT,
        "Rebuilt Quantum ERP runtime using MAS Core V2, MasStore V3, and dashboard kit.",
        PUBLIC_URL,
        docs_en,
        docs_ar,
        ai_md,
        system_prompt,
        planner_prompt,
        json.dumps([
            {"name": "local-health", "url": f"{LOCAL_URL}/health", "expect": 200},
            {"name": "public-health", "url": f"{PUBLIC_URL}/health", "expect": 200},
            {"name": "v7-items", "url": f"{PUBLIC_URL}/api/v7", "method": "POST", "body": {"Action": "read", "Name": "inv_items", "Options": {"DataOnly": True, "top": 2}}},
        ]),
    )
    await conn.execute(
        f"""
        INSERT INTO {QDML_SCHEMA}.service_registry (project_id, name, url, port, protocol, health_url, status, meta)
        VALUES ($1,'mas-erp-v2',$2,9010,'http',$3,'active',$4::jsonb)
        ON CONFLICT (name, port) DO UPDATE SET
            project_id=EXCLUDED.project_id,
            url=EXCLUDED.url,
            health_url=EXCLUDED.health_url,
            status='active',
            meta=EXCLUDED.meta
        """,
        row["id"],
        LOCAL_URL,
        f"{LOCAL_URL}/health",
        json.dumps({"public_url": PUBLIC_URL, "source_root": str(ROOT), "upstream": "https://ai-auto.cloud"}),
    )
    return str(row["id"])


async def reset_modules(conn, project_id: str) -> None:
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.module WHERE project_id=$1", project_id)


async def upsert_file(conn, project_id: str, spec: tuple, order: int) -> None:
    module_name, module_slug, tier, classification, component_slug, path_text, lang, kind = spec
    content = read_text(path_text)
    module_id = await conn.fetchval(
        f"""
        INSERT INTO {QDML_SCHEMA}.module (project_id, name, slug, tier, app, assembler, sort_order)
        VALUES ($1,$2,$3,$4,'main','mas-erp-v2-seed',$5)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            name=EXCLUDED.name,
            tier=EXCLUDED.tier,
            assembler=EXCLUDED.assembler,
            sort_order=EXCLUDED.sort_order
        RETURNING id
        """,
        project_id,
        module_name,
        module_slug,
        tier,
        order,
    )
    component_id = await conn.fetchval(
        f"""
        INSERT INTO {QDML_SCHEMA}.component
            (module_id, name, slug, kind, target, meta, classification, description, ai_category, sort_order)
        VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7,$8,$9,$10)
        ON CONFLICT (module_id, slug) DO UPDATE SET
            name=EXCLUDED.name,
            kind=EXCLUDED.kind,
            target=EXCLUDED.target,
            meta=EXCLUDED.meta,
            classification=EXCLUDED.classification,
            description=EXCLUDED.description,
            ai_category=EXCLUDED.ai_category,
            sort_order=EXCLUDED.sort_order,
            updated_at=now()
        RETURNING id
        """,
        module_id,
        path_text,
        component_slug,
        kind,
        "mas-js" if lang in {"javascript", "html", "css", "markdown"} else lang,
        json.dumps({"source_path": str((ROOT / path_text) if not Path(path_text).is_absolute() else Path(path_text)), "runtime": PUBLIC_URL}),
        classification,
        f"MAS ERP V2 {path_text}",
        "frontend" if tier == "frontend" else tier,
        order,
    )
    lines = line_count(content)
    await conn.execute(
        f"""
        INSERT INTO {QDML_SCHEMA}.pillar
            (component_id, kind, content, lang, bulk_name, bulk_order, reveal, depends, exports,
             line_start, line_end, node_path, classification, role,
             ai_md, human_md_en, human_md_ar, description, human_summary)
        VALUES ($1,'bulk',$2,$3,'source',0,$4,'','',1,$5,$6,$7,'source',$8,$9,$10,$11,$12)
        ON CONFLICT (component_id, bulk_name) DO UPDATE SET
            content=EXCLUDED.content,
            lang=EXCLUDED.lang,
            reveal=EXCLUDED.reveal,
            line_start=EXCLUDED.line_start,
            line_end=EXCLUDED.line_end,
            node_path=EXCLUDED.node_path,
            classification=EXCLUDED.classification,
            ai_md=EXCLUDED.ai_md,
            human_md_en=EXCLUDED.human_md_en,
            human_md_ar=EXCLUDED.human_md_ar,
            description=EXCLUDED.description,
            human_summary=EXCLUDED.human_summary,
            updated_at=now()
        """,
        component_id,
        content,
        lang,
        path_text,
        lines,
        f"{module_slug}/{component_slug}/source",
        classification,
        f"{classification} source for MAS ERP V2. Keep edits inside MAS Core V2/MasStore V3 contract.",
        f"{path_text} in MAS ERP V2",
        f"{path_text} في MAS ERP V2",
        f"Registered source file {path_text}",
        f"{component_slug}: {lines} lines",
    )
    await conn.execute(
        f"""
        INSERT INTO {QDML_SCHEMA}.component_endpoint
            (component_id, endpoint_type, subdomain, path, port, url, health_url, is_primary, meta)
        VALUES ($1,'preview',NULL,$2,9010,$2,$3,true,$4::jsonb)
        ON CONFLICT (component_id, endpoint_type, path) DO UPDATE SET
            subdomain=NULL,
            port=EXCLUDED.port,
            url=EXCLUDED.url,
            health_url=EXCLUDED.health_url,
            is_primary=true,
            meta=EXCLUDED.meta,
            updated_at=now()
        """,
        component_id,
        f"/preview/{PROJECT}/{component_slug}",
        f"{LOCAL_URL}/health",
        json.dumps({"route_protocol": "project-domain-route", "public_runtime": PUBLIC_URL}),
    )


async def upsert_pages(conn, project_id: str) -> None:
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.project_page WHERE project_id=$1", project_id)
    for index, (slug, title, route, url) in enumerate(PAGES, start=1):
        await conn.execute(
            f"""
            INSERT INTO {QDML_SCHEMA}.project_page
                (project_id, slug, title, route_path, runtime_url, subdomain, url,
                 page_type, source_component_slug, meta)
            VALUES ($1,$2,$3,$4,$5,NULL,$5,'screen','erp-app',$6::jsonb)
            ON CONFLICT (project_id, slug) DO UPDATE SET
                title=EXCLUDED.title,
                route_path=EXCLUDED.route_path,
                runtime_url=EXCLUDED.runtime_url,
                subdomain=NULL,
                url=EXCLUDED.url,
                source_component_slug=EXCLUDED.source_component_slug,
                meta=EXCLUDED.meta,
                updated_at=now()
            """,
            project_id,
            slug,
            title,
            route,
            url,
            json.dumps({"sort_order": index, "project_subdomain_only": True, "local_url": LOCAL_URL + route}),
        )


async def upsert_tests(conn, project_id: str) -> None:
    auth_id = await conn.fetchval(
        f"""
        INSERT INTO {QDML_SCHEMA}.auth_script
            (project_id, name, slug, script_type, username, password_ref, credentials, script, is_default, meta)
        VALUES ($1,'No auth required','default','playwright','','',$2::jsonb,$3,true,$4::jsonb)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            credentials=EXCLUDED.credentials,
            script=EXCLUDED.script,
            is_default=true,
            updated_at=now()
        RETURNING id
        """,
        project_id,
        json.dumps({}),
        "await api.goto(api.test.url || api.project.test_url);\nawait api.wait(800);",
        json.dumps({"purpose": "public ERP smoke"}),
    )
    tests = [
        ("runtime-health", "Runtime health", "curl", "service", "runtime", f"{LOCAL_URL}/health", {"method": "GET"}, [{"status": 200}], ""),
        ("public-health", "Public health", "curl", "service", "runtime", f"{PUBLIC_URL}/health", {"method": "GET"}, [{"status": 200}], ""),
        ("v7-items", "Read items through MasStore contract", "curl", "api", "api-v7", f"{LOCAL_URL}/api/v7", {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": {"Action": "read", "Name": "inv_items", "Options": {"DataOnly": True, "top": 2}}}, [{"status": 200}, {"contains": "\"Success\":true"}], ""),
        ("sales-draft-save", "Sales invoice draft save", "curl", "api", "document-draft-save", f"{LOCAL_URL}/api/document-draft-save", {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": {"head_table": "sales_invoice_hd", "detail_table": "sales_invoice_dtl", "session": {"company_id": 3, "branch_id": 1, "user_id": 1, "user_name": "mas-erp-v2-test"}, "header": {"tenant_id": 3, "branch_id": 1, "doc_date": "2026-05-13", "posting_date": "2026-05-13", "due_date": "2026-05-13", "entity_id": 66, "warehouse_id": 10, "currency_id": 1, "exchange_rate": 1, "payment_term_id": 6, "posting_period_id": 17, "status": "draft", "subtotal": 95, "discount_total": 0, "extension_total": 0, "tax_total": 0, "grand_total": 95, "remarks": "MAS ERP V2 protocol test"}, "lines": [{"line_no": 1, "item_id": 19, "uom_id": 9, "qty": 1, "uom_factor": 1, "qty_base": 1, "price": 95, "discount_value": 0, "tax_value": 0, "line_total": 95, "remarks": "protocol"}]}}, [{"status": 200}, {"contains": "\"Success\":true"}], ""),
        ("page-dashboard-smoke", "Dashboard page smoke", "playwright", "page", "dashboard", f"{PUBLIC_URL}/#/dashboard", {}, [{"type": "visible", "selector": "body"}], "await api.expectVisible('body');\nawait api.expectVisible('text=لوحة القيادة');"),
        ("page-sales-smoke", "Sales invoice page smoke", "playwright", "page", "sales", f"{PUBLIC_URL}/#/sales", {}, [{"type": "visible", "selector": "body"}], "await api.expectVisible('body');\nawait api.expectVisible('text=فاتورة بيع');"),
    ]
    for slug, name, runner, kind, target, url, curl_config, assertions, script in tests:
        await conn.execute(
            f"""
            INSERT INTO {QDML_SCHEMA}.test_case
                (project_id, name, slug, runner_type, target_kind, target_slug, url, auth_script_id,
                 script, curl_config, assertions, timeout_ms, enabled, meta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,30000,true,$12::jsonb)
            ON CONFLICT (project_id, slug) DO UPDATE SET
                name=EXCLUDED.name,
                runner_type=EXCLUDED.runner_type,
                target_kind=EXCLUDED.target_kind,
                target_slug=EXCLUDED.target_slug,
                url=EXCLUDED.url,
                auth_script_id=EXCLUDED.auth_script_id,
                script=EXCLUDED.script,
                curl_config=EXCLUDED.curl_config,
                assertions=EXCLUDED.assertions,
                updated_at=now()
            """,
            project_id,
            name,
            slug,
            runner,
            kind,
            target,
            url,
            auth_id if runner == "playwright" else None,
            script,
            json.dumps(curl_config),
            json.dumps(assertions),
            json.dumps({"seed": "mas-erp-v2", "project_subdomain_only": True}),
        )


async def main() -> None:
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3, server_settings={"search_path": f"{QDML_SCHEMA},public"})
    try:
        await ensure_platform_schema(pool, QDML_SCHEMA)
        async with pool.acquire() as conn:
            async with conn.transaction():
                project_id = await upsert_project(conn)
                await reset_modules(conn, project_id)
                for order, spec in enumerate(FILES, start=1):
                    await upsert_file(conn, project_id, spec, order)
                await upsert_pages(conn, project_id)
                await upsert_tests(conn, project_id)
        print(f"seeded {PROJECT}: {len(FILES)} components, {len(PAGES)} pages")
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
