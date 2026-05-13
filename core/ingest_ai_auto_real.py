#!/usr/bin/env python3
"""
Ingest the real /srv/apps/ai-auto ERP into the AI-First QDML tree.

This replaces the toy ERP seed with source bulks from the working Quantum ERP:
document runtime, sales invoice UI, MAS libraries, schema, inventory SQL,
financial posting procedures, report SQL, and platform/domain pipeline code.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import asyncpg

from config import DATABASE_URL, QDML_SCHEMA
from platform_pipeline import ensure_platform_schema, slugify
from qdml_engine import QDMLEngine


AI_AUTO_ROOT = Path("/srv/apps/ai-auto")
PROJECT_SLUG = "erp"
MAX_CHUNK_LINES = 180


MODULES = [
    ("Quantum Runtime", "quantum-runtime", "backend", "quantum", "Node compatibility shell, runtime gateway, PostgreSQL adapter, and /API/v7 bridge."),
    ("Document Runtime", "document-runtime", "backend", "backend", "Schema-driven document profiles, defaults, save/finalize, lookups, and posting entrypoints."),
    ("MAS V2 Libraries", "mas-v2-libraries", "shared", "mas-store", "MAS API V2, MAS Store V2, MAS UI V2, bridges, app context, and mobile kit."),
    ("ERP Document Host", "erp-document-host", "frontend", "mas-ui", "Document host page and shell that loads schema-driven document modules."),
    ("Sales Invoice UI", "sales-invoice-ui", "frontend", "mas-ui", "Real sales invoice screen module: controller, state, validation, posting, inventory checks, and UI."),
    ("Shared Frontend Data", "shared-frontend-data", "frontend", "mas-store", "Frontend data/session/lookup runtime used by document screens."),
    ("Platform Domain Pipeline", "platform-domain-pipeline", "infra", "service", "AI-Auto platform admin, DNS, Cloudflare, services, provisioning, and domain pipeline code."),
    ("ERP Schema", "erp-schema", "data", "sql", "Accounting core schema contract with sales invoice and inventory metadata."),
    ("Inventory SQL", "inventory-sql", "data", "sql", "Inventory ledger, FIFO cost, warehouse balance, dispatch, and cache SQL."),
    ("Financial SQL", "financial-sql", "data", "sql", "Posting procedures, journal generation, defaults, and financial integrity SQL."),
    ("Reports SQL", "reports-sql", "data", "sql", "Inventory, cash, financial, dashboard, and menu report SQL functions."),
]


SOURCE_GROUPS = {
    "quantum-runtime": [
        "quantum/server.js",
        "quantum/runtime.js",
        "quantum/postgres.js",
        "quantum/v7.js",
        "quantum/schema-contract.js",
        "quantum/schema-registry.js",
        "quantum/cpp-client.js",
        "package.json",
    ],
    "document-runtime": [
        "quantum/document-profile.js",
        "quantum/document-service.js",
        "quantum/platform-service.js",
        "quantum/auth-service.js",
    ],
    "mas-v2-libraries": [
        "front/lib2/masapi_v2.js",
        "front/lib2/mas.store.v2.js",
        "front/lib2/mas-ui -v2.js",
        "front/lib2/mas.core.js",
        "front/lib2/app-context.js",
        "front/lib2/mobile-kit.js",
        "front/lib2/bridges/index.js",
        "front/lib2/bridges/masapi-v2.js",
        "front/lib2/bridges/mas-crud.js",
        "front/lib2/bridges/runtime.js",
        "front/lib2/bridges/dashboard.js",
        "front/lib2/bridges/mishkah.js",
    ],
    "erp-document-host": [
        "document-host.html",
        "front/document-host.html",
        "front/ui/document-host/main.js",
        "front/ui/document-host/data.js",
        "front/ui/document-host/logic.js",
        "front/ui/document-host/orders.js",
        "front/ui/document-host/ui.js",
        "front/ui/dashboard/main.js",
        "front/ui/dashboard/data.js",
        "front/ui/dashboard/logic.js",
        "front/ui/dashboard/orders.js",
        "front/ui/dashboard/ui.js",
        "front/index.html",
        "front/dashboard.html",
        "front/report-host.html",
    ],
    "sales-invoice-ui": [
        "front/ui/modules/documents/sales-invoice/index.js",
        "front/ui/modules/documents/sales-invoice/data.js",
        "front/ui/modules/documents/sales-invoice/logic.js",
        "front/ui/modules/documents/sales-invoice/orders.js",
        "front/ui/modules/documents/sales-invoice/ui.js",
    ],
    "shared-frontend-data": [
        "front/ui/shared/data/api.js",
        "front/ui/shared/data/session.js",
        "front/ui/shared/logic/document-profile.js",
        "front/ui/shared/logic/lookup-runtime.js",
        "front/ui/shared/logic/lookups.js",
        "front/ui/shared/logic/profile-local.js",
        "front/ui/shared/logic/quick-insert-local.js",
        "front/ui/shared/ui/lookup-field.js",
    ],
    "platform-domain-pipeline": [
        "quantum/platform-admin-service.js",
        "front/platform-admin.html",
        "front/ui/platform-admin/main.js",
        "front/ui/platform-admin/shared/data/api.js",
        "front/ui/platform-admin/core/mishkah.js",
        "front/ui/platform-admin/core/orders.js",
        "front/ui/platform-admin/core/registry.js",
        "front/ui/platform-admin/core/state.js",
        "front/ui/platform-admin/features/dns/logic.js",
        "front/ui/platform-admin/features/dns/orders.js",
        "front/ui/platform-admin/features/dns/ui.js",
        "front/ui/platform-admin/features/services/logic.js",
        "front/ui/platform-admin/features/services/orders.js",
        "front/ui/platform-admin/features/services/ui.js",
        "docs/domain-pipeline-api.md",
        "docs/platform-admin.md",
        "ops/nginx.ai-auto.cloud.conf",
        "ops/ai-auto-quantum.service",
    ],
    "erp-schema": [
        "accounting_core_schema_v1.json",
        "db/pgsql/manifest.json",
        "db/pgsql/manifest.schema.json",
        "docs/02_schema_and_naming_driven_core.md",
        "docs/08_doc_invoice_engine.md",
        "docs/10_finance_double_entry_flow.md",
        "docs/11_inventory_in_out_flow.md",
    ],
}


def collect_sql(folder: str) -> list[str]:
    base = AI_AUTO_ROOT / folder
    if not base.exists():
        return []
    return sorted(str(path.relative_to(AI_AUTO_ROOT)) for path in base.glob("*.sql"))


SOURCE_GROUPS["inventory-sql"] = collect_sql("db/pgsql/30-inventory") + collect_sql("db/pgsql/40-inv")
SOURCE_GROUPS["financial-sql"] = collect_sql("db/pgsql/30-fin") + collect_sql("db/pgsql/40-financial")
SOURCE_GROUPS["reports-sql"] = collect_sql("db/pgsql/50-reports")


def lang_for_path(path: str) -> str:
    suffix = Path(path).suffix.lower()
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".html": "html",
        ".css": "css",
        ".sql": "sql",
        ".json": "json",
        ".md": "markdown",
        ".service": "text",
        ".conf": "text",
    }.get(suffix, "text")


def target_for_path(path: str, module_slug: str) -> str:
    lang = lang_for_path(path)
    if lang == "sql":
        return "sql"
    if path.endswith(".html") or path.startswith("front/"):
        return "mas-js"
    if module_slug in {"quantum-runtime", "document-runtime", "platform-domain-pipeline"}:
        return "node"
    return "node"


def kind_for_path(path: str, module_slug: str) -> str:
    if path.endswith(".html") or module_slug in {"erp-document-host", "sales-invoice-ui"}:
        return "screen"
    if module_slug in {"quantum-runtime", "document-runtime", "platform-domain-pipeline"}:
        return "service"
    if lang_for_path(path) in {"sql", "json", "markdown", "text"}:
        return "config"
    return "library"


def classification_for_path(path: str, module_default: str) -> str:
    lower = path.lower()
    if lower.endswith(".sql") or "schema" in lower and lower.endswith(".json"):
        return "sql"
    if "mas.store" in lower or "/shared/data/" in lower or lower.endswith("/data.js") or "masapi" in lower:
        return "mas-store"
    if lower.startswith("front/") or lower.endswith(".html"):
        return "mas-ui" if "ui/" in lower or "document-host" in lower or "sales-invoice" in lower else "frontend"
    if lower.startswith("quantum/") and any(key in lower for key in ("schema", "runtime", "server", "v7")):
        return "quantum"
    if lower.startswith("quantum/"):
        return "backend"
    if lower.startswith("ops/") or "platform-admin" in lower or "domain-pipeline" in lower:
        return "service"
    return module_default


def heading_slug(lines: list[str], fallback: str) -> str:
    for raw in lines[:24]:
        line = raw.strip()
        if not line:
            continue
        match = re.search(r"(class|function|const|let|var|CREATE|PROCEDURE|FUNCTION|TABLE)\s+([A-Za-z0-9_.$-]+)", line, re.I)
        if match:
            return slugify(match.group(2), fallback)
        if line.startswith("import "):
            return "imports"
        if line.startswith("export "):
            return slugify(line[:70], fallback)
        if line.startswith("--") or line.startswith("#"):
            return slugify(line, fallback)
        if line.startswith("<"):
            return "markup"
    return fallback


def source_chunks(content: str, lang: str) -> list[dict[str, object]]:
    lines = content.splitlines()
    if len(lines) <= MAX_CHUNK_LINES:
        return [{"name": "source", "line_start": 1, "content": content}]

    chunks = []
    start = 0
    index = 1
    while start < len(lines):
        hard_end = min(len(lines), start + MAX_CHUNK_LINES)
        end = hard_end
        if hard_end < len(lines):
            for pos in range(hard_end - 1, start + 70, -1):
                probe = lines[pos].strip()
                if re.match(r"^(export\s+)?(async\s+)?function\s+|^export\s+(class|function|const)\s+|^class\s+|^CREATE\s+", probe, re.I):
                    end = pos
                    break
        if end <= start:
            end = hard_end
        part = lines[start:end]
        fallback = f"lines-{start + 1}-{end}"
        name = f"{index:03d}-{heading_slug(part, fallback)}"
        chunks.append({"name": name[:90], "line_start": start + 1, "content": "\n".join(part)})
        start = end
        index += 1
    return chunks


async def upsert_project(conn) -> str:
    docs_en = """# AI-Auto ERP

