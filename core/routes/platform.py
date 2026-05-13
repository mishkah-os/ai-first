"""
Platform protocol routes.

These endpoints expose project runtime metadata, preview links, component code
views, syntax checks, and AI context selection as first-class protocol objects.
"""
from __future__ import annotations

import json
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse

from platform_pipeline import (
    ai_auto_domain_pipeline,
    build_vibe_prompt_packet,
    code_modes,
    component_parts,
    dependency_health,
    discover_nginx_domains,
    ensure_project_test_protocol,
    execute_test_payload,
    list_project_tests,
    page_parts,
    project_protocol_tree,
    project_pages,
    project_tree,
    render_page_preview_html,
    render_preview_html,
    service_runtime_health,
    simulate_planner_run,
    strip_code_fence,
    syntax_report,
    upsert_project_profile,
)


router = APIRouter(tags=["AI-First Platform Protocol"])


def _json_row(row):
    data = dict(row)
    for key, value in list(data.items()):
        if hasattr(value, "isoformat"):
            data[key] = value.isoformat()
        elif key in {"plan", "payload", "meta", "curl_config", "assertions", "credentials", "result", "request", "tools", "selection", "prompt_packet", "input_refs"} and isinstance(value, str):
            try:
                data[key] = json.loads(value)
            except Exception:
                data[key] = value
        elif value is not None and not isinstance(value, (str, int, float, bool, list, dict)):
            data[key] = str(value)
    return data


async def build_context_packet(pool, schema: str, selections: list, mode: str = "mini", max_chars: int = 60000):
    packet = {"mode": mode, "max_chars": max_chars, "items": [], "excluded": [], "chars": 0}
    for item in selections:
        project = item.get("project")
        page = item.get("page")
        component = item.get("component")
        bulk = item.get("bulk")
        if not project:
            continue
        if page:
            page_data = await page_parts(pool, schema, project, page)
            if not page_data:
                packet["excluded"].append({"selector": item, "reason": "page_not_found"})
                continue
            text = code_modes(page_data["bulks"], "full" if mode == "full" else "mini")
            label = f"{project}:page:{page}"
        elif not component:
            tree = await project_tree(pool, schema, project)
            text = json.dumps(tree, ensure_ascii=False, indent=2)
            label = f"{project}:tree"
        else:
            parts = await component_parts(pool, schema, project, component)
            if not parts:
                packet["excluded"].append({"selector": item, "reason": "not_found"})
                continue
            selected_bulks = parts["bulks"]
            if bulk:
                selected_bulks = [b for b in selected_bulks if b["bulk_name"] == bulk]
            text = code_modes(selected_bulks, "full" if mode == "full" else "mini")
            label = f"{project}/{component}" + (f"/{bulk}" if bulk else "")
        if packet["chars"] + len(text) > max_chars:
            packet["excluded"].append({"selector": item, "reason": "context_budget", "chars": len(text)})
            continue
        packet["items"].append({"selector": item, "label": label, "content": text, "chars": len(text)})
        packet["chars"] += len(text)
    packet["ok"] = True
    return packet


@router.get("/api/platform/domains")
async def domains():
    return discover_nginx_domains()


@router.get("/api/platform/health/dependencies")
async def health_dependencies():
    checks = dependency_health()
    try:
        from bedrock_client import get_bedrock_client
        bedrock = await get_bedrock_client().health(live=False)
        bedrock["required"] = True
        checks.append(bedrock)
    except Exception as exc:
        checks.append({"name": "bedrock", "ok": False, "status": "error", "required": True, "error": str(exc)})
    return {"ok": all(c["ok"] or not c.get("required", True) for c in checks), "checks": checks}


@router.get("/api/platform/health/bedrock")
async def health_bedrock(live: bool = False):
    from bedrock_client import get_bedrock_client
    return await get_bedrock_client().health(live=live)


@router.get("/api/platform/projects")
async def list_projects(request: Request):
    schema = request.app.state.engine.schema
    return await project_tree(request.app.state.pool, schema)


