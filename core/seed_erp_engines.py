#!/usr/bin/env python3
"""
Seed AI-Auto ERP Engines into QDML:
1. Invoice Engine
2. Approval Engine
3. Tree Coding Engine
4. CRUD Table Engine
"""
import asyncio
import asyncpg
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA

INVOICE_ENGINE = {
"core": {
    "order": 0, "lang": "javascript",
    "exports": "InvoiceEngine",
    "content": r"""// Invoice Engine — Schema-Driven Invoice Generation
class InvoiceEngine {
    constructor(pg, schema) {
        this.pg = pg;
        this.schema = schema;
        this.counter = null;
    }

    async init() {
        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.invoices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_number TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT 'invoice' CHECK (type IN ('invoice','quote','credit_note','debit_note')),
            customer_id UUID,
            customer_name TEXT,
            customer_tax_id TEXT,
            date DATE DEFAULT CURRENT_DATE,
            due_date DATE,
            currency TEXT DEFAULT 'SAR',
            subtotal NUMERIC(12,2) DEFAULT 0,
            tax_amount NUMERIC(12,2) DEFAULT 0,
            discount_amount NUMERIC(12,2) DEFAULT 0,
            total NUMERIC(12,2) DEFAULT 0,
            status TEXT DEFAULT 'draft' CHECK (status IN ('draft','sent','paid','overdue','cancelled')),
            notes TEXT,
            meta JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )`);

        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.invoice_lines (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_id UUID REFERENCES ${this.schema}.invoices(id) ON DELETE CASCADE,
            line_order INT DEFAULT 0,
            item_code TEXT,
            description TEXT NOT NULL,
            quantity NUMERIC(10,3) DEFAULT 1,
            unit_price NUMERIC(12,2) NOT NULL,
            discount_percent NUMERIC(5,2) DEFAULT 0,
            tax_percent NUMERIC(5,2) DEFAULT 15,
            line_total NUMERIC(12,2) GENERATED ALWAYS AS (
                quantity * unit_price * (1 - discount_percent/100) * (1 + tax_percent/100)
            ) STORED,
            meta JSONB DEFAULT '{}'
        )`);

        await this.pg.query(`CREATE SEQUENCE IF NOT EXISTS ${this.schema}.invoice_seq START 1000`);
    }

    async generateNumber(prefix = 'INV') {
        const result = await this.pg.query(`SELECT nextval('${this.schema}.invoice_seq') as num`);
        const num = result.rows[0].num;
        const year = new Date().getFullYear();
        return `${prefix}-${year}-${String(num).padStart(5, '0')}`;
    }

    async create(data) {
        const number = await this.generateNumber(data.type === 'quote' ? 'QUO' : 'INV');

        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.invoices
            (invoice_number, type, customer_id, customer_name, customer_tax_id, date, due_date, currency, notes, meta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING *
        `, [number, data.type||'invoice', data.customer_id, data.customer_name,
            data.customer_tax_id, data.date||new Date(), data.due_date,
            data.currency||'SAR', data.notes, JSON.stringify(data.meta||{})]);

        const invoice = result.rows[0];

        // Add lines
        if (data.lines?.length) {
            for (let i = 0; i < data.lines.length; i++) {
                const line = data.lines[i];
                await this.pg.query(`
                    INSERT INTO ${this.schema}.invoice_lines
                    (invoice_id, line_order, item_code, description, quantity, unit_price, discount_percent, tax_percent)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                `, [invoice.id, i, line.item_code, line.description,
                    line.quantity||1, line.unit_price, line.discount_percent||0, line.tax_percent||15]);
            }
        }

        // Recalculate totals
        await this.recalculate(invoice.id);
        return await this.get(invoice.id);
    }

    async recalculate(invoiceId) {
        await this.pg.query(`
            UPDATE ${this.schema}.invoices SET
                subtotal = (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                discount_amount = (SELECT COALESCE(SUM(quantity * unit_price * discount_percent / 100), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                tax_amount = (SELECT COALESCE(SUM(quantity * unit_price * (1 - discount_percent/100) * tax_percent / 100), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                total = (SELECT COALESCE(SUM(line_total), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                updated_at = now()
            WHERE id = $1
        `, [invoiceId]);
    }

    async get(id) {
        const inv = await this.pg.query(`SELECT * FROM ${this.schema}.invoices WHERE id = $1`, [id]);
        if (!inv.rows.length) return null;
        const lines = await this.pg.query(`SELECT * FROM ${this.schema}.invoice_lines WHERE invoice_id = $1 ORDER BY line_order`, [id]);
        return { ...inv.rows[0], lines: lines.rows };
    }

    async list(filters = {}) {
        let where = ['1=1'];
        let params = [];
        let i = 1;

        if (filters.status) { where.push(`status = $${i++}`); params.push(filters.status); }
        if (filters.customer_id) { where.push(`customer_id = $${i++}`); params.push(filters.customer_id); }
        if (filters.type) { where.push(`type = $${i++}`); params.push(filters.type); }
        if (filters.from_date) { where.push(`date >= $${i++}`); params.push(filters.from_date); }
        if (filters.to_date) { where.push(`date <= $${i++}`); params.push(filters.to_date); }

        const result = await this.pg.query(`
            SELECT * FROM ${this.schema}.invoices WHERE ${where.join(' AND ')} ORDER BY created_at DESC LIMIT ${filters.limit||50}
        `, params);
        return result.rows;
    }

    async updateStatus(id, status) {
        await this.pg.query(`UPDATE ${this.schema}.invoices SET status=$2, updated_at=now() WHERE id=$1`, [id, status]);
        return await this.get(id);
    }

    async duplicate(id) {
        const original = await this.get(id);
        if (!original) throw new Error('Invoice not found');
        return await this.create({ ...original, lines: original.lines, date: new Date(), due_date: null, notes: `Duplicated from ${original.invoice_number}` });
    }

    async convertToInvoice(quoteId) {
        const quote = await this.get(quoteId);
        if (!quote || quote.type !== 'quote') throw new Error('Not a quote');
        await this.updateStatus(quoteId, 'cancelled');
        return await this.create({ ...quote, type: 'invoice', lines: quote.lines, notes: `Converted from quote ${quote.invoice_number}` });
    }
}
"""
},
"pdf_generator": {
    "order": 1, "lang": "javascript",
    "exports": "generateInvoicePDF",
    "content": r"""// Invoice PDF Generator (HTML-based for server-side rendering)
function generateInvoicePDF(invoice, config = {}) {
    const { company_name, company_logo, company_address, company_tax_id } = config;

    const formatMoney = (amount) => new Intl.NumberFormat('ar-SA', { style: 'currency', currency: invoice.currency || 'SAR' }).format(amount);
    const formatDate = (d) => new Date(d).toLocaleDateString('ar-SA');

    return `<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><style>
body{font-family:'Segoe UI',Tahoma,sans-serif;margin:0;padding:40px;color:#333;direction:rtl}
.invoice-header{display:flex;justify-content:space-between;margin-bottom:40px}
.company-info h1{margin:0;font-size:24px;color:#1a237e}.company-info p{margin:4px 0;color:#666}
.invoice-meta{text-align:left}.invoice-meta h2{margin:0;color:#1a237e}
.invoice-meta table td{padding:4px 12px;font-size:14px}
.customer-info{background:#f5f5f5;padding:20px;border-radius:8px;margin-bottom:30px}
.items-table{width:100%;border-collapse:collapse;margin-bottom:30px}
.items-table th{background:#1a237e;color:#fff;padding:12px;text-align:right}
.items-table td{padding:10px 12px;border-bottom:1px solid #eee}
.items-table tr:hover{background:#f9f9f9}
.totals{margin-left:auto;width:300px}.totals table{width:100%}
.totals td{padding:8px 12px;border-bottom:1px solid #eee}
.totals .total-row{font-size:18px;font-weight:bold;color:#1a237e}
.footer{margin-top:40px;padding-top:20px;border-top:2px solid #1a237e;text-align:center;color:#666;font-size:12px}
.status-badge{display:inline-block;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:bold}
.status-draft{background:#fff3e0;color:#e65100}.status-sent{background:#e3f2fd;color:#1565c0}
.status-paid{background:#e8f5e9;color:#2e7d32}.status-overdue{background:#fce4ec;color:#c62828}
</style></head>
<body>
<div class="invoice-header">
    <div class="company-info">
        ${company_logo ? `<img src="${company_logo}" height="50">` : ''}
        <h1>${company_name || 'Company'}</h1>
        <p>${company_address || ''}</p>
        <p>الرقم الضريبي: ${company_tax_id || ''}</p>
    </div>
    <div class="invoice-meta">
        <h2>${invoice.type === 'quote' ? 'عرض سعر' : 'فاتورة'}</h2>
        <table>
            <tr><td>الرقم:</td><td><strong>${invoice.invoice_number}</strong></td></tr>
            <tr><td>التاريخ:</td><td>${formatDate(invoice.date)}</td></tr>
            ${invoice.due_date ? `<tr><td>تاريخ الاستحقاق:</td><td>${formatDate(invoice.due_date)}</td></tr>` : ''}
            <tr><td>الحالة:</td><td><span class="status-badge status-${invoice.status}">${invoice.status}</span></td></tr>
        </table>
    </div>
</div>
<div class="customer-info">
    <strong>العميل:</strong> ${invoice.customer_name || '—'}
    ${invoice.customer_tax_id ? `<br>الرقم الضريبي: ${invoice.customer_tax_id}` : ''}
</div>
<table class="items-table">
    <thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>السعر</th><th>الخصم</th><th>الضريبة</th><th>الإجمالي</th></tr></thead>
    <tbody>
        ${(invoice.lines||[]).map((line, i) => `
        <tr>
            <td>${i+1}</td>
            <td>${line.description}${line.item_code ? ` <small>(${line.item_code})</small>` : ''}</td>
            <td>${line.quantity}</td>
            <td>${formatMoney(line.unit_price)}</td>
            <td>${line.discount_percent}%</td>
            <td>${line.tax_percent}%</td>
            <td>${formatMoney(line.line_total)}</td>
        </tr>`).join('')}
    </tbody>
</table>
<div class="totals"><table>
    <tr><td>المجموع الفرعي:</td><td>${formatMoney(invoice.subtotal)}</td></tr>
    <tr><td>الخصم:</td><td>${formatMoney(invoice.discount_amount)}</td></tr>
    <tr><td>الضريبة (VAT):</td><td>${formatMoney(invoice.tax_amount)}</td></tr>
    <tr class="total-row"><td>الإجمالي:</td><td>${formatMoney(invoice.total)}</td></tr>
</table></div>
${invoice.notes ? `<div style="margin-top:30px;padding:15px;background:#f5f5f5;border-radius:8px"><strong>ملاحظات:</strong><br>${invoice.notes}</div>` : ''}
<div class="footer"><p>${company_name} — جميع الحقوق محفوظة © ${new Date().getFullYear()}</p></div>
</body></html>`;
}
"""
}
}

