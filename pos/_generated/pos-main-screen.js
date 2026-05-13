// POS Main Screen — MAS.js Module
// Connects to mas-store → WS3 → branch schema
// All data flows through schema-driven CRUD

import masStore from '/lib/mas-store.js';
import { calculateLineTotal, calculateOrderTotals, OrderStatus } from '/lib/order-domain.js';

const POSScreen = {
    state: {
        branch_id: null,
        shift: null,
        currentOrder: null,
        orders: [],
        menuItems: [],
        categories: [],
        modifiers: [],
        paymentMethods: [],
        activeCategory: null
    },

    async init(branchId) {
        this.state.branch_id = branchId;

        // Connect to branch via mas-store → WS3
        await masStore.init({ projectId: branchId });

        // Load essential data
        await this.loadMenu();
        await this.loadShift();

        // Listen for real-time changes
        masStore.on('change', (event) => this.handleStoreChange(event));

        // Render
        this.render();
    },

    async loadMenu() {
        this.state.menuItems = (await masStore.query('menu_items', {})) || [];
        this.state.categories = (await masStore.query('menu_categories', {})) || [];
        this.state.modifiers = (await masStore.query('menu_modifiers', {})) || [];
        this.state.paymentMethods = (await masStore.query('payment_methods', {})) || [];
    },

    async loadShift() {
        const shifts = await masStore.query('pos_shift', { status: 'open' });
        this.state.shift = shifts?.[0] || null;
    },

    handleStoreChange(event) {
        const { table, action, delta } = event;
        if (table === 'order_header' || table === 'order_line') {
            this.refreshOrders();
        }
    },

    // ─── Order Operations ───

    async newOrder(orderType = 'dine_in') {
        const order = await masStore.save('order_header', {
            id: crypto.randomUUID(),
            status: OrderStatus.NEW,
            order_type: orderType,
            shift_id: this.state.shift?.id,
            employee_id: this.state.shift?.employee_id,
            subtotal: 0, tax_amount: 0, discount_amount: 0, total: 0,
            lines: []
        });
        this.state.currentOrder = order;
        this.render();
    },

    async addItem(menuItemId) {
        if (!this.state.currentOrder) await this.newOrder();

        const item = this.state.menuItems.find(i => i.id === menuItemId);
        if (!item) return;

        const line = {
            id: crypto.randomUUID(),
            order_id: this.state.currentOrder.id,
            menu_item_id: item.id,
            item_name: item.name,
            item_name_ar: item.name_ar,
            quantity: 1,
            unit_price: item.price,
            tax_percent: item.tax_percent || 15,
            discount_percent: 0,
            modifiers: [],
            status: 'pending'
        };

        await masStore.save('order_line', line);
        await this.recalculateOrder();
        this.render();
    },

    async recalculateOrder() {
        if (!this.state.currentOrder) return;
        const lines = await masStore.query('order_line', { order_id: this.state.currentOrder.id });
        const totals = calculateOrderTotals(lines);

        this.state.currentOrder = {
            ...this.state.currentOrder,
            ...totals,
            updated_at: new Date().toISOString()
        };
        await masStore.save('order_header', this.state.currentOrder);
    },

    // ─── Render ───

    render() {
        const app = document.getElementById('app');
        if (!app) return;

        app.innerHTML = `
        <div class="pos-layout" dir="rtl">
            <aside class="pos-menu-panel">
                <div class="category-tabs">
                    ${this.state.categories.map(c => `
                        <button class="cat-tab ${this.state.activeCategory === c.id ? 'active' : ''}"
                                onclick="POSScreen.selectCategory('${c.id}')">
                            ${c.name_ar || c.name}
                        </button>
                    `).join('')}
                </div>
                <div class="menu-grid">
                    ${this.getFilteredItems().map(item => `
                        <button class="menu-item-btn" onclick="POSScreen.addItem('${item.id}')">
                            <span class="item-name">${item.name_ar || item.name}</span>
                            <span class="item-price">${item.price} ر.س</span>
                        </button>
                    `).join('')}
                </div>
            </aside>

            <main class="pos-order-panel">
                <div class="order-header">
                    <h2>طلب ${this.state.currentOrder ? '#' + this.state.currentOrder.id.slice(0,8) : 'جديد'}</h2>
                    <button class="btn-new-order" onclick="POSScreen.newOrder()">+ طلب جديد</button>
                </div>
                <div class="order-lines">
                    ${this.renderOrderLines()}
                </div>
                <div class="order-totals">
                    ${this.renderTotals()}
                </div>
                <div class="order-actions">
                    <button class="btn-pay" onclick="POSScreen.openPayment()">💳 دفع</button>
                    <button class="btn-send" onclick="POSScreen.sendToKitchen()">🍳 إرسال للمطبخ</button>
                </div>
            </main>
        </div>`;
    },

    getFilteredItems() {
        if (!this.state.activeCategory) return this.state.menuItems;
        return this.state.menuItems.filter(i => i.category_id === this.state.activeCategory);
    },

    selectCategory(catId) {
        this.state.activeCategory = catId;
        this.render();
    },

    renderOrderLines() {
        if (!this.state.currentOrder) return '<p class="empty">لا يوجد طلب حالي</p>';
        return '<!-- Lines rendered from mas-store query -->';
    },

    renderTotals() {
        const o = this.state.currentOrder;
        if (!o) return '';
        return `
            <div class="total-row"><span>المجموع:</span><span>${o.subtotal?.toFixed(2)} ر.س</span></div>
            <div class="total-row"><span>الضريبة:</span><span>${o.tax_amount?.toFixed(2)} ر.س</span></div>
            <div class="total-row final"><span>الإجمالي:</span><span>${o.total?.toFixed(2)} ر.س</span></div>
        `;
    },

    async sendToKitchen() {
        // Routes order lines to kitchen sections via WS3
        // KDS screens receive only their section's items
    },

    async openPayment() {
        // Opens payment modal with available methods
    }
};

export default POSScreen;
