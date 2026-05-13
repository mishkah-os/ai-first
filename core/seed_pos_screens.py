#!/usr/bin/env python3
"""
POS Screens — KDS, Finance, Dashboard
All connected to mas-store → WS3 → branch schema
"""
import asyncio
import asyncpg
from pathlib import Path
from qdml_engine import QDMLEngine
from config import DATABASE_URL, QDML_SCHEMA


async def main():
    print("=" * 70)
    print("POS Screens — KDS + Finance + Dashboard (Real MAS.js)")
    print("=" * 70)

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"})
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══════════════════════════════════════
    # KDS SCREEN
    # ═══════════════════════════════════════
    print("\n─── KDS Screen (Kitchen Display) ───")

    await engine.create_component("screen-kds", "KDS Main Screen", "kds-main-screen",
        kind="screen", target="mas-js", project_slug="pos")

    await engine.create_bulk("kds-main-screen", "state", r"""// KDS Screen — State & Initialization
import masStore from '/lib/mas-store.js';
import { groupLinesBySection } from '/lib/order-domain.js';

const KDS = {
    state: {
        branch_id: null,
        section_id: null,       // Which kitchen section this display shows
        activeTab: 'prep',      // prep | expo | handoff | delivery
        jobs: [],               // Current job orders for this section
        sections: [],           // All kitchen sections
        settings: {
            autoPrint: false,
            printerId: null,
            theme: 'dark',
            soundEnabled: true,
            autoRefresh: 5000
        }
    },

    async init(branchId, sectionId = null) {
        this.state.branch_id = branchId;
        this.state.section_id = sectionId;

        await masStore.init({ projectId: branchId });

        // Load kitchen sections
        this.state.sections = await masStore.query('kitchen_sections', {}) || [];

        // If no section specified, show all
        if (!sectionId && this.state.sections.length > 0) {
            this.state.section_id = this.state.sections[0].id;
        }

        // Load active jobs
        await this.loadJobs();

        // Real-time updates
        masStore.on('change', (e) => this.handleChange(e));

        // Auto-refresh fallback
        setInterval(() => this.loadJobs(), this.state.settings.autoRefresh);

        this.render();
    },

    async loadJobs() {
        const filter = { status: this.getStatusForTab() };
        if (this.state.section_id && this.state.activeTab === 'prep') {
            filter.section_id = this.state.section_id;
        }

        this.state.jobs = await masStore.query('job_order_header', filter) || [];

        // Enrich with details
        for (const job of this.state.jobs) {
            job.details = await masStore.query('job_order_detail', { job_order_id: job.id }) || [];
            for (const detail of job.details) {
                detail.modifiers = await masStore.query('job_order_detail_modifier', { job_order_detail_id: detail.id }) || [];
            }
        }

        // Sort by priority then time
        this.state.jobs.sort((a, b) => {
            if (a.priority === 'urgent' && b.priority !== 'urgent') return -1;
            if (b.priority === 'urgent' && a.priority !== 'urgent') return 1;
            return new Date(a.created_at) - new Date(b.created_at);
        });

        this.render();
    },

    getStatusForTab() {
        const map = { prep: 'pending', expo: 'completed', handoff: 'ready', delivery: 'delivery_pending' };
        return map[this.state.activeTab] || 'pending';
    },

    handleChange(event) {
        const { table } = event;
        if (table === 'job_order_header' || table === 'job_order_detail') {
            this.loadJobs();
            if (this.state.settings.soundEnabled) this.playAlert();
        }
    },

    playAlert() {
        try { new Audio('/assets/kds-alert.mp3').play(); } catch (e) {}
    }
};
""", lang="javascript", bulk_order=0, exports="KDS", project_slug="pos")

    await engine.create_bulk("kds-main-screen", "actions", r"""// KDS Screen — Actions (start, complete, bump, recall)

Object.assign(KDS, {
    async startJob(jobId) {
        await masStore.save('job_order_header', {
            id: jobId,
            status: 'started',
            started_at: new Date().toISOString()
        });

        await masStore.save('job_order_status_history', {
            id: crypto.randomUUID(),
            job_order_id: jobId,
            old_status: 'pending',
            new_status: 'started',
            changed_at: new Date().toISOString()
        });

        await this.loadJobs();
    },

    async completeJob(jobId) {
        await masStore.save('job_order_header', {
            id: jobId,
            status: 'completed',
            completed_at: new Date().toISOString()
        });

        await masStore.save('job_order_status_history', {
            id: crypto.randomUUID(),
            job_order_id: jobId,
            old_status: 'started',
            new_status: 'completed',
            changed_at: new Date().toISOString()
        });

        // Check if all jobs for this order are done
        const job = this.state.jobs.find(j => j.id === jobId);
        if (job) {
            const allJobs = await masStore.query('job_order_header', { order_id: job.order_id });
            const allDone = allJobs.every(j => j.status === 'completed' || j.id === jobId);
            if (allDone) {
                await masStore.save('order_header', {
                    id: job.order_id,
                    status: 'ready',
                    updated_at: new Date().toISOString()
                });
            }
        }

        await this.loadJobs();
    },

    async bumpJob(jobId) {
        // Move to next station (expo → handoff → delivery)
        const job = this.state.jobs.find(j => j.id === jobId);
        if (!job) return;

        const nextStatus = {
            completed: 'ready',
            ready: 'served'
        };

        const next = nextStatus[job.status];
        if (next) {
            await masStore.save('job_order_header', { id: jobId, status: next });
            await this.loadJobs();
        }
    },

    async recallJob(jobId) {
        // Pull back from expo to prep
        await masStore.save('job_order_header', { id: jobId, status: 'pending', started_at: null, completed_at: null });
        await this.loadJobs();
    },

    async updateLineStatus(detailId, newStatus) {
        await masStore.save('job_order_detail', { id: detailId, status: newStatus });
    },

    async printTicket(jobId) {
        const job = this.state.jobs.find(j => j.id === jobId);
        if (!job) return;

        // Send to printer service via WS
        const printData = {
            type: 'print_ticket',
            job: {
                order_number: job.order_number,
                section: job.section_name,
                order_type: job.order_type,
                table_number: job.table_number,
                items: job.details.map(d => ({
                    name: d.item_name_ar || d.item_name,
                    qty: d.quantity,
                    modifiers: d.modifiers.map(m => m.modifier_name_ar || m.modifier_name),
                    notes: d.notes
                })),
                notes: job.notes,
                time: new Date().toLocaleTimeString('ar-SA')
            }
        };

        // mas-store will send via WS to printer service
        masStore.ws?.send(JSON.stringify(printData));
    },

    setTab(tab) {
        this.state.activeTab = tab;
        this.loadJobs();
    },

    setSection(sectionId) {
        this.state.section_id = sectionId;
        this.loadJobs();
    }
});
""", lang="javascript", bulk_order=1, exports="", depends="state", project_slug="pos")

    await engine.create_bulk("kds-main-screen", "render", r"""// KDS Screen — Render (Dark theme, Arabic RTL)

Object.assign(KDS, {
    render() {
        const app = document.getElementById('app');
        if (!app) return;

        const { jobs, sections, activeTab, section_id, settings } = this.state;

        app.innerHTML = `
        <div class="kds-app ${settings.theme}" dir="rtl">
            <!-- Top Bar -->
            <header class="kds-header">
                <div class="kds-tabs">
                    ${['prep', 'expo', 'handoff', 'delivery'].map(tab => `
                        <button class="kds-tab ${activeTab === tab ? 'active' : ''}"
                                onclick="KDS.setTab('${tab}')">
                            ${this.tabLabel(tab)}
                            <span class="tab-count">${this.countForTab(tab)}</span>
                        </button>
                    `).join('')}
                </div>

                <div class="kds-sections">
                    ${sections.map(s => `
                        <button class="section-btn ${section_id === s.id ? 'active' : ''}"
                                onclick="KDS.setSection('${s.id}')">
                            ${s.name_ar || s.name}
                        </button>
                    `).join('')}
                </div>

                <div class="kds-actions">
                    <button onclick="KDS.toggleSettings()">⚙️</button>
                    <span class="kds-clock" id="kdsClock"></span>
                </div>
            </header>

            <!-- Tickets Grid -->
            <main class="kds-grid">
                ${jobs.length === 0 ? '<div class="kds-empty">لا توجد طلبات</div>' : ''}
                ${jobs.map(job => this.renderTicket(job)).join('')}
            </main>
        </div>`;

        // Start clock
        this.startClock();
    },

    renderTicket(job) {
        const elapsed = this.getElapsedTime(job.created_at);
        const urgentClass = elapsed > 600 ? 'urgent' : elapsed > 300 ? 'warning' : '';

        return `
        <div class="kds-ticket ${urgentClass} ${job.priority === 'urgent' ? 'priority-urgent' : ''}"
             data-id="${job.id}">
            <div class="ticket-header">
                <span class="ticket-number">#${job.order_number || job.id.slice(0,6)}</span>
                <span class="ticket-type ${job.order_type}">${this.typeLabel(job.order_type)}</span>
                <span class="ticket-time">${this.formatElapsed(elapsed)}</span>
            </div>

            ${job.table_number ? `<div class="ticket-table">🪑 طاولة ${job.table_number}</div>` : ''}

            <div class="ticket-items">
                ${(job.details || []).map(item => `
                    <div class="ticket-item ${item.status === 'completed' ? 'done' : ''}">
                        <span class="item-qty">${item.quantity}x</span>
                        <span class="item-name">${item.item_name_ar || item.item_name}</span>
                        ${(item.modifiers || []).map(m => `
                            <div class="item-modifier ${m.type}">
                                ${m.type === 'removal' ? '❌' : '➕'} ${m.modifier_name_ar || m.modifier_name}
                            </div>
                        `).join('')}
                        ${item.notes ? `<div class="item-notes">📝 ${item.notes}</div>` : ''}
                    </div>
                `).join('')}
            </div>

            ${job.notes ? `<div class="ticket-notes">📝 ${job.notes}</div>` : ''}

            <div class="ticket-actions">
                ${job.status === 'pending' ? `
                    <button class="btn-start" onclick="KDS.startJob('${job.id}')">▶️ بدء</button>
                ` : ''}
                ${job.status === 'started' ? `
                    <button class="btn-done" onclick="KDS.completeJob('${job.id}')">✅ جاهز</button>
                ` : ''}
                ${job.status === 'completed' ? `
                    <button class="btn-bump" onclick="KDS.bumpJob('${job.id}')">➡️ تسليم</button>
                ` : ''}
                <button class="btn-print" onclick="KDS.printTicket('${job.id}')">🖨️</button>
                <button class="btn-recall" onclick="KDS.recallJob('${job.id}')">↩️</button>
            </div>
        </div>`;
    },

    tabLabel(tab) {
        const labels = { prep: '🍳 التحضير', expo: '📦 التجميع', handoff: '🤝 التسليم', delivery: '🚗 التوصيل' };
        return labels[tab] || tab;
    },

    typeLabel(type) {
        const labels = { dine_in: 'صالة', takeaway: 'سفري', delivery: 'توصيل', drive_thru: 'سيارة' };
        return labels[type] || type;
    },

    countForTab(tab) {
        // Would query mas-store for count per status
        return this.state.activeTab === tab ? this.state.jobs.length : '·';
    },

    getElapsedTime(created) {
        return Math.floor((Date.now() - new Date(created).getTime()) / 1000);
    },

    formatElapsed(seconds) {
        const m = Math.floor(seconds / 60);
        const s = seconds % 60;
        return `${m}:${String(s).padStart(2, '0')}`;
    },

    startClock() {
        const el = document.getElementById('kdsClock');
        if (el) {
            setInterval(() => {
                el.textContent = new Date().toLocaleTimeString('ar-SA');
            }, 1000);
        }
    },

    toggleSettings() {
        // Open settings panel
    }
});

// CSS injected as module
const KDS_STYLES = `
.kds-app{min-height:100vh;font-family:-apple-system,sans-serif;background:#1a1a2e;color:#eee}
.kds-app.dark{background:#0d0d1a;color:#f0f0f0}
.kds-header{display:flex;align-items:center;padding:8px 16px;background:#16213e;border-bottom:2px solid #0f3460;gap:16px}
.kds-tabs{display:flex;gap:4px}
.kds-tab{padding:8px 16px;border:none;background:#1a1a2e;color:#aaa;border-radius:6px;cursor:pointer;display:flex;align-items:center;gap:6px;font-size:14px}
.kds-tab.active{background:#0f3460;color:#fff}
.tab-count{background:#e94560;color:#fff;padding:1px 6px;border-radius:10px;font-size:11px}
.kds-sections{display:flex;gap:4px;margin-right:auto}
.section-btn{padding:6px 12px;border:1px solid #333;background:transparent;color:#aaa;border-radius:4px;cursor:pointer;font-size:12px}
.section-btn.active{border-color:#e94560;color:#e94560}
.kds-clock{font-size:18px;font-weight:bold;color:#53c6f0}
.kds-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;padding:16px;overflow-y:auto;max-height:calc(100vh - 60px)}
.kds-ticket{background:#16213e;border:2px solid #1a1a2e;border-radius:12px;overflow:hidden;transition:.2s}
.kds-ticket.warning{border-color:#f59e0b}
.kds-ticket.urgent{border-color:#e94560;animation:pulse 1s infinite}
.kds-ticket.priority-urgent{box-shadow:0 0 12px rgba(233,69,96,.4)}
@keyframes pulse{50%{border-color:#ff6b8a}}
.ticket-header{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;background:#0f3460}
.ticket-number{font-weight:bold;font-size:16px}
.ticket-type{font-size:11px;padding:2px 8px;border-radius:4px;background:#1a1a2e}
.ticket-type.delivery{background:#e94560;color:#fff}
.ticket-type.takeaway{background:#f59e0b;color:#000}
.ticket-time{font-size:13px;color:#53c6f0;font-weight:bold}
.ticket-table{padding:4px 12px;background:#1a1a2e;font-size:12px;text-align:center}
.ticket-items{padding:8px 12px}
.ticket-item{padding:6px 0;border-bottom:1px solid #1a1a2e;display:flex;flex-wrap:wrap;gap:4px;align-items:baseline}
.ticket-item.done{opacity:.4;text-decoration:line-through}
.item-qty{font-weight:bold;color:#53c6f0;min-width:30px}
.item-name{font-size:14px}
.item-modifier{font-size:11px;padding:1px 6px;border-radius:4px;background:#1a1a2e;color:#aaa;width:100%;margin-right:34px}
.item-modifier.removal{color:#e94560}
.item-notes{font-size:11px;color:#f59e0b;width:100%;margin-right:34px}
.ticket-notes{padding:6px 12px;font-size:12px;color:#f59e0b;background:#1a1a2e;margin:4px 8px;border-radius:4px}
.ticket-actions{display:flex;gap:4px;padding:8px;justify-content:center}
.ticket-actions button{padding:6px 12px;border:none;border-radius:6px;cursor:pointer;font-size:12px}
.btn-start{background:#2196F3;color:#fff}.btn-done{background:#4CAF50;color:#fff}
.btn-bump{background:#FF9800;color:#fff}.btn-print{background:#333;color:#fff}.btn-recall{background:#666;color:#fff}
.kds-empty{grid-column:1/-1;text-align:center;padding:60px;font-size:24px;opacity:.5}
`;

// Inject styles
if (typeof document !== 'undefined') {
    const style = document.createElement('style');
    style.textContent = KDS_STYLES;
    document.head.appendChild(style);
}

export default KDS;
""", lang="javascript", bulk_order=2, exports="default", depends="state,actions", project_slug="pos")
    print("  ✅ kds-main-screen (3 bulks: state, actions, render)")

    # ═══════════════════════════════════════
    # FINANCE SCREEN
    # ═══════════════════════════════════════
    print("\n─── Finance Screen ───")

    await engine.create_component("screen-finance", "Finance Screen", "finance-screen",
        kind="screen", target="mas-js", project_slug="pos")

    await engine.create_bulk("finance-screen", "main", r"""// Finance Screen — Shift Management & Reconciliation
import masStore from '/lib/mas-store.js';

const Finance = {
    state: {
        branch_id: null,
        currentShift: null,
        shifts: [],
        paymentMethods: [],
        view: 'shift' // shift | daily | orders
    },

    async init(branchId) {
        this.state.branch_id = branchId;
        await masStore.init({ projectId: branchId });

        this.state.paymentMethods = await masStore.query('payment_methods', {}) || [];
        await this.loadShifts();
        this.render();
    },

    async loadShifts() {
        this.state.shifts = await masStore.query('pos_shift', {}) || [];
        this.state.currentShift = this.state.shifts.find(s => s.status === 'open') || null;
    },

    async openShift(employeeId, openingCash) {
        const shift = {
            id: crypto.randomUUID(),
            employee_id: employeeId,
            status: 'open',
            opening_cash: openingCash,
            opened_at: new Date().toISOString(),
            total_sales: 0,
            orders_count: 0
        };
        await masStore.save('pos_shift', shift);
        this.state.currentShift = shift;
        this.render();
    },

    async closeShift(closingCash, notes) {
        if (!this.state.currentShift) return;

        const shiftId = this.state.currentShift.id;

        // Get all orders for this shift
        const orders = await masStore.query('order_header', { shift_id: shiftId }) || [];
        const payments = [];
        for (const order of orders) {
            const op = await masStore.query('order_payment', { order_id: order.id }) || [];
            payments.push(...op);
        }

        // Calculate totals
        const totalSales = orders.reduce((s, o) => s + (o.total || 0), 0);
        const totalTax = orders.reduce((s, o) => s + (o.tax_amount || 0), 0);
        const totalDiscount = orders.reduce((s, o) => s + (o.discount_amount || 0), 0);

        // Payment breakdown
        const breakdown = {};
        for (const p of payments) {
            const key = p.payment_method_id || 'cash';
            if (!breakdown[key]) breakdown[key] = { count: 0, total: 0 };
            breakdown[key].count++;
            breakdown[key].total += p.amount;
        }

        // Update shift
        await masStore.save('pos_shift', {
            id: shiftId,
            status: 'closed',
            closing_cash: closingCash,
            closed_at: new Date().toISOString(),
            total_sales: totalSales,
            total_tax: totalTax,
            total_discounts: totalDiscount,
            orders_count: orders.length,
            notes
        });

        // Save payment summaries
        for (const [methodId, data] of Object.entries(breakdown)) {
            await masStore.save('shift_payment_summary', {
                id: crypto.randomUUID(),
                shift_id: shiftId,
                payment_method_id: methodId,
                transactions_count: data.count,
                total_amount: data.total
            });
        }

        this.state.currentShift = null;
        await this.loadShifts();
        this.render();

        return { totalSales, orders: orders.length, breakdown };
    },

    render() {
        const app = document.getElementById('app');
        if (!app) return;

        app.innerHTML = `
        <div class="finance-app" dir="rtl">
            <header class="finance-header">
                <h1>💰 المالية</h1>
                <div class="finance-tabs">
                    <button class="${this.state.view === 'shift' ? 'active' : ''}" onclick="Finance.setView('shift')">الوردية</button>
                    <button class="${this.state.view === 'daily' ? 'active' : ''}" onclick="Finance.setView('daily')">يومي</button>
                    <button class="${this.state.view === 'orders' ? 'active' : ''}" onclick="Finance.setView('orders')">الطلبات</button>
                </div>
            </header>

            <main class="finance-content">
                ${this.state.view === 'shift' ? this.renderShiftView() : ''}
                ${this.state.view === 'daily' ? this.renderDailyView() : ''}
                ${this.state.view === 'orders' ? this.renderOrdersView() : ''}
            </main>
        </div>`;
    },

    renderShiftView() {
        const shift = this.state.currentShift;

        if (!shift) {
            return `
            <div class="finance-card center">
                <h2>لا يوجد وردية مفتوحة</h2>
                <form onsubmit="Finance.handleOpenShift(event)">
                    <div class="form-group">
                        <label>الرصيد الافتتاحي (ر.س)</label>
                        <input type="number" name="opening_cash" value="500" step="0.01" required>
                    </div>
                    <button type="submit" class="btn-primary">فتح وردية</button>
                </form>
            </div>`;
        }

        return `
        <div class="shift-summary">
            <div class="shift-status open">
                <h2>وردية مفتوحة</h2>
                <p>منذ: ${new Date(shift.opened_at).toLocaleTimeString('ar-SA')}</p>
                <p>الافتتاحي: ${shift.opening_cash} ر.س</p>
            </div>

            <div class="shift-stats">
                <div class="stat-card"><h3>${shift.total_sales || 0}</h3><p>المبيعات (ر.س)</p></div>
                <div class="stat-card"><h3>${shift.orders_count || 0}</h3><p>الطلبات</p></div>
            </div>

            <form onsubmit="Finance.handleCloseShift(event)" class="close-shift-form">
                <h3>إغلاق الوردية</h3>
                <div class="form-group">
                    <label>النقد المعدود (ر.س)</label>
                    <input type="number" name="closing_cash" step="0.01" required>
                </div>
                <div class="form-group">
                    <label>ملاحظات</label>
                    <textarea name="notes"></textarea>
                </div>
                <button type="submit" class="btn-danger">إغلاق الوردية</button>
            </form>
        </div>`;
    },

    renderDailyView() {
        return `<div class="finance-card"><h2>التقرير اليومي</h2><p>قيد الإنشاء...</p></div>`;
    },

    renderOrdersView() {
        return `<div class="finance-card"><h2>سجل الطلبات</h2><p>قيد الإنشاء...</p></div>`;
    },

    setView(v) { this.state.view = v; this.render(); },

    handleOpenShift(e) {
        e.preventDefault();
        const cash = parseFloat(new FormData(e.target).get('opening_cash'));
        this.openShift('current_employee', cash);
    },

    handleCloseShift(e) {
        e.preventDefault();
        const fd = new FormData(e.target);
        this.closeShift(parseFloat(fd.get('closing_cash')), fd.get('notes'));
    }
};

export default Finance;
""", lang="javascript", bulk_order=0, exports="default", project_slug="pos")
    print("  ✅ finance-screen")

    # ═══════════════════════════════════════
    # DASHBOARD SCREEN
    # ═══════════════════════════════════════
    print("\n─── Dashboard Screen ───")

    await engine.create_component("screen-dashboard", "Dashboard Screen", "dashboard-screen",
        kind="screen", target="mas-js", project_slug="pos")

    await engine.create_bulk("dashboard-screen", "main", r"""// POS Dashboard — Management Overview
import masStore from '/lib/mas-store.js';

const Dashboard = {
    state: {
        branch_id: null,
        stats: {},
        recentOrders: [],
        topItems: [],
        shiftSummary: null
    },

    async init(branchId) {
        this.state.branch_id = branchId;
        await masStore.init({ projectId: branchId });
        await this.loadStats();
        this.render();

        // Refresh every 30 seconds
        setInterval(() => this.loadStats(), 30000);
    },

    async loadStats() {
        const orders = await masStore.query('order_header', {}) || [];
        const today = new Date().toISOString().split('T')[0];
        const todayOrders = orders.filter(o => o.created_at?.startsWith(today));

        this.state.stats = {
            todaySales: todayOrders.reduce((s, o) => s + (o.total || 0), 0),
            todayOrders: todayOrders.length,
            avgTicket: todayOrders.length > 0 ? todayOrders.reduce((s, o) => s + (o.total || 0), 0) / todayOrders.length : 0,
            openOrders: orders.filter(o => !['paid', 'cancelled', 'refunded'].includes(o.status)).length
        };

        this.state.recentOrders = todayOrders.sort((a, b) => new Date(b.created_at) - new Date(a.created_at)).slice(0, 10);

        // Shift info
        const shifts = await masStore.query('pos_shift', { status: 'open' }) || [];
        this.state.shiftSummary = shifts[0] || null;
    },

    render() {
        const app = document.getElementById('app');
        if (!app) return;

        const { stats, recentOrders, shiftSummary } = this.state;

        app.innerHTML = `
        <div class="dash-app" dir="rtl">
            <header class="dash-header">
                <h1>📊 لوحة التحكم</h1>
                <div class="dash-meta">
                    <span class="dash-date">${new Date().toLocaleDateString('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</span>
                    ${shiftSummary ? `<span class="shift-badge open">وردية مفتوحة</span>` : `<span class="shift-badge closed">لا وردية</span>`}
                </div>
            </header>

            <div class="dash-stats-grid">
                <div class="dash-stat-card primary">
                    <h3>${stats.todaySales?.toFixed(2) || 0} ر.س</h3>
                    <p>مبيعات اليوم</p>
                </div>
                <div class="dash-stat-card success">
                    <h3>${stats.todayOrders || 0}</h3>
                    <p>طلبات اليوم</p>
                </div>
                <div class="dash-stat-card warning">
                    <h3>${stats.avgTicket?.toFixed(2) || 0} ر.س</h3>
                    <p>متوسط الفاتورة</p>
                </div>
                <div class="dash-stat-card info">
                    <h3>${stats.openOrders || 0}</h3>
                    <p>طلبات نشطة</p>
                </div>
            </div>

            <div class="dash-grid-2">
                <div class="dash-card">
                    <h3>آخر الطلبات</h3>
                    <table class="dash-table">
                        <thead><tr><th>الرقم</th><th>النوع</th><th>المبلغ</th><th>الحالة</th><th>الوقت</th></tr></thead>
                        <tbody>
                            ${recentOrders.map(o => `
                            <tr>
                                <td>#${(o.id || '').slice(0, 6)}</td>
                                <td>${o.order_type || '—'}</td>
                                <td>${o.total?.toFixed(2) || 0} ر.س</td>
                                <td><span class="status-badge ${o.status}">${o.status}</span></td>
                                <td>${o.created_at ? new Date(o.created_at).toLocaleTimeString('ar-SA', { hour: '2-digit', minute: '2-digit' }) : '—'}</td>
                            </tr>`).join('')}
                        </tbody>
                    </table>
                </div>

                <div class="dash-card">
                    <h3>ملخص سريع</h3>
                    <div class="quick-actions">
                        <a href="/pos" class="quick-btn">🛒 نقطة البيع</a>
                        <a href="/kds" class="quick-btn">🍳 شاشة المطبخ</a>
                        <a href="/finance" class="quick-btn">💰 المالية</a>
                        <a href="/menu" class="quick-btn">📋 القائمة</a>
                    </div>
                </div>
            </div>
        </div>`;
    }
};

export default Dashboard;
""", lang="javascript", bulk_order=0, exports="default", project_slug="pos")
    print("  ✅ dashboard-screen")

    # ═══════════════════════════════════════
    # COMPILE ALL
    # ═══════════════════════════════════════
    print("\n─── Compile ───")
    gen = Path("/srv/apps/ai-first/pos/_generated")
    gen.mkdir(parents=True, exist_ok=True)

    components_to_compile = [
        "kds-main-screen",
        "finance-screen",
        "dashboard-screen"
    ]

    for slug in components_to_compile:
        code = await engine.compile_component(slug, project_slug="pos")
        if code:
            (gen / f"{slug}.js").write_text(code, encoding="utf-8")
            print(f"  📦 {slug}.js ({code.count(chr(10))+1} lines)")

    # ═══ Stats ═══
    stats = await engine.stats()
    print(f"\n{'=' * 70}")
    print(f"POS COMPLETE:")
    print(f"  Backend:  BranchManager + SchemaCRUD + WS3Handler")
    print(f"  Domain:   OrderDomain (shared pure functions)")
    print(f"  Screens:  POS + KDS + Finance + Dashboard")
    print(f"  Schema:   57 tables in registry")
    print(f"  System:   {stats['projects']}P {stats['modules']}M {stats['components']}C {stats['bulks']}B {stats['total_lines']:,}L")
    print(f"{'=' * 70}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
