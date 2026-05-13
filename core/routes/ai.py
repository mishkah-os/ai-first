"""
AI Protocol Routes — Single entry point for AI-driven development
"""
import json
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/ai", tags=["AI Protocol"])


@router.post("/")
async def ai_execute(request: Request, body: dict):
    """
    Unified AI endpoint:
    - action: create | modify | delete | reveal | test | compile
    - target: project/module/component path
    - selector: {project, module, component, bulk}
    - prompt: natural language description
    - mini_code: reference code for context
    """
    engine = request.app.state.engine
    pool = request.app.state.pool
    schema = engine.schema

    action = body.get("action", "reveal")
    target = body.get("target", "")
    selector = body.get("selector", {})
    prompt = body.get("prompt", "")

    if action == "reveal":
        return await _reveal(engine, pool, schema, selector)
    elif action == "compile":
        return await _compile(engine, selector)
    elif action == "create":
        return await _create(engine, pool, schema, target, prompt, body.get("mini_code"))
    elif action == "modify":
        return await _modify(engine, pool, schema, selector, prompt, body.get("content"))
    elif action == "mini":
        project = selector.get("project") or target
        if not project:
            raise HTTPException(400, "project required")
        mini = await engine.mini(project, level=body.get("level", 1))
        return {"success": True, "mini_code": mini}
    elif action == "describe":
        project = selector.get("project") or target
        data = await engine.describe(project if project else None)
        return {"success": True, "data": data}
    else:
        raise HTTPException(400, f"Unknown action: {action}")


async def _reveal(engine, pool, schema, selector):
    """Reveal component with sliding window"""
    project = selector.get("project")
    component = selector.get("component")
    bulk = selector.get("bulk")
    level = selector.get("level", 3)

    if not component:
        # If no component, show project overview
        if project:
            mini = await engine.mini(project, level=1)
            return {"success": True, "type": "project_overview", "mini_code": mini}
        else:
            data = await engine.describe()
            return {"success": True, "type": "platform_overview", "data": data}

    # Reveal specific component or bulk
    data = await engine.reveal(component, bulk, level=level, project_slug=project)
    if data is None:
        raise HTTPException(404, f"Component '{component}' not found")

    return {"success": True, "type": "bulk" if bulk else "component", "data": data}


async def _compile(engine, selector):
    """Compile component to output"""
    component = selector.get("component")
    project = selector.get("project")

    if not component:
        raise HTTPException(400, "selector.component required")

    code = await engine.compile_component(component, project_slug=project)
    if code is None:
        raise HTTPException(404, f"Component '{component}' not found")

    return {
        "success": True,
        "code": code,
        "lines": code.count('\n') + 1,
        "chars": len(code)
    }


