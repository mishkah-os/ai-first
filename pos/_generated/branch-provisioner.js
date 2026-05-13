// Branch Provisioner — Creates real PostgreSQL schemas for branches
// Called once per branch setup, generates all 57 tables

import { BranchManager } from './branch-manager.js';

export class BranchProvisioner {
    constructor(pool, schemaRegistry) {
        this.pool = pool;
        this.branchManager = new BranchManager(pool, 'qdml');
        this.schemaRegistry = schemaRegistry; // 57 tables from pos_schema.json
    }

    async provisionBranch(branchConfig) {
        const { id, name, code } = branchConfig;
        const schemaName = `pos_${code}`;

        console.log(`[Provision] Creating schema: ${schemaName}`);

        // 1. Create PostgreSQL schema
        await this.pool.query(`CREATE SCHEMA IF NOT EXISTS ${schemaName}`);

        // 2. Generate and apply all tables from schema registry
        let tableCount = 0;
        for (const table of this.schemaRegistry) {
            const ddl = this.branchManager.generateTableDDL(schemaName, table);
            await this.pool.query(ddl);
            tableCount++;
        }

        // 3. Create indexes
        const indexes = [
            `CREATE INDEX IF NOT EXISTS idx_oh_status ON ${schemaName}.order_header(status)`,
            `CREATE INDEX IF NOT EXISTS idx_oh_shift ON ${schemaName}.order_header(shift_id)`,
            `CREATE INDEX IF NOT EXISTS idx_oh_created ON ${schemaName}.order_header(created_at DESC)`,
            `CREATE INDEX IF NOT EXISTS idx_ol_order ON ${schemaName}.order_line(order_id)`,
            `CREATE INDEX IF NOT EXISTS idx_joh_order ON ${schemaName}.job_order_header(order_id)`,
            `CREATE INDEX IF NOT EXISTS idx_joh_section ON ${schemaName}.job_order_header(section_id, status)`,
            `CREATE INDEX IF NOT EXISTS idx_jod_job ON ${schemaName}.job_order_detail(job_order_id)`,
            `CREATE INDEX IF NOT EXISTS idx_mi_cat ON ${schemaName}.menu_items(category_id)`,
            `CREATE INDEX IF NOT EXISTS idx_shift_status ON ${schemaName}.pos_shift(status)`,
        ];

        for (const idx of indexes) {
            try { await this.pool.query(idx); } catch (e) {}
        }

        // 4. Seed initial data (payment methods, kitchen sections)
        await this.seedDefaults(schemaName, branchConfig);

        // 5. Register in QDML
        await this.pool.query(`
            INSERT INTO qdml.app_instances (app_name, config, status)
            VALUES ($1, $2::jsonb, 'active')
        `, [name, JSON.stringify({ schema: schemaName, code, branch_id: id, tables: tableCount })]);

        console.log(`[Provision] ✅ ${schemaName}: ${tableCount} tables created`);
        return { schema: schemaName, tables: tableCount };
    }

    async seedDefaults(schema, config) {
        // Default payment methods
        const methods = [
            { name: 'نقدي', name_en: 'Cash', type: 'cash', is_default: true },
            { name: 'بطاقة مدى', name_en: 'Mada', type: 'card', is_default: false },
            { name: 'بطاقة ائتمان', name_en: 'Credit Card', type: 'card', is_default: false },
            { name: 'تحويل بنكي', name_en: 'Bank Transfer', type: 'transfer', is_default: false },
        ];

        for (const m of methods) {
            await this.pool.query(`
                INSERT INTO ${schema}.payment_methods (id, name, type, is_default)
                VALUES (gen_random_uuid(), $1, $2, $3)
            `, [m.name, m.type, m.is_default]);
        }

        // Default kitchen sections
        const sections = config.kitchen_sections || [
            { name: 'المطبخ الرئيسي', name_en: 'Main Kitchen' },
            { name: 'المشويات', name_en: 'Grill' },
            { name: 'المشروبات', name_en: 'Beverages' },
            { name: 'التجميع', name_en: 'Expo' },
        ];

        for (const s of sections) {
            await this.pool.query(`
                INSERT INTO ${schema}.kitchen_sections (id, name, is_active)
                VALUES (gen_random_uuid(), $1, true)
            `, [s.name]);
        }
    }

    // Provision all configured branches
    async provisionAll(branches) {
        const results = [];
        for (const branch of branches) {
            const result = await this.provisionBranch(branch);
            results.push({ ...branch, ...result });
        }
        return results;
    }
}

// Pre-configured branches
export const BRANCHES = [
    { id: 'dar-001', name: 'قرية درويش - المركز الرئيسي', code: 'dar' },
    { id: 'club-001', name: 'Clubhouse', code: 'clubhouse' },
    { id: '88-001', name: 'Eighty Eight', code: 'eightyeight' },
    { id: 'remal-001', name: 'رمال', code: 'remal' },
];
