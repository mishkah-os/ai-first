// Branch Manager — PostgreSQL schema isolation per branch
// Each branch gets its own PostgreSQL schema with all POS tables
// Data never mixes between branches

export class BranchManager {
    constructor(pool, masterSchema) {
        this.pool = pool;
        this.masterSchema = masterSchema; // 'qdml'
        this.branches = new Map();
    }

    async loadBranches() {
        const rows = await this.pool.query(
            `SELECT * FROM ${this.masterSchema}.app_instances WHERE kit_id IS NOT NULL`
        );
        for (const row of rows.rows) {
            this.branches.set(row.id, row);
        }
        return this.branches;
    }

    async provisionBranch(branchId, branchName, config = {}) {
        const schemaName = `pos_${branchId.replace(/-/g, '_')}`;

        // Create isolated PostgreSQL schema
        await this.pool.query(`CREATE SCHEMA IF NOT EXISTS ${schemaName}`);

        // Generate DDL from pos_schema.json and apply
        const tables = config.schema?.tables || [];
        for (const table of tables) {
            const ddl = this.generateTableDDL(schemaName, table);
            await this.pool.query(ddl);
        }

        // Register branch
        this.branches.set(branchId, { id: branchId, name: branchName, schema: schemaName, config });

        return { schema: schemaName, tables: tables.length };
    }

    generateTableDDL(schema, tableDef) {
        const cols = ['id UUID PRIMARY KEY DEFAULT gen_random_uuid()'];

        for (const field of tableDef.fields || []) {
            if (field.name === 'id') continue; // Skip, already added
            let col = `${field.name} ${this.pgType(field.type)}`;
            if (field.required) col += ' NOT NULL';
            if (field.default !== undefined) col += ` DEFAULT ${this.pgDefault(field.default, field.type)}`;
            cols.push(col);
        }

        cols.push('created_at TIMESTAMPTZ DEFAULT now()');
        cols.push('updated_at TIMESTAMPTZ DEFAULT now()');

        return `CREATE TABLE IF NOT EXISTS ${schema}.${tableDef.name} (\n  ${cols.join(',\n  ')}\n)`;
    }

    pgType(type) {
        const map = {
            string: 'TEXT', text: 'TEXT', number: 'NUMERIC', integer: 'INTEGER',
            boolean: 'BOOLEAN', date: 'DATE', datetime: 'TIMESTAMPTZ',
            json: 'JSONB', uuid: 'UUID', money: 'NUMERIC(12,2)',
            array: 'JSONB', object: 'JSONB'
        };
        return map[type] || 'TEXT';
    }

    pgDefault(value, type) {
        if (value === null) return 'NULL';
        if (type === 'boolean') return value ? 'true' : 'false';
        if (type === 'json' || type === 'object' || type === 'array') return `'${JSON.stringify(value)}'::jsonb`;
        if (typeof value === 'number') return String(value);
        return `'${value}'`;
    }

    getSchema(branchId) {
        const branch = this.branches.get(branchId);
        return branch?.schema || null;
    }
}