@router.post("/api/platform/projects")
async def save_project_profile(request: Request, body: dict):
    schema = request.app.state.engine.schema
    project = await upsert_project_profile(request.app.state.pool, schema, body)
    return {"ok": True, "project": project}


@router.get("/api/platform/projects/{project_slug}/inventory")
async def project_inventory(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    tree = await project_tree(request.app.state.pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")
    return {"ok": True, "project": tree[0]}


@router.get("/api/platform/projects/{project_slug}/protocol-tree")
async def protocol_tree(request: Request, project_slug: str, q: str = ""):
    schema = request.app.state.engine.schema
    tree = await project_protocol_tree(request.app.state.pool, schema, project_slug, content_query=q)
    if not tree["projects"]:
        raise HTTPException(404, "Project not found")
    return tree


@router.get("/api/platform/projects/{project_slug}/runtime-health")
async def project_runtime_health(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    tree = await project_tree(request.app.state.pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")
    return {"ok": True, "health": service_runtime_health(tree[0])}


@router.get("/api/platform/projects/{project_slug}/pages")
async def list_project_pages(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    tree = await project_tree(request.app.state.pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")
    return {"ok": True, "project": project_slug, "pages": await project_pages(request.app.state.pool, schema, project_slug)}


@router.post("/api/platform/projects/{project_slug}/ensure-page-links")
async def ensure_page_links(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    tree = await project_tree(request.app.state.pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")
    pages = await project_pages(request.app.state.pool, schema, project_slug)
    return {"ok": True, "project": project_slug, "links": len(pages), "pages": pages}


@router.post("/api/platform/projects/{project_slug}/ensure-test-protocol")
async def ensure_test_protocol(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    result = await ensure_project_test_protocol(request.app.state.pool, schema, project_slug)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "project not found"))
    return result


@router.get("/api/platform/projects/{project_slug}/tests")
async def project_tests(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    result = await list_project_tests(request.app.state.pool, schema, project_slug)
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "project not found"))
    return result


@router.post("/api/platform/projects/{project_slug}/auth-scripts")
async def save_auth_script(request: Request, project_slug: str, body: dict):
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    project_id = await pool.fetchval(f"SELECT id FROM {schema}.project WHERE slug=$1", project_slug)
    if not project_id:
        raise HTTPException(404, "Project not found")
    slug = body.get("slug") or body.get("name") or "default"
    if not body.get("script"):
        raise HTTPException(400, "script required")
    row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.auth_script
            (project_id, name, slug, script_type, username, password_ref, credentials, script, is_default, meta)
        VALUES ($1,$2,$3,$4,$5,$6,$7::jsonb,$8,$9,$10::jsonb)
        ON CONFLICT (project_id, slug) DO UPDATE SET
            name=EXCLUDED.name,
            script_type=EXCLUDED.script_type,
            username=EXCLUDED.username,
            password_ref=EXCLUDED.password_ref,
            credentials=EXCLUDED.credentials,
            script=EXCLUDED.script,
            is_default=EXCLUDED.is_default,
            meta=EXCLUDED.meta,
            updated_at=now()
        RETURNING *
        """,
        project_id,
        body.get("name") or slug,
        slug,
        body.get("script_type") or "playwright",
        body.get("username") or "",
        body.get("password_ref") or "",
        json.dumps(body.get("credentials") or {}),
        body["script"],
        bool(body.get("is_default", False)),
        json.dumps(body.get("meta") or {}),
    )
    return {"ok": True, "auth_script": _json_row(row)}


@router.post("/api/platform/projects/{project_slug}/tests")
async def save_project_test(request: Request, project_slug: str, body: dict):
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    project_id = await pool.fetchval(f"SELECT id FROM {schema}.project WHERE slug=$1", project_slug)
    if not project_id:
        raise HTTPException(404, "Project not found")
    slug = body.get("slug") or body.get("name")
    if not slug:
        raise HTTPException(400, "slug required")
    row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.test_case
            (project_id, name, slug, runner_type, target_kind, target_slug, url, auth_script_id,
             script, curl_config, assertions, timeout_ms, enabled, meta)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10::jsonb,$11::jsonb,$12,$13,$14::jsonb)
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
            timeout_ms=EXCLUDED.timeout_ms,
            enabled=EXCLUDED.enabled,
            meta=EXCLUDED.meta,
            updated_at=now()
        RETURNING *
        """,
        project_id,
        body.get("name") or slug,
        slug,
        body.get("runner_type") or "playwright",
        body.get("target_kind") or "project",
        body.get("target_slug") or "",
        body.get("url") or "",
        body.get("auth_script_id"),
        body.get("script") or "",
        json.dumps(body.get("curl_config") or {}),
        json.dumps(body.get("assertions") or []),
        int(body.get("timeout_ms") or 30000),
        bool(body.get("enabled", True)),
        json.dumps(body.get("meta") or {}),
    )
    return {"ok": True, "test": _json_row(row)}


@router.post("/api/platform/tests/run")
async def run_test(request: Request, body: dict):
    schema = request.app.state.engine.schema
    result = await execute_test_payload(request.app.state.pool, schema, body)
    if not result.get("ok") and result.get("error") in {"project_required", "test_not_found"}:
        raise HTTPException(404, result.get("error"))
    return result


@router.post("/api/platform/projects/{project_slug}/ensure-preview-links")
async def ensure_preview_links(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    tree = await project_tree(pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")

    rows = await pool.fetch(
        f"""
        SELECT c.id, c.slug
        FROM {schema}.component c
        JOIN {schema}.module m ON c.module_id=m.id
        JOIN {schema}.project p ON m.project_id=p.id
        WHERE p.slug=$1
        """,
        project_slug,
    )
    for row in rows:
        url = f"/preview/{project_slug}/{row['slug']}"
        await pool.execute(
            f"""
            INSERT INTO {schema}.component_endpoint (component_id, endpoint_type, subdomain, path, url, is_primary, meta)
            VALUES ($1,'preview',$2,$3,$3,true,$4::jsonb)
            ON CONFLICT (component_id, endpoint_type, path) DO UPDATE SET
                subdomain=EXCLUDED.subdomain,
                url=EXCLUDED.url,
                is_primary=true,
                meta=EXCLUDED.meta,
                updated_at=now()
            """,
            row["id"],
            None,
            url,
            json.dumps({"route_protocol": "platform-preview-route", "project_subdomain_only": True}),
        )
    return {"ok": True, "project": project_slug, "links": len(rows)}


@router.get("/api/platform/projects/{project_slug}/components/{component_slug}/code")
async def component_code(request: Request, project_slug: str, component_slug: str, mode: str = "mini"):
    schema = request.app.state.engine.schema
    parts = await component_parts(request.app.state.pool, schema, project_slug, component_slug)
    if not parts:
        raise HTTPException(404, "Component not found")
    return {
        "ok": True,
        "project": project_slug,
        "component": component_slug,
        "mode": mode,
        "code": code_modes(parts["bulks"], "full" if mode == "full" else "mini"),
        "bulks": [
            {
                "name": b["bulk_name"],
                "lang": b["lang"],
                "lines": b["lines"],
                "chars": b["chars"],
                "exports": b["exports"],
                "depends": b["depends"],
            }
            for b in parts["bulks"]
        ],
    }


@router.post("/api/platform/projects/{project_slug}/components/{component_slug}/bulks/{bulk_name}")
async def update_component_bulk(request: Request, project_slug: str, component_slug: str, bulk_name: str, body: dict):
    schema = request.app.state.engine.schema
    content = body.get("content")
    if content is None:
        raise HTTPException(400, "content required")
    result = await request.app.state.engine.mutate_bulk(
        component_slug,
        bulk_name,
        content,
        changed_by=body.get("changed_by", "human"),
        reason=body.get("reason", "human edit"),
        project_slug=project_slug,
    )
    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "bulk not found"))
    return {"ok": True, "project": project_slug, "component": component_slug, "bulk": bulk_name}


@router.get("/api/platform/projects/{project_slug}/components/{component_slug}/bulks/{bulk_name}")
async def get_component_bulk(request: Request, project_slug: str, component_slug: str, bulk_name: str):
    schema = request.app.state.engine.schema
    row = await request.app.state.pool.fetchrow(
        f"""
        SELECT pi.bulk_name, pi.content, pi.lang, pi.lines, pi.chars, pi.exports,
               pi.depends, pi.reveal, pi.overflow, pi.line_start, pi.line_end,
               COALESCE(pi.classification,c.classification,'custom') AS classification
        FROM {schema}.pillar pi
        JOIN {schema}.component c ON c.id=pi.component_id
        JOIN {schema}.module m ON m.id=c.module_id
        JOIN {schema}.project p ON p.id=m.project_id
        WHERE p.slug=$1 AND c.slug=$2 AND pi.bulk_name=$3 AND pi.kind='bulk'
        """,
        project_slug,
        component_slug,
        bulk_name,
    )
    if not row:
        raise HTTPException(404, "bulk not found")
    data = _json_row(row)
    return {"ok": True, "project": project_slug, "component": component_slug, "bulk": bulk_name, "data": data}


@router.get("/api/platform/projects/{project_slug}/components/{component_slug}/bulks/{bulk_name}/meta")
async def get_component_bulk_meta(request: Request, project_slug: str, component_slug: str, bulk_name: str):
    schema = request.app.state.engine.schema
    row = await request.app.state.pool.fetchrow(
        f"""
        SELECT pi.id, p.slug AS project, c.slug AS component, pi.bulk_name AS bulk,
               pi.lang, pi.lines, pi.chars, pi.line_start, pi.line_end,
               COALESCE(pi.classification,c.classification,'custom') AS classification,
               pi.role, pi.node_path, pi.ai_md, pi.human_md_en, pi.human_md_ar,
               pi.description, pi.human_summary
        FROM {schema}.pillar pi
        JOIN {schema}.component c ON c.id=pi.component_id
        JOIN {schema}.module m ON m.id=c.module_id
        JOIN {schema}.project p ON p.id=m.project_id
        WHERE p.slug=$1 AND c.slug=$2 AND pi.bulk_name=$3 AND pi.kind='bulk'
        """,
        project_slug,
        component_slug,
        bulk_name,
    )
    if not row:
        raise HTTPException(404, "bulk not found")
    return {"ok": True, "meta": _json_row(row)}


@router.post("/api/platform/projects/{project_slug}/components/{component_slug}/bulks/{bulk_name}/meta")
async def update_component_bulk_meta(request: Request, project_slug: str, component_slug: str, bulk_name: str, body: dict):
    schema = request.app.state.engine.schema
    row = await request.app.state.pool.fetchrow(
        f"""
        UPDATE {schema}.pillar pi
        SET classification=COALESCE(NULLIF($4,''), pi.classification),
            role=COALESCE(NULLIF($5,''), pi.role),
            ai_md=COALESCE($6, pi.ai_md),
            human_md_en=COALESCE($7, pi.human_md_en),
            human_md_ar=COALESCE($8, pi.human_md_ar),
            description=COALESCE($9, pi.description),
            human_summary=COALESCE($10, pi.human_summary),
            updated_at=now()
        FROM {schema}.component c
        JOIN {schema}.module m ON m.id=c.module_id
        JOIN {schema}.project p ON p.id=m.project_id
        WHERE pi.component_id=c.id
          AND p.slug=$1 AND c.slug=$2 AND pi.bulk_name=$3 AND pi.kind='bulk'
        RETURNING pi.*
        """,
        project_slug,
        component_slug,
        bulk_name,
        body.get("classification"),
        body.get("role"),
        body.get("ai_md"),
        body.get("human_md_en"),
        body.get("human_md_ar"),
        body.get("description"),
        body.get("human_summary"),
    )
    if not row:
        raise HTTPException(404, "bulk not found")
    return {"ok": True, "bulk": _json_row(row)}


@router.get("/preview/{project_slug}/{component_slug}", response_class=HTMLResponse)
async def preview_component(request: Request, project_slug: str, component_slug: str):
    schema = request.app.state.engine.schema
    parts = await component_parts(request.app.state.pool, schema, project_slug, component_slug)
    if not parts:
        page = await page_parts(request.app.state.pool, schema, project_slug, component_slug)
        if not page:
            raise HTTPException(404, "Component or page not found")
        return HTMLResponse(render_page_preview_html(project_slug, page["page"], page["bulks"]))
    return HTMLResponse(render_preview_html(project_slug, component_slug, parts["parts"], parts["bulks"]))


@router.get("/page/{project_slug}/{page_slug}", response_class=HTMLResponse)
async def preview_page(request: Request, project_slug: str, page_slug: str):
    schema = request.app.state.engine.schema
    page = await page_parts(request.app.state.pool, schema, project_slug, page_slug)
    if not page:
        raise HTTPException(404, "Page not found")
    return HTMLResponse(render_page_preview_html(project_slug, page["page"], page["bulks"]))


@router.post("/api/platform/domain-pipeline")
async def run_domain_pipeline(body: dict):
    result = ai_auto_domain_pipeline(body)
    if not result.get("ok"):
        return result
    return result


@router.post("/api/platform/projects/{project_slug}/domain-pipeline")
async def run_project_domain_pipeline(request: Request, project_slug: str, body: dict):
    schema = request.app.state.engine.schema
    tree = await project_tree(request.app.state.pool, schema, project_slug)
    if not tree:
        raise HTTPException(404, "Project not found")
    project = tree[0]
    full_domain = body.get("full_domain") or project.get("subdomain")
    port = body.get("listen_port") or project.get("port")
    if not full_domain or not port:
        raise HTTPException(400, "full_domain and listen_port are required")
    payload = {
        **body,
        "full_domain": full_domain,
        "listen_port": int(port),
        "service_name": body.get("service_name") or project.get("service_name") or f"qdml-{project_slug}",
        "dry_run": bool(body.get("dry_run", True)),
    }
    return ai_auto_domain_pipeline(payload)


@router.post("/api/platform/context")
async def selected_context(request: Request, body: dict):
    """Build an AI context packet from multi-select projects/components/bulks."""
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    max_chars = int(body.get("max_chars") or 60000)
    mode = body.get("mode") or "mini"
    selections = body.get("selection") or []
    if not isinstance(selections, list):
        raise HTTPException(400, "selection must be a list")

    return await build_context_packet(pool, schema, selections, mode=mode, max_chars=max_chars)


@router.post("/api/platform/prompt-packet")
async def prompt_packet(request: Request, body: dict):
    schema = request.app.state.engine.schema
    return await build_vibe_prompt_packet(request.app.state.pool, schema, body)


@router.post("/api/platform/planner/simulate")
async def planner_simulate(request: Request, body: dict):
    schema = request.app.state.engine.schema
    return await simulate_planner_run(request.app.state.pool, schema, body)


@router.get("/api/platform/agents")
async def list_agents(request: Request):
    schema = request.app.state.engine.schema
    rows = await request.app.state.pool.fetch(f"SELECT * FROM {schema}.agent_profile ORDER BY agent_role, slug")
    return {"ok": True, "agents": [_json_row(row) for row in rows]}


@router.get("/api/platform/instructions")
async def list_instructions(request: Request):
    schema = request.app.state.engine.schema
    rows = await request.app.state.pool.fetch(f"SELECT * FROM {schema}.classification_instruction ORDER BY classification, code_kind")
    return {"ok": True, "instructions": [_json_row(row) for row in rows]}


@router.post("/api/platform/instructions")
async def save_instruction(request: Request, body: dict):
    schema = request.app.state.engine.schema
    instruction_id = body.get("id")
    classification = body.get("classification") or "custom"
    code_kind = body.get("code_kind") or "code"
    if instruction_id:
      row = await request.app.state.pool.fetchrow(
          f"""
          UPDATE {schema}.classification_instruction
          SET classification=$2,
              code_kind=$3,
              agent_slug=NULLIF($4,''),
              ai_md=$5,
              human_md_en=$6,
              human_md_ar=$7,
              schema_md=$8,
              meta=COALESCE($9::jsonb, meta),
              updated_at=now()
          WHERE id=$1
          RETURNING *
          """,
          instruction_id,
          classification,
          code_kind,
          body.get("agent_slug") or "",
          body.get("ai_md") or "",
          body.get("human_md_en") or "",
          body.get("human_md_ar") or "",
          body.get("schema_md") or "",
          json.dumps(body.get("meta")) if body.get("meta") is not None else None,
      )
    else:
      row = await request.app.state.pool.fetchrow(
          f"""
          INSERT INTO {schema}.classification_instruction
              (classification, code_kind, agent_slug, ai_md, human_md_en, human_md_ar, schema_md, meta)
          VALUES ($1,$2,NULLIF($3,''),$4,$5,$6,$7,$8::jsonb)
          ON CONFLICT (classification, code_kind) DO UPDATE SET
              agent_slug=EXCLUDED.agent_slug,
              ai_md=EXCLUDED.ai_md,
              human_md_en=EXCLUDED.human_md_en,
              human_md_ar=EXCLUDED.human_md_ar,
              schema_md=EXCLUDED.schema_md,
              meta=EXCLUDED.meta,
              updated_at=now()
          RETURNING *
          """,
          classification,
          code_kind,
          body.get("agent_slug") or "",
          body.get("ai_md") or "",
          body.get("human_md_en") or "",
          body.get("human_md_ar") or "",
          body.get("schema_md") or "",
          json.dumps(body.get("meta") or {}),
      )
    if not row:
        raise HTTPException(404, "instruction not found")
    return {"ok": True, "instruction": _json_row(row)}


@router.get("/api/platform/tasks")
async def list_tasks(request: Request, project: str | None = None, status: str | None = None, limit: int = 50):
    schema = request.app.state.engine.schema
    args = []
    where = ["COALESCE(t.archived,false)=false"]
    if project:
        args.append(project)
        where.append(f"p.slug=${len(args)}")
    if status:
        args.append(status)
        where.append(f"t.status=${len(args)}")
    args.append(max(1, min(int(limit or 50), 200)))
    rows = await request.app.state.pool.fetch(
        f"""
        SELECT t.*, p.slug AS project_slug, p.name AS project_name
        FROM {schema}.tasks t
        LEFT JOIN {schema}.project p ON p.id=t.project_id
        WHERE {' AND '.join(where)}
        ORDER BY t.created_at DESC
        LIMIT ${len(args)}
        """,
        *args,
    )
    return {"ok": True, "tasks": [_json_row(r) for r in rows]}


@router.post("/api/platform/tasks")
async def create_task(request: Request, body: dict):
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    project_slug = body.get("project") or body.get("project_slug")
    if not project_slug:
        raise HTTPException(400, "project required")
    project_id = await pool.fetchval(f"SELECT id FROM {schema}.project WHERE slug=$1", project_slug)
    if not project_id:
        raise HTTPException(404, "project not found")
    selections = body.get("selection") or [{"project": project_slug}]
    if not isinstance(selections, list):
        raise HTTPException(400, "selection must be a list")
    mode = body.get("mode") or "mini"
    max_chars = int(body.get("max_chars") or 60000)
    context = await build_context_packet(pool, schema, selections, mode=mode, max_chars=max_chars)
    plan = body.get("plan") or {
        "selection": selections,
        "context_mode": mode,
        "max_chars": max_chars,
        "included": [{"label": i["label"], "chars": i["chars"]} for i in context["items"]],
        "excluded": context["excluded"],
        "protocol": {
            "attention": "selected_components_only",
            "noise_policy": "exclude_unselected_and_context_budget_overflow",
            "next_ai_request_should_read": "tree first, then selected mini/full bulks only",
        },
    }
    row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.tasks
          (project_id, title, task_type, classification, target_component, status, user_prompt, plan, created_by)
        VALUES ($1,$2,$3,$4,$5,'pending',$6,$7::jsonb,$8)
        RETURNING *
        """,
        project_id,
        body.get("title") or body.get("prompt", "AI task")[:90],
        body.get("task_type") if body.get("task_type") in {"create", "update", "structure", "plan"} else "plan",
        body.get("classification") or "planner",
        body.get("target_component") or "",
        body.get("prompt") or "",
        json.dumps(plan, ensure_ascii=False),
        body.get("created_by") or "user",
    )
    await pool.execute(
        f"INSERT INTO {schema}.task_events (task_id,event_type,payload) VALUES ($1,'created',$2::jsonb)",
        row["id"],
        json.dumps({"project": project_slug, "context_chars": context["chars"], "selection_count": len(selections)}, ensure_ascii=False),
    )
    return {"ok": True, "task": _json_row(row), "context": context}


@router.get("/api/platform/tasks/{task_id}/events")
async def list_task_events(request: Request, task_id: str):
    schema = request.app.state.engine.schema
    rows = await request.app.state.pool.fetch(
        f"SELECT * FROM {schema}.task_events WHERE task_id=$1 ORDER BY created_at",
        task_id,
    )
    return {"ok": True, "events": [_json_row(r) for r in rows]}


@router.post("/api/platform/tasks/{task_id}/events")
async def add_task_event(request: Request, task_id: str, body: dict):
    schema = request.app.state.engine.schema
    row = await request.app.state.pool.fetchrow(
        f"""
        INSERT INTO {schema}.task_events (task_id,event_type,payload)
        VALUES ($1,$2,$3::jsonb)
        RETURNING *
        """,
        task_id,
        body.get("event_type") or "note",
        json.dumps(body.get("payload") or {}, ensure_ascii=False),
    )
    return {"ok": True, "event": _json_row(row)}


@router.post("/api/platform/tasks/{task_id}/agents")
async def create_agent_execution(request: Request, task_id: str, body: dict):
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    agent_role = body.get("agent_role") if body.get("agent_role") in {"planner", "creator", "updater", "reviewer"} else "planner"
    status = body.get("status") if body.get("status") in {"running", "completed", "failed"} else "running"
    row = await pool.fetchrow(
        f"""
        INSERT INTO {schema}.agent_executions
          (task_id, agent_role, classification, target_component, status, system_prompt_used,
           user_message, ai_response, tokens_used, duration_ms, error)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
        RETURNING *
        """,
        task_id,
        agent_role,
        body.get("classification") or "",
        body.get("target_component") or "",
        status,
        body.get("system_prompt_used") or "",
        body.get("user_message") or "",
        body.get("ai_response") or "",
        int(body.get("tokens_used") or 0),
        int(body.get("duration_ms") or 0),
        body.get("error") or "",
    )
    await pool.execute(
        f"INSERT INTO {schema}.task_events (task_id,agent_execution_id,event_type,payload) VALUES ($1,$2,'agent_execution',$3::jsonb)",
        task_id,
        row["id"],
        json.dumps({"agent_role": row["agent_role"], "status": row["status"]}, ensure_ascii=False),
    )
    return {"ok": True, "agent_execution": _json_row(row)}


@router.post("/api/platform/syntax/{project_slug}")
async def syntax_check_project(request: Request, project_slug: str):
    schema = request.app.state.engine.schema
    return await syntax_report(request.app.state.pool, schema, project_slug)


@router.post("/api/platform/normalize/{project_slug}")
async def normalize_project_code(request: Request, project_slug: str):
    """Strip markdown code fences from persisted bulks for a project."""
    schema = request.app.state.engine.schema
    pool = request.app.state.pool
    rows = await pool.fetch(
        f"""
        SELECT pi.id, pi.content
        FROM {schema}.pillar pi
        JOIN {schema}.component c ON pi.component_id=c.id
        JOIN {schema}.module m ON c.module_id=m.id
        JOIN {schema}.project p ON m.project_id=p.id
        WHERE p.slug=$1 AND pi.content LIKE '%```%'
        """,
        project_slug,
    )
    changed = 0
    for row in rows:
        normalized = strip_code_fence(row["content"])
        if normalized != row["content"]:
            await pool.execute(f"UPDATE {schema}.pillar SET content=$1, updated_at=now() WHERE id=$2", normalized, row["id"])
            changed += 1
    return {"ok": True, "project": project_slug, "normalized": changed}
