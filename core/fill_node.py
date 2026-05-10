"""Fill Node.js WS Relay pillars into DB components."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

PILLARS = {
"ws-server": {"logic": r'''
const { WebSocketServer } = require('ws');
const http = require('http');

const server = http.createServer();
const wss = new WebSocketServer({ server });

wss.on('connection', (ws) => {
    console.log('Client connected to AI-First WS Relay');
    
    ws.on('message', (message) => {
        try {
            const req = JSON.parse(message);
            console.log('WS Request:', req.action);
            
            if (req.action === 'ping') {
                ws.send(JSON.stringify({ action: 'pong', time: new Date() }));
            }
        } catch (e) {
            ws.send(JSON.stringify({ error: 'Invalid JSON' }));
        }
    });

    ws.on('close', () => console.log('Client disconnected'));
});

const PORT = process.env.WS_PORT || 8080;
server.listen(PORT, () => {
    console.log(`AI-First WS Relay listening on port ${PORT}`);
});
'''},

"pg-listener": {"logic": r'''
const { Client } = require('pg');

async function startListener() {
    const client = new Client({
        connectionString: process.env.DATABASE_URL
    });

    await client.connect();
    console.log('Node.js PG Listener connected');

    await client.query('LISTEN change_log_event');

    client.on('notification', (msg) => {
        console.log('Change detected:', msg.payload);
        // Here we would broadcast to all connected WS clients
    });
}

startListener().catch(console.error);
'''},

"client-mgr": {"logic": r'''
class ClientManager {
    constructor() {
        this.clients = new Map(); // socket -> sessionInfo
    }
    add(ws, session) {
        this.clients.set(ws, { 
            id: session.userId, 
            tenantId: session.tenantId,
            subs: new Set() 
        });
    }
    remove(ws) { this.clients.delete(ws); }
    subscribe(ws, table) {
        const client = this.clients.get(ws);
        if (client) client.subs.add(table);
    }
    getClientsForTable(table, tenantId) {
        return [...this.clients.entries()]
            .filter(([ws, info]) => info.tenantId === tenantId && info.subs.has(table))
            .map(([ws]) => ws);
    }
}
'''},

"pubsub": {"logic": r'''
const ClientManager = require('./client-mgr');

class PubSub {
    constructor(wss, clientMgr) {
        this.wss = wss;
        this.clientMgr = clientMgr;
    }
    broadcastChange(payload) {
        const { table, tenant_id, data } = payload;
        const targets = this.clientMgr.getClientsForTable(table, tenant_id);
        const msg = JSON.stringify({ action: 'delta', table, data });
        targets.forEach(ws => ws.send(msg));
    }
}
'''}

async def main():
    print("Plan: Fill Node.js WS Relay components")
    for slug, pillars in PILLARS.items():
        print(f"  + {slug}: {len(pillars.get('logic', ''))} bytes of logic")

if __name__ == "__main__":
    asyncio.run(main())
