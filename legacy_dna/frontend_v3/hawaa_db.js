import BackendConfig from "./config.js";
import MasStoreV3 from "./mas-store-v3.js";
import {
  asArray,
  deriveTables,
  identityValue,
  normalizeRecord,
  tableList,
} from "../shared/logic/schema.js";

const DEFAULT_DB_NAME = "sbn_mas_store_v3";
const STORE_NAME = "records";
const DB_VERSION = 1;

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function openIndexedDb(dbName = DEFAULT_DB_NAME) {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) {
      resolve(null);
      return;
    }
    const request = window.indexedDB.open(dbName, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: "key" });
        store.createIndex("table", "table", { unique: false });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function createLocalAdapter(db) {
  if (!db) {
    return {
      query: async () => [],
      read: async () => null,
      save: async () => {},
      remove: async () => {},
    };
  }

  return {
    async query(tableName) {
      const tx = db.transaction(STORE_NAME, "readonly");
      const index = tx.objectStore(STORE_NAME).index("table");
      const rows = await requestToPromise(index.getAll(String(tableName)));
      return asArray(rows).map((entry) => entry.row).filter(Boolean);
    },
    async read(tableName, id) {
      const tx = db.transaction(STORE_NAME, "readonly");
      const entry = await requestToPromise(tx.objectStore(STORE_NAME).get(`${tableName}:${id}`));
      return entry?.row || null;
    },
    async save(tableName, rows) {
      const tx = db.transaction(STORE_NAME, "readwrite");
      const store = tx.objectStore(STORE_NAME);
      asArray(rows).forEach((row) => {
        if (!row?.id) return;
        store.put({ key: `${tableName}:${row.id}`, table: String(tableName), id: String(row.id), row });
      });
      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
    },
    async remove(tableName, id) {
      const tx = db.transaction(STORE_NAME, "readwrite");
      tx.objectStore(STORE_NAME).delete(`${tableName}:${id}`);
      await new Promise((resolve, reject) => {
        tx.oncomplete = resolve;
        tx.onerror = () => reject(tx.error);
      });
    },
  };
}

function buildI18n(rows) {
  const dict = {};
  asArray(rows).forEach((row) => {
    const key = row?.label_key || row?.key;
    const lang = String(row?.lang || "").toLowerCase();
    const text = row?.text || row?.value || "";
    if (!key || !lang || !text) return;
    if (!dict[key]) dict[key] = {};
    dict[key][lang] = text;
  });
  return dict;
}

function cacheKey(runtime, name) {
  return `${runtime.storagePrefix || runtime.appId || "sbn"}:${name}`;
}

function readJsonCache(runtime, name) {
  try {
    const raw = localStorage.getItem(cacheKey(runtime, name));
    return raw ? JSON.parse(raw) : null;
  } catch (_error) {
    return null;
  }
}

function writeJsonCache(runtime, name, value) {
  try {
    localStorage.setItem(cacheKey(runtime, name), JSON.stringify(value));
  } catch (_error) {}
}

class SbnDB {
  constructor() {
    this.runtime = BackendConfig.resolveRuntimeConfig();
    this.schema = { schema: { tables: [] } };
    this.snapshot = null;
    this.tables = {};
    this.local = null;
    this.realtimeStore = MasStoreV3;
    this.ready = false;
  }

  t(key, lang = this.runtime.lang) {
    return this.snapshot?.i18n?.[key]?.[lang] || this.snapshot?.i18n?.[key]?.ar || key;
  }

  async init(lang = this.runtime.lang) {
    this.runtime = { ...BackendConfig.resolveRuntimeConfig(), lang };
    BackendConfig.configureRest(this.runtime);
    this.local = createLocalAdapter(await openIndexedDb(`${this.runtime.storagePrefix || this.runtime.appId || "sbn"}_mas_store_v3`));
    const [schemaPayload, snapshot] = await Promise.all([
      this.fetchSchema(),
      this.fetchSnapshot(lang),
    ]);
    this.schema = schemaPayload;
    this.snapshot = snapshot;
    this.tables = deriveTables(this.schema);
    const tableNames = this.resolveTableNames(snapshot);

    this.realtimeStore.init({
      runtime: this.runtime,
      schema: this.schema,
      tables: tableNames,
      local: this.local,
      identityResolver: (tableName, record) => identityValue(this.schema, tableName, record),
      recordNormalizer: (tableName, record) => normalizeRecord(this.schema, tableName, record),
      logger: console,
    });

    await this.seedSnapshot(snapshot);
    this.ready = true;
    return this;
  }

