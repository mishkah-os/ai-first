// POS Finance Engine — Shift Management & Reconciliation
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
