;(function (global) {
  "use strict";

  function clone(value) {
    if (value == null) return value;
    try { return structuredClone(value); } catch (_error) {
      return JSON.parse(JSON.stringify(value));
    }
  }

  function rows(payload) {
    if (!payload) return [];
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload.Data)) return payload.Data;
    if (payload.Data && Array.isArray(payload.Data.rows)) return payload.Data.rows;
    if (payload.Data && Array.isArray(payload.Data.objects)) return payload.Data.objects;
    if (Array.isArray(payload.rows)) return payload.rows;
    if (Array.isArray(payload.data)) return payload.data;
    return [];
  }

  function valueOf(cell) {
    if (cell && typeof cell === "object" && "id" in cell) return cell.id;
    if (cell && typeof cell === "object" && "value" in cell) return cell.value;
    return cell == null ? "" : cell;
  }

  function labelOf(cell) {
    if (cell && typeof cell === "object" && "value" in cell) return cell.value;
    return cell == null ? "" : String(cell);
  }

  function makeId(prefix) {
    if (global.crypto && typeof global.crypto.randomUUID === "function") return `${prefix}-${global.crypto.randomUUID()}`;
    return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 8)}`;
  }

  class MasStoreV3 {
    constructor(config) {
      this.config = Object.assign({ apiBase: "", tenantId: 3, branchId: 1, userId: 1 }, config || {});
      this.cache = new Map();
      this.watchers = new Set();
      this.state = { loading: false, lastError: "", lastSyncAt: "", tables: {} };
    }

    subscribe(fn) {
      if (typeof fn !== "function") return function () {};
      this.watchers.add(fn);
      return () => this.watchers.delete(fn);
    }

    emit(event, payload) {
      this.watchers.forEach((fn) => {
        try { fn(event, payload, clone(this.state)); } catch (_error) {}
      });
    }

    async request(url, options) {
      const response = await fetch(url, Object.assign({ headers: { "Accept": "application/json" } }, options || {}));
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.Success === false) {
        throw new Error(payload.Error || payload.error || `Request failed: ${response.status}`);
      }
      return payload;
    }

    async v7(payload) {
      return this.request(`${this.config.apiBase}/api/v7`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8", "Accept": "application/json" },
        body: JSON.stringify(payload || {})
      });
    }

    async schema(name) {
      const key = `schema:${name}`;
      if (this.cache.has(key)) return this.cache.get(key);
      const payload = await this.v7({ Action: "schema", Name: name });
      const object = rows(payload)[0] || (payload.Data && payload.Data.objects && payload.Data.objects[0]) || null;
      this.cache.set(key, object);
      return object;
    }

    async read(name, options) {
      const payload = await this.v7({
        Action: "read",
        Name: name,
        Filters: (options && options.filters) || [],
        Options: Object.assign({ DataOnly: true, top: 20 }, (options && options.options) || {})
      });
      const list = rows(payload);
      this.state.tables[name] = list;
      this.state.lastSyncAt = new Date().toISOString();
      this.emit("table", { name, rows: list });
      return list;
    }

    async save(table, records) {
      const schema = await this.schema(table);
      const columns = ((schema && schema.columns) || []).map((col) => ({ name: col.name, type: col.type || col.data_type || "varchar" }));
      const allowed = new Set(columns.map((col) => col.name));
      const data = (Array.isArray(records) ? records : [records]).map((row) => {
        const out = {};
        if (row && row.ID != null && allowed.has("id")) out.id = row.ID;
        Object.keys(row || {}).forEach((key) => { if (allowed.has(key)) out[key] = valueOf(row[key]); });
        return out;
      });
      return this.v7({ Action: "save", Data: [{ name: table, columns, data }] });
    }

    async proc(name, params) { return this.v7({ Action: "proc", Name: name, Params: params || [] }); }
    async fun(name, params) { return this.v7({ Action: "fun", Name: name, Params: params || [] }); }

    async documentProfile(headTable) {
      const payload = await this.request(`${this.config.apiBase}/api/document-profile?head_table=${encodeURIComponent(headTable)}`);
      return payload.profile;
    }

    async documentDefaults(headTable, header) {
      const params = new URLSearchParams({
        head_table: headTable,
        company_id: String(this.config.tenantId),
        branch_id: String(this.config.branchId),
        user_id: String(this.config.userId),
        user_name: "mas-erp-v2"
      });
      Object.keys(header || {}).forEach((key) => {
        if (header[key] !== undefined && header[key] !== null && header[key] !== "") params.set(key, header[key]);
      });
      return this.request(`${this.config.apiBase}/api/document-defaults?${params.toString()}`);
    }

    async searchDocuments(headTable, criteria) {
      return this.request(`${this.config.apiBase}/api/document-search`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify({
          head_table: headTable,
          criteria: criteria || {},
          company_id: this.config.tenantId,
          branch_id: this.config.branchId,
          user_id: this.config.userId,
          user_name: "mas-erp-v2"
        })
      });
    }

    async saveDocumentDraft(options) {
      return this.saveDocument("/api/document-draft-save", options);
    }

    async finalizeDocument(options) {
      return this.saveDocument("/api/document-finalize", options);
    }

    async saveDocument(path, options) {
      const payload = {
        head_table: options.headTable,
        detail_table: options.detailTable,
        header: options.headerRow || {},
        lines: options.lineRows || [],
        session: options.session || {
          company_id: this.config.tenantId,
          branch_id: this.config.branchId,
          user_id: this.config.userId,
          user_name: "mas-erp-v2"
        }
      };
      return this.request(`${this.config.apiBase}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json; charset=utf-8" },
        body: JSON.stringify(payload)
      });
    }

    emptyLine() {
      return { _id: makeId("line"), item_id: "", uom_id: "", qty: "1", price: "0", discount_value: "0", tax_value: "0", remarks: "" };
    }

    normalizeDocLine(line) {
      const qty = Number(line.qty || line.quantity || 0);
      const price = Number(line.price || line.unit_price || 0);
      const discount = Number(line.discount_value || 0);
      const tax = Number(line.tax_value || 0);
      const subtotal = Math.max(0, qty * price - discount);
      return Object.assign({}, line, {
        qty,
        price,
        discount_value: discount,
        tax_value: tax,
        line_total: subtotal + tax,
        uom_factor: Number(line.uom_factor || 1),
        qty_base: Number(line.qty_base || qty)
      });
    }
  }

  global.MasStoreV3 = {
    create(config) { return new MasStoreV3(config); },
    rows,
    valueOf,
    labelOf
  };
})(typeof window !== "undefined" ? window : globalThis);