APPROVAL_ENGINE = {
"core": {
    "order": 0, "lang": "javascript",
    "exports": "ApprovalEngine",
    "content": r"""// Approval Engine — Multi-Level Approval Workflows
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
"""
}
}

TREE_CODING_ENGINE = {
"core": {
    "order": 0, "lang": "javascript",
    "exports": "TreeCodingEngine",
    "content": r"""// Tree Coding Engine — Hierarchical Auto-Coding System
class TreeCodingEngine {
    constructor(pg, schema) {
        this.pg = pg;
        this.schema = schema;
    }

    async init() {
        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.tree_nodes (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            parent_id UUID REFERENCES ${this.schema}.tree_nodes(id),
            code TEXT NOT NULL,
            full_code TEXT NOT NULL,
            name TEXT NOT NULL,
            name_ar TEXT,
            level INT DEFAULT 0,
            tree_type TEXT NOT NULL,
            sort_order INT DEFAULT 0,
            is_leaf BOOLEAN DEFAULT false,
            is_active BOOLEAN DEFAULT true,
            meta JSONB DEFAULT '{}',
            children_count INT DEFAULT 0,
            path TEXT[],
            created_at TIMESTAMPTZ DEFAULT now()
        )`);

        await this.pg.query(`CREATE INDEX IF NOT EXISTS idx_tree_parent ON ${this.schema}.tree_nodes(parent_id)`);
        await this.pg.query(`CREATE INDEX IF NOT EXISTS idx_tree_code ON ${this.schema}.tree_nodes(tree_type, full_code)`);
        await this.pg.query(`CREATE INDEX IF NOT EXISTS idx_tree_type ON ${this.schema}.tree_nodes(tree_type, level)`);
    }

    async createTree(type, rootName, config = {}) {
        const root = await this.pg.query(`
            INSERT INTO ${this.schema}.tree_nodes (code, full_code, name, name_ar, level, tree_type, path, meta)
            VALUES ('0', '0', $1, $2, 0, $3, ARRAY['0'], $4) RETURNING *
        `, [rootName, config.name_ar || rootName, type, JSON.stringify(config)]);
        return root.rows[0];
    }

    async addNode(parentId, data) {
        const parent = await this.pg.query(`SELECT * FROM ${this.schema}.tree_nodes WHERE id = $1`, [parentId]);
        if (!parent.rows.length) throw new Error('Parent not found');
        const p = parent.rows[0];

        // Auto-generate code
        const siblings = await this.pg.query(`
            SELECT code FROM ${this.schema}.tree_nodes WHERE parent_id = $1 ORDER BY code DESC LIMIT 1
        `, [parentId]);

        const nextCode = siblings.rows.length ? String(parseInt(siblings.rows[0].code) + 1).padStart(2, '0') : '01';
        const fullCode = p.full_code === '0' ? nextCode : `${p.full_code}-${nextCode}`;
        const path = [...p.path, nextCode];

        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.tree_nodes (parent_id, code, full_code, name, name_ar, level, tree_type, sort_order, is_leaf, meta, path)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11) RETURNING *
        `, [parentId, nextCode, fullCode, data.name, data.name_ar||data.name,
            p.level+1, p.tree_type, data.sort_order||0, data.is_leaf||false,
            JSON.stringify(data.meta||{}), path]);

        // Update parent
        await this.pg.query(`UPDATE ${this.schema}.tree_nodes SET children_count = children_count + 1, is_leaf = false WHERE id = $1`, [parentId]);

        return result.rows[0];
    }

    async getTree(type, maxLevel = 10) {
        const rows = await this.pg.query(`
            SELECT * FROM ${this.schema}.tree_nodes
            WHERE tree_type = $1 AND level <= $2 AND is_active = true
            ORDER BY level, sort_order, code
        `, [type, maxLevel]);
        return this.buildHierarchy(rows.rows);
    }

    buildHierarchy(flatNodes) {
        const map = new Map();
        const roots = [];

        flatNodes.forEach(node => map.set(node.id, { ...node, children: [] }));

        flatNodes.forEach(node => {
            const item = map.get(node.id);
            if (node.parent_id && map.has(node.parent_id)) {
                map.get(node.parent_id).children.push(item);
            } else if (node.level === 0) {
                roots.push(item);
            }
        });

        return roots;
    }

    async search(type, query) {
        return (await this.pg.query(`
            SELECT * FROM ${this.schema}.tree_nodes
            WHERE tree_type = $1 AND is_active = true
            AND (name ILIKE $2 OR name_ar ILIKE $2 OR full_code ILIKE $2)
            ORDER BY level, sort_order LIMIT 50
        `, [type, `%${query}%`])).rows;
    }

    async getAncestors(nodeId) {
        return (await this.pg.query(`
            WITH RECURSIVE ancestors AS (
                SELECT * FROM ${this.schema}.tree_nodes WHERE id = $1
                UNION ALL
                SELECT t.* FROM ${this.schema}.tree_nodes t
                JOIN ancestors a ON t.id = a.parent_id
            )
            SELECT * FROM ancestors ORDER BY level
        `, [nodeId])).rows;
    }

    async getDescendants(nodeId) {
        return (await this.pg.query(`
            WITH RECURSIVE descendants AS (
                SELECT * FROM ${this.schema}.tree_nodes WHERE parent_id = $1
                UNION ALL
                SELECT t.* FROM ${this.schema}.tree_nodes t
                JOIN descendants d ON t.parent_id = d.id
            )
            SELECT * FROM descendants ORDER BY level, sort_order
        `, [nodeId])).rows;
    }

    async moveNode(nodeId, newParentId) {
        const node = (await this.pg.query(`SELECT * FROM ${this.schema}.tree_nodes WHERE id=$1`, [nodeId])).rows[0];
        const newParent = (await this.pg.query(`SELECT * FROM ${this.schema}.tree_nodes WHERE id=$1`, [newParentId])).rows[0];
        if (!node || !newParent) throw new Error('Node or parent not found');
        if (node.tree_type !== newParent.tree_type) throw new Error('Cannot move between tree types');

        const oldParentId = node.parent_id;
        const newFullCode = newParent.full_code === '0' ? node.code : `${newParent.full_code}-${node.code}`;
        const newPath = [...newParent.path, node.code];

        await this.pg.query(`UPDATE ${this.schema}.tree_nodes SET parent_id=$2, full_code=$3, level=$4, path=$5 WHERE id=$1`,
            [nodeId, newParentId, newFullCode, newParent.level+1, newPath]);

        // Update old parent count
        if (oldParentId) {
            await this.pg.query(`UPDATE ${this.schema}.tree_nodes SET children_count = children_count - 1 WHERE id=$1`, [oldParentId]);
        }
        await this.pg.query(`UPDATE ${this.schema}.tree_nodes SET children_count = children_count + 1 WHERE id=$1`, [newParentId]);

        return await this.pg.query(`SELECT * FROM ${this.schema}.tree_nodes WHERE id=$1`, [nodeId]).then(r => r.rows[0]);
    }
}
"""
}
}

