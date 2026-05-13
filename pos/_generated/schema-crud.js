// Schema-Driven CRUD — generates all queries from schema definition
// No hardcoded SQL. Schema changes = automatic query changes.

export class SchemaCRUD {
    constructor(pool, branchManager, schemaRegistry) {
        this.pool = pool;
        this.branches = branchManager;
        this.registry = schemaRegistry; // pos_schema.json loaded
    }

    async create(branchId, tableName, data) {
        const schema = this.branches.getSchema(branchId);
        if (!schema) throw new Error(`Branch ${branchId} not provisioned`);

        const tableDef = this.registry.getTable(tableName);
        if (!tableDef) throw new Error(`Table ${tableName} not in schema`);

        // Validate against schema
        this.validate(data, tableDef);

        // Build INSERT dynamically from data keys that exist in schema
        const validFields = Object.keys(data).filter(k =>
            tableDef.fields.some(f => f.name === k)
        );

        const cols = validFields.join(', ');
        const placeholders = validFields.map((_, i) => `$${i + 1}`).join(', ');
        const values = validFields.map(k => this.coerce(data[k], tableDef.fields.find(f => f.name === k)));

        const result = await this.pool.query(
            `INSERT INTO ${schema}.${tableName} (${cols}) VALUES (${placeholders}) RETURNING *`,
            values
        );

        return result.rows[0];
    }

    async read(branchId, tableName, id) {
        const schema = this.branches.getSchema(branchId);
        const result = await this.pool.query(
            `SELECT * FROM ${schema}.${tableName} WHERE id = $1`, [id]
        );
        return result.rows[0] || null;
    }

    async update(branchId, tableName, id, data) {
        const schema = this.branches.getSchema(branchId);
        const tableDef = this.registry.getTable(tableName);

        const validFields = Object.keys(data).filter(k =>
            k !== 'id' && tableDef.fields.some(f => f.name === k)
        );

        const sets = validFields.map((f, i) => `${f} = $${i + 1}`);
        sets.push(`updated_at = now()`);
        const values = validFields.map(k => this.coerce(data[k], tableDef.fields.find(f => f.name === k)));
        values.push(id);

        const result = await this.pool.query(
            `UPDATE ${schema}.${tableName} SET ${sets.join(', ')} WHERE id = $${values.length} RETURNING *`,
            values
        );

        return result.rows[0];
    }

    async delete(branchId, tableName, id) {
        const schema = this.branches.getSchema(branchId);
        await this.pool.query(`DELETE FROM ${schema}.${tableName} WHERE id = $1`, [id]);
        return { deleted: true };
    }

    async list(branchId, tableName, opts = {}) {
        const schema = this.branches.getSchema(branchId);
        const { page = 1, limit = 50, sort = 'created_at', order = 'DESC', where = {} } = opts;
        const offset = (page - 1) * limit;

        let conditions = [];
        let params = [];
        let i = 1;

        for (const [key, value] of Object.entries(where)) {
            conditions.push(`${key} = $${i++}`);
            params.push(value);
        }

        const whereClause = conditions.length ? `WHERE ${conditions.join(' AND ')}` : '';

        const countResult = await this.pool.query(
            `SELECT COUNT(*) as total FROM ${schema}.${tableName} ${whereClause}`, params
        );

        params.push(limit, offset);
        const result = await this.pool.query(
            `SELECT * FROM ${schema}.${tableName} ${whereClause} ORDER BY ${sort} ${order} LIMIT $${i++} OFFSET $${i}`,
            params
        );

        return {
            data: result.rows,
            total: parseInt(countResult.rows[0].total),
            page, limit,
            pages: Math.ceil(parseInt(countResult.rows[0].total) / limit)
        };
    }

    validate(data, tableDef) {
        for (const field of tableDef.fields) {
            if (field.required && !data[field.name] && field.name !== 'id') {
                throw new Error(`Field '${field.name}' is required in ${tableDef.name}`);
            }
        }
    }

    coerce(value, fieldDef) {
        if (value === null || value === undefined) return null;
        if (!fieldDef) return value;

        switch (fieldDef.type) {
            case 'json': case 'object': case 'array':
                return typeof value === 'string' ? value : JSON.stringify(value);
            case 'number': case 'money':
                return Number(value);
            case 'integer':
                return parseInt(value);
            case 'boolean':
                return Boolean(value);
            default:
                return value;
        }
    }
}
