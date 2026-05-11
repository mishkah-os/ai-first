// Approval Engine — Multi-Level Approval Workflows
class ApprovalEngine {
    constructor(pg, schema) {
        this.pg = pg;
        this.schema = schema;
    }

    async init() {
        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.approval_workflows (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            levels JSONB NOT NULL DEFAULT '[]',
            auto_approve_below NUMERIC(12,2),
            config JSONB DEFAULT '{}',
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT now()
        )`);

        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.approval_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            workflow_id UUID REFERENCES ${this.schema}.approval_workflows(id),
            entity_type TEXT NOT NULL,
            entity_id UUID NOT NULL,
            entity_data JSONB,
            amount NUMERIC(12,2),
            current_level INT DEFAULT 0,
            status TEXT DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected','cancelled','escalated')),
            requester_id UUID,
            requester_name TEXT,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            resolved_at TIMESTAMPTZ
        )`);

        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.approval_actions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            request_id UUID REFERENCES ${this.schema}.approval_requests(id) ON DELETE CASCADE,
            level INT NOT NULL,
            approver_id UUID,
            approver_name TEXT,
            action TEXT CHECK (action IN ('approve','reject','escalate','comment')),
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )`);
    }

    async createWorkflow(data) {
        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.approval_workflows (name, slug, entity_type, levels, auto_approve_below, config)
            VALUES ($1,$2,$3,$4,$5,$6) RETURNING *
        `, [data.name, data.slug, data.entity_type, JSON.stringify(data.levels), data.auto_approve_below, JSON.stringify(data.config||{})]);
        return result.rows[0];
    }

    async submitForApproval(data) {
        // Find matching workflow
        const workflow = await this.pg.query(`
            SELECT * FROM ${this.schema}.approval_workflows
            WHERE entity_type = $1 AND is_active = true LIMIT 1
        `, [data.entity_type]);

        if (!workflow.rows.length) throw new Error(`No active workflow for ${data.entity_type}`);
        const wf = workflow.rows[0];

        // Auto-approve if below threshold
        if (wf.auto_approve_below && data.amount && data.amount < wf.auto_approve_below) {
            return { status: 'auto_approved', amount: data.amount, threshold: wf.auto_approve_below };
        }

        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.approval_requests
            (workflow_id, entity_type, entity_id, entity_data, amount, requester_id, requester_name, notes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8) RETURNING *
        `, [wf.id, data.entity_type, data.entity_id, JSON.stringify(data.entity_data||{}),
            data.amount, data.requester_id, data.requester_name, data.notes]);

        return result.rows[0];
    }

    async approve(requestId, approverId, approverName, comment) {
        const req = await this.pg.query(`SELECT * FROM ${this.schema}.approval_requests WHERE id = $1`, [requestId]);
        if (!req.rows.length) throw new Error('Request not found');
        const request = req.rows[0];

        const wf = await this.pg.query(`SELECT * FROM ${this.schema}.approval_workflows WHERE id = $1`, [request.workflow_id]);
        const levels = JSON.parse(wf.rows[0].levels);
        const nextLevel = request.current_level + 1;

        // Record action
        await this.pg.query(`
            INSERT INTO ${this.schema}.approval_actions (request_id, level, approver_id, approver_name, action, comment)
            VALUES ($1,$2,$3,$4,'approve',$5)
        `, [requestId, request.current_level, approverId, approverName, comment]);

        // Check if all levels approved
        if (nextLevel >= levels.length) {
            await this.pg.query(`UPDATE ${this.schema}.approval_requests SET status='approved', resolved_at=now() WHERE id=$1`, [requestId]);
            return { status: 'approved', final: true };
        } else {
            await this.pg.query(`UPDATE ${this.schema}.approval_requests SET current_level=$2 WHERE id=$1`, [requestId, nextLevel]);
            return { status: 'pending', current_level: nextLevel, next_approver: levels[nextLevel] };
        }
    }

    async reject(requestId, approverId, approverName, reason) {
        await this.pg.query(`
            INSERT INTO ${this.schema}.approval_actions (request_id, level, approver_id, approver_name, action, comment)
            VALUES ($1, (SELECT current_level FROM ${this.schema}.approval_requests WHERE id=$1), $2, $3, 'reject', $4)
        `, [requestId, approverId, approverName, reason]);

        await this.pg.query(`UPDATE ${this.schema}.approval_requests SET status='rejected', resolved_at=now() WHERE id=$1`, [requestId]);
        return { status: 'rejected', reason };
    }

    async getPending(approverId) {
        return (await this.pg.query(`
            SELECT ar.*, aw.name as workflow_name, aw.levels
            FROM ${this.schema}.approval_requests ar
            JOIN ${this.schema}.approval_workflows aw ON ar.workflow_id = aw.id
            WHERE ar.status = 'pending'
            ORDER BY ar.created_at
        `)).rows;
    }
}
