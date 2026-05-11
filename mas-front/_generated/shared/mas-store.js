// mas-store v3 Unified — Core + IndexedDB + WS + Outbox
const DB_NAME = 'mas-store';
const DB_VERSION = 3;
const STORES = { entities: 'id', outbox: '++id', cursors: 'table', cache: 'key' };

let db = null;
let ws = null;
let config = {
    wsUrl: window.MAS_WS_URL || 'ws://localhost:8003',
    apiUrl: window.MAS_API_URL || '/api',
    syncInterval: 5000,
    outboxRetry: 3000
};

// ─── IndexedDB ───
async function openDB() {
    if (db) return db;
    return new Promise((resolve, reject) => {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = (e) => {
            const d = e.target.result;
            for (const [name, key] of Object.entries(STORES)) {
                if (!d.objectStoreNames.contains(name)) {
                    d.createObjectStore(name, { keyPath: key.startsWith('++') ? undefined : key, autoIncrement: key.startsWith('++') });
                }
            }
        };
        req.onsuccess = (e) => { db = e.target.result; resolve(db); };
        req.onerror = reject;
    });
}

async function idbGet(store, key) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readonly');
        const req = tx.objectStore(store).get(key);
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}

async function idbPut(store, value) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readwrite');
        const req = tx.objectStore(store).put(value);
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}

async function idbDelete(store, key) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readwrite');
        const req = tx.objectStore(store).delete(key);
        req.onsuccess = () => res();
        req.onerror = rej;
    });
}

async function idbGetAll(store) {
    const d = await openDB();
    return new Promise((res, rej) => {
        const tx = d.transaction(store, 'readonly');
        const req = tx.objectStore(store).getAll();
        req.onsuccess = () => res(req.result);
        req.onerror = rej;
    });
}

// ─── WebSocket Delta Sync ───
let reconnectAttempts = 0;

async function connectWS(projectId) {
    if (ws && ws.readyState === WebSocket.OPEN) return ws;

    return new Promise((resolve, reject) => {
        ws = new WebSocket(config.wsUrl);

        ws.onopen = () => {
            reconnectAttempts = 0;
            ws.send(JSON.stringify({ type: 'subscribe', project_id: projectId }));
            resolve(ws);
        };

        ws.onmessage = async (event) => {
            const msg = JSON.parse(event.data);
            await handleWSMessage(msg);
        };

        ws.onclose = () => {
            ws = null;
            if (reconnectAttempts < 5) {
                const delay = Math.min(1000 * Math.pow(2, reconnectAttempts++), 30000);
                setTimeout(() => connectWS(projectId), delay);
            }
        };

        ws.onerror = reject;
    });
}

function disconnectWS() {
    if (ws) { ws.close(); ws = null; }
}

async function handleWSMessage(msg) {
    switch (msg.type) {
        case 'change':
            await applyRemoteChange(msg);
            break;
        case 'sync_response':
            for (const [table, data] of Object.entries(msg.data || {})) {
                for (const change of data.changes || []) {
                    await applyRemoteChange({ table, ...change });
                }
                if (data.latest_cursor) {
                    await idbPut('cursors', { table, cursor: data.latest_cursor });
                }
            }
            break;
    }
}

async function applyRemoteChange(change) {
    const { table, record_id, action, delta, tombstone } = change;
    const key = `${table}:${record_id}`;

    if (action === 'delete' || tombstone) {
        await idbDelete('entities', key);
    } else {
        const existing = await idbGet('entities', key);
        const entity = existing ? { ...existing, ...delta } : { id: key, ...delta };
        entity._table = table;
        entity._record_id = record_id;
        await idbPut('entities', entity);
    }

    window.dispatchEvent(new CustomEvent('store:change', {
        detail: { table, record_id, action, delta }
    }));
}

async function requestSync(tables) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;

    const cursors = {};
    for (const table of tables) {
        const c = await idbGet('cursors', table);
        cursors[table] = c ? c.cursor : 0;
    }

    ws.send(JSON.stringify({ type: 'sync', cursors }));
}

// ─── Offline-First Outbox ───
async function queueOp(operation) {
    await idbPut('outbox', {
        ...operation,
        status: 'pending',
        attempts: 0,
        created_at: Date.now()
    });

    if (navigator.onLine) processOutbox();
}

async function processOutbox() {
    const all = await idbGetAll('outbox');
    const pending = all.filter(op => op.status === 'pending');

    for (const op of pending) {
        if (op.attempts >= 3) {
            op.status = 'failed';
            await idbPut('outbox', op);
            continue;
        }

        try {
            const url = `${config.apiUrl}/${op.table}/${op.record_id || ''}`;
            const resp = await fetch(url, {
                method: op.action === 'delete' ? 'DELETE' : (op.record_id ? 'PUT' : 'POST'),
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('token')}`
                },
                body: op.action !== 'delete' ? JSON.stringify(op.data) : undefined
            });

            if (resp.ok) {
                op.status = 'completed';
                await idbPut('outbox', op);
            } else {
                throw new Error(`HTTP ${resp.status}`);
            }
        } catch (e) {
            op.attempts++;
            op.last_error = e.message;
            await idbPut('outbox', op);
        }
    }
}

// Retry on reconnect
window.addEventListener('online', () => processOutbox());
setInterval(() => { if (navigator.onLine) processOutbox(); }, config.outboxRetry);

// ─── Public API ───
class MasStore {
    constructor() { this.listeners = new Map(); }

    async init(opts = {}) {
        Object.assign(config, opts);
        await openDB();
        if (opts.projectId) await connectWS(opts.projectId);
    }

    async get(table, id) {
        const key = `${table}:${id}`;
        return await idbGet('entities', key);
    }

    async save(table, entity) {
        if (!entity.id) entity.id = crypto.randomUUID();
        const key = `${table}:${entity.id}`;
        entity._table = table;
        entity._record_id = entity.id;
        Object.assign(entity, { id: key });
        await idbPut('entities', entity);

        await queueOp({ table, record_id: entity._record_id, action: 'save', data: entity });
        return entity;
    }

    async delete(table, id) {
        const key = `${table}:${id}`;
        await idbDelete('entities', key);
        await queueOp({ table, record_id: id, action: 'delete' });
    }

    async query(table, filter = {}) {
        const all = await idbGetAll('entities');
        return all.filter(e => {
            if (e._table !== table) return false;
            for (const [k, v] of Object.entries(filter)) {
                if (e[k] !== v) return false;
            }
            return true;
        });
    }

    async sync(tables) { await requestSync(tables); }

    on(event, cb) {
        if (!this.listeners.has(event)) this.listeners.set(event, []);
        this.listeners.get(event).push(cb);
        return () => { const cbs = this.listeners.get(event); cbs.splice(cbs.indexOf(cb), 1); };
    }
}

const masStore = new MasStore();

window.addEventListener('store:change', (e) => {
    const cbs = masStore.listeners.get('change') || [];
    cbs.forEach(cb => cb(e.detail));
});

window.masStore = masStore;
export default masStore;