Real Quantum ERP running at https://ai-auto.cloud. This project is not a demo:
it contains schema-driven documents, sales invoice posting, inventory balance,
financial journal generation, platform/domain pipeline code, and MAS V2 frontend
runtime. The project domain is the only runtime host; screens are routes.
"""
    docs_ar = """# AI-Auto ERP

مشروع ERP حقيقي يعمل على https://ai-auto.cloud. يحتوي Quantum runtime،
document-service، فاتورة المبيعات، المخازن، القيود المالية، تقارير SQL،
ومسار إدارة الدومينات والخدمات. الدومين للمشروع فقط، والشاشات routes داخله.
"""
    ai_md = """Real ERP migration seed. Treat /srv/apps/ai-auto as the source lineage.
Sales invoice depends on document-profile, document-service, /API/v7, MASApiV2,
MAS Store V2, lookup runtime, inventory SQL, and financial posting procedures.
Do not replace it with a static mock. Any UI change must preserve document
profile contracts, gkeys/events, warehouse balance checks, and finalize/posting
flows. Test with Playwright on document-host preview and curl on document APIs."""
    system_prompt = """AI-Auto ERP invariants:
- Project runtime host: https://ai-auto.cloud only. No component/page subdomains.
- Sales invoice head table: sales_invoice_hd; line table: sales_invoice_dtl.
- Document APIs: /api/document-profile, /api/document-defaults, /api/document-draft-save, /api/document-finalize.
- Legacy/schema gateway: POST /API/v7.
- Inventory correctness depends on inv_movement_ledger, fn_inv_get_fifo_cost, fn_inv_warehouse_balance, and proc_inv_rebuild_stock_cache.
- Financial correctness depends on proc_fin_generate_journal and proc_fin_post_sales_invoice."""
    planner_prompt = """Planner must split ERP changes by contract:
