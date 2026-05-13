"""
Ingest the real Mostamal Hawaa source trees into QDML.

The platform stores code as project -> module -> component -> pillar records.
This script intentionally ingests the original app/admin files instead of demo
generated code so AI context selection works on the real system.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from pathlib import Path


DATABASE_URL = os.getenv(
    "QDML_DATABASE_URL",
    "postgresql://ai_auto:233f290cb68a514e3bb740d134f5bd50@127.0.0.1:5432/ai_auto",
)
SCHEMA = os.getenv("QDML_SCHEMA", "qdml")

APP_ROOT = Path("/srv/apps/os/static/app/mostamal_hawaa")
ADMIN_ROOT = Path("/srv/apps/os/static/app/mostamal_hawaa_admin")


def q(value: str | int | None) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def qjson(value) -> str:
    return q(json.dumps(value, ensure_ascii=False)) + "::jsonb"


def content_expr(text: str) -> str:
    raw = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"convert_from(decode('{raw}','base64'),'UTF8')"


def slugify(value: str, fallback: str = "item") -> str:
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or fallback


def lang_for(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".js": "javascript",
        ".mjs": "javascript",
        ".css": "css",
        ".html": "html",
        ".json": "json",
        ".webmanifest": "json",
        ".md": "markdown",
        ".sh": "bash",
    }.get(suffix, "text")


def target_for(path: Path) -> str:
    if path.suffix.lower() == ".py":
        return "python"
    if path.suffix.lower() in {".sql"}:
        return "sql"
    if path.suffix.lower() in {".json", ".webmanifest", ".md", ".html"}:
        return "mas-js"
    return "mas-js"


def kind_for(path: Path) -> str:
    rel = path.as_posix()
    name = path.name.lower()
    if name in {"index.html", "app.js"}:
        return "screen"
    if "/features/" in rel and name == "ui.js":
        return "screen"
    if name in {"orders.js", "api.js", "db.js", "mas-store-v3.js"}:
        return "service"
    if path.suffix.lower() in {".css", ".md", ".json", ".webmanifest", ".html"}:
        return "config"
    return "library"


def classification_for(path: Path) -> str:
    rel = path.as_posix()
    name = path.name.lower()
    if name == "mas-store-v3.js":
        return "mas-store-module"
    if name == "db.js":
        return "mas-store-db-shell"
    if name == "app.js":
        return "mas-v2-entrypoint"
    if name == "ui.js":
        return "mas-screen"
    if name == "orders.js":
        return "mas-orders"
    if path.suffix.lower() == ".css":
        return "css-theme"
    if path.suffix.lower() == ".md":
        return "docs"
    if "/admin" in rel:
        return "admin-module"
    return "source-module"


def module_for(root: Path, path: Path) -> tuple[str, str, str]:
    rel = path.relative_to(root).as_posix()
    if rel.startswith("src/core/"):
        return ("Core Runtime", "core-runtime", "shared")
    if rel.startswith("src/shared/logic/"):
        return ("Shared Logic", "shared-logic", "shared")
    if rel.startswith("src/shared/ui/"):
        return ("Shared UI", "shared-ui", "frontend")
    if rel.startswith("src/features/"):
        parts = rel.split("/")
        feature = Path(parts[2]).stem if len(parts) > 2 else "features"
        return (feature.replace("_", " ").title(), f"feature-{slugify(feature)}", "frontend")
    if rel.startswith("docs/") or path.suffix.lower() == ".md":
        return ("Documentation", "docs", "shared")
    if rel == "index.html" or rel == "service-worker.js":
        return ("App Shell", "app-shell", "frontend")
    return ("Assets", "assets", "shared")


def project_docs(root: Path, admin: bool = False) -> tuple[str, str]:
    docs = []
    for name in [
        "APP_STATUS_AND_ROADMAP.md",
        "MAS_STORE_DEVELOPER_GUIDE.md",
        "STORE_AND_SCHEMA_GUIDE.md",
        "SCAFFOLD_AND_CUSTOMIZATION.md",
        "ADMIN_GUIDE.md",
    ]:
        path = root / name
        if path.exists():
            docs.append(f"# {name}\n\n{path.read_text(encoding='utf-8', errors='ignore')}")
    en = "\n\n---\n\n".join(docs)
    ar = (
        "# Mostamal Hawaa Real Source Ingestion\n\n"
        "هذا المشروع ليس عينة مولدة. تم ربطه بمصدر مستعمل حواء الأصلي، "
        "وتقسيمه داخل QDML إلى موديولات ومكونات وبلوكات قابلة للاختيار والاختبار.\n\n"
        f"- source: `{root}`\n"
        f"- runtime: MAS v2 compatibility bridge\n"
        f"- admin: `{admin}`\n"
    )
    return en, ar


def collect_files(root: Path) -> list[Path]:
    allowed = {".js", ".css", ".html", ".json", ".webmanifest", ".md"}
    files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() in allowed or path.name in {"service-worker.js"}:
            files.append(path)
    return sorted(files)


def project_sql(slug: str, name: str, root: Path, subdomain: str, port: int, service_name: str, admin: bool = False) -> list[str]:
    docs_en, docs_ar = project_docs(root, admin)
    return [
        f"""
