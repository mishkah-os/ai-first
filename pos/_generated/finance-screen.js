// Finance Screen — Shift Management & Reconciliation
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
