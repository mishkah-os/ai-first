"""
QDML Platform — FastAPI Entry Point
All code lives in PostgreSQL. Files are compiled artifacts.
"""
import asyncpg
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from config import DATABASE_URL, QDML_SCHEMA, POOL_MIN, POOL_MAX, HOST, PORT
from qdml_engine import QDMLEngine
from routes import auth, qdml, compile


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

generated_dir = Path(__file__).parent.parent / "mas-front" / "_generated"
if generated_dir.exists():
    app.mount("/lib", StaticFiles(directory=str(generated_dir)), name="lib")
    app.mount("/app", StaticFiles(directory=str(generated_dir), html=True), name="app")


@app.get("/health")
async def health():
    engine = app.state.engine
    try:
        stats = await engine.stats()
        return {"status": "ok", "engine": "qdml-v3", "stats": stats}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/")
async def root():
    return {
        "service": "QDML Platform",
        "version": "3.0.0",
        "endpoints": {
            "auth": "/api/auth/login",
            "qdml": "/api/qdml",
            "compile": "/api/compile/{component}",
            "stats": "/api/qdml/stats",
            "mini": "/api/qdml/mini/{project}",
            "health": "/health",
            "admin": "/admin"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=HOST, port=PORT, reload=True)
