// Invoice Engine — Schema-Driven Invoice Generation
class InvoiceEngine {
    constructor(pg, schema) {
        this.pg = pg;
        this.schema = schema;
        this.counter = null;
    }

    async init() {
        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.invoices (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_number TEXT UNIQUE NOT NULL,
            type TEXT DEFAULT 'invoice' CHECK (type IN ('invoice','quote','credit_note','debit_note')),
            customer_id UUID,
            customer_name TEXT,
            customer_tax_id TEXT,
            date DATE DEFAULT CURRENT_DATE,
            due_date DATE,
            currency TEXT DEFAULT 'SAR',
            subtotal NUMERIC(12,2) DEFAULT 0,
            tax_amount NUMERIC(12,2) DEFAULT 0,
            discount_amount NUMERIC(12,2) DEFAULT 0,
            total NUMERIC(12,2) DEFAULT 0,
            status TEXT DEFAULT 'draft' CHECK (status IN ('draft','sent','paid','overdue','cancelled')),
            notes TEXT,
            meta JSONB DEFAULT '{}',
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ DEFAULT now()
        )`);

        await this.pg.query(`CREATE TABLE IF NOT EXISTS ${this.schema}.invoice_lines (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            invoice_id UUID REFERENCES ${this.schema}.invoices(id) ON DELETE CASCADE,
            line_order INT DEFAULT 0,
            item_code TEXT,
            description TEXT NOT NULL,
            quantity NUMERIC(10,3) DEFAULT 1,
            unit_price NUMERIC(12,2) NOT NULL,
            discount_percent NUMERIC(5,2) DEFAULT 0,
            tax_percent NUMERIC(5,2) DEFAULT 15,
            line_total NUMERIC(12,2) GENERATED ALWAYS AS (
                quantity * unit_price * (1 - discount_percent/100) * (1 + tax_percent/100)
            ) STORED,
            meta JSONB DEFAULT '{}'
        )`);

        await this.pg.query(`CREATE SEQUENCE IF NOT EXISTS ${this.schema}.invoice_seq START 1000`);
    }

    async generateNumber(prefix = 'INV') {
        const result = await this.pg.query(`SELECT nextval('${this.schema}.invoice_seq') as num`);
        const num = result.rows[0].num;
        const year = new Date().getFullYear();
        return `${prefix}-${year}-${String(num).padStart(5, '0')}`;
    }

    async create(data) {
        const number = await this.generateNumber(data.type === 'quote' ? 'QUO' : 'INV');

        const result = await this.pg.query(`
            INSERT INTO ${this.schema}.invoices
            (invoice_number, type, customer_id, customer_name, customer_tax_id, date, due_date, currency, notes, meta)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            RETURNING *
        `, [number, data.type||'invoice', data.customer_id, data.customer_name,
            data.customer_tax_id, data.date||new Date(), data.due_date,
            data.currency||'SAR', data.notes, JSON.stringify(data.meta||{})]);

        const invoice = result.rows[0];

        // Add lines
        if (data.lines?.length) {
            for (let i = 0; i < data.lines.length; i++) {
                const line = data.lines[i];
                await this.pg.query(`
                    INSERT INTO ${this.schema}.invoice_lines
                    (invoice_id, line_order, item_code, description, quantity, unit_price, discount_percent, tax_percent)
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                `, [invoice.id, i, line.item_code, line.description,
                    line.quantity||1, line.unit_price, line.discount_percent||0, line.tax_percent||15]);
            }
        }

        // Recalculate totals
        await this.recalculate(invoice.id);
        return await this.get(invoice.id);
    }

    async recalculate(invoiceId) {
        await this.pg.query(`
            UPDATE ${this.schema}.invoices SET
                subtotal = (SELECT COALESCE(SUM(quantity * unit_price), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                discount_amount = (SELECT COALESCE(SUM(quantity * unit_price * discount_percent / 100), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                tax_amount = (SELECT COALESCE(SUM(quantity * unit_price * (1 - discount_percent/100) * tax_percent / 100), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                total = (SELECT COALESCE(SUM(line_total), 0) FROM ${this.schema}.invoice_lines WHERE invoice_id = $1),
                updated_at = now()
            WHERE id = $1
        `, [invoiceId]);
    }

    async get(id) {
        const inv = await this.pg.query(`SELECT * FROM ${this.schema}.invoices WHERE id = $1`, [id]);
        if (!inv.rows.length) return null;
        const lines = await this.pg.query(`SELECT * FROM ${this.schema}.invoice_lines WHERE invoice_id = $1 ORDER BY line_order`, [id]);
        return { ...inv.rows[0], lines: lines.rows };
    }

    async list(filters = {}) {
        let where = ['1=1'];
        let params = [];
        let i = 1;

        if (filters.status) { where.push(`status = $${i++}`); params.push(filters.status); }
        if (filters.customer_id) { where.push(`customer_id = $${i++}`); params.push(filters.customer_id); }
        if (filters.type) { where.push(`type = $${i++}`); params.push(filters.type); }
        if (filters.from_date) { where.push(`date >= $${i++}`); params.push(filters.from_date); }
        if (filters.to_date) { where.push(`date <= $${i++}`); params.push(filters.to_date); }

        const result = await this.pg.query(`
            SELECT * FROM ${this.schema}.invoices WHERE ${where.join(' AND ')} ORDER BY created_at DESC LIMIT ${filters.limit||50}
        `, params);
        return result.rows;
    }

    async updateStatus(id, status) {
        await this.pg.query(`UPDATE ${this.schema}.invoices SET status=$2, updated_at=now() WHERE id=$1`, [id, status]);
        return await this.get(id);
    }

    async duplicate(id) {
        const original = await this.get(id);
        if (!original) throw new Error('Invoice not found');
        return await this.create({ ...original, lines: original.lines, date: new Date(), due_date: null, notes: `Duplicated from ${original.invoice_number}` });
    }

    async convertToInvoice(quoteId) {
        const quote = await this.get(quoteId);
        if (!quote || quote.type !== 'quote') throw new Error('Not a quote');
        await this.updateStatus(quoteId, 'cancelled');
        return await this.create({ ...quote, type: 'invoice', lines: quote.lines, notes: `Converted from quote ${quote.invoice_number}` });
    }
}

// Invoice PDF Generator (HTML-based for server-side rendering)
function generateInvoicePDF(invoice, config = {}) {
    const { company_name, company_logo, company_address, company_tax_id } = config;

    const formatMoney = (amount) => new Intl.NumberFormat('ar-SA', { style: 'currency', currency: invoice.currency || 'SAR' }).format(amount);
    const formatDate = (d) => new Date(d).toLocaleDateString('ar-SA');

    return `<!DOCTYPE html>
<html dir="rtl">
<head><meta charset="UTF-8"><style>
body{font-family:'Segoe UI',Tahoma,sans-serif;margin:0;padding:40px;color:#333;direction:rtl}
.invoice-header{display:flex;justify-content:space-between;margin-bottom:40px}
.company-info h1{margin:0;font-size:24px;color:#1a237e}.company-info p{margin:4px 0;color:#666}
.invoice-meta{text-align:left}.invoice-meta h2{margin:0;color:#1a237e}
.invoice-meta table td{padding:4px 12px;font-size:14px}
.customer-info{background:#f5f5f5;padding:20px;border-radius:8px;margin-bottom:30px}
.items-table{width:100%;border-collapse:collapse;margin-bottom:30px}
.items-table th{background:#1a237e;color:#fff;padding:12px;text-align:right}
.items-table td{padding:10px 12px;border-bottom:1px solid #eee}
.items-table tr:hover{background:#f9f9f9}
.totals{margin-left:auto;width:300px}.totals table{width:100%}
.totals td{padding:8px 12px;border-bottom:1px solid #eee}
.totals .total-row{font-size:18px;font-weight:bold;color:#1a237e}
.footer{margin-top:40px;padding-top:20px;border-top:2px solid #1a237e;text-align:center;color:#666;font-size:12px}
.status-badge{display:inline-block;padding:4px 12px;border-radius:12px;font-size:12px;font-weight:bold}
.status-draft{background:#fff3e0;color:#e65100}.status-sent{background:#e3f2fd;color:#1565c0}
.status-paid{background:#e8f5e9;color:#2e7d32}.status-overdue{background:#fce4ec;color:#c62828}
</style></head>
<body>
<div class="invoice-header">
    <div class="company-info">
        ${company_logo ? `<img src="${company_logo}" height="50">` : ''}
        <h1>${company_name || 'Company'}</h1>
        <p>${company_address || ''}</p>
        <p>الرقم الضريبي: ${company_tax_id || ''}</p>
    </div>
    <div class="invoice-meta">
        <h2>${invoice.type === 'quote' ? 'عرض سعر' : 'فاتورة'}</h2>
        <table>
            <tr><td>الرقم:</td><td><strong>${invoice.invoice_number}</strong></td></tr>
            <tr><td>التاريخ:</td><td>${formatDate(invoice.date)}</td></tr>
            ${invoice.due_date ? `<tr><td>تاريخ الاستحقاق:</td><td>${formatDate(invoice.due_date)}</td></tr>` : ''}
            <tr><td>الحالة:</td><td><span class="status-badge status-${invoice.status}">${invoice.status}</span></td></tr>
        </table>
    </div>
</div>
<div class="customer-info">
    <strong>العميل:</strong> ${invoice.customer_name || '—'}
    ${invoice.customer_tax_id ? `<br>الرقم الضريبي: ${invoice.customer_tax_id}` : ''}
</div>
<table class="items-table">
    <thead><tr><th>#</th><th>البيان</th><th>الكمية</th><th>السعر</th><th>الخصم</th><th>الضريبة</th><th>الإجمالي</th></tr></thead>
    <tbody>
        ${(invoice.lines||[]).map((line, i) => `
        <tr>
            <td>${i+1}</td>
            <td>${line.description}${line.item_code ? ` <small>(${line.item_code})</small>` : ''}</td>
            <td>${line.quantity}</td>
            <td>${formatMoney(line.unit_price)}</td>
            <td>${line.discount_percent}%</td>
            <td>${line.tax_percent}%</td>
            <td>${formatMoney(line.line_total)}</td>
        </tr>`).join('')}
    </tbody>
</table>
<div class="totals"><table>
    <tr><td>المجموع الفرعي:</td><td>${formatMoney(invoice.subtotal)}</td></tr>
    <tr><td>الخصم:</td><td>${formatMoney(invoice.discount_amount)}</td></tr>
    <tr><td>الضريبة (VAT):</td><td>${formatMoney(invoice.tax_amount)}</td></tr>
    <tr class="total-row"><td>الإجمالي:</td><td>${formatMoney(invoice.total)}</td></tr>
</table></div>
${invoice.notes ? `<div style="margin-top:30px;padding:15px;background:#f5f5f5;border-radius:8px"><strong>ملاحظات:</strong><br>${invoice.notes}</div>` : ''}
<div class="footer"><p>${company_name} — جميع الحقوق محفوظة © ${new Date().getFullYear()}</p></div>
</body></html>`;
}