CRUD_TABLE_ENGINE = {
"core": {
    "order": 0, "lang": "javascript",
    "exports": "CRUDTableEngine",
    "content": r"""// CRUD Table Engine — Schema-Driven Dynamic Tables
class CRUDTableEngine {
    constructor(pg, schema) {
        this.pg = pg;
        this.schema = schema;
        this.registry = new Map();
    }

    async registerTable(tableDef) {
        const { name, slug, fields, access_rules, smart_features, indexes } = tableDef;

        // Generate DDL
        const ddl = this.generateDDL(slug, fields);
        await this.pg.query(ddl);

        // Create indexes
        if (indexes) {
            for (const idx of indexes) {
                await this.pg.query(`CREATE INDEX IF NOT EXISTS idx_${slug}_${idx.name} ON ${this.schema}.${slug}(${idx.columns.join(',')})`);
            }
        }

        // Store in registry
        this.registry.set(slug, tableDef);

        // Save to schema_registry
        await this.pg.query(`
            INSERT INTO ${this.schema}.schema_registry (project_id, table_name, schema_doc, is_active)
            VALUES ((SELECT id FROM ${this.schema}.project LIMIT 1), $1, $2, true)
            ON CONFLICT (project_id, table_name, version) DO UPDATE SET schema_doc = $2
        `, [slug, JSON.stringify(tableDef)]);

        return { table: slug, fields: fields.length, created: true };
    }

    generateDDL(slug, fields) {
        let cols = ['id UUID PRIMARY KEY DEFAULT gen_random_uuid()'];

        for (const field of fields) {
            let colDef = `${field.name} ${this.mapType(field.type)}`;
            if (field.required) colDef += ' NOT NULL';
            if (field.default !== undefined) colDef += ` DEFAULT ${this.formatDefault(field.default, field.type)}`;
            if (field.unique) colDef += ' UNIQUE';
            if (field.check) colDef += ` CHECK (${field.name} ${field.check})`;
            cols.push(colDef);
        }

        cols.push('created_at TIMESTAMPTZ DEFAULT now()');
        cols.push('updated_at TIMESTAMPTZ DEFAULT now()');
        cols.push('created_by UUID');
        cols.push('is_deleted BOOLEAN DEFAULT false');

        return `CREATE TABLE IF NOT EXISTS ${this.schema}.${slug} (\n  ${cols.join(',\n  ')}\n)`;
    }

    mapType(type) {
        const map = { string: 'TEXT', number: 'NUMERIC', integer: 'INTEGER', boolean: 'BOOLEAN',
                      date: 'DATE', datetime: 'TIMESTAMPTZ', json: 'JSONB', uuid: 'UUID', text: 'TEXT',
                      money: 'NUMERIC(12,2)', percent: 'NUMERIC(5,2)', email: 'TEXT', phone: 'TEXT', url: 'TEXT' };
        return map[type] || 'TEXT';
    }

    formatDefault(value, type) {
        if (value === null) return 'NULL';
        if (type === 'boolean') return value ? 'true' : 'false';
        if (type === 'number' || type === 'integer' || type === 'money') return value;
        return `'${value}'`;
    }

    async create(table, data, userId) {
        const tableDef = this.registry.get(table);
        if (!tableDef) throw new Error(`Table '${table}' not registered`);

        // Validate required fields
        for (const field of tableDef.fields) {
            if (field.required && !data[field.name]) throw new Error(`Field '${field.name}' is required`);
        }

        const fields = Object.keys(data).filter(k => tableDef.fields.some(f => f.name === k));
        const values = fields.map(f => data[f]);
        const placeholders = fields.map((_, i) => `$${i+1}`);

        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.${table} (${fields.join(',')}, created_by)
            VALUES (${placeholders.join(',')}, $${fields.length+1}) RETURNING *
        `, [...values, userId]);

        return result.rows[0];
    }

    async read(table, id) {
        const result = await this.pg.query(`SELECT * FROM ${this.schema}.${table} WHERE id=$1 AND is_deleted=false`, [id]);
        return result.rows[0] || null;
    }

    async update(table, id, data, userId) {
        const tableDef = this.registry.get(table);
        if (!tableDef) throw new Error(`Table '${table}' not registered`);

        const fields = Object.keys(data).filter(k => tableDef.fields.some(f => f.name === k));
        const sets = fields.map((f, i) => `${f}=$${i+1}`);
        sets.push(`updated_at=now()`);
        const values = fields.map(f => data[f]);

        const result = await this.pg.query(`
            UPDATE ${this.schema}.${table} SET ${sets.join(',')} WHERE id=$${fields.length+1} AND is_deleted=false RETURNING *
        `, [...values, id]);

        return result.rows[0];
    }

    async delete(table, id, soft = true) {
        if (soft) {
            await this.pg.query(`UPDATE ${this.schema}.${table} SET is_deleted=true, updated_at=now() WHERE id=$1`, [id]);
        } else {
            await this.pg.query(`DELETE FROM ${this.schema}.${table} WHERE id=$1`, [id]);
        }
        return { deleted: true };
    }

    async list(table, opts = {}) {
        const { page=1, limit=25, sort='created_at', order='DESC', filters={}, search } = opts;
        const offset = (page-1) * limit;

        let where = ['is_deleted = false'];
        let params = [];
        let i = 1;

        for (const [key, value] of Object.entries(filters)) {
            if (Array.isArray(value)) { where.push(`${key} = ANY($${i++})`); params.push(value); }
            else if (typeof value === 'object' && value.op) {
                where.push(`${key} ${value.op} $${i++}`); params.push(value.value);
            }
            else { where.push(`${key} = $${i++}`); params.push(value); }
        }

        if (search) {
            const tableDef = this.registry.get(table);
            const searchable = tableDef.fields.filter(f => f.searchable || f.type === 'string').map(f => f.name);
            if (searchable.length) {
                where.push(`(${searchable.map(f => `${f} ILIKE $${i}`).join(' OR ')})`);
                params.push(`%${search}%`); i++;
            }
        }

        const countResult = await this.pg.query(`SELECT COUNT(*) as total FROM ${this.schema}.${table} WHERE ${where.join(' AND ')}`, params);
        const total = parseInt(countResult.rows[0].total);

        const result = await this.pg.query(`
            SELECT * FROM ${this.schema}.${table} WHERE ${where.join(' AND ')}
            ORDER BY ${sort} ${order} LIMIT $${i++} OFFSET $${i++}
        `, [...params, limit, offset]);

        return { data: result.rows, total, page, limit, pages: Math.ceil(total/limit) };
    }
}
"""
}
}


