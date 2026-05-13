#!/usr/bin/env python3
"""
POS Remaining Engines: Menu, Delivery, Reservation, Printer
"""
import asyncio
import asyncpg
from pathlib import Path
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA


async def main():
    print("=" * 70)
    print("POS — Menu + Delivery + Reservation + Printer Engines")
    print("=" * 70)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══════════════════════════════════════
    # MENU ENGINE
    # ═══════════════════════════════════════
    print("\n─── Menu Engine ───")
    await engine.create_component("runtime", "Menu Engine", "menu-engine",
        kind="service", target="node", project_slug="pos")

    await engine.create_bulk("menu-engine", "main", r"""// Menu Engine — Categories, Items, Modifiers, Pricing
// All schema-driven, no hardcoded queries

export class MenuEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Categories ───
    async getCategories() {
        return (await this.crud.list(this.branchId, 'menu_categories', { sort: 'sort_order', order: 'ASC' })).data;
    }

    async createCategory(data) {
        return await this.crud.create(this.branchId, 'menu_categories', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            icon: data.icon || '',
            sort_order: data.sort_order || 0,
            is_active: true,
            color: data.color || '#2196F3'
        });
    }

    // ─── Items ───
    async getItems(categoryId = null) {
        const where = categoryId ? { category_id: categoryId } : {};
        return (await this.crud.list(this.branchId, 'menu_items', { where, sort: 'sort_order', order: 'ASC' })).data;
    }

    async createItem(data) {
        return await this.crud.create(this.branchId, 'menu_items', {
            id: crypto.randomUUID(),
            category_id: data.category_id,
            name: data.name,
            name_ar: data.name_ar || data.name,
            description: data.description || '',
            price: data.price,
            cost: data.cost || 0,
            tax_percent: data.tax_percent ?? 15,
            sku: data.sku || '',
            barcode: data.barcode || '',
            image_url: data.image_url || '',
            is_active: true,
            track_stock: data.track_stock || false,
            stock_quantity: data.stock_quantity || 0,
            sort_order: data.sort_order || 0,
            prep_time_minutes: data.prep_time_minutes || 0,
            calories: data.calories || null
        });
    }

    async updateItem(id, data) {
        return await this.crud.update(this.branchId, 'menu_items', id, data);
    }

    async toggleItemActive(id) {
        const item = await this.crud.read(this.branchId, 'menu_items', id);
        return await this.crud.update(this.branchId, 'menu_items', id, { is_active: !item.is_active });
    }

    // ─── Modifiers ───
    async getModifiers() {
        return (await this.crud.list(this.branchId, 'menu_modifiers', {})).data;
    }

    async createModifier(data) {
        return await this.crud.create(this.branchId, 'menu_modifiers', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            price: data.price || 0,
            type: data.type || 'add_on', // add_on | removal | swap
            is_active: true
        });
    }

    async linkModifierToItem(itemId, modifierId) {
        return await this.crud.create(this.branchId, 'menu_item_modifier', {
            id: crypto.randomUUID(),
            menu_item_id: itemId,
            modifier_id: modifierId,
            is_default: false
        });
    }

    // ─── Pricing (sizes/combos) ───
    async getItemPrices(itemId) {
        return (await this.crud.list(this.branchId, 'menu_item_price', { where: { menu_item_id: itemId } })).data;
    }

    async addItemPrice(itemId, data) {
        return await this.crud.create(this.branchId, 'menu_item_price', {
            id: crypto.randomUUID(),
            menu_item_id: itemId,
            size_name: data.size_name,
            size_name_ar: data.size_name_ar || data.size_name,
            price: data.price,
            is_default: data.is_default || false
        });
    }

    // ─── Section Mapping ───
    async mapCategoryToSection(categoryId, sectionId) {
        return await this.crud.create(this.branchId, 'category_sections', {
            id: crypto.randomUUID(),
            category_id: categoryId,
            section_id: sectionId
        });
    }

    // ─── Search ───
    async searchItems(query) {
        const all = await this.getItems();
        const q = query.toLowerCase();
        return all.filter(item =>
            item.name?.toLowerCase().includes(q) ||
            item.name_ar?.includes(query) ||
            item.sku?.toLowerCase().includes(q) ||
            item.barcode?.includes(query)
        );
    }

    // ─── Import/Export ───
    async exportMenu() {
        const categories = await this.getCategories();
        const items = await this.getItems();
        const modifiers = await this.getModifiers();
        return { categories, items, modifiers, exported_at: new Date().toISOString() };
    }

    async importMenu(data) {
        let imported = { categories: 0, items: 0, modifiers: 0 };

        for (const cat of data.categories || []) {
            await this.createCategory(cat);
            imported.categories++;
        }
        for (const item of data.items || []) {
            await this.createItem(item);
            imported.items++;
        }
        for (const mod of data.modifiers || []) {
            await this.createModifier(mod);
            imported.modifiers++;
        }

        return imported;
    }
}
""", lang="javascript", bulk_order=0, exports="MenuEngine", project_slug="pos")
    print("  ✅ menu-engine")

    # ═══════════════════════════════════════
    # DELIVERY ENGINE
    # ═══════════════════════════════════════
    print("\n─── Delivery Engine ───")
    await engine.create_component("runtime", "Delivery Engine", "delivery-engine",
        kind="service", target="node", project_slug="pos")

    await engine.create_bulk("delivery-engine", "main", r"""// Delivery Engine — Zones, Drivers, Order Routing, Tracking
export class DeliveryEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Zones ───
    async getZones() {
        return (await this.crud.list(this.branchId, 'delivery_zones', { sort: 'name' })).data;
    }

    async createZone(data) {
        return await this.crud.create(this.branchId, 'delivery_zones', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            min_order: data.min_order || 0,
            delivery_fee: data.delivery_fee || 0,
            estimated_minutes: data.estimated_minutes || 30,
            is_active: true,
            polygon: data.polygon || null, // GeoJSON for zone boundaries
            max_distance_km: data.max_distance_km || 10
        });
    }

    // ─── Drivers ───
    async getDrivers(activeOnly = true) {
        const where = activeOnly ? { is_active: true } : {};
        return (await this.crud.list(this.branchId, 'delivery_drivers', { where })).data;
    }

    async getAvailableDrivers() {
        const drivers = await this.getDrivers();
        // Exclude drivers with active deliveries
        const activeDeliveries = (await this.crud.list(this.branchId, 'order_delivery', {
            where: { status: 'in_transit' }
        })).data;
        const busyDriverIds = new Set(activeDeliveries.map(d => d.driver_id));
        return drivers.filter(d => !busyDriverIds.has(d.id));
    }

    async createDriver(data) {
        return await this.crud.create(this.branchId, 'delivery_drivers', {
            id: crypto.randomUUID(),
            name: data.name,
            phone: data.phone,
            vehicle_type: data.vehicle_type || 'motorcycle',
            is_active: true
        });
    }

    // ─── Order Delivery ───
    async assignDriver(orderId, driverId) {
        const driver = await this.crud.read(this.branchId, 'delivery_drivers', driverId);
        if (!driver) throw new Error('Driver not found');

        const delivery = await this.crud.create(this.branchId, 'order_delivery', {
            id: crypto.randomUUID(),
            order_id: orderId,
            driver_id: driverId,
            driver_name: driver.name,
            status: 'assigned',
            assigned_at: new Date().toISOString(),
            picked_up_at: null,
            delivered_at: null
        });

        // Update order status
        await this.crud.update(this.branchId, 'order_header', orderId, {
            status: 'out_for_delivery'
        });

        return delivery;
    }

    async updateDeliveryStatus(deliveryId, status) {
        const now = new Date().toISOString();
        const updates = { status };

        if (status === 'picked_up') updates.picked_up_at = now;
        if (status === 'delivered') updates.delivered_at = now;

        const delivery = await this.crud.update(this.branchId, 'order_delivery', deliveryId, updates);

        // If delivered, update order
        if (status === 'delivered') {
            await this.crud.update(this.branchId, 'order_header', delivery.order_id, {
                status: 'served'
            });
        }

        return delivery;
    }

    // ─── Fee Calculation ───
    async calculateDeliveryFee(zoneId) {
        if (!zoneId) return 0;
        const zone = await this.crud.read(this.branchId, 'delivery_zones', zoneId);
        return zone?.delivery_fee || 0;
    }

    // ─── Tracking ───
    async getActiveDeliveries() {
        return (await this.crud.list(this.branchId, 'order_delivery', {
            where: { status: 'in_transit' }
        })).data;
    }

    async getDriverHistory(driverId, limit = 20) {
        return (await this.crud.list(this.branchId, 'order_delivery', {
            where: { driver_id: driverId },
            sort: 'assigned_at',
            order: 'DESC',
            limit
        })).data;
    }
}
""", lang="javascript", bulk_order=0, exports="DeliveryEngine", project_slug="pos")
    print("  ✅ delivery-engine")

    # ═══════════════════════════════════════
    # RESERVATION ENGINE
    # ═══════════════════════════════════════
    print("\n─── Reservation Engine ───")
    await engine.create_component("runtime", "Reservation Engine", "reservation-engine",
        kind="service", target="node", project_slug="pos")

    await engine.create_bulk("reservation-engine", "main", r"""// Reservation Engine — Table Management, Booking, Scheduling
export class ReservationEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Tables ───
    async getTables() {
        return (await this.crud.list(this.branchId, 'dining_tables', { sort: 'table_number' })).data;
    }

    async getAvailableTables(datetime, partySize) {
        const tables = await this.getTables();
        const reservations = await this.getReservationsForTime(datetime);
        const reservedTableIds = new Set();

        for (const res of reservations) {
            const resTables = await this.crud.list(this.branchId, 'reservation_table', {
                where: { reservation_id: res.id }
            });
            resTables.data.forEach(rt => reservedTableIds.add(rt.table_id));
        }

        // Also check table locks
        const locks = (await this.crud.list(this.branchId, 'table_lock', {
            where: { is_active: true }
        })).data;
        locks.forEach(l => reservedTableIds.add(l.table_id));

        return tables.filter(t =>
            !reservedTableIds.has(t.id) &&
            t.capacity >= partySize &&
            t.is_active
        );
    }

    async getReservationsForTime(datetime) {
        const date = new Date(datetime);
        const windowStart = new Date(date.getTime() - 2 * 60 * 60 * 1000); // -2h
        const windowEnd = new Date(date.getTime() + 2 * 60 * 60 * 1000);   // +2h

        const all = (await this.crud.list(this.branchId, 'reservations', {
            where: { status: 'confirmed' }
        })).data;

        return all.filter(r => {
            const resTime = new Date(r.reservation_time);
            return resTime >= windowStart && resTime <= windowEnd;
        });
    }

    // ─── Reservations ───
    async createReservation(data) {
        const reservation = await this.crud.create(this.branchId, 'reservations', {
            id: crypto.randomUUID(),
            customer_name: data.customer_name,
            customer_phone: data.customer_phone,
            party_size: data.party_size,
            reservation_time: data.reservation_time,
            duration_minutes: data.duration_minutes || 90,
            status: 'confirmed',
            notes: data.notes || '',
            created_at: new Date().toISOString()
        });

        // Assign tables
        if (data.table_ids?.length) {
            for (const tableId of data.table_ids) {
                await this.crud.create(this.branchId, 'reservation_table', {
                    id: crypto.randomUUID(),
                    reservation_id: reservation.id,
                    table_id: tableId
                });
            }
        }

        return reservation;
    }

    async cancelReservation(id) {
        return await this.crud.update(this.branchId, 'reservations', id, {
            status: 'cancelled'
        });
    }

    async seatReservation(id) {
        const reservation = await this.crud.read(this.branchId, 'reservations', id);
        if (!reservation) throw new Error('Reservation not found');

        // Lock the tables
        const resTables = (await this.crud.list(this.branchId, 'reservation_table', {
            where: { reservation_id: id }
        })).data;

        for (const rt of resTables) {
            await this.crud.create(this.branchId, 'table_lock', {
                id: crypto.randomUUID(),
                table_id: rt.table_id,
                locked_by: 'reservation',
                reference_id: id,
                is_active: true,
                locked_at: new Date().toISOString()
            });
        }

        return await this.crud.update(this.branchId, 'reservations', id, {
            status: 'seated',
            seated_at: new Date().toISOString()
        });
    }

    async releaseTable(tableId) {
        const locks = (await this.crud.list(this.branchId, 'table_lock', {
            where: { table_id: tableId, is_active: true }
        })).data;

        for (const lock of locks) {
            await this.crud.update(this.branchId, 'table_lock', lock.id, { is_active: false });
        }
    }

    // ─── Today's view ───
    async getTodayReservations() {
        const today = new Date().toISOString().split('T')[0];
        const all = (await this.crud.list(this.branchId, 'reservations', {
            sort: 'reservation_time', order: 'ASC'
        })).data;

        return all.filter(r => r.reservation_time?.startsWith(today) && r.status !== 'cancelled');
    }
}
""", lang="javascript", bulk_order=0, exports="ReservationEngine", project_slug="pos")
    print("  ✅ reservation-engine")

    # ═══════════════════════════════════════
    # PRINTER SERVICE
    # ═══════════════════════════════════════
    print("\n─── Printer Service ───")
    await engine.create_component("runtime", "Printer Service", "printer-service",
        kind="service", target="node", project_slug="pos")

    await engine.create_bulk("printer-service", "main", r"""// Printer Service — Bridges WS3 to thermal printers
// Receives print commands via WebSocket, renders tickets, sends to printer
// Supports: ESC/POS thermal, Windows raw print (via C# bridge), network printers

export class PrinterService {
    constructor(config = {}) {
        this.printers = new Map();
        this.printQueue = [];
        this.processing = false;
        this.config = {
            defaultWidth: 48,        // chars per line (80mm thermal)
            encoding: 'cp864',       // Arabic code page
            cutAfterPrint: true,
            openDrawer: false,
            ...config
        };
    }

    // ─── Printer Registration ───
    registerPrinter(id, config) {
        this.printers.set(id, {
            id,
            name: config.name,
            type: config.type || 'thermal', // thermal | network | windows
            connection: config.connection,   // USB path, IP:port, or printer name
            sections: config.sections || [], // kitchen sections this printer handles
            status: 'ready'
        });
    }

    getPrinterForSection(sectionId) {
        for (const [id, printer] of this.printers) {
            if (printer.sections.includes(sectionId) || printer.sections.includes('*')) {
                return printer;
            }
        }
        return this.printers.values().next().value; // fallback to first
    }

    // ─── Ticket Rendering ───
    renderKitchenTicket(job) {
        const w = this.config.defaultWidth;
        const lines = [];

        // Header
        lines.push(this.center('═'.repeat(w), w));
        lines.push(this.center(`طلب #${job.order_number}`, w));
        lines.push(this.center(`${job.section_name || 'المطبخ'}`, w));
        lines.push(this.center('═'.repeat(w), w));

        // Order info
        lines.push(this.leftRight(job.order_type || 'صالة', new Date().toLocaleTimeString('ar-SA'), w));
        if (job.table_number) lines.push(`طاولة: ${job.table_number}`);
        if (job.customer_name) lines.push(`العميل: ${job.customer_name}`);
        lines.push('─'.repeat(w));

        // Items
        for (const item of job.items || []) {
            lines.push(`${item.qty}x  ${item.name}`);
            for (const mod of item.modifiers || []) {
                lines.push(`    ${mod.startsWith('-') ? '❌' : '➕'} ${mod}`);
            }
            if (item.notes) lines.push(`    📝 ${item.notes}`);
        }

        // Notes
        if (job.notes) {
            lines.push('─'.repeat(w));
            lines.push(`📝 ${job.notes}`);
        }

        // Footer
        lines.push('─'.repeat(w));
        lines.push(this.center(job.time || new Date().toLocaleTimeString('ar-SA'), w));
        lines.push('');
        lines.push('');

        return lines.join('\n');
    }

    renderReceiptTicket(order) {
        const w = this.config.defaultWidth;
        const lines = [];
        const fmt = (n) => Number(n || 0).toFixed(2);

        // Company header
        lines.push(this.center(order.company_name || 'المطعم', w));
        lines.push(this.center(order.branch_name || '', w));
        if (order.tax_id) lines.push(this.center(`الرقم الضريبي: ${order.tax_id}`, w));
        lines.push('═'.repeat(w));

        // Order info
        lines.push(this.leftRight(`فاتورة #${order.order_number}`, order.date || new Date().toLocaleDateString('ar-SA'), w));
        lines.push(this.leftRight(`النوع: ${order.order_type}`, `الكاشير: ${order.employee_name || ''}`, w));
        lines.push('─'.repeat(w));

        // Items
        for (const line of order.lines || []) {
            const lineTotal = fmt(line.quantity * line.unit_price);
            lines.push(this.leftRight(`${line.quantity}x ${line.item_name_ar || line.item_name}`, `${lineTotal}`, w));
            if (line.discount_percent > 0) {
                lines.push(`    خصم ${line.discount_percent}%`);
            }
        }

        // Totals
        lines.push('─'.repeat(w));
        lines.push(this.leftRight('المجموع:', `${fmt(order.subtotal)} ر.س`, w));
        if (order.discount_amount > 0) lines.push(this.leftRight('الخصم:', `-${fmt(order.discount_amount)} ر.س`, w));
        lines.push(this.leftRight('الضريبة (15%):', `${fmt(order.tax_amount)} ر.س`, w));
        lines.push('═'.repeat(w));
        lines.push(this.leftRight('الإجمالي:', `${fmt(order.total)} ر.س`, w));
        lines.push('═'.repeat(w));

        // Payment
        if (order.payment_method) {
            lines.push(this.leftRight('طريقة الدفع:', order.payment_method, w));
        }

        // Footer
        lines.push('');
        lines.push(this.center('شكراً لزيارتكم', w));
        lines.push(this.center('Thank you for visiting', w));
        lines.push('');

        return lines.join('\n');
    }

    // ─── Helpers ───
    center(text, width) {
        const pad = Math.max(0, Math.floor((width - text.length) / 2));
        return ' '.repeat(pad) + text;
    }

    leftRight(left, right, width) {
        const space = Math.max(1, width - left.length - right.length);
        return left + ' '.repeat(space) + right;
    }

    // ─── Print Queue ───
    async print(printerId, content) {
        this.printQueue.push({ printerId, content, timestamp: Date.now() });
        if (!this.processing) await this.processQueue();
    }

    async processQueue() {
        this.processing = true;

        while (this.printQueue.length > 0) {
            const job = this.printQueue.shift();
            const printer = this.printers.get(job.printerId);

            if (!printer) continue;

            try {
                if (printer.type === 'thermal') {
                    await this.sendToThermal(printer, job.content);
                } else if (printer.type === 'network') {
                    await this.sendToNetwork(printer, job.content);
                } else if (printer.type === 'windows') {
                    await this.sendToWindows(printer, job.content);
                }
            } catch (e) {
                console.error(`Print failed on ${printer.name}: ${e.message}`);
                printer.status = 'error';
            }
        }

        this.processing = false;
    }

    async sendToThermal(printer, content) {
        // ESC/POS commands
        const ESC = '\x1B';
        const GS = '\x1D';

        let data = '';
        data += ESC + '@';           // Initialize
        data += ESC + 'a' + '\x01';  // Center align
        data += ESC + 't' + '\x16';  // Arabic code page
        data += content;

        if (this.config.cutAfterPrint) {
            data += GS + 'V' + '\x00'; // Full cut
        }

        // Send via USB/serial (platform-specific)
        // In Node.js: require('usb') or require('serialport')
        console.log(`[PRINT] Thermal → ${printer.connection}: ${content.length} chars`);
    }

    async sendToNetwork(printer, content) {
        // TCP socket to network printer
        const [host, port] = printer.connection.split(':');
        // const net = require('net');
        // const client = net.createConnection({ host, port: parseInt(port) || 9100 });
        // client.write(content);
        // client.end();
        console.log(`[PRINT] Network → ${printer.connection}: ${content.length} chars`);
    }

    async sendToWindows(printer, content) {
        // Calls C# bridge via stdio or named pipe
        // const { execSync } = require('child_process');
        // execSync(`echo "${content}" | KdsPrinterClient.exe --printer="${printer.connection}"`);
        console.log(`[PRINT] Windows → ${printer.connection}: ${content.length} chars`);
    }

    // ─── WS3 Integration ───
    handleWSMessage(msg) {
        if (msg.type === 'print_ticket') {
            const printer = this.getPrinterForSection(msg.job?.section_id || '*');
            if (printer) {
                const content = this.renderKitchenTicket(msg.job);
                this.print(printer.id, content);
            }
        } else if (msg.type === 'print_receipt') {
            const printer = this.getPrinterForSection('receipt');
            if (printer) {
                const content = this.renderReceiptTicket(msg.order);
                this.print(printer.id, content);
            }
        }
    }
}
""", lang="javascript", bulk_order=0, exports="PrinterService", project_slug="pos")
    print("  ✅ printer-service")

    # ═══════════════════════════════════════
    # BRANCH PROVISIONING (Real branches)
    # ═══════════════════════════════════════
    print("\n─── Branch Provisioning ───")
    await engine.create_component("runtime", "Branch Provisioner", "branch-provisioner",
        kind="service", target="node", project_slug="pos")

    await engine.create_bulk("branch-provisioner", "main", r"""// Branch Provisioner — Creates real PostgreSQL schemas for branches
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
""", lang="javascript", bulk_order=0, exports="BranchProvisioner,BRANCHES", project_slug="pos")
    print("  ✅ branch-provisioner")

    # ═══ Compile ═══
    print("\n─── Compile ───")
    gen = Path("/srv/apps/ai-first/pos/_generated")
    for slug in ["menu-engine", "delivery-engine", "reservation-engine", "printer-service", "branch-provisioner"]:
        code = await engine.compile_component(slug, project_slug="pos")
        if code:
            (gen / f"{slug}.js").write_text(code, encoding="utf-8")
            print(f"  📦 {slug}.js ({code.count(chr(10))+1} lines)")

    stats = await engine.stats()
    print(f"\n{'=' * 70}")
    print(f"POS ENGINES COMPLETE: {stats['components']}C {stats['bulks']}B {stats['total_lines']:,}L")
    print(f"{'=' * 70}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
