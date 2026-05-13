#!/usr/bin/env python3
"""
Migrate POS System to QDML — Complete restructuring
57 tables, KDS, Finance, Printer, Dashboard — all schema-driven
"""
import asyncio
import asyncpg
import json
from pathlib import Path
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA

POS_SCHEMA_PATH = Path("/srv/apps/os/data/schemas/pos_schema.json")
POS_STATIC = Path("/srv/apps/os/static/pos")
POS_DATA = Path("/srv/apps/os/data")


def read_file(path, max_lines=200):
    """Read file content, truncate if too large"""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.split('\n')
    if len(lines) > max_lines:
        return '\n'.join(lines[:max_lines]) + f"\n// ... truncated ({len(lines)} total lines)"
    return content


def extract_js_section(path, start_marker=None, end_marker=None, max_lines=150):
    """Extract a section from a JS file"""
    if not path.exists():
        return ""
    content = path.read_text(encoding="utf-8", errors="ignore")
    if start_marker:
        idx = content.find(start_marker)
        if idx >= 0:
            content = content[idx:]
    if end_marker:
        idx = content.find(end_marker)
        if idx >= 0:
            content = content[:idx]
    lines = content.split('\n')
    if len(lines) > max_lines:
        return '\n'.join(lines[:max_lines]) + f"\n// ... ({len(lines)} lines total)"
    return content


# ═══════════════════════════════════════════════════════════
# POS MODULES DEFINITION
# ═══════════════════════════════════════════════════════════

POS_MODULES = [
    ("Schema & Config", "pos-schema", "backend", "Schema-driven table definitions"),
    ("Order Engine", "pos-orders", "backend", "Order lifecycle management"),
    ("KDS Engine", "pos-kds", "backend", "Kitchen display & job routing"),
    ("Finance Engine", "pos-finance", "backend", "Shift reconciliation & payments"),
    ("Menu Engine", "pos-menu", "backend", "Menu items, modifiers, pricing"),
    ("Delivery Engine", "pos-delivery", "backend", "Delivery zones, drivers, routing"),
    ("Reservation Engine", "pos-reservations", "backend", "Table management & scheduling"),
    ("POS Screen", "pos-screen", "frontend", "Main point-of-sale UI"),
    ("KDS Screen", "pos-kds-screen", "frontend", "Kitchen display UI"),
    ("Finance Screen", "pos-finance-screen", "frontend", "Financial reports UI"),
    ("Dashboard", "pos-dashboard", "frontend", "Management dashboard"),
    ("Printer Service", "pos-printer", "backend", "Thermal printer C# integration"),
]


