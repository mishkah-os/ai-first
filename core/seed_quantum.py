"""
Seed AI-Auto Quantum Engine into PostgreSQL via QDML.
Registers postgres.js, schema-registry.js, server.js as atomic bulks.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DATABASE_URL, QDML_SCHEMA
import asyncpg
from qdml_engine import QDMLEngine

QUANTUM_DIR = "/srv/apps/ai-auto/quantum"

POSTGRES_BULKS = [
    {"name": "imports_config",       "start": 1,   "end": 50,  "exports": "pg", "depends": ""},
    {"name": "pool_management",      "start": 51,  "end": 120, "exports": "getPool,query", "depends": "imports_config"},
    {"name": "type_coercion",        "start": 121, "end": 200, "exports": "coerceValue,isNumericRoutineType", "depends": ""},
    {"name": "routine_introspection","start": 201, "end": 330, "exports": "getRoutineSignature,introspectRoutine", "depends": "pool_management", "overflow": True},
    {"name": "routine_execution",    "start": 331, "end": 470, "exports": "executeRoutine,executeProcedure", "depends": "routine_introspection", "overflow": True},
    {"name": "read_operations",      "start": 471, "end": 620, "exports": "readObject,buildWhereClause", "depends": "pool_management", "overflow": True},
    {"name": "save_operations",      "start": 621, "end": 800, "exports": "saveObjects,buildRecordsetDefinition", "depends": "pool_management", "overflow": True},
    {"name": "delete_operations",    "start": 801, "end": 900, "exports": "deleteObject", "depends": "pool_management", "overflow": True},
    {"name": "document_service",     "start": 901, "end": 1050, "exports": "documentRead,documentSave,documentDelete", "depends": "read_operations,save_operations", "overflow": True},
    {"name": "platform_service",     "start": 1051, "end": 1163, "exports": "createPostgresRuntime", "depends": "document_service", "overflow": True},
]

SCHEMA_REGISTRY_BULKS = [
    {"name": "imports_setup",        "start": 1,   "end": 40,  "exports": "", "depends": ""},
    {"name": "normalization",        "start": 41,  "end": 130, "exports": "normalizeObject,toLegacyDataType,toPostgresSqlType", "depends": "imports_setup"},
    {"name": "registry_core",        "start": 131, "end": 200, "exports": "getObject,listObjects,createRegistry", "depends": "normalization"},
    {"name": "contract_validation",  "start": 201, "end": 256, "exports": "validateContract,getFingerprint", "depends": "registry_core"},
]

SERVER_BULKS = [
    {"name": "imports_config",       "start": 1,   "end": 80,  "exports": "", "depends": ""},
    {"name": "middleware",           "start": 81,  "end": 180, "exports": "authMiddleware,corsMiddleware,jsonBody", "depends": "imports_config", "overflow": True},
    {"name": "api_v7_handler",       "start": 181, "end": 370, "exports": "handleApiV7", "depends": "middleware", "overflow": True},
    {"name": "invoice_handler",      "start": 371, "end": 550, "exports": "handleInvoice", "depends": "middleware", "overflow": True},
    {"name": "erp_handlers",         "start": 551, "end": 750, "exports": "handleNewCode,handleUploadImage", "depends": "middleware", "overflow": True},
    {"name": "platform_routes",      "start": 751, "end": 950, "exports": "handlePlatformRoutes", "depends": "erp_handlers", "overflow": True},
    {"name": "server_start",         "start": 951, "end": 1193, "exports": "startServer", "depends": "platform_routes", "overflow": True},
]


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def extract(lines, start, end):
    actual_end = min(end, len(lines))
    return "".join(lines[start-1:actual_end])


async def main():
    print("=" * 60)
    print("QDML SEED — AI-Auto Quantum Engine")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ MODULE: quantum ═══
    print("\n[1/5] Creating quantum module...")
    await engine.create_module("platform-core", "Quantum Engine", "quantum", tier="backend", app="quantum")

    # ═══ COMPONENTS ═══
    print("[2/5] Creating components...")
    await engine.create_component("quantum", "PostgreSQL Runtime", "pg-runtime", kind="service", target="node", project_slug="platform-core")
    await engine.create_component("quantum", "Schema Registry", "schema-registry", kind="library", target="node", project_slug="platform-core")
    await engine.create_component("quantum", "HTTP Server", "quantum-server", kind="service", target="node", project_slug="platform-core")

    # ═══ POSTGRES BULKS ═══
    print("[3/5] Registering postgres.js (10 bulks)...")
    pg_lines = read_lines(os.path.join(QUANTUM_DIR, "postgres.js"))
    for i, bk in enumerate(POSTGRES_BULKS):
        content = extract(pg_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "pg-runtime", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       10 bulks from {len(pg_lines)} lines")

    # ═══ SCHEMA-REGISTRY BULKS ═══
    print("[4/5] Registering schema-registry.js (4 bulks)...")
    sr_lines = read_lines(os.path.join(QUANTUM_DIR, "schema-registry.js"))
    for i, bk in enumerate(SCHEMA_REGISTRY_BULKS):
        content = extract(sr_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "schema-registry", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       4 bulks from {len(sr_lines)} lines")

    # ═══ SERVER BULKS ═══
    print("[5/5] Registering server.js (7 bulks)...")
    sv_lines = read_lines(os.path.join(QUANTUM_DIR, "server.js"))
    for i, bk in enumerate(SERVER_BULKS):
        content = extract(sv_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "quantum-server", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       7 bulks from {len(sv_lines)} lines")

    # ═══ COMPILE TEST ═══
    print("\n--- Compile Test ---")
    pg_code = await engine.compile_component("pg-runtime", project_slug="platform-core")
    sr_code = await engine.compile_component("schema-registry", project_slug="platform-core")
    sv_code = await engine.compile_component("quantum-server", project_slug="platform-core")
    print(f"  postgres.js:        {pg_code.count(chr(10))+1} lines")
    print(f"  schema-registry.js: {sr_code.count(chr(10))+1} lines")
    print(f"  server.js:          {sv_code.count(chr(10))+1} lines")

    # ═══ STATS ═══
    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"PLATFORM: {stats['projects']} projects | {stats['modules']} modules | {stats['components']} components | {stats['bulks']} bulks | {stats['total_lines']} lines")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
