"""
Seed WS3 Relay — a new Node.js WebSocket service built via QDML.
Uses PostgreSQL LISTEN/NOTIFY + change_log for cursor-based sync.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DATABASE_URL, QDML_SCHEMA
import asyncpg
from qdml_engine import QDMLEngine

WS3_BULKS = {
"package_json": {
    "order": 0, "lang": "javascript", "exports": "", "depends": "",
    "content": r"""{
  "name": "qdml-ws3-relay",
  "version": "1.0.0",
  "type": "module",
  "main": "index.js",
  "scripts": {
    "start": "node index.js"
  },
  "dependencies": {
    "ws": "^8.16.0",
    "pg": "^8.11.0"
  }
}
"""
},

"index": {
    "order": 1, "lang": "javascript", "exports": "startRelay", "depends": "package_json",
    "content": r"""import { WebSocketServer } from 'ws';
import pg from 'pg';

const { Pool } = pg;

const CONFIG = {
  port: parseInt(process.env.WS3_PORT || '8003'),
  pgUrl: process.env.DATABASE_URL || 'postgresql://ai_auto:233f290cb68a514e3bb740d134f5bd50@127.0.0.1:5432/ai_auto',
  schema: process.env.QDML_SCHEMA || 'qdml',
  heartbeatInterval: 30000,
};

const pool = new Pool({ connectionString: CONFIG.pgUrl, max: 5 });
const clients = new Map();
let listenerConn = null;

async function setupListener() {
  listenerConn = await pool.connect();
  await listenerConn.query('LISTEN qdml_changes');
  listenerConn.on('notification', (msg) => {
    if (msg.channel === 'qdml_changes') {
      const payload = JSON.parse(msg.payload);
      broadcastChange(payload);
    }
  });
  console.log('[WS3] LISTEN qdml_changes active');
}

function broadcastChange(payload) {
  const msg = JSON.stringify({ type: 'change', ...payload });
  for (const [ws, meta] of clients) {
    if (ws.readyState === 1) {
      if (!meta.project_id || meta.project_id === payload.project_id) {
        ws.send(msg);
      }
    }
  }
}

function startRelay() {
  const wss = new WebSocketServer({ port: CONFIG.port });

  wss.on('connection', (ws, req) => {
    const id = Math.random().toString(36).slice(2, 10);
    clients.set(ws, { id, project_id: null, cursors: {}, subscribedTables: [] });
    console.log(`[WS3] Client connected: ${id} (total: ${clients.size})`);

    ws.on('message', async (raw) => {
      try {
        const msg = JSON.parse(raw.toString());
        await handleMessage(ws, msg);
      } catch (e) {
        ws.send(JSON.stringify({ type: 'error', error: e.message }));
      }
    });

    ws.on('close', () => {
      clients.delete(ws);
      console.log(`[WS3] Client disconnected: ${id} (total: ${clients.size})`);
    });

    ws.send(JSON.stringify({ type: 'hello', id, server: 'qdml-ws3-relay', version: '1.0.0' }));
  });

  const heartbeat = setInterval(() => {
    for (const [ws] of clients) {
      if (ws.readyState === 1) ws.ping();
    }
  }, CONFIG.heartbeatInterval);

  wss.on('close', () => clearInterval(heartbeat));

  setupListener().catch(e => console.error('[WS3] Listener setup failed:', e));
  console.log(`[WS3] Relay running on ws://0.0.0.0:${CONFIG.port}`);
  return wss;
}

