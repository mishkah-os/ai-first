// CRUD Table Engine — Schema-Driven Dynamic Tables
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
