// POS Order Engine — Schema-Driven CRUD
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