INSERT INTO {SCHEMA}.project
  (name, slug, description, icon, base_domain, subdomain, port, service_name, service_type, nginx_domain, test_url, docs_en_md, docs_ar_md, status, test_credentials, curl_tests)
VALUES
  ({q(name)}, {q(slug)}, {q('Original Mostamal Hawaa source mapped into QDML')}, {q('shopping-bag')},
   {q('test.localhost')}, {q(subdomain)}, {port}, {q(service_name)}, 'node', {q(subdomain)},
   {q('http://' + subdomain)}, {content_expr(docs_en)}, {content_expr(docs_ar)}, 'active',
   {qjson({'admin_phone': '+201000000999', 'admin_password': 'SbnTest@2026'} if admin else {})},
   {qjson([{'name': 'health', 'url': f'http://127.0.0.1:{port}/health', 'expect': 200}, {'name': 'index', 'url': f'http://127.0.0.1:{port}/', 'expect': 200}])})
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
  test_credentials=EXCLUDED.test_credentials,
  curl_tests=EXCLUDED.curl_tests;
""",
        f"DELETE FROM {SCHEMA}.module WHERE project_id=(SELECT id FROM {SCHEMA}.project WHERE slug={q(slug)});",
        f"""
INSERT INTO {SCHEMA}.service_registry (project_id, name, url, port, protocol, health_url, status, meta)
VALUES (
  (SELECT id FROM {SCHEMA}.project WHERE slug={q(slug)}),
  {q(service_name)}, {q(f'http://127.0.0.1:{port}')}, {port}, 'http',
  {q(f'http://127.0.0.1:{port}/health')}, 'active',
  {qjson({'source_root': str(root), 'subdomain': subdomain, 'runtime': 'original-source-mas-v2-compat'})}
)
ON CONFLICT (name, port) DO UPDATE SET
  url=EXCLUDED.url,
  health_url=EXCLUDED.health_url,
  status=EXCLUDED.status,
  meta=EXCLUDED.meta;
""",
    ]


def file_sql(project_slug: str, root: Path, path: Path, sort_order: int, subdomain_base: str, port: int) -> list[str]:
    rel = path.relative_to(root).as_posix()
    module_name, module_slug, tier = module_for(root, path)
    component_slug = slugify(rel.rsplit(".", 1)[0], "source")
    component_name = rel
    content = path.read_text(encoding="utf-8", errors="ignore")
    lang = lang_for(path)
    kind = kind_for(path)
    classification = classification_for(path)
    meta = {
        "source_path": str(path),
        "relative_path": rel,
        "source_root": str(root),
        "runtime": "mas-v2" if path.suffix.lower() in {".js", ".html"} else "asset",
    }
    preview_path = f"/preview/{project_slug}/{component_slug}"
    component_subdomain = f"{component_slug}--{project_slug}.{subdomain_base}"
    return [
        f"""
INSERT INTO {SCHEMA}.module (project_id, name, slug, tier, app, assembler, sort_order)
VALUES ((SELECT id FROM {SCHEMA}.project WHERE slug={q(project_slug)}), {q(module_name)}, {q(module_slug)}, {q(tier)}, 'main', 'source-tree', {sort_order})
ON CONFLICT (project_id, slug) DO UPDATE SET
  name=EXCLUDED.name,
  tier=EXCLUDED.tier,
  app=EXCLUDED.app,
  assembler=EXCLUDED.assembler,
  sort_order=LEAST({SCHEMA}.module.sort_order, EXCLUDED.sort_order);
""",
        f"""
INSERT INTO {SCHEMA}.component (module_id, name, slug, kind, target, meta, classification, description, ai_category, sort_order)
VALUES (
  (SELECT m.id FROM {SCHEMA}.module m JOIN {SCHEMA}.project p ON p.id=m.project_id WHERE p.slug={q(project_slug)} AND m.slug={q(module_slug)}),
  {q(component_name)}, {q(component_slug)}, {q(kind)}, {q(target_for(path))},
  {qjson(meta)}, {q(classification)}, {q('Original file: ' + rel)}, {q('frontend' if tier == 'frontend' else tier)}, {sort_order}
)
ON CONFLICT (module_id, slug) DO UPDATE SET
  name=EXCLUDED.name,
  kind=EXCLUDED.kind,
  target=EXCLUDED.target,
  meta=EXCLUDED.meta,
  classification=EXCLUDED.classification,
  description=EXCLUDED.description,
  ai_category=EXCLUDED.ai_category,
  sort_order=EXCLUDED.sort_order,
  updated_at=now();