1. document/runtime backend
2. MAS Store/data/session/lookup
3. MAS UI/sales invoice screen
4. SQL inventory/financial procedures
5. Playwright/curl QA
Ask for only the needed bulks; exclude unrelated platform-admin or reports unless the request touches domain pipeline or reporting."""
    row = await conn.fetchrow(
        f"""
        INSERT INTO {QDML_SCHEMA}.project
            (name, slug, description, icon, base_domain, subdomain, port, service_name,
             service_type, nginx_domain, test_url, docs_en_md, docs_ar_md,
             ai_md, system_prompt_md, planner_prompt_md, status)
        VALUES
            ('AI-Auto ERP', $1, $2, 'database', 'ai-auto.cloud', 'ai-auto.cloud', 3011,
             'ai-auto-quantum', 'node', 'ai-auto.cloud', 'https://ai-auto.cloud',
             $3, $4, $5, $6, $7, 'active')
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
            status='active'
        RETURNING id
        """,
        PROJECT_SLUG,
        "Real AI-Auto Quantum ERP: schema-driven documents, sales invoices, inventory, finance, reports, and platform pipeline.",
        docs_en,
        docs_ar,
        ai_md,
        system_prompt,
        planner_prompt,
    )
    await conn.execute(
        f"""
        INSERT INTO {QDML_SCHEMA}.service_registry (project_id, name, url, port, protocol, health_url, status, meta)
        VALUES ($1,'ai-auto-quantum','http://127.0.0.1:3011',3011,'http','http://127.0.0.1:3011/health','active',$2::jsonb)
        ON CONFLICT (name, port) DO UPDATE SET
            project_id=EXCLUDED.project_id,
            url=EXCLUDED.url,
            health_url=EXCLUDED.health_url,
            status='active',
            meta=EXCLUDED.meta
        """,
        row["id"],
        json.dumps({"public_host": "https://ai-auto.cloud", "source": "/srv/apps/ai-auto"}),
    )
    return str(row["id"])


async def reset_project(conn, project_id: str) -> None:
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.project_page WHERE project_id=$1", project_id)
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.test_case WHERE project_id=$1", project_id)
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.auth_script WHERE project_id=$1", project_id)
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.module WHERE project_id=$1", project_id)


async def upsert_pages_and_tests(conn, project_id: str) -> None:
    pages = [
        ("home", "AI-Auto ERP Home", "/", "https://ai-auto.cloud/", "front-index-html"),
        ("sales-invoice", "Sales Invoice Document", "/document-host.html?head_table=sales_invoice_hd&mode=preview", "https://ai-auto.cloud/document-host.html?head_table=sales_invoice_hd&mode=preview", "front-ui-modules-documents-sales-invoice-index-js"),
        ("platform-admin", "AI-Auto Platform Admin", "/platform-admin.html", "https://ai-auto.cloud/platform-admin.html", "front-ui-platform-admin-main-js"),
        ("dashboard", "ERP Dashboard", "/dashboard.html", "https://ai-auto.cloud/dashboard.html", "front-ui-dashboard-main-js"),
        ("reports", "ERP Report Host", "/report-host.html", "https://ai-auto.cloud/report-host.html", "front-report-host-html"),
    ]
    for order, (slug, title, route_path, runtime_url, source_component) in enumerate(pages):
        await conn.execute(
            f"""
            INSERT INTO {QDML_SCHEMA}.project_page
                (project_id, slug, title, route_path, runtime_url, subdomain, url,
                 page_type, source_component_slug, meta)
            VALUES ($1,$2,$3,$4,$5,NULL,$5,'screen',$6,$7::jsonb)
            ON CONFLICT (project_id, slug) DO UPDATE SET
                title=EXCLUDED.title,
                route_path=EXCLUDED.route_path,
                runtime_url=EXCLUDED.runtime_url,
                subdomain=NULL,
                url=EXCLUDED.url,
                page_type=EXCLUDED.page_type,
                source_component_slug=EXCLUDED.source_component_slug,
                meta=EXCLUDED.meta,
                updated_at=now()
            """,
            project_id,
            slug,
            title,
            route_path,
            runtime_url,
            source_component,
            json.dumps({"route_protocol": "project-domain-route", "sort_order": order}),
        )

    auth = await conn.fetchrow(
        f"""
        INSERT INTO {QDML_SCHEMA}.auth_script
            (project_id, name, slug, script_type, username, password_ref, credentials, script, is_default, meta)
        VALUES ($1,'AI-Auto preview session','default','playwright','preview','local-preview-session',$2::jsonb,$3,true,$4::jsonb)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            credentials=EXCLUDED.credentials,
            script=EXCLUDED.script,
            is_default=true,
            updated_at=now()
        RETURNING id
        """,
        project_id,
        json.dumps({"session": {"user_name": "preview", "company_name": "Preview Company", "company_id": 1, "branch_id": 1, "branch_name": "الفرع الرئيسي", "user_id": 1, "login_mode": "preview", "lang": "ar"}}),
        """