async def _create(engine, pool, schema, target, prompt, mini_code):
    """Create new component from AI specification — uses Bedrock if available"""
    parts = target.split("/") if target else []

    if len(parts) < 3:
        raise HTTPException(400, "target must be: project/module/component")

    project_slug, module_slug, component_slug = parts[0], parts[1], parts[2]

    # Check project exists
    project = await pool.fetchrow(f"SELECT id FROM {schema}.project WHERE slug=$1", project_slug)
    if not project:
        raise HTTPException(404, f"Project '{project_slug}' not found. Create it first.")

    # Check/create module
    module = await pool.fetchrow(f"""
        SELECT m.id FROM {schema}.module m
        JOIN {schema}.project p ON m.project_id = p.id
        WHERE p.slug=$1 AND m.slug=$2
    """, project_slug, module_slug)

    if not module:
        await engine.create_module(project_slug, module_slug.replace('-', ' ').title(), module_slug, tier="frontend", app=project_slug)

    # Check component doesn't exist
    existing = await pool.fetchrow(f"""
        SELECT c.id FROM {schema}.component c
        JOIN {schema}.module m ON c.module_id = m.id
        JOIN {schema}.project p ON m.project_id = p.id
        WHERE p.slug=$1 AND c.slug=$2
    """, project_slug, component_slug)

    if existing:
        raise HTTPException(409, f"Component '{component_slug}' already exists. Use action=modify instead.")

    # Create component
    await engine.create_component(module_slug, component_slug.replace('-', ' ').title(), component_slug,
                                  kind="screen", target="mas-js", project_slug=project_slug)

    # Generate code — use Bedrock AI if available, otherwise use mini_code/template
    from bedrock_client import get_bedrock_client
    bedrock = get_bedrock_client()
    ai_generated = False

    if bedrock.available and prompt:
        try:
            code = await bedrock.generate_component(
                description=prompt,
                kit_type="screen" if "screen" in component_slug else "service",
                reference_code=mini_code or ""
            )
            ai_generated = True
        except Exception as e:
            code = None

    if not ai_generated or not code:
        code = mini_code or f"""// {component_slug} — Generated from prompt
// Prompt: {prompt[:200]}

export default function {component_slug.replace('-', '_')}() {{
    return '<div class="{component_slug}">Component generated — modify with AI</div>';
}}
"""

    await engine.create_bulk(component_slug, "main", code, lang="javascript", project_slug=project_slug)

    return {
        "success": True,
        "created": f"{project_slug}/{module_slug}/{component_slug}",
        "ai_generated": ai_generated,
        "mini_code": code[:500],
        "next_actions": ["modify", "compile", "test"]
    }


async def _modify(engine, pool, schema, selector, prompt, content):
    """Modify existing component bulk — uses Bedrock if content not provided"""
    project = selector.get("project")
    component = selector.get("component")
    bulk = selector.get("bulk", "main")

    if not component:
        raise HTTPException(400, "selector.component required")

    # If no content provided, use AI to generate modification
    if not content and prompt:
        from bedrock_client import get_bedrock_client
        bedrock = get_bedrock_client()

        if bedrock.available:
            # Get current code
            current = await engine.reveal(component, bulk, level=3, project_slug=project)
            if current and isinstance(current, dict) and current.get("content"):
                try:
                    content = await bedrock.modify_component(current["content"], prompt)
                except Exception as e:
                    raise HTTPException(500, f"AI modification failed: {str(e)}")
            else:
                raise HTTPException(404, f"Bulk '{component}/{bulk}' not found")
        else:
            raise HTTPException(400, "content required (Bedrock not configured)")

    if not content:
        raise HTTPException(400, "content required")

    result = await engine.mutate_bulk(component, bulk, content, changed_by="ai", reason=prompt or "AI modification", project_slug=project)

    if not result.get("ok"):
        raise HTTPException(404, result.get("error", "Modification failed"))

    return {
        "success": True,
        "modified": f"{component}/{bulk}",
        "reason": prompt,
        "ai_modified": True,
        "next_actions": ["reveal", "compile", "test"]
    }


@router.get("/system-prompt")
async def get_system_prompt(request: Request):
    """Return the AI system prompt for tools integration"""
    engine = request.app.state.engine
    stats = await engine.stats()

    return {
        "system_prompt": f"""You are working with QDML Platform — a system where all code lives in PostgreSQL as structured records.

Current state: {stats['projects']} projects, {stats['components']} components, {stats['bulks']} bulks, {stats['total_lines']:,} lines.

Available actions via POST /api/ai:
- reveal: Show project structure or component code
- create: Create new component (target="project/module/component", prompt="description")
- modify: Change existing code (selector={{component,bulk}}, content="new code")
- compile: Generate output file from component bulks
- mini: Get compact project overview
- describe: Get full project tree

Available kits via /api/kits:
- mobile-kit: Header, Footer, SideMenu, Auth screens
- dashboard-kit: Sidebar layout, Widgets, DataTable
- offer-kit: Pricing pages, Feature tables

Pipelines via /api/kits/pipelines:
- build-mobile-app: Full app build pipeline
- customer-onboarding: Customer setup pipeline""",
        "stats": stats
    }
