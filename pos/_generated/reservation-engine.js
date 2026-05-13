// Reservation Engine — Table Management, Booking, Scheduling
export class ReservationEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Tables ───
    async getTables() {
        return (await this.crud.list(this.branchId, 'dining_tables', { sort: 'table_number' })).data;
    }

    async getAvailableTables(datetime, partySize) {
        const tables = await this.getTables();
        const reservations = await this.getReservationsForTime(datetime);
        const reservedTableIds = new Set();

        for (const res of reservations) {
            const resTables = await this.crud.list(this.branchId, 'reservation_table', {
                where: { reservation_id: res.id }
            });
            resTables.data.forEach(rt => reservedTableIds.add(rt.table_id));
        }

        // Also check table locks
        const locks = (await this.crud.list(this.branchId, 'table_lock', {
            where: { is_active: true }
        })).data;
        locks.forEach(l => reservedTableIds.add(l.table_id));

        return tables.filter(t =>
            !reservedTableIds.has(t.id) &&
            t.capacity >= partySize &&
            t.is_active
        );
    }

    async getReservationsForTime(datetime) {
        const date = new Date(datetime);
        const windowStart = new Date(date.getTime() - 2 * 60 * 60 * 1000); // -2h
        const windowEnd = new Date(date.getTime() + 2 * 60 * 60 * 1000);   // +2h

        const all = (await this.crud.list(this.branchId, 'reservations', {
            where: { status: 'confirmed' }
        })).data;

        return all.filter(r => {
            const resTime = new Date(r.reservation_time);
            return resTime >= windowStart && resTime <= windowEnd;
        });
    }

    // ─── Reservations ───
    async createReservation(data) {
        const reservation = await this.crud.create(this.branchId, 'reservations', {
            id: crypto.randomUUID(),
            customer_name: data.customer_name,
            customer_phone: data.customer_phone,
            party_size: data.party_size,
            reservation_time: data.reservation_time,
            duration_minutes: data.duration_minutes || 90,
            status: 'confirmed',
            notes: data.notes || '',
            created_at: new Date().toISOString()
        });

        // Assign tables
        if (data.table_ids?.length) {
            for (const tableId of data.table_ids) {
                await this.crud.create(this.branchId, 'reservation_table', {
                    id: crypto.randomUUID(),
                    reservation_id: reservation.id,
                    table_id: tableId
                });
            }
        }

        return reservation;
    }

    async cancelReservation(id) {
        return await this.crud.update(this.branchId, 'reservations', id, {
            status: 'cancelled'
        });
    }

    async seatReservation(id) {
        const reservation = await this.crud.read(this.branchId, 'reservations', id);
        if (!reservation) throw new Error('Reservation not found');

        // Lock the tables
        const resTables = (await this.crud.list(this.branchId, 'reservation_table', {
            where: { reservation_id: id }
        })).data;

        for (const rt of resTables) {
            await this.crud.create(this.branchId, 'table_lock', {
                id: crypto.randomUUID(),
                table_id: rt.table_id,
                locked_by: 'reservation',
                reference_id: id,
                is_active: true,
                locked_at: new Date().toISOString()
            });
        }

        return await this.crud.update(this.branchId, 'reservations', id, {
            status: 'seated',
            seated_at: new Date().toISOString()
        });
    }

    async releaseTable(tableId) {
        const locks = (await this.crud.list(this.branchId, 'table_lock', {
            where: { table_id: tableId, is_active: true }
        })).data;

        for (const lock of locks) {
            await this.crud.update(this.branchId, 'table_lock', lock.id, { is_active: false });
        }
    }

    // ─── Today's view ───
    async getTodayReservations() {
        const today = new Date().toISOString().split('T')[0];
        const all = (await this.crud.list(this.branchId, 'reservations', {
            sort: 'reservation_time', order: 'ASC'
        })).data;

        return all.filter(r => r.reservation_time?.startsWith(today) && r.status !== 'cancelled');
    }
}
