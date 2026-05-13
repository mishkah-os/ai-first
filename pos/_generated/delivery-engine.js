// Delivery Engine — Zones, Drivers, Order Routing, Tracking
export class DeliveryEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Zones ───
    async getZones() {
        return (await this.crud.list(this.branchId, 'delivery_zones', { sort: 'name' })).data;
    }

    async createZone(data) {
        return await this.crud.create(this.branchId, 'delivery_zones', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            min_order: data.min_order || 0,
            delivery_fee: data.delivery_fee || 0,
            estimated_minutes: data.estimated_minutes || 30,
            is_active: true,
            polygon: data.polygon || null, // GeoJSON for zone boundaries
            max_distance_km: data.max_distance_km || 10
        });
    }

    // ─── Drivers ───
    async getDrivers(activeOnly = true) {
        const where = activeOnly ? { is_active: true } : {};
        return (await this.crud.list(this.branchId, 'delivery_drivers', { where })).data;
    }

    async getAvailableDrivers() {
        const drivers = await this.getDrivers();
        // Exclude drivers with active deliveries
        const activeDeliveries = (await this.crud.list(this.branchId, 'order_delivery', {
            where: { status: 'in_transit' }
        })).data;
        const busyDriverIds = new Set(activeDeliveries.map(d => d.driver_id));
        return drivers.filter(d => !busyDriverIds.has(d.id));
    }

    async createDriver(data) {
        return await this.crud.create(this.branchId, 'delivery_drivers', {
            id: crypto.randomUUID(),
            name: data.name,
            phone: data.phone,
            vehicle_type: data.vehicle_type || 'motorcycle',
            is_active: true
        });
    }

    // ─── Order Delivery ───
    async assignDriver(orderId, driverId) {
        const driver = await this.crud.read(this.branchId, 'delivery_drivers', driverId);
        if (!driver) throw new Error('Driver not found');

        const delivery = await this.crud.create(this.branchId, 'order_delivery', {
            id: crypto.randomUUID(),
            order_id: orderId,
            driver_id: driverId,
            driver_name: driver.name,
            status: 'assigned',
            assigned_at: new Date().toISOString(),
            picked_up_at: null,
            delivered_at: null
        });

        // Update order status
        await this.crud.update(this.branchId, 'order_header', orderId, {
            status: 'out_for_delivery'
        });

        return delivery;
    }

    async updateDeliveryStatus(deliveryId, status) {
        const now = new Date().toISOString();
        const updates = { status };

        if (status === 'picked_up') updates.picked_up_at = now;
        if (status === 'delivered') updates.delivered_at = now;

        const delivery = await this.crud.update(this.branchId, 'order_delivery', deliveryId, updates);

        // If delivered, update order
        if (status === 'delivered') {
            await this.crud.update(this.branchId, 'order_header', delivery.order_id, {
                status: 'served'
            });
        }

        return delivery;
    }

    // ─── Fee Calculation ───
    async calculateDeliveryFee(zoneId) {
        if (!zoneId) return 0;
        const zone = await this.crud.read(this.branchId, 'delivery_zones', zoneId);
        return zone?.delivery_fee || 0;
    }

    // ─── Tracking ───
    async getActiveDeliveries() {
        return (await this.crud.list(this.branchId, 'order_delivery', {
            where: { status: 'in_transit' }
        })).data;
    }

    async getDriverHistory(driverId, limit = 20) {
        return (await this.crud.list(this.branchId, 'order_delivery', {
            where: { driver_id: driverId },
            sort: 'assigned_at',
            order: 'DESC',
            limit
        })).data;
    }
}
