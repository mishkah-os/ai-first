// KDS Engine — Kitchen Display System + Job Order Routing
// Routes orders to kitchen sections, manages prep workflow

class KDSEngine {
    constructor(store, schema) {
        this.store = store;
        this.schema = schema;
        this.sections = new Map(); // section_id -> config
    }

    async init() {
        // Load kitchen sections
        const sections = await this.store.query('kitchen_sections', {});
        sections.forEach(s => this.sections.set(s.id, s));
    }

    async routeOrderToKitchen(orderId) {
        const lines = await this.store.query('order_line', { order_id: orderId });
        const sectionGroups = new Map(); // section_id -> lines[]

        for (const line of lines) {
            // Resolve section via: item -> category -> category_sections -> kitchen_section
            const sectionId = await this.resolveSectionForItem(line.menu_item_id);
            if (!sectionGroups.has(sectionId)) sectionGroups.set(sectionId, []);
            sectionGroups.get(sectionId).push(line);
        }

        // Create job orders per section
        const jobOrders = [];
        for (const [sectionId, sectionLines] of sectionGroups) {
            const jobOrder = await this.createJobOrder(orderId, sectionId, sectionLines);
            jobOrders.push(jobOrder);
        }

        return jobOrders;
    }

    async createJobOrder(orderId, sectionId, lines) {
        const order = await this.store.get('order_header', orderId);
        const section = this.sections.get(sectionId);

        const jobHeader = {
            id: crypto.randomUUID(),
            order_id: orderId,
            order_number: order.order_number,
            section_id: sectionId,
            section_name: section?.name || 'Default',
            status: 'pending',
            priority: order.priority || 'normal',
            order_type: order.order_type,
            table_number: order.table_number,
            customer_name: order.customer_name,
            items_count: lines.length,
            notes: order.notes,
            created_at: new Date().toISOString(),
            started_at: null,
            completed_at: null
        };

        await this.store.save('job_order_header', jobHeader);

        // Create detail lines
        for (let i = 0; i < lines.length; i++) {
            const line = lines[i];
            const detail = {
                id: crypto.randomUUID(),
                job_order_id: jobHeader.id,
                order_line_id: line.id,
                item_name: line.item_name,
                item_name_ar: line.item_name_ar,
                quantity: line.quantity,
                status: 'pending',
                notes: line.notes,
                sort_order: i,
                modifiers: line.modifiers || []
            };

            await this.store.save('job_order_detail', detail);

            // Store modifiers
            for (const mod of detail.modifiers) {
                await this.store.save('job_order_detail_modifier', {
                    id: crypto.randomUUID(),
                    job_order_detail_id: detail.id,
                    modifier_name: mod.modifier_name,
                    modifier_name_ar: mod.modifier_name_ar,
                    type: mod.type
                });
            }
        }

        return jobHeader;
    }

    async resolveSectionForItem(menuItemId) {
        // item -> category -> category_sections -> section
        const item = await this.store.get('menu_items', menuItemId);
        if (!item) return 'default';

        const catSections = await this.store.query('category_sections', { category_id: item.category_id });
        if (catSections.length > 0) return catSections[0].section_id;

        return 'default'; // Fallback section
    }

    async updateJobStatus(jobOrderId, newStatus, employeeId) {
        const job = await this.store.get('job_order_header', jobOrderId);
        if (!job) throw new Error('Job order not found');

        const now = new Date().toISOString();
        const updates = { status: newStatus, updated_at: now };

        if (newStatus === 'started' && !job.started_at) updates.started_at = now;
        if (newStatus === 'completed') updates.completed_at = now;

        Object.assign(job, updates);
        await this.store.save('job_order_header', job);

        // Log history
        await this.store.save('job_order_status_history', {
            id: crypto.randomUUID(),
            job_order_id: jobOrderId,
            old_status: job.status,
            new_status: newStatus,
            changed_by: employeeId,
            changed_at: now
        });

        // If all jobs for order completed, update order status
        if (newStatus === 'completed') {
            await this.checkOrderCompletion(job.order_id);
        }

        return job;
    }

    async checkOrderCompletion(orderId) {
        const jobs = await this.store.query('job_order_header', { order_id: orderId });
        const allCompleted = jobs.every(j => j.status === 'completed');
        if (allCompleted) {
            await this.store.save('order_header', {
                id: orderId,
                status: 'ready',
                updated_at: new Date().toISOString()
            });
        }
    }

    async getKDSView(sectionId, statusFilter = 'pending') {
        const jobs = await this.store.query('job_order_header', {
            section_id: sectionId,
            status: statusFilter
        });

        // Enrich with details
        for (const job of jobs) {
            job.details = await this.store.query('job_order_detail', { job_order_id: job.id });
        }

        return jobs.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
    }

    async getBatchInfo(batchId) {
        return await this.store.query('job_order_batch', { batch_id: batchId });
    }

    // Fingerprint for deduplication (prevent duplicate prints)
    fingerprint(job) {
        return `${job.id}:${job.status}:${job.updated_at}`;
    }
}

export default KDSEngine;
