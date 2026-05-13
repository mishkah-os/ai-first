// WS3 POS Handler — Branch-aware real-time sync for POS
// Each branch subscribes to its own channel
// Changes in one branch NEVER leak to another

export class WS3POSHandler {
    constructor(ws3Server, branchManager, schemaCRUD) {
        this.ws3 = ws3Server;
        this.branches = branchManager;
        this.crud = schemaCRUD;
        this.branchClients = new Map(); // branchId -> Set<ws>
    }

    init() {
        this.ws3.on('connection', (ws, req) => {
            ws.on('message', async (raw) => {
                const msg = JSON.parse(raw.toString());
                await this.handleMessage(ws, msg);
            });

            ws.on('close', () => this.removeClient(ws));
        });
    }

    async handleMessage(ws, msg) {
        switch (msg.type) {
            case 'join_branch':
                this.addClientToBranch(ws, msg.branch_id);
                ws.send(JSON.stringify({ type: 'joined', branch_id: msg.branch_id }));
                break;

            case 'crud': {
                const { branch_id, table, action, id, data } = msg;
                let result;

                switch (action) {
                    case 'create':
                        result = await this.crud.create(branch_id, table, data);
                        this.broadcastToBranch(branch_id, { type: 'change', table, action: 'insert', record_id: result.id, delta: result });
                        break;
                    case 'update':
                        result = await this.crud.update(branch_id, table, id, data);
                        this.broadcastToBranch(branch_id, { type: 'change', table, action: 'update', record_id: id, delta: result });
                        break;
                    case 'delete':
                        await this.crud.delete(branch_id, table, id);
                        this.broadcastToBranch(branch_id, { type: 'change', table, action: 'delete', record_id: id, tombstone: true });
                        break;
                    case 'read':
                        result = await this.crud.read(branch_id, table, id);
                        break;
                    case 'list':
                        result = await this.crud.list(branch_id, table, msg.opts || {});
                        break;
                }

                ws.send(JSON.stringify({ type: 'crud_response', request_id: msg.request_id, data: result }));
                break;
            }

            case 'sync': {
                // Full table sync for a branch
                const { branch_id, tables, cursors } = msg;
                const response = {};

                for (const table of tables) {
                    const cursor = cursors?.[table] || 0;
                    const result = await this.crud.list(branch_id, table, {
                        where: {}, // could filter by updated_at > cursor
                        limit: 1000
                    });
                    response[table] = { data: result.data, cursor: Date.now() };
                }

                ws.send(JSON.stringify({ type: 'sync_response', data: response }));
                break;
            }
        }
    }

    addClientToBranch(ws, branchId) {
        if (!this.branchClients.has(branchId)) {
            this.branchClients.set(branchId, new Set());
        }
        this.branchClients.get(branchId).add(ws);
        ws._branchId = branchId;
    }

    removeClient(ws) {
        if (ws._branchId) {
            this.branchClients.get(ws._branchId)?.delete(ws);
        }
    }

    broadcastToBranch(branchId, message) {
        const clients = this.branchClients.get(branchId);
        if (!clients) return;

        const payload = JSON.stringify(message);
        for (const ws of clients) {
            if (ws.readyState === 1) ws.send(payload);
        }
    }
}
