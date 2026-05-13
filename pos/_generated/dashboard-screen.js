// POS Dashboard — Management Overview
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