async def main():
    print("=" * 60)
    print("QDML — ERP Engines (Invoice, Approval, Tree, CRUD)")
    print("=" * 60)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # Create ERP project
    try:
        await engine.create_project("AI-Auto ERP", "erp", "Schema-driven ERP system")
    except: pass

    # Create modules
    modules = [
        ("Invoice Engine", "invoice-engine"),
        ("Approval Engine", "approval-engine"),
        ("Tree Coding Engine", "tree-engine"),
        ("CRUD Table Engine", "crud-engine"),
    ]
    for name, slug in modules:
        try: await engine.create_module("erp", name, slug, tier="backend", app="erp")
        except: pass

    # Register components and bulks
    engines_data = [
        ("invoice-engine", "Invoice Engine", "invoice-engine-core", INVOICE_ENGINE),
        ("approval-engine", "Approval Engine", "approval-engine-core", APPROVAL_ENGINE),
        ("tree-engine", "Tree Coding Engine", "tree-engine-core", TREE_CODING_ENGINE),
        ("crud-engine", "CRUD Table Engine", "crud-engine-core", CRUD_TABLE_ENGINE),
    ]

    for mod_slug, name, comp_slug, bulks in engines_data:
        try: await engine.create_component(mod_slug, name, comp_slug, kind="service", target="node", project_slug="erp")
        except: pass

        for bname, bdata in bulks.items():
            await engine.create_bulk(comp_slug, bname, bdata["content"], lang=bdata["lang"],
                bulk_order=bdata["order"], exports=bdata.get("exports",""), project_slug="erp")
        print(f"  ✅ {name}: {len(bulks)} bulks")

    # Compile
    from pathlib import Path
    gen = Path("/srv/apps/ai-first/erp/_generated")
    gen.mkdir(parents=True, exist_ok=True)

    for _, _, comp_slug, _ in engines_data:
        code = await engine.compile_component(comp_slug, project_slug="erp")
        if code:
            (gen / f"{comp_slug}.js").write_text(code, encoding="utf-8")
            print(f"  📦 {comp_slug}.js: {code.count(chr(10))+1} lines")

    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"ERP COMPLETE: {stats['bulks']} bulks | {stats['total_lines']:,} lines | {stats['db_size_mb']} MB")
    print(f"{'=' * 60}")
    await pool.close()

if __name__ == "__main__":
    asyncio.run(main())