  async reloadLanguage(lang) {
    this.runtime = { ...this.runtime, lang };
    localStorage.setItem(`${this.runtime.storagePrefix || this.runtime.appId || "sbn"}:lang`, lang);
    if (this.realtimeStore?.config) this.realtimeStore.config.lang = lang;
    const snapshot = await this.fetchSnapshot(lang);
    this.snapshot = snapshot;
    await this.seedSnapshot(snapshot);
    return this;
  }

  async fetchSchema() {
    const url = BackendConfig.apiUrl(
      `/api/schema?branch=${encodeURIComponent(this.runtime.branchId)}&module=${encodeURIComponent(this.runtime.moduleId)}&include=schema`,
      this.runtime,
    );
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`schema-load-failed:${response.status}`);
      const payload = await response.json();
      const schema = payload?.modules?.[this.runtime.moduleId]?.schema || { schema: { tables: [] } };
      writeJsonCache(this.runtime, "schema-cache", schema);
      return schema;
    } catch (error) {
      const cached = readJsonCache(this.runtime, "schema-cache");
      if (cached) return cached;
      throw error;
    }
  }

  async fetchSnapshot(lang) {
    const url = BackendConfig.apiUrl(
      `/api/branches/${encodeURIComponent(this.runtime.branchId)}/modules/${encodeURIComponent(this.runtime.moduleId)}?lang=${encodeURIComponent(lang || "ar")}`,
      this.runtime,
    );
    const cacheName = `snapshot-cache:${lang || "ar"}`;
    try {
      const response = await fetch(url);
      if (!response.ok) throw new Error(`snapshot-load-failed:${response.status}`);
      const payload = await response.json();
      if (!payload.i18n && payload.tables?.sbn_ui_labels) {
        payload.i18n = buildI18n(payload.tables.sbn_ui_labels);
      }
      writeJsonCache(this.runtime, cacheName, payload);
      return payload;
    } catch (error) {
      const cached = readJsonCache(this.runtime, cacheName);
      if (cached) return cached;
      throw error;
    }
  }

  resolveTableNames(snapshot) {
    const fromSnapshot = Object.keys(snapshot?.tables || {});
    const fromSchema = tableList(this.schema).map((table) => table.name).filter(Boolean);
    return Array.from(new Set([...fromSchema, ...fromSnapshot])).filter(Boolean);
  }

  normalizeRows(tableName, rows) {
    return asArray(rows).map((row) => normalizeRecord(this.schema, tableName, row)).filter((row) => row?.id);
  }

  async seedSnapshot(snapshot) {
    const tables = snapshot?.tables || {};
    await Promise.all(Object.keys(tables).map(async (tableName) => {
      const rows = this.normalizeRows(tableName, tables[tableName]);
      if (!rows.length) return;
      await this.local.save(tableName, rows);
      this.realtimeStore.replaceCache(tableName, rows);
    }));
  }

  async load(tableName, filters = {}) {
    return this.realtimeStore.query(tableName, filters);
  }

  watch(tableName, handler, options = {}) {
    return this.realtimeStore.watch(tableName, handler, options);
  }

  async save(tableName, record, meta = {}) {
    return this.realtimeStore.save(tableName, normalizeRecord(this.schema, tableName, record), meta);
  }

  async remove(tableName, id, meta = {}) {
    return this.realtimeStore.delete(tableName, id, meta);
  }

  status() {
    return this.realtimeStore.getStatus();
  }
}

const DB = new SbnDB();

export default DB;