startRelay();
"""
},

"message_handler": {
    "order": 2, "lang": "javascript", "exports": "handleMessage", "depends": "index",
    "content": r"""async function handleMessage(ws, msg) {
  const meta = clients.get(ws);
  if (!meta) return;

  switch (msg.type) {
    case 'subscribe': {
      meta.project_id = msg.project_id || null;
      meta.subscribedTables = msg.tables || [];
      ws.send(JSON.stringify({ type: 'subscribed', project_id: meta.project_id, tables: meta.subscribedTables }));
      break;
    }

    case 'sync': {
      const cursors = msg.cursors || {};
      const results = {};

      for (const [table, cursor] of Object.entries(cursors)) {
        const rows = await pool.query(
          `SELECT * FROM ${CONFIG.schema}.change_log WHERE project_id = $1 AND table_name = $2 AND cursor_seq > $3 ORDER BY cursor_seq LIMIT 1000`,
          [meta.project_id, table, cursor]
        );
        results[table] = {
          changes: rows.rows.map(r => ({
            action: r.action,
            record_id: r.record_id,
            delta: r.delta,
            cursor_seq: r.cursor_seq,
            tombstone: r.tombstone,
            ts: r.ts
          })),
          latest_cursor: rows.rows.length ? rows.rows[rows.rows.length - 1].cursor_seq : cursor
        };
      }

      ws.send(JSON.stringify({ type: 'sync_response', data: results }));
      break;
    }

    case 'publish': {
      const { project_id, table_name, action, record_id, delta } = msg;
      if (!project_id || !table_name || !action) {
        ws.send(JSON.stringify({ type: 'error', error: 'Missing required fields: project_id, table_name, action' }));
        return;
      }

      const result = await pool.query(
        `INSERT INTO ${CONFIG.schema}.change_log (project_id, table_name, record_id, action, delta, tombstone, actor_id)
         VALUES ($1, $2, $3, $4, $5, $6, $7) RETURNING cursor_seq`,
        [project_id, table_name, record_id || '', action, JSON.stringify(delta || {}), action === 'delete', meta.id]
      );

      const cursor_seq = result.rows[0].cursor_seq;
      ws.send(JSON.stringify({ type: 'published', cursor_seq }));

      broadcastChange({ table: table_name, id: record_id, op: action, project_id });
      break;
    }

    case 'ping': {
      ws.send(JSON.stringify({ type: 'pong', ts: Date.now() }));
      break;
    }

    default:
      ws.send(JSON.stringify({ type: 'error', error: `Unknown message type: ${msg.type}` }));
  }
}
"""
},

"cursor_tracker": {
    "order": 3, "lang": "javascript", "exports": "getLatestCursors,getChangesSince", "depends": "message_handler",
    "content": r"""async function getLatestCursors(projectId) {
  const result = await pool.query(
    `SELECT table_name, MAX(cursor_seq) as latest
     FROM ${CONFIG.schema}.change_log
     WHERE project_id = $1
     GROUP BY table_name`,
    [projectId]
  );
  const cursors = {};
  for (const row of result.rows) {
    cursors[row.table_name] = parseInt(row.latest);
  }
  return cursors;
}

async function getChangesSince(projectId, tableName, sinceCursor, limit = 500) {
  const result = await pool.query(
    `SELECT action, record_id, delta, cursor_seq, tombstone, ts
     FROM ${CONFIG.schema}.change_log
     WHERE project_id = $1 AND table_name = $2 AND cursor_seq > $3
     ORDER BY cursor_seq
     LIMIT $4`,
    [projectId, tableName, sinceCursor, limit]
  );
  return result.rows;
}
"""
}
}


async def main():
    print("=" * 60)
    print("QDML SEED — WS3 Relay (Node.js)")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ MODULE ═══
    print("\n[1/3] Creating ws3-relay module...")
    await engine.create_module("platform-core", "WS3 Relay", "ws3-relay", tier="backend", app="ws3-relay")

    # ═══ COMPONENTS ═══
    print("[2/3] Creating components...")
    await engine.create_component("ws3-relay", "WS3 Relay Server", "ws3-server", kind="service", target="node", project_slug="platform-core")

    # ═══ BULKS ═══
    print("[3/3] Registering WS3 bulks...")
    for name, data in WS3_BULKS.items():
        await engine.create_bulk(
            "ws3-server", name, data["content"], lang=data["lang"],
            bulk_order=data["order"], depends=data.get("depends", ""),
            exports=data.get("exports", ""), project_slug="platform-core"
        )
    print(f"       {len(WS3_BULKS)} bulks registered")

    # ═══ COMPILE & WRITE ═══
    print("\n--- Compiling to _generated/ws3-relay/ ---")
    import pathlib
    gen_dir = pathlib.Path(__file__).parent.parent / "mas-front" / "_generated" / "ws3-relay"
    gen_dir.mkdir(parents=True, exist_ok=True)

    code = await engine.compile_component("ws3-server", project_slug="platform-core")
    (gen_dir / "index.js").write_text(code, encoding="utf-8")

    # Write package.json separately (first bulk)
    pkg_content = WS3_BULKS["package_json"]["content"]
    (gen_dir / "package.json").write_text(pkg_content.strip(), encoding="utf-8")

    print(f"  index.js:     {code.count(chr(10))+1} lines")
    print(f"  package.json: written")

    # ═══ STATS ═══
    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"PLATFORM: {stats['projects']} projects | {stats['modules']} modules | {stats['components']} components | {stats['bulks']} bulks | {stats['total_lines']} lines")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