const url = api.test.url || api.project.test_url || "https://ai-auto.cloud/document-host.html?head_table=sales_invoice_hd&mode=preview";
const session = (api.auth || {}).session || { user_name: "preview", company_name: "Preview Company", company_id: 1, branch_id: 1, branch_name: "الفرع الرئيسي", user_id: 1, login_mode: "preview", lang: "ar" };
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
""",
        json.dumps({"purpose": "preview document-host without destructive login"}),
    )
    test_specs = [
        ("runtime-health", "Runtime health curl", "curl", "service", "runtime", "https://ai-auto.cloud/health", None, {"method": "GET"}, [{"status": 200}]),
        ("sales-invoice-profile", "Sales invoice document profile", "curl", "api", "document-profile", "https://ai-auto.cloud/api/document-profile?head_table=sales_invoice_hd", None, {"method": "GET"}, [{"status": 200}, {"contains": '"Success":true'}]),
        ("sales-invoice-defaults", "Sales invoice defaults", "curl", "api", "document-defaults", "https://ai-auto.cloud/api/document-defaults?head_table=sales_invoice_hd", None, {"method": "GET"}, [{"status": 200}, {"contains": '"defaults"'}]),
        ("sales-invoice-v7-schema", "Sales invoice /API/v7 schema", "curl", "api", "api-v7", "https://ai-auto.cloud/API/v7", None, {"method": "POST", "headers": {"Content-Type": "application/json"}, "body": {"Action": "schema", "Name": "sales_invoice_hd"}}, [{"status": 200}, {"contains": '"sales_invoice_hd"'}]),
        ("page-sales-invoice-smoke", "Sales invoice page smoke", "playwright", "page", "sales-invoice", "https://ai-auto.cloud/document-host.html?head_table=sales_invoice_hd&mode=preview", auth["id"], {}, [{"type": "visible", "selector": "body"}]),
        ("page-platform-admin-smoke", "Platform admin page smoke", "playwright", "page", "platform-admin", "https://ai-auto.cloud/platform-admin.html", auth["id"], {}, [{"type": "visible", "selector": "body"}]),
    ]
    for slug, name, runner, target_kind, target_slug, url, auth_id, curl_config, assertions in test_specs:
        script = """