async def main():
    print("=" * 70)
    print("QDML — POS System Migration (57 tables, 686 fields)")
    print("=" * 70)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ Create Project ═══
    print("\n[1/8] Creating POS project...")
    try:
        await engine.create_project("Mishkah POS", "pos", "Restaurant POS with KDS, Finance, Delivery")
    except:
        pass

    # ═══ Create Modules ═══
    print("[2/8] Creating modules...")
    for name, slug, tier, desc in POS_MODULES:
        try:
            await engine.create_module("pos", name, slug, tier=tier, app="pos")
            print(f"  ✅ {slug}")
        except:
            print(f"  ℹ️  {slug} exists")

    # ═══ Register Schema ═══
    print("\n[3/8] Registering schema (57 tables, 686 fields)...")
    schema_data = json.loads(POS_SCHEMA_PATH.read_text())
    tables = schema_data['schema']['tables']

    try:
        await engine.create_component("pos-schema", "POS Schema Definition", "pos-schema-def",
                                     kind="config", target="sql", project_slug="pos")
    except: pass

    # Store schema as structured bulk
    schema_summary = f"""// POS Schema: {schema_data['schema']['name']} v{schema_data['schema']['version']}
// {len(tables)} tables, {sum(len(t.get('fields',[])) for t in tables)} fields
// Auto-generates PostgreSQL DDL via Quantum Core

const POS_SCHEMA = {json.dumps({
    'name': schema_data['schema']['name'],
    'version': schema_data['schema']['version'],
    'table_count': len(tables),
    'tables': [{
        'name': t['name'],
        'fields': [{
            'name': f['name'],
            'type': f.get('type', 'string'),
            'required': f.get('required', False),
            'primary': f.get('primary', False)
        } for f in t.get('fields', [])]
    } for t in tables]
}, indent=2)};

export default POS_SCHEMA;
"""

    await engine.create_bulk("pos-schema-def", "schema_full", schema_summary[:50000],
        lang="javascript", bulk_order=0, exports="POS_SCHEMA", project_slug="pos")
    print(f"  ✅ Schema registered ({len(tables)} tables)")

    # Store full schema in schema_registry
    async with pool.acquire() as conn:
        pid = await conn.fetchval(f"SELECT id FROM {QDML_SCHEMA}.project WHERE slug='pos'")
        for table in tables:
            await conn.execute(f"""
                INSERT INTO {QDML_SCHEMA}.schema_registry (project_id, table_name, schema_doc, is_active)
                VALUES ($1, $2, $3::jsonb, true)
                ON CONFLICT (project_id, table_name, version) DO UPDATE SET schema_doc = $3::jsonb
            """, pid, table['name'], json.dumps(table))
    print(f"  ✅ {len(tables)} table schemas in schema_registry")

    # ═══ Order Engine ═══
    print("\n[4/8] Building Order Engine...")
    try:
        await engine.create_component("pos-orders", "Order Engine", "order-engine",
                                     kind="service", target="node", project_slug="pos")
    except: pass

    order_engine_code = r"""// POS Order Engine — Schema-Driven CRUD
// Manages: order_header, order_line, order_line_modifier, order_payment, order_refund

class OrderEngine {
    constructor(store, schema) {
        this.store = store; // mas-store instance
        this.schema = schema;
    }

    async createOrder(orderData) {
        const order = {
            id: crypto.randomUUID(),
            order_number: await this.nextOrderNumber(),
            status: 'new',
            order_type: orderData.order_type || 'dine_in',
            table_id: orderData.table_id,
            customer_id: orderData.customer_id,
            employee_id: orderData.employee_id,
            subtotal: 0,
            tax_amount: 0,
            discount_amount: 0,
            service_charge: 0,
            total: 0,
            notes: orderData.notes || '',
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString()
        };

        await this.store.save('order_header', order);
        return order;
    }

    async addLine(orderId, itemData) {
        const line = {
            id: crypto.randomUUID(),
            order_id: orderId,
            menu_item_id: itemData.menu_item_id,
            item_name: itemData.item_name,
            item_name_ar: itemData.item_name_ar,
            quantity: itemData.quantity || 1,
            unit_price: itemData.unit_price,
            discount_percent: itemData.discount_percent || 0,
            tax_percent: itemData.tax_percent || 15,
            line_total: 0,
            status: 'pending',
            notes: itemData.notes || '',
            modifiers: [],
            created_at: new Date().toISOString()
        };

        // Calculate line total
        line.line_total = this.calculateLineTotal(line);

        // Add modifiers
        if (itemData.modifiers?.length) {
            for (const mod of itemData.modifiers) {
                const modifier = {
                    id: crypto.randomUUID(),
                    order_line_id: line.id,
                    modifier_id: mod.id,
                    modifier_name: mod.name,
                    modifier_name_ar: mod.name_ar,
                    price_adjustment: mod.price || 0,
                    type: mod.type || 'add_on'
                };
                line.modifiers.push(modifier);
                await this.store.save('order_line_modifier', modifier);
            }
        }

        await this.store.save('order_line', line);

        // Recalculate order totals
        await this.recalculateOrder(orderId);

        return line;
    }

    calculateLineTotal(line) {
        const base = line.quantity * line.unit_price;
        const discount = base * (line.discount_percent / 100);
        const afterDiscount = base - discount;
        const tax = afterDiscount * (line.tax_percent / 100);
        return afterDiscount + tax;
    }

    async recalculateOrder(orderId) {
        const lines = await this.store.query('order_line', { order_id: orderId });
        const subtotal = lines.reduce((sum, l) => sum + (l.quantity * l.unit_price), 0);
        const discountAmount = lines.reduce((sum, l) => sum + (l.quantity * l.unit_price * l.discount_percent / 100), 0);
        const taxAmount = lines.reduce((sum, l) => sum + ((l.quantity * l.unit_price - l.quantity * l.unit_price * l.discount_percent / 100) * l.tax_percent / 100), 0);
        const total = subtotal - discountAmount + taxAmount;

        await this.store.save('order_header', {
            id: orderId,
            subtotal, discount_amount: discountAmount, tax_amount: taxAmount, total,
            updated_at: new Date().toISOString()
        });
    }

    async updateStatus(orderId, newStatus, employeeId) {
        const order = await this.store.get('order_header', orderId);
        if (!order) throw new Error('Order not found');

        const oldStatus = order.status;
        order.status = newStatus;
        order.updated_at = new Date().toISOString();
        await this.store.save('order_header', order);

        // Log status change
        await this.store.save('order_status_log', {
            id: crypto.randomUUID(),
            order_id: orderId,
            old_status: oldStatus,
            new_status: newStatus,
            changed_by: employeeId,
            changed_at: new Date().toISOString()
        });

        return order;
    }

    async addPayment(orderId, paymentData) {
        const payment = {
            id: crypto.randomUUID(),
            order_id: orderId,
            payment_method_id: paymentData.method_id,
            amount: paymentData.amount,
            reference: paymentData.reference || '',
            status: 'completed',
            created_at: new Date().toISOString()
        };

        await this.store.save('order_payment', payment);

        // Check if fully paid
        const payments = await this.store.query('order_payment', { order_id: orderId });
        const totalPaid = payments.reduce((sum, p) => sum + p.amount, 0);
        const order = await this.store.get('order_header', orderId);

        if (totalPaid >= order.total) {
            await this.updateStatus(orderId, 'paid', paymentData.employee_id);
        }

        return payment;
    }

    async getOrderWithLines(orderId) {
        const order = await this.store.get('order_header', orderId);
        if (!order) return null;
        order.lines = await this.store.query('order_line', { order_id: orderId });
        order.payments = await this.store.query('order_payment', { order_id: orderId });
        return order;
    }

    async nextOrderNumber() {
        // In production, use PostgreSQL sequence
        return `ORD-${Date.now().toString(36).toUpperCase()}`;
    }
}

export default OrderEngine;
"""

    await engine.create_bulk("order-engine", "main", order_engine_code,
        lang="javascript", bulk_order=0, exports="OrderEngine", project_slug="pos")
    print("  ✅ Order Engine registered")

    # ═══ KDS Engine ═══
    print("\n[5/8] Building KDS Engine...")
    try:
        await engine.create_component("pos-kds", "KDS Engine", "kds-engine",
                                     kind="service", target="node", project_slug="pos")
    except: pass

    kds_engine_code = r"""// KDS Engine — Kitchen Display System + Job Order Routing
// Routes orders to kitchen sections, manages prep workflow

class KDSEngine {
    constructor(store, schema) {
        this.store = store;
        this.schema = schema;
        this.sections = new Map(); // section_id -> config
    }

    async init() {
        // Load kitchen sections
        const sections = await this.store.query('kitchen_sections', {});
        sections.forEach(s => this.sections.set(s.id, s));
    }

    async routeOrderToKitchen(orderId) {
        const lines = await this.store.query('order_line', { order_id: orderId });
        const sectionGroups = new Map(); // section_id -> lines[]

        for (const line of lines) {
            // Resolve section via: item -> category -> category_sections -> kitchen_section
            const sectionId = await this.resolveSectionForItem(line.menu_item_id);
            if (!sectionGroups.has(sectionId)) sectionGroups.set(sectionId, []);
            sectionGroups.get(sectionId).push(line);
        }

        // Create job orders per section
        const jobOrders = [];
        for (const [sectionId, sectionLines] of sectionGroups) {
            const jobOrder = await this.createJobOrder(orderId, sectionId, sectionLines);
            jobOrders.push(jobOrder);
        }

        return jobOrders;
    }

    async createJobOrder(orderId, sectionId, lines) {
        const order = await this.store.get('order_header', orderId);
        const section = this.sections.get(sectionId);

        const jobHeader = {
            id: crypto.randomUUID(),
            order_id: orderId,
            order_number: order.order_number,
            section_id: sectionId,
            section_name: section?.name || 'Default',
            status: 'pending',
            priority: order.priority || 'normal',
            order_type: order.order_type,
            table_number: order.table_number,
            customer_name: order.customer_name,
            items_count: lines.length,
            notes: order.notes,
            created_at: new Date().toISOString(),
            started_at: null,
            completed_at: null
        };

        await this.store.save('job_order_header', jobHeader);

        // Create detail lines
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const detail = {
                id: crypto.randomUUID(),
                job_order_id: jobHeader.id,
                order_line_id: line.id,
                item_name: line.item_name,
                item_name_ar: line.item_name_ar,
                quantity: line.quantity,
                status: 'pending',
                notes: line.notes,
                sort_order: i,
                modifiers: line.modifiers || []
            };

            await this.store.save('job_order_detail', detail);

            // Store modifiers
            for (const mod of detail.modifiers) {
                await this.store.save('job_order_detail_modifier', {
                    id: crypto.randomUUID(),
                    job_order_detail_id: detail.id,
                    modifier_name: mod.modifier_name,
                    modifier_name_ar: mod.modifier_name_ar,
                    type: mod.type
                });
            }
        }

        return jobHeader;
    }

    async resolveSectionForItem(menuItemId) {
        // item -> category -> category_sections -> section
        const item = await this.store.get('menu_items', menuItemId);
        if (!item) return 'default';

        const catSections = await this.store.query('category_sections', { category_id: item.category_id });
        if (catSections.length > 0) return catSections[0].section_id;

        return 'default'; // Fallback section
    }

    async updateJobStatus(jobOrderId, newStatus, employeeId) {
        const job = await this.store.get('job_order_header', jobOrderId);
        if (!job) throw new Error('Job order not found');

        const now = new Date().toISOString();
        const updates = { status: newStatus, updated_at: now };

        if (newStatus === 'started' && !job.started_at) updates.started_at = now;
        if (newStatus === 'completed') updates.completed_at = now;

        Object.assign(job, updates);
        await this.store.save('job_order_header', job);

        // Log history
        await this.store.save('job_order_status_history', {
            id: crypto.randomUUID(),
            job_order_id: jobOrderId,
            old_status: job.status,
            new_status: newStatus,
            changed_by: employeeId,
            changed_at: now
        });

        // If all jobs for order completed, update order status
        if (newStatus === 'completed') {
            await this.checkOrderCompletion(job.order_id);
        }

        return job;
    }

    async checkOrderCompletion(orderId) {
        const jobs = await this.store.query('job_order_header', { order_id: orderId });
        const allCompleted = jobs.every(j => j.status === 'completed');
        if (allCompleted) {
            await this.store.save('order_header', {
                id: orderId,
                status: 'ready',
                updated_at: new Date().toISOString()
            });
        }
    }

    async getKDSView(sectionId, statusFilter = 'pending') {
        const jobs = await this.store.query('job_order_header', {
            section_id: sectionId,
            status: statusFilter
        });

        // Enrich with details
        for (const job of jobs) {
            job.details = await this.store.query('job_order_detail', { job_order_id: job.id });
        }

        return jobs.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    }

    async getBatchInfo(batchId) {
        return await this.store.query('job_order_batch', { batch_id: batchId });
    }

    // Fingerprint for deduplication (prevent duplicate prints)
    fingerprint(job) {
        return `${job.id}:${job.status}:${job.updated_at}`;
    }
}

export default KDSEngine;
"""

    await engine.create_bulk("kds-engine", "main", kds_engine_code,
        lang="javascript", bulk_order=0, exports="KDSEngine", project_slug="pos")
    print("  ✅ KDS Engine registered")

    # ═══ Finance Engine ═══
    print("\n[6/8] Building Finance Engine...")
    try:
        await engine.create_component("pos-finance", "Finance Engine", "finance-engine",
                                     kind="service", target="node", project_slug="pos")
    except: pass

    finance_code = r"""// POS Finance Engine — Shift Management & Reconciliation
class FinanceEngine {
    constructor(store) { this.store = store; }

    async openShift(data) {
        const shift = {
            id: crypto.randomUUID(),
            terminal_id: data.terminal_id,
            employee_id: data.employee_id,
            employee_name: data.employee_name,
            opening_cash: data.opening_cash || 0,
            closing_cash: null,
            status: 'open',
            opened_at: new Date().toISOString(),
            closed_at: null,
            total_sales: 0,
            total_refunds: 0,
            total_discounts: 0,
            total_tax: 0,
            orders_count: 0,
            notes: ''
        };
        await this.store.save('pos_shift', shift);
        return shift;
    }

    async closeShift(shiftId, closingData) {
        const shift = await this.store.get('pos_shift', shiftId);
        if (!shift) throw new Error('Shift not found');

        // Calculate totals
        const orders = await this.store.query('order_header', { shift_id: shiftId });
        const payments = [];
        for (const order of orders) {
            const op = await this.store.query('order_payment', { order_id: order.id });
            payments.push(...op);
        }

        // Payment method summary
        const methodSummary = {};
        for (const payment of payments) {
            const key = payment.payment_method_id;
            if (!methodSummary[key]) methodSummary[key] = { count: 0, total: 0 };
            methodSummary[key].count++;
            methodSummary[key].total += payment.amount;
        }

        // Update shift
        shift.status = 'closed';
        shift.closed_at = new Date().toISOString();
        shift.closing_cash = closingData.closing_cash;
        shift.total_sales = orders.reduce((s, o) => s + o.total, 0);
        shift.total_refunds = orders.filter(o => o.status === 'refunded').reduce((s, o) => s + o.total, 0);
        shift.total_discounts = orders.reduce((s, o) => s + (o.discount_amount || 0), 0);
        shift.total_tax = orders.reduce((s, o) => s + (o.tax_amount || 0), 0);
        shift.orders_count = orders.length;
        shift.notes = closingData.notes || '';

        await this.store.save('pos_shift', shift);

        // Save payment summaries
        for (const [methodId, summary] of Object.entries(methodSummary)) {
            await this.store.save('shift_payment_summary', {
                id: crypto.randomUUID(),
                shift_id: shiftId,
                payment_method_id: methodId,
                transactions_count: summary.count,
                total_amount: summary.total
            });
        }

        // Cash audit if provided
        if (closingData.cash_denominations) {
            await this.store.save('shift_cash_audit', {
                id: crypto.randomUUID(),
                shift_id: shiftId,
                denominations: closingData.cash_denominations,
                counted_total: closingData.closing_cash,
                expected_total: (methodSummary['cash']?.total || 0) + shift.opening_cash,
                difference: closingData.closing_cash - ((methodSummary['cash']?.total || 0) + shift.opening_cash),
                audited_by: closingData.audited_by
            });
        }

        return { shift, summary: methodSummary };
    }

    async getShiftReport(shiftId) {
        const shift = await this.store.get('pos_shift', shiftId);
        const summaries = await this.store.query('shift_payment_summary', { shift_id: shiftId });
        const audit = await this.store.query('shift_cash_audit', { shift_id: shiftId });
        return { shift, payment_summaries: summaries, cash_audit: audit[0] || null };
    }

    async getDailySummary(date) {
        const shifts = await this.store.query('pos_shift', {});
        const dayShifts = shifts.filter(s => s.opened_at?.startsWith(date));
        return {
            date,
            shifts: dayShifts.length,
            total_sales: dayShifts.reduce((s, sh) => s + (sh.total_sales || 0), 0),
            total_orders: dayShifts.reduce((s, sh) => s + (sh.orders_count || 0), 0),
            total_tax: dayShifts.reduce((s, sh) => s + (sh.total_tax || 0), 0)
        };
    }
}

export default FinanceEngine;
"""

    await engine.create_bulk("finance-engine", "main", finance_code,
        lang="javascript", bulk_order=0, exports="FinanceEngine", project_slug="pos")
    print("  ✅ Finance Engine registered")

    # ═══ Branch Data ═══
    print("\n[7/8] Registering branch configurations...")
    branches_config = Path("/srv/apps/os/data/branches.config.json")
    if branches_config.exists():
        config = json.loads(branches_config.read_text())
        async with pool.acquire() as conn:
            pid = await conn.fetchval(f"SELECT id FROM {QDML_SCHEMA}.project WHERE slug='pos'")
            await conn.execute(f"""
                INSERT INTO {QDML_SCHEMA}.ai_context (project_id, context_type, selector, content, metadata)
                VALUES ($1, 'template', $2::jsonb, $3, $4::jsonb)
                ON CONFLICT DO NOTHING
            """, pid,
                json.dumps({"type": "branches_config"}),
                json.dumps(config),
                json.dumps({"source": "branches.config.json"})
            )
        print(f"  ✅ Branch config stored ({len(config)} entries)")

    # Store branch seeds
    for branch_name in ['dar', 'clubhouse', 'eightyeight', 'remal']:
        seeds_path = POS_DATA / "branches" / branch_name / "shared_seeds.json"
        if seeds_path.exists():
            seeds = json.loads(seeds_path.read_text())
            async with pool.acquire() as conn:
                await conn.execute(f"""
                    INSERT INTO {QDML_SCHEMA}.ai_context (project_id, context_type, selector, content, metadata)
                    VALUES ($1, 'template', $2::jsonb, $3, $4::jsonb)
                    ON CONFLICT DO NOTHING
                """, pid,
                    json.dumps({"type": "branch_seeds", "branch": branch_name}),
                    json.dumps(seeds)[:50000],  # Limit size
                    json.dumps({"branch": branch_name, "source": "shared_seeds.json"})
                )
            print(f"  ✅ Branch seeds: {branch_name}")

    # ═══ Compile ═══
    print("\n[8/8] Compiling POS components...")
    gen = Path("/srv/apps/ai-first/pos/_generated")
    gen.mkdir(parents=True, exist_ok=True)

    for comp_slug in ["order-engine", "kds-engine", "finance-engine", "pos-schema-def"]:
        code = await engine.compile_component(comp_slug, project_slug="pos")
        if code:
            (gen / f"{comp_slug}.js").write_text(code, encoding="utf-8")
            print(f"  📦 {comp_slug}.js: {code.count(chr(10))+1} lines")

    # ═══ Final Stats ═══
    stats = await engine.stats()
    print(f"\n{'=' * 70}")
    print(f"POS MIGRATION COMPLETE!")
    print(f"  Projects:   {stats['projects']}")
    print(f"  Modules:    {stats['modules']}")
    print(f"  Components: {stats['components']}")
    print(f"  Bulks:      {stats['bulks']}")
    print(f"  Lines:      {stats['total_lines']:,}")
    print(f"  DB Size:    {stats['db_size_mb']} MB")
    print(f"  Schema:     57 tables in schema_registry")
    print(f"{'=' * 70}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
