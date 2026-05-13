// KDS Screen — State & Initialization
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

// KDS Screen — Actions (start, complete, bump, recall)

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

// KDS Screen — Render (Dark theme, Arabic RTL)

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