await api.expectVisible("body");
api.log("ai-auto route ready", api.page.url());
"""
        await conn.execute(
            f"""
            INSERT INTO {QDML_SCHEMA}.test_case
                (project_id, name, slug, runner_type, target_kind, target_slug, url,
                 auth_script_id, script, curl_config, assertions, timeout_ms, enabled, meta)
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
            target_kind,
            target_slug,
            url,
            auth_id,
            script if runner == "playwright" else "",
            json.dumps(curl_config),
            json.dumps(assertions),
            json.dumps({"seed": "ai-auto-real-erp", "route_protocol": "project-domain-route"}),
        )


async def ingest_sources(engine: QDMLEngine, conn, project_id: str) -> tuple[int, int, int]:
    module_ids: dict[str, str] = {}
    module_meta = {slug: (name, tier, classification, description) for name, slug, tier, classification, description in MODULES}
    for order, (name, slug, tier, _classification, description) in enumerate(MODULES):
        module_id = await engine.create_module(PROJECT_SLUG, name, slug, tier=tier, app="ai-auto")
        await conn.execute(
            f"UPDATE {QDML_SCHEMA}.module SET sort_order=$1 WHERE id=$2",
            order,
            module_id,
        )
        module_ids[slug] = module_id

    component_count = 0
    bulk_count = 0
    total_lines = 0
    for module_slug, rel_paths in SOURCE_GROUPS.items():
        name, _tier, module_classification, module_description = module_meta[module_slug]
        for comp_order, rel_path in enumerate(rel_paths):
            source_path = AI_AUTO_ROOT / rel_path
            if not source_path.exists() or not source_path.is_file():
                print(f"[skip] missing {rel_path}")
                continue
            content = source_path.read_text(encoding="utf-8", errors="replace").rstrip()
            lang = lang_for_path(rel_path)
            component_slug = slugify(rel_path, f"component-{component_count}")
            component_name = rel_path
            classification = classification_for_path(rel_path, module_classification)
            component_id = await engine.create_component(
                module_slug,
                component_name,
                component_slug,
                kind=kind_for_path(rel_path, module_slug),
                target=target_for_path(rel_path, module_slug),
                meta={"source_path": str(source_path), "module_description": module_description},
                project_slug=PROJECT_SLUG,
            )
            await conn.execute(
                f"""
                UPDATE {QDML_SCHEMA}.component
                SET classification=$1, description=$2, ai_category=$3, sort_order=$4, updated_at=now()
                WHERE id=$5
                """,
                classification,
                f"Imported from /srv/apps/ai-auto/{rel_path}",
                classification,
                comp_order,
                component_id,
            )
            for chunk_order, chunk in enumerate(source_chunks(content, lang)):
                bulk_id = await engine.create_bulk(
                    component_slug,
                    str(chunk["name"]),
                    str(chunk["content"]),
                    lang=lang,
                    bulk_order=chunk_order,
                    reveal=f"/srv/apps/ai-auto/{rel_path}:{chunk['line_start']}",
                    depends="ai-auto-real-source",
                    exports=rel_path,
                    project_slug=PROJECT_SLUG,
                )
                chunk_lines = str(chunk["content"]).count("\n") + 1 if chunk["content"] else 0
                line_start = int(chunk["line_start"])
                await conn.execute(
                    f"""
                    UPDATE {QDML_SCHEMA}.pillar
                    SET line_start=$1,
                        line_end=$2,
                        node_path=$3,
                        classification=$4,
                        ai_md=$5,
                        human_md_en=$6,
                        human_md_ar=$7,
                        role='source',
                        updated_at=now()
                    WHERE id=$8
                    """,
                    line_start,
                    line_start + max(chunk_lines - 1, 0),
                    f"{module_slug}/{component_slug}/{chunk['name']}",
                    classification,
                    f"Real ai-auto source bulk from {rel_path}, lines {line_start}-{line_start + max(chunk_lines - 1, 0)}. Classification: {classification}.",
                    f"{rel_path} lines {line_start}-{line_start + max(chunk_lines - 1, 0)}.",
                    f"ملف {rel_path} من ai-auto الحقيقي، الأسطر {line_start}-{line_start + max(chunk_lines - 1, 0)}.",
                    bulk_id,
                )
                bulk_count += 1
                total_lines += chunk_lines
            component_count += 1
    return component_count, bulk_count, total_lines


async def main() -> None:
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2,
        max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"},
    )
    try:
        await ensure_platform_schema(pool, QDML_SCHEMA)
        engine = QDMLEngine(pool, schema=QDML_SCHEMA)
        async with pool.acquire() as conn:
            project_id = await upsert_project(conn)
            await reset_project(conn, project_id)
            components, bulks, lines = await ingest_sources(engine, conn, project_id)
            await upsert_pages_and_tests(conn, project_id)
        print(json.dumps({
            "ok": True,
            "project": PROJECT_SLUG,
            "source": str(AI_AUTO_ROOT),
            "components": components,
            "bulks": bulks,
            "lines": lines,
            "runtime": "https://ai-auto.cloud",
        }, ensure_ascii=False, indent=2))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
