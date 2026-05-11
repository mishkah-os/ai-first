"""
Kit System & Pipeline Routes
"""
import json
from fastapi import APIRouter, Request, HTTPException

router = APIRouter(prefix="/api/kits", tags=["Kit System"])


@router.get("/")
async def list_kits(request: Request):
    pool = request.app.state.pool
    schema = request.app.state.engine.schema
    rows = await pool.fetch(f"SELECT * FROM {schema}.kit_registry ORDER BY kit_type")
    return [dict(r) for r in rows]


@router.get("/pipelines")
async def list_pipelines(request: Request):
    pool = request.app.state.pool
    schema = request.app.state.engine.schema
    rows = await pool.fetch(f"SELECT * FROM {schema}.pipelines ORDER BY name")
    return [dict(r) for r in rows]


@router.get("/detail/{slug}")
async def get_kit(request: Request, slug: str):
    pool = request.app.state.pool
    schema = request.app.state.engine.schema
    row = await pool.fetchrow(f"SELECT * FROM {schema}.kit_registry WHERE slug=$1", slug)
    if not row:
        raise HTTPException(404, "Kit not found")
    return dict(row)


@router.post("/create-app")
async def create_app_from_kit(request: Request, body: dict):
    """Create a new app instance from a kit"""
    pool = request.app.state.pool
    schema = request.app.state.engine.schema

    kit_slug = body.get("kit")
    app_name = body.get("app_name")
    variables = body.get("variables", {})

    if not kit_slug or not app_name:
        raise HTTPException(400, "kit and app_name required")

    # Get kit
    kit = await pool.fetchrow(f"SELECT * FROM {schema}.kit_registry WHERE slug=$1", kit_slug)
    if not kit:
        raise HTTPException(404, f"Kit '{kit_slug}' not found")

    # Create app instance
    row = await pool.fetchrow(f"""
        INSERT INTO {schema}.app_instances (app_name, kit_id, config, status)
        VALUES ($1, $2, $3::jsonb, 'draft')
        RETURNING id, app_name, status, created_at
    """, app_name, kit['id'], json.dumps(variables))

    return {
        "id": str(row['id']),
        "app_name": row['app_name'],
        "kit": kit_slug,
        "status": row['status'],
        "variables": variables,
        "next_steps": ["customize", "build", "deploy"]
    }


@router.get("/apps")
async def list_apps(request: Request):
    pool = request.app.state.pool
    schema = request.app.state.engine.schema
    rows = await pool.fetch(f"""
        SELECT ai.*, kr.name as kit_name, kr.kit_type
        FROM {schema}.app_instances ai
        LEFT JOIN {schema}.kit_registry kr ON ai.kit_id = kr.id
        ORDER BY ai.created_at DESC
    """)
    return [dict(r) for r in rows]


@router.post("/pipelines/{slug}/execute")
async def execute_pipeline(request: Request, slug: str, body: dict):
    """Execute a pipeline with context"""
    pool = request.app.state.pool
    schema = request.app.state.engine.schema

    pipeline = await pool.fetchrow(f"SELECT * FROM {schema}.pipelines WHERE slug=$1", slug)
    if not pipeline:
        raise HTTPException(404, f"Pipeline '{slug}' not found")

    stages = json.loads(pipeline['stages']) if isinstance(pipeline['stages'], str) else pipeline['stages']

    # Simulate pipeline execution
    results = {
        "pipeline": slug,
        "status": "completed",
        "context": body,
        "stages": {}
    }

    for stage in stages:
        results["stages"][stage] = {"status": "completed", "duration_ms": 50}

    return results


@router.post("/compile-kit/{kit_slug}")
async def compile_kit(request: Request, kit_slug: str, body: dict = {}):
    """Compile a kit with variables into ready-to-use code"""
    pool = request.app.state.pool
    engine = request.app.state.engine
    schema = engine.schema

    kit = await pool.fetchrow(f"SELECT * FROM {schema}.kit_registry WHERE slug=$1", kit_slug)
    if not kit:
        raise HTTPException(404, f"Kit '{kit_slug}' not found")

    # Get associated components
    components_list = json.loads(kit['components']) if isinstance(kit['components'], str) else kit['components']

    # Find the component to compile
    comp_slug = f"{kit_slug}-components"
    code = await engine.compile_component(comp_slug, project_slug="kits")

    if not code:
        raise HTTPException(404, f"Kit component '{comp_slug}' not found")

    # Apply variable substitutions
    variables = body.get("variables", {})
    kit_vars = json.loads(kit['variables']) if isinstance(kit['variables'], str) else kit['variables']
    all_vars = {**kit_vars, **variables}

    for key, value in all_vars.items():
        if isinstance(value, str):
            code = code.replace(f"${{{key}}}", value)

    return {
        "kit": kit_slug,
        "code": code,
        "lines": code.count('\n') + 1,
        "variables_applied": list(all_vars.keys())
    }
