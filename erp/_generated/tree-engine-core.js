// Tree Coding Engine — Hierarchical Auto-Coding System
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
