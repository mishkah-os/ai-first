"""
Seed OS WebSocket Kernel into PostgreSQL via QDML.
Registers ws-clients, pubsub, and sync-manager as atomic bulks.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DATABASE_URL, QDML_SCHEMA
import asyncpg
from qdml_engine import QDMLEngine

OS_RUNTIME = "/srv/apps/os/src/runtime"

# ════════════════════════════════════════════════════════
# BULK DEFINITIONS — atomic splits of each OS file
# ════════════════════════════════════════════════════════

WS_CLIENTS_BULKS = [
    {"name": "imports_utils",          "start": 1,   "end": 39,  "exports": "parseRecordTimestamp,resolveLiveSince", "depends": ""},
    {"name": "live_data_window",       "start": 41,  "end": 94,  "exports": "applyLiveDataWindowToSnapshot", "depends": "imports_utils"},
    {"name": "manager_setup",          "start": 96,  "end": 132, "exports": "", "depends": "live_data_window"},
    {"name": "message_sending",        "start": 134, "end": 185, "exports": "sendToClient,broadcastToBranch,emitFullSyncDirective", "depends": "manager_setup"},
    {"name": "send_snapshot",          "start": 187, "end": 216, "exports": "sendSnapshot", "depends": "message_sending"},
    {"name": "hello_handler",          "start": 218, "end": 312, "exports": "handleHello,sendServerLog", "depends": "send_snapshot"},
    {"name": "message_router",         "start": 314, "end": 442, "exports": "handleMessage", "depends": "hello_handler", "overflow": True},
    {"name": "exports",                "start": 444, "end": 467, "exports": "createWsClientManager", "depends": "message_router"},
]

PUBSUB_BULKS = [
    {"name": "config_init",            "start": 1,   "end": 54,  "exports": "PUBSUB_TYPES", "depends": ""},
    {"name": "manager_setup",          "start": 55,  "end": 97,  "exports": "", "depends": "config_init"},
    {"name": "payload_optimization",   "start": 99,  "end": 145, "exports": "buildSlimSnapshotFromFrame", "depends": "manager_setup"},
    {"name": "transaction_tables",     "start": 147, "end": 210, "exports": "resolveTransactionTableName,normalizeTransactionTableList", "depends": "config_init"},
    {"name": "envelope_building",      "start": 212, "end": 269, "exports": "deepEqual,buildSnapshotEnvelope,buildDeltaEnvelope", "depends": ""},
    {"name": "sync_publish",           "start": 271, "end": 333, "exports": "buildSyncPublishData,loadTopicBootstrap", "depends": "envelope_building"},
    {"name": "topic_management",       "start": 335, "end": 402, "exports": "ensurePubsubTopic,registerPubsubSubscriber,unregisterPubsubSubscriptions,broadcastPubsub", "depends": "sync_publish"},
    {"name": "frame_detection",        "start": 404, "end": 461, "exports": "isPubsubFrame,getTableNoticeTopics,resolveBranchTopicsFromFrame", "depends": "topic_management"},
    {"name": "branch_broadcasting",    "start": 463, "end": 579, "exports": "buildBranchDeltaDetail,broadcastBranchTopics,getAllTableNames,broadcastTableNotice,broadcastSyncUpdate", "depends": "frame_detection", "overflow": True},
    {"name": "frame_handler_auth",     "start": 581, "end": 701, "exports": "", "depends": "branch_broadcasting", "overflow": True},
    {"name": "frame_handler_publish",  "start": 702, "end": 804, "exports": "", "depends": "frame_handler_auth", "overflow": True},
    {"name": "manager_exports",        "start": 806, "end": 846, "exports": "createPubsubManager", "depends": "frame_handler_publish"},
]

SYNC_MANAGER_BULKS = [
    {"name": "setup_constants",        "start": 1,   "end": 29,  "exports": "", "depends": ""},
    {"name": "snapshot_normalize",     "start": 31,  "end": 94,  "exports": "normalizeIncomingSnapshot,posSnapshotNormalizer", "depends": "setup_constants"},
    {"name": "insert_only_validate",   "start": 96,  "end": 220, "exports": "ensureInsertOnlySnapshot", "depends": "snapshot_normalize", "overflow": True},
    {"name": "apply_sync",             "start": 222, "end": 290, "exports": "applySyncSnapshot,ensureSyncState", "depends": "insert_only_validate"},
    {"name": "state_exports",          "start": 292, "end": 311, "exports": "createSyncManager,invalidateSyncState,getSyncStates", "depends": "apply_sync"},
]


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def extract(lines, start, end):
    return "".join(lines[start-1:end])


async def main():
    print("=" * 60)
    print("QDML SEED — OS WebSocket Kernel")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ Check if platform-core project exists ═══
    existing = await engine._fetch_one(f"SELECT id FROM {QDML_SCHEMA}.project WHERE slug='platform-core'")
    if not existing:
        print("\n[1/6] Creating platform-core project...")
        await engine.create_project("Platform Core", "platform-core", "OS + Quantum + Shared infrastructure")
    else:
        print("\n[1/6] platform-core project exists")

    # ═══ MODULE: ws-relay ═══
    print("[2/6] Creating ws-relay module...")
    await engine.create_module("platform-core", "WS Relay", "ws-relay", tier="backend", app="ws-relay")

    # ═══ COMPONENTS ═══
    print("[3/6] Creating components...")
    await engine.create_component("ws-relay", "WebSocket Client Manager", "ws-clients", kind="service", target="node", project_slug="platform-core")
    await engine.create_component("ws-relay", "PubSub Manager", "pubsub", kind="service", target="node", project_slug="platform-core")
    await engine.create_component("ws-relay", "Sync Manager", "sync-manager", kind="service", target="node", project_slug="platform-core")

    # ═══ WS-CLIENTS BULKS ═══
    print("[4/6] Registering ws-clients.js (8 bulks)...")
    ws_lines = read_lines(os.path.join(OS_RUNTIME, "ws-clients.js"))
    for i, bk in enumerate(WS_CLIENTS_BULKS):
        content = extract(ws_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "ws-clients", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       8 bulks from {len(ws_lines)} lines")

    # ═══ PUBSUB BULKS ═══
    print("[5/6] Registering pubsub.js (12 bulks)...")
    ps_lines = read_lines(os.path.join(OS_RUNTIME, "pubsub.js"))
    for i, bk in enumerate(PUBSUB_BULKS):
        content = extract(ps_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "pubsub", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       12 bulks from {len(ps_lines)} lines")

    # ═══ SYNC-MANAGER BULKS ═══
    print("[6/6] Registering sync-manager.js (5 bulks)...")
    sm_lines = read_lines(os.path.join(OS_RUNTIME, "sync-manager.js"))
    for i, bk in enumerate(SYNC_MANAGER_BULKS):
        content = extract(sm_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "sync-manager", bk["name"], content, lang="javascript",
            bulk_order=i, depends=bk["depends"], exports=bk["exports"],
            overflow=bk.get("overflow", False), project_slug="platform-core"
        )
    print(f"       5 bulks from {len(sm_lines)} lines")

    # ═══ COMPILE TEST ═══
    print("\n--- Compile Test ---")
    ws_code = await engine.compile_component("ws-clients", project_slug="platform-core")
    ps_code = await engine.compile_component("pubsub", project_slug="platform-core")
    sm_code = await engine.compile_component("sync-manager", project_slug="platform-core")
    print(f"  ws-clients.js:   {ws_code.count(chr(10))+1} lines")
    print(f"  pubsub.js:       {ps_code.count(chr(10))+1} lines")
    print(f"  sync-manager.js: {sm_code.count(chr(10))+1} lines")
    print(f"  TOTAL:           {ws_code.count(chr(10)) + ps_code.count(chr(10)) + sm_code.count(chr(10)) + 3} lines")

    # ═══ STATS ═══
    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"PLATFORM: {stats['projects']} projects | {stats['modules']} modules | {stats['components']} components | {stats['bulks']} bulks | {stats['total_lines']} lines")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
