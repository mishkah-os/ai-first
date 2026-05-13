// Order Domain — shared between frontend and backend
// Pure functions, no side effects, no DB calls

export const OrderStatus = {
    NEW: 'new', CONFIRMED: 'confirmed', PREPARING: 'preparing',
    READY: 'ready', SERVED: 'served', PAID: 'paid',
    CANCELLED: 'cancelled', REFUNDED: 'refunded'
};

export const OrderType = {
    DINE_IN: 'dine_in', TAKEAWAY: 'takeaway',
    DELIVERY: 'delivery', DRIVE_THRU: 'drive_thru'
};

export function calculateLineTotal(line) {
    const base = (line.quantity || 1) * (line.unit_price || 0);
    const modifierTotal = (line.modifiers || []).reduce((s, m) => s + (m.price_adjustment || 0), 0);
    const subtotal = base + modifierTotal;
    const discount = subtotal * ((line.discount_percent || 0) / 100);
    const afterDiscount = subtotal - discount;
    const tax = afterDiscount * ((line.tax_percent || 15) / 100);
    return { subtotal, discount, tax, total: afterDiscount + tax };
}

export function calculateOrderTotals(lines) {
    let subtotal = 0, totalDiscount = 0, totalTax = 0, total = 0;

    for (const line of lines) {
        const calc = calculateLineTotal(line);
        subtotal += calc.subtotal;
        totalDiscount += calc.discount;
        totalTax += calc.tax;
        total += calc.total;
    }

    return { subtotal, discount: totalDiscount, tax: totalTax, total };
}

export function validateOrderTransition(currentStatus, newStatus) {
    const allowed = {
        new: ['confirmed', 'cancelled'],
        confirmed: ['preparing', 'cancelled'],
        preparing: ['ready', 'cancelled'],
        ready: ['served', 'cancelled'],
        served: ['paid', 'refunded'],
        paid: ['refunded'],
        cancelled: [],
        refunded: []
    };
    return (allowed[currentStatus] || []).includes(newStatus);
}

export function formatOrderNumber(sequence, branchCode = '001') {
    const date = new Date();
    const y = date.getFullYear().toString().slice(-2);
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${branchCode}-${y}${m}${d}-${String(sequence).padStart(4, '0')}`;
}

export function groupLinesBySection(lines, categorySections) {
    const groups = new Map();
    for (const line of lines) {
        const mapping = categorySections.find(cs => cs.category_id === line.category_id);
        const sectionId = mapping?.section_id || 'default';
        if (!groups.has(sectionId)) groups.set(sectionId, []);
        groups.get(sectionId).push(line);
    }
    return groups;
}
