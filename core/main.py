"""
QDML Platform — FastAPI Entry Point
All code lives in PostgreSQL. Files are compiled artifacts.
"""
import asyncpg
import os
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import DATABASE_URL, QDML_SCHEMA, POOL_MIN, POOL_MAX, HOST, PORT
from qdml_engine import QDMLEngine
from platform_pipeline import (
    component_parts,
    ensure_platform_schema,
    page_parts,
    render_page_preview_html,
    render_preview_html,
)
from routes import auth, qdml, compile, ai, kits, dashboard, deploy, platform


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=POOL_MIN,
        max_size=POOL_MAX,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    app.state.pool = pool
    app.state.engine = QDMLEngine(pool, schema=QDML_SCHEMA)
    await ensure_platform_schema(pool, QDML_SCHEMA)

    print(f"[QDML] Connected to PostgreSQL | schema={QDML_SCHEMA} | pool={POOL_MIN}-{POOL_MAX}")
    stats = await app.state.engine.stats()
    print(f"[QDML] {stats['projects']} projects | {stats['bulks']} bulks | {stats['total_lines']} lines | DB {stats['db_size_mb']}MB")

    yield

    await pool.close()
    print("[QDML] Pool closed")


app = FastAPI(
    title="QDML Platform",
    description="Code as Database Records — Microservices-Ready",
    version="3.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(qdml.router)
app.include_router(compile.router)
app.include_router(ai.router)
app.include_router(kits.router)
app.include_router(dashboard.router)
app.include_router(deploy.router)
app.include_router(platform.router)

generated_dir = Path(__file__).parent.parent / "mas-front" / "_generated"
if generated_dir.exists():
    app.mount("/lib", StaticFiles(directory=str(generated_dir)), name="lib")
    app.mount("/app", StaticFiles(directory=str(generated_dir), html=True), name="app")

core_dir = Path(__file__).parent
app.mount("/core-assets", StaticFiles(directory=str(core_dir)), name="core-assets")

kit_dir = generated_dir / "kits"
shared_dir = generated_dir / "shared"
if kit_dir.exists():
    app.mount("/kit-assets", StaticFiles(directory=str(kit_dir)), name="kit-assets")
if shared_dir.exists():
    app.mount("/store-assets", StaticFiles(directory=str(shared_dir)), name="store-assets")


HOST_PREVIEW_RE = re.compile(r"^(?P<subject>.+)--(?P<project>.+)\.(?:test\.localhost|ai-auto\.cloud)$")


@app.get("/health")
async def health():
    engine = app.state.engine
    try:
        stats = await engine.stats()
        return {"status": "ok", "engine": "qdml-v3", "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


@app.get("/api/info")
async def api_info():
    return {
        "service": "QDML Platform",
        "version": "3.0.0",
        "endpoints": {
            "auth": "/api/auth/login",
            "qdml": "/api/qdml",
            "compile": "/api/compile/{component}",
            "ai": "/api/ai",
            "kits": "/api/kits",
            "pipelines": "/api/kits/pipelines",
            "stats": "/api/qdml/stats",
            "mini": "/api/qdml/mini/{project}",
            "health": "/health",
            "admin": "/admin"
        }
    }


@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    host = (request.headers.get("host") or "").split(":")[0].lower()
    host_match = HOST_PREVIEW_RE.match(host)
    if host_match:
        project_slug = host_match.group("project")
        subject_slug = host_match.group("subject")
        page = await page_parts(app.state.pool, QDML_SCHEMA, project_slug, subject_slug)
        if page:
            return HTMLResponse(render_page_preview_html(project_slug, page["page"], page["bulks"]))
        parts = await component_parts(app.state.pool, QDML_SCHEMA, project_slug, subject_slug)
        if parts:
            return HTMLResponse(render_preview_html(project_slug, subject_slug, parts["parts"], parts["bulks"]))
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AI-First WF</title>
<script src="/core-assets/mas.core.v2.js"></script>
<style>
:root{--ink:#14151f;--muted:#5d6375;--line:#dfe3ec;--bg:#f6f7fb;--panel:#fff;--accent:#0f766e;--blue:#2563eb}
*{box-sizing:border-box}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,sans-serif;background:var(--bg);color:var(--ink)}
.page{min-height:100vh;display:flex;flex-direction:column}.top{height:58px;border-bottom:1px solid var(--line);background:rgba(255,255,255,.86);display:flex;align-items:center;justify-content:space-between;padding:0 clamp(18px,4vw,56px);position:sticky;top:0;backdrop-filter:blur(12px);z-index:3}
.brand{font-weight:800;letter-spacing:0}.nav{display:flex;gap:8px}.nav a{color:var(--muted);text-decoration:none;font-size:13px;padding:8px 10px;border-radius:6px}.nav a:hover{background:#eef2f7;color:var(--ink)}
.hero{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(320px,.95fr);gap:44px;align-items:center;padding:clamp(42px,7vw,88px) clamp(18px,4vw,56px) 34px}
.hero h1{font-size:clamp(42px,6vw,74px);line-height:.98;margin:0 0 18px;letter-spacing:0}.hero p{font-size:18px;line-height:1.65;color:var(--muted);max-width:680px;margin:0 0 24px}
.actions{display:flex;gap:10px;flex-wrap:wrap}.btn{border:1px solid var(--line);background:#fff;color:var(--ink);padding:11px 16px;border-radius:7px;font-weight:700;text-decoration:none;font-size:14px}.btn.primary{background:var(--accent);border-color:var(--accent);color:#fff}
.map{background:#101827;color:#e5eefc;border-radius:8px;padding:18px;border:1px solid #1e293b;box-shadow:0 18px 50px rgba(15,23,42,.16)}.map h2{font-size:13px;text-transform:uppercase;color:#93c5fd;margin:0 0 14px}.node{border:1px solid #334155;border-radius:7px;padding:10px;margin:8px 0;background:#172033}.node strong{display:block;font-size:14px}.node span{display:block;color:#9ca3af;font-size:12px;margin-top:3px}
.band{border-top:1px solid var(--line);padding:26px clamp(18px,4vw,56px) 48px;background:#fff}.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px}.card{border:1px solid var(--line);border-radius:8px;padding:16px;background:#fff}.card h3{font-size:15px;margin:0 0 8px}.card p{color:var(--muted);font-size:13px;line-height:1.55;margin:0}
@media(max-width:860px){.hero{grid-template-columns:1fr;padding-top:36px}.grid{grid-template-columns:1fr 1fr}.nav{display:none}}@media(max-width:560px){.grid{grid-template-columns:1fr}.hero h1{font-size:40px}}
</style>
</head>
<body><div id="app"></div>
<script>
const {D,app}=MAS;
const body=()=>D.div({class:'page'},[
  D.header({class:'top'},[D.div({class:'brand'},'AI-First WF'),D.nav({class:'nav'},[
    D.a({href:'/admin'},'Platform'),D.a({href:'/api/platform/projects'},'Projects'),D.a({href:'/api/info'},'API')
  ])]),
  D.main({class:'hero'},[
    D.section([D.h1('AI-First WF'),D.p('A protocol-native application factory where AI builds with a live project tree, QDML mutations, real preview links, service checks, and deployable runtime metadata instead of loose files.'),D.div({class:'actions'},[
      D.a({class:'btn primary',href:'/admin'},'Open Platform'),
      D.a({class:'btn',href:'/preview/mostamal-hawaa/mostamal-app'},'Preview Mostamal Hawaa'),
      D.a({class:'btn',href:'/api/platform/health/dependencies'},'Check Services')
    ])]),
    D.aside({class:'map'},[D.h2('Runtime Protocol'),['Project profile: domain, port, service, docs','Module tree: frontend, backend, data, infra','Component endpoints: preview, API, health','AI context: mini/full code with selection budget','Pipeline: compile, syntax check, nginx, service'].map(x=>D.div({class:'node'},[D.strong(x.split(':')[0]),D.span(x.split(':').slice(1).join(':').trim())]))])
  ]),
  D.section({class:'band'},D.div({class:'grid'},[
    ['QDML Source of Truth','Projects, modules, components, and bulks are stored as structured records.'],
    ['MAS Core V2 UI','The platform interface is rendered through the same frontend engine it asks AI to use.'],
    ['Real Links','Every screen and service can expose preview, health, full-code, and mini-code links.'],
    ['Day-0 Pipeline','Nginx, systemd, certbot, syntax checks, docs, and ports are treated as project metadata.']
  ].map(i=>D.article({class:'card'},[D.h3(i[0]),D.p(i[1])]))))
]);
app(body,{}).mount('#app');
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=os.getenv("QDML_RELOAD", "0") == "1")