""",
        f"""
INSERT INTO {SCHEMA}.pillar (component_id, kind, content, lang, bulk_name, bulk_order, reveal, depends, exports, description, human_summary)
VALUES (
  (SELECT c.id FROM {SCHEMA}.component c JOIN {SCHEMA}.module m ON m.id=c.module_id JOIN {SCHEMA}.project p ON p.id=m.project_id WHERE p.slug={q(project_slug)} AND c.slug={q(component_slug)}),
  'bulk', {content_expr(content)}, {q(lang)}, 'source', 0, {q(rel)}, '', '', {q('Original source bulk')}, {q(rel)}
)
ON CONFLICT (component_id, bulk_name) DO UPDATE SET
  content=EXCLUDED.content,
  lang=EXCLUDED.lang,
  reveal=EXCLUDED.reveal,
  description=EXCLUDED.description,
  human_summary=EXCLUDED.human_summary,
  updated_at=now();
""",
        f"""
INSERT INTO {SCHEMA}.component_endpoint (component_id, endpoint_type, subdomain, path, port, url, health_url, is_primary, meta)
VALUES (
  (SELECT c.id FROM {SCHEMA}.component c JOIN {SCHEMA}.module m ON m.id=c.module_id JOIN {SCHEMA}.project p ON p.id=m.project_id WHERE p.slug={q(project_slug)} AND c.slug={q(component_slug)}),
  'preview', {q(component_subdomain)}, {q(preview_path)}, {port}, {q(preview_path)}, {q(f'http://127.0.0.1:{port}/health')}, true,
  {qjson({'component_subdomain': component_subdomain, 'source_path': str(path), 'preview_path': preview_path})}
)
ON CONFLICT (component_id, endpoint_type, path) DO UPDATE SET
  subdomain=EXCLUDED.subdomain,
  port=EXCLUDED.port,
  url=EXCLUDED.url,
  health_url=EXCLUDED.health_url,
  is_primary=EXCLUDED.is_primary,
  meta=EXCLUDED.meta,
  updated_at=now();
""",
        f"""
INSERT INTO {SCHEMA}.test_suite (component_id, test_name, test_type, test_code, curl_config, assertions)
VALUES (
  (SELECT c.id FROM {SCHEMA}.component c JOIN {SCHEMA}.module m ON m.id=c.module_id JOIN {SCHEMA}.project p ON p.id=m.project_id WHERE p.slug={q(project_slug)} AND c.slug={q(component_slug)}),
  'source-syntax', 'unit', {q('node --check ' + str(path) if lang == 'javascript' else 'structural')},
  {qjson({'source_path': str(path), 'lang': lang})}, {qjson({'must_parse': lang in {'javascript', 'css', 'json', 'html'}})}
)
ON CONFLICT (component_id, test_name) DO UPDATE SET
  test_type=EXCLUDED.test_type,
  test_code=EXCLUDED.test_code,
  curl_config=EXCLUDED.curl_config,
  assertions=EXCLUDED.assertions;
""",
    ]


def build_sql() -> str:
    statements = ["BEGIN;", f"SET search_path TO {SCHEMA}, public;"]
    projects = [
        ("mostamal-hawaa", "Mostamal Hawaa", APP_ROOT, "mostamal.test.localhost", 9001, "qdml-mostamal-hawaa", False),
        ("mostamal-hawaa-admin", "Mostamal Hawaa Admin", ADMIN_ROOT, "mostamal-admin.test.localhost", 9002, "qdml-mostamal-hawaa-admin", True),
    ]
    for slug, name, root, subdomain, port, service_name, is_admin in projects:
        statements.extend(project_sql(slug, name, root, subdomain, port, service_name, is_admin))
        for idx, path in enumerate(collect_files(root), start=1):
            statements.extend(file_sql(slug, root, path, idx, "test.localhost", port))
    statements.append("COMMIT;")
    return "\n".join(statements)


def main() -> None:
    sql = build_sql()
    proc = subprocess.run(["psql", DATABASE_URL, "-v", "ON_ERROR_STOP=1"], input=sql, text=True)
    if proc.returncode:
        raise SystemExit(proc.returncode)
    print("ingested mostamal-hawaa and mostamal-hawaa-admin original source trees")


if __name__ == "__main__":
    main()
