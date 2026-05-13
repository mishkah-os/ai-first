// POS Server Entry Point — Connects WS3 + All Engines
import { WebSocketServer } from 'ws';
import pg from 'pg';

const { Pool } = pg;

const CONFIG = {
    port: parseInt(process.env.WS3_PORT || '8003'),
    pgUrl: process.env.DATABASE_URL || 'postgresql://ai_auto:233f290cb68a514e3bb740d134f5bd50@127.0.0.1:5432/ai_auto',
    masterSchema: process.env.QDML_SCHEMA || 'qdml'
};

const pool = new Pool({ connectionString: CONFIG.pgUrl, max: 10 });

// ─── Branch Manager ───
class BranchManager {
    constructor() { this.branches = new Map(); }

    async load() {
        const result = await pool.query(
            `SELECT * FROM ${CONFIG.masterSchema}.app_instances WHERE status = 'active'`
        );
        for (const row of result.rows) {
            const config = typeof row.config === 'string' ? JSON.parse(row.config) : row.config;
            this.branches.set(config?.code || row.id, { ...row, schema: config?.schema });
        }
        console.log(`[Branches] Loaded ${this.branches.size} branches`);
    }

    getSchema(branchCode) {
        const branch = this.branches.get(branchCode);
        return branch?.schema || `pos_${branchCode}`;
    }
}

// ─── Schema CRUD ───
class SchemaCRUD {
    async create(schema, table, data) {
        const fields = Object.keys(data).filter(k => k !== 'id');
        if (!data.id) data.id = crypto.randomUUID();
        fields.unshift('id');

        const cols = fields.join(', ');
        const placeholders = fields.map((_, i) => `$${i + 1}`).join(', ');
        const values = fields.map(k => typeof data[k] === 'object' ? JSON.stringify(data[k]) : data[k]);

        const result = await pool.query(
            `INSERT INTO ${schema}.${table} (${cols}) VALUES (${placeholders}) RETURNING *`, values
        );
        return result.rows[0];
    }

    async read(schema, table, id) {
        const result = await pool.query(`SELECT * FROM ${schema}.${table} WHERE id = $1`, [id]);
        return result.rows[0] || null;
    }

    async update(schema, table, id, data) {
        const fields = Object.keys(data).filter(k => k !== 'id');
        const sets = fields.map((f, i) => `${f} = $${i + 1}`);
        sets.push('updated_at = now()');
        const values = fields.map(k => typeof data[k] === 'object' ? JSON.stringify(data[k]) : data[k]);
        values.push(id);

        const result = await pool.query(
            `UPDATE ${schema}.${table} SET ${sets.join(', ')} WHERE id = $${values.length} RETURNING *`, values
        );
        return result.rows[0];
    }

    async delete(schema, table, id) {
        await pool.query(`DELETE FROM ${schema}.${table} WHERE id = $1`, [id]);
    }

    async list(schema, table, opts = {}) {
        const { where = {}, sort = 'created_at', order = 'DESC', limit = 100, offset = 0 } = opts;
        let conditions = [];
        let params = [];
        let i = 1;

        for (const [key, value] of Object.entries(where)) {
            conditions.push(`${key} = $${i++}`);
            params.push(value);
        }

        const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';
        params.push(limit, offset);

        const result = await pool.query(
            `SELECT * FROM ${schema}.${table} ${whereClause} ORDER BY ${sort} ${order} LIMIT $${i++} OFFSET $${i}`,
            params
        );
        return result.rows;
    }
}

// ─── WebSocket Server ───
const branchManager = new BranchManager();
const crud = new SchemaCRUD();
const clients = new Map(); // ws -> { branchCode, id }

async function start() {
    await branchManager.load();

    const wss = new WebSocketServer({ port: CONFIG.port });

    wss.on('connection', (ws) => {
        const clientId = crypto.randomUUID().slice(0, 8);
        clients.set(ws, { id: clientId, branchCode: null });

        ws.send(JSON.stringify({ type: 'hello', id: clientId, server: 'pos-ws3', version: '2.0' }));

        ws.on('message', async (raw) => {
            try {
                const msg = JSON.parse(raw.toString());
                await handleMessage(ws, msg);
            } catch (e) {
                ws.send(JSON.stringify({ type: 'error', error: e.message }));
            }
        });

        ws.on('close', () => clients.delete(ws));
    });

    // LISTEN for PostgreSQL notifications
    const listener = await pool.connect();
    await listener.query('LISTEN pos_changes');
    listener.on('notification', (msg) => {
        if (msg.channel === 'pos_changes') {
            const payload = JSON.parse(msg.payload);
            broadcastToBranch(payload.branch, payload);
        }
    });

    console.log(`[POS-WS3] Running on ws://0.0.0.0:${CONFIG.port}`);
    console.log(`[POS-WS3] Branches: ${[...branchManager.branches.keys()].join(', ') || 'none yet'}`);
}

async function handleMessage(ws, msg) {
    const client = clients.get(ws);

    switch (msg.type) {
        case 'join_branch': {
            client.branchCode = msg.branch;
            ws.send(JSON.stringify({ type: 'joined', branch: msg.branch }));
            break;
        }

        case 'crud': {
            if (!client.branchCode) { ws.send(JSON.stringify({ type: 'error', error: 'Not joined to branch' })); return; }

            const schema = branchManager.getSchema(client.branchCode);
            const { table, action, id, data, opts } = msg;
            let result;

            switch (action) {
                case 'create':
                    result = await crud.create(schema, table, data);
                    broadcastToBranch(client.branchCode, { type: 'change', table, action: 'insert', record_id: result.id, delta: result }, ws);
                    break;
                case 'read':
                    result = await crud.read(schema, table, id);
                    break;
                case 'update':
                    result = await crud.update(schema, table, id, data);
                    broadcastToBranch(client.branchCode, { type: 'change', table, action: 'update', record_id: id, delta: result }, ws);
                    break;
                case 'delete':
                    await crud.delete(schema, table, id);
                    broadcastToBranch(client.branchCode, { type: 'change', table, action: 'delete', record_id: id, tombstone: true }, ws);
                    result = { deleted: true };
                    break;
                case 'list':
                    result = await crud.list(schema, table, opts || {});
                    break;
            }

            ws.send(JSON.stringify({ type: 'crud_response', request_id: msg.request_id, data: result }));
            break;
        }

        case 'sync': {
            if (!client.branchCode) return;
            const schema = branchManager.getSchema(client.branchCode);
            const response = {};

            for (const table of msg.tables || []) {
                try {
                    response[table] = await crud.list(schema, table, { limit: 1000 });
                } catch (e) {
                    response[table] = [];
                }
            }

            ws.send(JSON.stringify({ type: 'sync_response', data: response }));
            break;
        }

        case 'print_ticket':
        case 'print_receipt': {
            // Forward to all printer clients in same branch
            broadcastToBranch(client.branchCode, msg, ws);
            break;
        }
    }
}

function broadcastToBranch(branchCode, message, excludeWs = null) {
    const payload = JSON.stringify(message);
    for (const [ws, meta] of clients) {
        if (ws !== excludeWs && meta.branchCode === branchCode && ws.readyState === 1) {
            ws.send(payload);
        }
    }
}

// Heartbeat
setInterval(() => {
    for (const [ws] of clients) {
        if (ws.readyState === 1) ws.ping();
    }
}, 30000);

start().catch(e => console.error('[POS-WS3] Fatal:', e));
