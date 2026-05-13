// Printer Service — Bridges WS3 to thermal printers
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
