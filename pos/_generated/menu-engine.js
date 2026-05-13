// Menu Engine — Categories, Items, Modifiers, Pricing
// All schema-driven, no hardcoded queries

export class MenuEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }

    // ─── Categories ───
    async getCategories() {
        return (await this.crud.list(this.branchId, 'menu_categories', { sort: 'sort_order', order: 'ASC' })).data;
    }

    async createCategory(data) {
        return await this.crud.create(this.branchId, 'menu_categories', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            icon: data.icon || '',
            sort_order: data.sort_order || 0,
            is_active: true,
            color: data.color || '#2196F3'
        });
    }

    // ─── Items ───
    async getItems(categoryId = null) {
        const where = categoryId ? { category_id: categoryId } : {};
        return (await this.crud.list(this.branchId, 'menu_items', { where, sort: 'sort_order', order: 'ASC' })).data;
    }

    async createItem(data) {
        return await this.crud.create(this.branchId, 'menu_items', {
            id: crypto.randomUUID(),
            category_id: data.category_id,
            name: data.name,
            name_ar: data.name_ar || data.name,
            description: data.description || '',
            price: data.price,
            cost: data.cost || 0,
            tax_percent: data.tax_percent ?? 15,
            sku: data.sku || '',
            barcode: data.barcode || '',
            image_url: data.image_url || '',
            is_active: true,
            track_stock: data.track_stock || false,
            stock_quantity: data.stock_quantity || 0,
            sort_order: data.sort_order || 0,
            prep_time_minutes: data.prep_time_minutes || 0,
            calories: data.calories || null
        });
    }

    async updateItem(id, data) {
        return await this.crud.update(this.branchId, 'menu_items', id, data);
    }

    async toggleItemActive(id) {
        const item = await this.crud.read(this.branchId, 'menu_items', id);
        return await this.crud.update(this.branchId, 'menu_items', id, { is_active: !item.is_active });
    }

    // ─── Modifiers ───
    async getModifiers() {
        return (await this.crud.list(this.branchId, 'menu_modifiers', {})).data;
    }

    async createModifier(data) {
        return await this.crud.create(this.branchId, 'menu_modifiers', {
            id: crypto.randomUUID(),
            name: data.name,
            name_ar: data.name_ar || data.name,
            price: data.price || 0,
            type: data.type || 'add_on', // add_on | removal | swap
            is_active: true
        });
    }

    async linkModifierToItem(itemId, modifierId) {
        return await this.crud.create(this.branchId, 'menu_item_modifier', {
            id: crypto.randomUUID(),
            menu_item_id: itemId,
            modifier_id: modifierId,
            is_default: false
        });
    }

    // ─── Pricing (sizes/combos) ───
    async getItemPrices(itemId) {
        return (await this.crud.list(this.branchId, 'menu_item_price', { where: { menu_item_id: itemId } })).data;
    }

    async addItemPrice(itemId, data) {
        return await this.crud.create(this.branchId, 'menu_item_price', {
            id: crypto.randomUUID(),
            menu_item_id: itemId,
            size_name: data.size_name,
            size_name_ar: data.size_name_ar || data.size_name,
            price: data.price,
            is_default: data.is_default || false
        });
    }

    // ─── Section Mapping ───
    async mapCategoryToSection(categoryId, sectionId) {
        return await this.crud.create(this.branchId, 'category_sections', {
            id: crypto.randomUUID(),
            category_id: categoryId,
            section_id: sectionId
        });
    }

    // ─── Search ───
    async searchItems(query) {
        const all = await this.getItems();
        const q = query.toLowerCase();
        return all.filter(item =>
            item.name?.toLowerCase().includes(q) ||
            item.name_ar?.includes(query) ||
            item.sku?.toLowerCase().includes(q) ||
            item.barcode?.includes(query)
        );
    }

    // ─── Import/Export ───
    async exportMenu() {
        const categories = await this.getCategories();
        const items = await this.getItems();
        const modifiers = await this.getModifiers();
        return { categories, items, modifiers, exported_at: new Date().toISOString() };
    }

    async importMenu(data) {
        let imported = { categories: 0, items: 0, modifiers: 0 };

        for (const cat of data.categories || []) {
            await this.createCategory(cat);
            imported.categories++;
        }
        for (const item of data.items || []) {
            await this.createItem(item);
            imported.items++;
        }
        for (const mod of data.modifiers || []) {
            await this.createModifier(mod);
            imported.modifiers++;
        }

        return imported;
    }
}
