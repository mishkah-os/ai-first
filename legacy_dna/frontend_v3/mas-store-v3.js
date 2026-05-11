import { SCHEMA } from "./schema.js";
import { buildLiveDataHelloConfig, filterLiveRows } from "./live-data-policy.js";

const DEFAULT_TABLES = [
  "sbn_posts",
  "sbn_products",
  "sbn_services",
  "sbn_wiki_articles",
  "sbn_notifications",
  "sbn_users",
];
const DEFAULT_API_HOST = "https://os.ai-auto.cloud";
const WS_V3_PATH = "/ws/v3";
const OUTBOX_VERSION = 1;
const CURSOR_VERSION = 1;
const DEFAULT_RETRY_INTERVAL_MS = 5000;
const DEFAULT_MAX_RETRIES = 8;

function clone(value) {
  if (value == null) return value;
  if (typeof structuredClone === "function") {
    try { return structuredClone(value); } catch (_error) {}
  }
  return JSON.parse(JSON.stringify(value));
}

function coerceArray(value) {
  if (Array.isArray(value)) return value;
  if (!value || typeof value !== "object") return [];
  if (Array.isArray(value.rows)) return value.rows;
  if (Array.isArray(value.items)) return value.items;
  if (Array.isArray(value.list)) return value.list;
  if (Array.isArray(value.data)) return value.data;
  if (Array.isArray(value.values)) return value.values;
  if (Array.isArray(value.records)) return value.records;
  return [];
}

function normalizeToken(value) {
  return value === undefined || value === null ? "" : String(value).trim();
}

function safeJsonParse(value) {
  if (!value || typeof value !== "string") return null;
  try { return JSON.parse(value); } catch (_error) { return null; }
}

function createId(prefix = "masv3") {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(16).slice(2, 10)}`;
}

function nowIso() {
  return new Date().toISOString();
}

function normalizeFilter(filters) {
  if (!filters || typeof filters !== "object") return {};
  const out = {};
  Object.keys(filters).forEach((key) => {
    if (["page", "limit", "offset", "fresh", "cacheMode"].includes(key)) return;
    if (key === "index" || key === "value") return;
    out[key] = filters[key];
  });
  if (filters.index && filters.value !== undefined && out[filters.index] === undefined) {
    out[filters.index] = filters.value;
  }
  return out;
}

function applyFilter(rows, filters) {
  const normalized = normalizeFilter(filters);
  const keys = Object.keys(normalized);
  if (!keys.length) return Array.isArray(rows) ? rows : [];
  return (Array.isArray(rows) ? rows : []).filter((row) => {
    if (!row || typeof row !== "object") return false;
    return keys.every((key) => String(row[key]) === String(normalized[key]));
  });
}

function rowsSignature(rows) {
  const list = Array.isArray(rows) ? rows : [];
  return list
    .map((row) => {
      if (!row || typeof row !== "object") return "";
      const id = row.id === undefined || row.id === null ? "" : String(row.id);
      const updated = row.updatedAt || row.updated_at || row.createdAt || row.created_at || "";
      const read = row.is_read === undefined ? "" : String(row.is_read);
      return `${id}:${updated}:${read}:${JSON.stringify(row)}`;
    })
    .sort()
    .join("|");
}

function uniqueRows(rows) {
  const byId = new Map();
  (Array.isArray(rows) ? rows : []).forEach((row) => {
    if (!row || row.id == null) return;
    byId.set(String(row.id), row);
  });
  return Array.from(byId.values());
}

function rowTime(row) {
  if (!row || typeof row !== "object") return 0;
  const value = row.updatedAt || row.updated_at || row.createdAt || row.created_at || "";
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function compareRows(tableName, left, right) {
  const table = String(tableName || "");
  if (table.endsWith("messages")) {
    const diff = rowTime(left) - rowTime(right);
    if (diff) return diff;
  } else {
    const diff = rowTime(right) - rowTime(left);
    if (diff) return diff;
  }
  return String(left && left.id || "").localeCompare(String(right && right.id || ""));
}

function normalizeAction(action) {
  return String(action || "").trim().toLowerCase();
}

function isDeleteAction(action) {
  const normalized = normalizeAction(action);
  return normalized === "module:delete" || normalized === "delete" || normalized === "remove";
}

function extractEventDelta(payload) {
  if (!payload || typeof payload !== "object") return null;
  const patch = payload.patch && typeof payload.patch === "object"
    ? payload.patch
    : payload.delta && typeof payload.delta === "object"
      ? payload.delta
      : payload;
  const table = payload.table || payload.entry?.table || patch.table || payload.notice?.table || "";
  if (!table) return null;
  const action = payload.action || payload.entry?.action || patch.action || patch.op || payload.notice?.action || "module:save";
  const changedRecord = patch.changed && typeof patch.changed === "object"
    ? Object.assign({}, patch.id != null ? { id: patch.id } : {}, patch.changed)
    : null;
  const record =
    payload.record ||
    payload.entry?.record ||
    patch.record ||
    changedRecord ||
    null;
  const recordRef =
    payload.recordRef ||
    payload.entry?.recordRef ||
    patch.recordRef ||
    payload.notice?.recordRef ||
    payload.meta?.recordRef ||
    (patch.id != null ? { id: patch.id } : null) ||
    null;
  const id =
    record && (record.id || record.key) ||
    recordRef && (recordRef.id || recordRef.key || recordRef.recordKey) ||
    patch.id ||
    null;
  if (!record && !id) return null;
  return {
    table: String(table),
    action,
    record,
    id,
    recordRef,
    patch,
    cursor: patch.cursor || payload.cursor || payload.meta?.cursor || null,
    sequence: patch.sequence || payload.sequence || payload.meta?.sequence || null,
    eventId: patch.eventId || payload.eventId || payload.meta?.eventId || "",
  };
}

function resolveWsUrl(apiHost) {
  const base = String(apiHost || DEFAULT_API_HOST).trim();
  let url = "";
  if (/^wss?:\/\//i.test(base)) {
    const normalized = base.replace(/\/+$/, "");
    url = /\/ws(?:\/v3)?$/i.test(normalized)
      ? normalized.replace(/\/ws(?:\/v3)?$/i, WS_V3_PATH)
      : `${normalized}${WS_V3_PATH}`;
  } else if (/^https?:\/\//i.test(base)) {
    const normalized = base.replace(/^http:/i, "ws:").replace(/^https:/i, "wss:").replace(/\/+$/, "");
    url = /\/ws(?:\/v3)?$/i.test(normalized)
      ? normalized.replace(/\/ws(?:\/v3)?$/i, WS_V3_PATH)
      : `${normalized}${WS_V3_PATH}`;
  } else {
    const host = base.replace(/^\/+/, "").replace(/\/+$/, "");
    url = /\/ws(?:\/v3)?$/i.test(host)
      ? `wss://${host.replace(/\/ws(?:\/v3)?$/i, WS_V3_PATH)}`
      : `wss://${host}${WS_V3_PATH}`;
  }
  return appendSessionParams(url);
}

function readStoredSession() {
  if (typeof window === "undefined" || !window.localStorage) return {};
  const session = {};
  const appPrefix = String(window.APP_CONFIG?.storagePrefix || window.APP_CONFIG?.appId || "sbn").trim() || "sbn";
  try {
    const structured =
      safeJsonParse(window.localStorage.getItem(`${appPrefix}_session`) || "") ||
      safeJsonParse(window.localStorage.getItem("sbn_session") || "") ||
      safeJsonParse(window.localStorage.getItem("aqarat_session") || "");
    const token =
      (structured && structured.token) ||
      window.localStorage.getItem(`${appPrefix}_token`) ||
      window.localStorage.getItem("sbn_token") ||
      window.localStorage.getItem("aqarat_token") ||
      window.localStorage.getItem("auth_token") ||
      window.localStorage.getItem("mishkah_token") ||
      "";
    if (token) session.token = token;
  } catch (_error) {}
  try {
    const structured =
      safeJsonParse(window.localStorage.getItem(`${appPrefix}_session`) || "") ||
      safeJsonParse(window.localStorage.getItem("sbn_session") || "") ||
      safeJsonParse(window.localStorage.getItem("aqarat_session") || "");
    const raw =
      window.localStorage.getItem(`${appPrefix}_user`) ||
      window.localStorage.getItem("sbn_user") ||
      window.localStorage.getItem("aqarat_user") ||
      window.localStorage.getItem("auth_user") ||
      window.localStorage.getItem("mishkah_user") ||
      "";
    const user = (structured && structured.user) || safeJsonParse(raw);
    const userId = user && (user.id || user.user_id || user.userId);
    if (userId) session.userId = String(userId).trim();
  } catch (_error) {}
  return session;
}

function withSessionParams(filters = {}) {
  const session = readStoredSession();
  const payload = Object.assign({}, filters || {});
  if (session.token) payload._auth_token = session.token;
  if (session.userId) payload._scope_user_id = session.userId;
  return payload;
}

function getRestClient() {
  if (typeof window === "undefined") return null;
  return window.Mishkah && window.Mishkah.REST ? window.Mishkah.REST : null;
}

function appendSessionParams(rawUrl) {
  const session = readStoredSession();
  if (!session.token && !session.userId) return rawUrl;
  try {
    const parsed = new URL(rawUrl);
    if (session.token && !parsed.searchParams.get("token")) parsed.searchParams.set("token", session.token);
    if (session.userId && !parsed.searchParams.get("user_id")) parsed.searchParams.set("user_id", session.userId);
    return parsed.toString();
  } catch (_error) {
    const params = new URLSearchParams();
    if (session.token) params.set("token", session.token);
    if (session.userId) params.set("user_id", session.userId);
    return rawUrl + (String(rawUrl).includes("?") ? "&" : "?") + params.toString();
  }
}

class MasStoreV3 {
  constructor() {
    this.config = {};
    this.tables = DEFAULT_TABLES.slice();
    this.local = null;
    this.remote = null;
    this.readyState = false;
    this.connectStarted = false;
    this.connectionState = "idle";
    this.cache = new Map();
    this.watchers = new Map();
    this.emitTimers = new Map();
    this.events = new Map();
    this.outbox = [];
    this.outboxKey = "";
    this.cursorKey = "";
    this.cursors = {};
    this.flushTimer = null;
    this.reconnectTimer = null;
    this.reconnectAttempts = 0;
    this.flushLock = false;
    this.onlineUnsubscribe = null;
    this.bootstrapRequests = new Map();
  }

  init(options = {}) {
    if (this.readyState) return this;
    const runtime = options.runtime || {};
    this.tables = Array.isArray(options.tables) && options.tables.length
      ? options.tables.map(String)
      : DEFAULT_TABLES.slice();
    this.local = options.local || null;
    this.config = {
      branchId: runtime.branchId || "sbn",
      moduleId: runtime.moduleId || "mostamal",
      apiHost: runtime.apiHost || DEFAULT_API_HOST,
      lang: runtime.lang || options.lang || "ar",
      schema: options.schema || SCHEMA,
      liveData: options.liveData || buildLiveDataHelloConfig(),
      identityResolver: typeof options.identityResolver === "function" ? options.identityResolver : null,
      recordNormalizer: typeof options.recordNormalizer === "function" ? options.recordNormalizer : null,
      logger: options.logger || console,
      retryIntervalMs: Number(options.retryIntervalMs) > 0 ? Number(options.retryIntervalMs) : DEFAULT_RETRY_INTERVAL_MS,
      maxRetries: Number(options.maxRetries) > 0 ? Number(options.maxRetries) : DEFAULT_MAX_RETRIES,
    };
    this.outboxKey = [
      "mas-store-v3-outbox",
      this.config.branchId,
      this.config.moduleId,
      this.tables.join(","),
      OUTBOX_VERSION,
    ].join(":");
    this.cursorKey = [
      "mas-store-v3-cursors",
      this.config.branchId,
      this.config.moduleId,
      this.tables.join(","),
      CURSOR_VERSION,
    ].join(":");
    this.outbox = this.loadOutbox();
    this.cursors = this.loadCursors();

    this.remote = this.createRemote();
    this.attachRemoteWatchers();
    this.seedLocalCache();
    this.connect();
    this.startOutboxLoop();
    this.readyState = true;
    return this;
  }

  createRemote() {
    if (typeof window === "undefined") return null;
    const nativeRemote = this.createNativeRemote();
    if (nativeRemote) return nativeRemote;
    this.config.logger.warn?.("[MasStoreV3] REST/WebSocket unavailable; using local-only mode");
    return null;
  }

  createNativeRemote() {
    if (typeof WebSocket === "undefined") return null;
    const store = this;
    let ws = null;
    let connected = false;
    const tableWatchers = new Map();

    function notifyTable(table, rows, meta = {}) {
      const set = tableWatchers.get(table);
      if (!set || !set.size) return;
      set.forEach((handler) => {
        try { handler(clone(rows), Object.assign({ table, source: "native-ws" }, meta)); } catch (_error) {}
      });
    }

    function applySnapshot(payload) {
      const modules = payload && payload.modules && typeof payload.modules === "object" ? payload.modules : {};
      const moduleSnapshot = modules[store.config.moduleId] || modules[String(store.config.moduleId)] || null;
      const tables = moduleSnapshot && moduleSnapshot.tables && typeof moduleSnapshot.tables === "object"
        ? moduleSnapshot.tables
        : {};
      store.tables.forEach((table) => {
        if (!Array.isArray(tables[table])) return;
        notifyTable(table, tables[table]);
      });
    }

    async function search(table, filters = {}) {
      const rest = getRestClient();
      if (!rest || typeof rest.repo !== "function") return [];
      const repo = rest.repo(table);
      if (!repo || typeof repo.search !== "function") return [];
      const payload = Object.assign({
        branch: store.config.branchId,
        module: store.config.moduleId,
        page: 1,
        limit: 1000,
        fresh: true,
        cacheMode: "network-only",
        lang: store.config.lang || "ar",
      }, normalizeFilter(filters));
      if (String(table || "").toLowerCase().endsWith("users")) payload._public_identity = true;
      const response = await repo.search(withSessionParams(payload));
      return store.normalizeRecordList(table, coerceArray(response));
    }

    async function saveRecord(table, record, meta = {}) {
      const normalizedRecord = store.normalizeRecordIdentity(table, record);
      if (connected && ws && ws.readyState === WebSocket.OPEN) {
        try { return publishMutation("module:save", table, normalizedRecord, meta); } catch (_error) {}
      }
      const rest = getRestClient();
      if (rest && typeof rest.repo === "function") {
        const repo = rest.repo(table);
        if (repo) {
          // CRUD create is an upsert on this backend. Prefer it for local-first
          // saves because new optimistic records already have generated IDs.
          if (typeof repo.create === "function") return repo.create(normalizedRecord, {
            branch: store.config.branchId,
            module: store.config.moduleId,
            lang: store.config.lang || "ar",
          });
        }
      }
      return publishMutation("module:save", table, normalizedRecord);
    }

    function publishMutation(action, table, record, meta = {}) {
      if (!connected || !ws || ws.readyState !== WebSocket.OPEN) {
        throw new Error("WS v3 unavailable");
      }
      const requestId = createId("ws-v3-mut");
      ws.send(JSON.stringify({
        type: "client:publish",
        protocol: "mas-store-v3",
        protocolVersion: 3,
        branchId: store.config.branchId,
        moduleId: store.config.moduleId,
        action,
        table,
        record,
        recordRef: record && record.id != null ? { id: record.id } : null,
        mutationId: requestId,
        meta: Object.assign({ source: "mas-store-v3" }, meta || {}),
      }));
      return { ok: true, queued: true, via: "ws-v3", requestId };
    }

    async function deleteRecord(table, ref, meta = {}) {
      const id = typeof ref === "object" ? (store.getRecordIdentity(table, ref) || ref.id) : ref;
      if (id == null) throw new Error("delete id required");
      if (connected && ws && ws.readyState === WebSocket.OPEN) {
        try { return publishMutation("module:delete", table, { id }, meta); } catch (_error) {}
      }
      const rest = getRestClient();
      if (rest && typeof rest.repo === "function") {
        const repo = rest.repo(table);
          if (repo && typeof repo.delete === "function") {
          return repo.delete(id, {
            branch: store.config.branchId,
            module: store.config.moduleId,
            lang: store.config.lang || "ar",
          });
        }
      }
      return publishMutation("module:delete", table, { id }, meta);
    }

    function closeSocket() {
      const current = ws;
      ws = null;
      connected = false;
      if (current && current.readyState !== WebSocket.CLOSED) {
        try { current.close(); } catch (_error) {}
      }
    }

    function handleDisconnect() {
      connected = false;
      ws = null;
      store.connectStarted = false;
      store.setConnectionState("offline");
      store.scheduleReconnect();
    }

    function sendHello() {
      const session = readStoredSession();
      ws.send(JSON.stringify({
        type: "client:hello",
        protocol: "mas-store-v3",
        protocolVersion: 3,
        branchId: store.config.branchId,
        moduleId: store.config.moduleId,
        role: "mas-store-v3",
        userId: session.userId || "",
        lang: store.config.lang || "ar",
        liveData: store.config.liveData,
        watchTables: store.tables.map((table) => ({
          moduleId: store.config.moduleId,
          table,
          mode: "delta",
        })),
        requestSnapshot: false,
        lastCursors: store.getCursors(),
        capabilities: {
          delta: true,
          tablePatch: true,
          batchPatch: true,
          cursor: true,
          indexedDbBootstrap: true,
          restFallback: true,
        },
      }));
    }

    async function readRecord(table, id) {
      const rest = getRestClient();
      if (rest && typeof rest.repo === "function") {
        const repo = rest.repo(table);
        if (repo && typeof repo.get === "function") return repo.get(id);
      }
      const rows = await search(table, {});
      return rows.find((row) => row && String(store.getRecordIdentity(table, row) || row.id) === String(id)) || null;
    }

    function ensureSocketOpen(resolve) {
      try {
        ws = new WebSocket(resolveWsUrl(store.config.apiHost));
        ws.onopen = () => {
          connected = true;
          sendHello();
          resolve(true);
        };
        ws.onmessage = (event) => {
          let payload = null;
          try { payload = JSON.parse(event.data); } catch (_error) { return; }
          if (payload && payload.type === "server:snapshot") applySnapshot(payload);
          if (payload && payload.type === "server:ready") {
            if (payload.cursors && typeof payload.cursors === "object") store.mergeCursors(payload.cursors);
          }
          if (payload && payload.type === "server:patch.batch") {
            const patches = Array.isArray(payload.patches) ? payload.patches : [];
            patches.forEach((patch) => {
              const delta = extractEventDelta(Object.assign({ type: "server:patch", delta: patch }, patch));
              if (delta && store.tables.includes(delta.table)) {
                notifyTable(delta.table, delta.record ? [delta.record] : [{ id: delta.id }], {
                  delta: true,
                  action: delta.action,
                  recordRef: delta.recordRef,
                  eventId: delta.eventId,
                  cursor: delta.cursor || payload.cursor || null,
                  sequence: delta.sequence || payload.sequence || null,
                  patch: delta.patch || patch,
                  batch: true,
                });
              }
            });
          }
          if (payload && (payload.type === "server:event" || payload.type === "server:patch")) {
            const delta = extractEventDelta(payload);
            if (delta && store.tables.includes(delta.table)) {
              notifyTable(delta.table, delta.record ? [delta.record] : [{ id: delta.id }], {
                delta: true,
                action: delta.action,
                recordRef: delta.recordRef,
                eventId: delta.eventId,
                cursor: delta.cursor,
                sequence: delta.sequence,
                patch: delta.patch,
              });
            }
          }
          if (payload && payload.type === "ping") {
            try { ws.send(JSON.stringify({ type: "pong", ts: nowIso() })); } catch (_error) {}
          }
        };
        ws.onclose = () => handleDisconnect();
        ws.onerror = () => {
          closeSocket();
          store.setConnectionState("offline");
          resolve(false);
        };
      } catch (_error) {
        closeSocket();
        resolve(false);
      }
    }

    return {
      config: Object.assign({}, this.config, { mode: "native-rest-ws" }),
      connect() {
        if (connected || ws) return Promise.resolve(true);
        return new Promise((resolve) => {
          ensureSocketOpen(resolve);
        });
      },
      ready() {
        return Promise.resolve(connected);
      },
      watch(table, handler) {
        if (typeof handler !== "function") return function noop() {};
        if (!tableWatchers.has(table)) tableWatchers.set(table, new Set());
        tableWatchers.get(table).add(handler);
        return () => {
          const set = tableWatchers.get(table);
          if (set) set.delete(handler);
        };
      },
      query: search,
      read: readRecord,
      save: saveRecord,
      update: saveRecord,
      insert: saveRecord,
      delete: deleteRecord,
    };
  }

  attachRemoteWatchers() {
    if (!this.remote || typeof this.remote.watch !== "function") return;
    this.tables.forEach((tableName) => {
      try {
        this.remote.watch(tableName, (rows, meta = {}) => {
          if (meta && meta.delta) {
            this.applyRemoteDelta(tableName, coerceArray(rows)[0] || null, meta);
            return;
          }
          this.applyRemoteSnapshot(tableName, coerceArray(rows), meta);
        }, { immediate: false });
      } catch (_error) {}
    });
  }

  async seedLocalCache() {
    if (!this.local || typeof this.local.query !== "function") return;
    await Promise.all(this.tables.map(async (tableName) => {
      const rows = await this.local.query(tableName, {}).catch(() => []);
      if (rows.length) this.replaceCache(tableName, rows, { silent: true });
    })).catch(() => {});
    this.tables.forEach((tableName) => this.emit(tableName));
  }

  connect() {
    if (this.connectStarted || !this.remote || typeof this.remote.connect !== "function") return Promise.resolve(this);
    this.connectStarted = true;
    this.setConnectionState("connecting");
    return Promise.resolve()
      .then(() => this.remote.connect())
      .then((connected) => {
        if (connected === false) throw new Error("WS v3 connect failed");
        this.reconnectAttempts = 0;
        this.setConnectionState("connected");
        this.bootstrapActiveWatchers();
        this.flushOutbox();
      })
      .catch((error) => {
        this.connectStarted = false;
        this.setConnectionState("offline");
        this.scheduleReconnect();
        this.config.logger.warn?.("[MasStoreV3] Background WS connect failed:", error);
      })
      .then(() => this);
  }

  scheduleReconnect() {
    if (!this.remote || this.reconnectTimer) return;
    const attempt = Math.min(this.reconnectAttempts + 1, 8);
    this.reconnectAttempts = attempt;
    const delay = Math.min(30000, 750 * Math.pow(2, attempt - 1));
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  ready() {
    return Promise.resolve(this.readyState);
  }

  getRecordIdentity(tableName, record) {
    if (!record || typeof record !== "object") return null;
    if (typeof this.config.identityResolver === "function") {
      const value = this.config.identityResolver(tableName, record);
      if (value !== undefined && value !== null && value !== "") return String(value);
    }
    return normalizeToken(record.id || record.uuid || record.uid || record.key || "");
  }

  normalizeRecordIdentity(tableName, record) {
    if (!record || typeof record !== "object") return record;
    const normalized = typeof this.config.recordNormalizer === "function"
      ? this.config.recordNormalizer(tableName, record)
      : Object.assign({}, record);
    const id = this.getRecordIdentity(tableName, normalized);
    if (id && (normalized.id === undefined || normalized.id === null || normalized.id === "")) {
      normalized.id = id;
    }
    return normalized;
  }

  normalizeRecordList(tableName, rows) {
    return coerceArray(rows)
      .map((row) => this.normalizeRecordIdentity(tableName, row))
      .filter((row) => row && row.id != null);
  }

  watch(tableName, handler, options = {}) {
    const table = String(tableName || "");
    if (!table || typeof handler !== "function") return function noop() {};
    const watcher = {
      handler,
      filters: options.filters || options.filter || options.query || null,
      userId: options.userId || options.user_id || null,
      conversationId: options.conversationId || options.conversation_id || null,
      scope: options.scope || null,
      dedupe: options.dedupe !== false,
      bootstrap: options.bootstrap !== false,
      lastSignature: null,
    };
    if (!this.watchers.has(table)) this.watchers.set(table, new Set());
    this.watchers.get(table).add(watcher);
    if (options.immediate !== false) {
      Promise.resolve()
        .then(() => this.deliverWatcher(table, watcher, { table, source: "cache" }))
        .catch(() => {});
    }
    if (watcher.bootstrap) {
      Promise.resolve()
        .then(() => this.bootstrapWatcher(table, watcher))
        .catch((error) => {
          this.config.logger.debug?.(`[MasStoreV3] Bootstrap skipped for ${table}:`, error);
        });
    }
    return () => {
      const set = this.watchers.get(table);
      if (set) set.delete(watcher);
    };
  }

  async query(tableName, filters = {}) {
    const table = String(tableName || "");
    const localRows = await this.queryLocal(table, filters);
    if (localRows.length) {
      this.refreshRemote(table, filters);
      return localRows;
    }
    const remoteRows = await this.queryRemote(table, filters);
    if (remoteRows.length) {
      await this.saveLocalRows(table, remoteRows);
      this.mergeCache(table, remoteRows);
      return applyFilter(remoteRows, filters);
    }
    return [];
  }

  async read(tableName, id) {
    const table = String(tableName || "");
    const key = normalizeToken(id);
    if (!key) return null;
    if (this.local && typeof this.local.read === "function") {
      const local = await this.local.read(table, key).catch(() => null);
      if (local) return this.normalizeRecordIdentity(table, local);
    }
    const rows = await this.query(table, {});
    return rows.find((row) => row && String(this.getRecordIdentity(table, row) || row.id) === key) || null;
  }

  async save(tableName, record, meta = {}) {
    const table = String(tableName || "");
    if (!record || typeof record !== "object") throw new Error("[MasStoreV3] record object required");
    const normalized = this.normalizeRecordIdentity(table, record);
    await this.saveLocalRows(table, [normalized]);
    this.upsertCache(table, normalized);
    this.scheduleEmit(table);

    this.enqueueMutation("save", table, normalized, meta);
    this.flushOutbox();
    return clone(normalized);
  }

  insert(tableName, record, meta = {}) {
    return this.save(tableName, record, meta);
  }

  update(tableName, record, meta = {}) {
    return this.save(tableName, record, meta);
  }

  async delete(tableName, ref, meta = {}) {
    const table = String(tableName || "");
    const id = typeof ref === "object" ? (this.getRecordIdentity(table, ref) || ref.id) : ref;
    if (this.local && typeof this.local.remove === "function") {
      await this.local.remove(table, id).catch(() => {});
    }
    this.removeCache(table, id);
    this.scheduleEmit(table);
    this.enqueueMutation("delete", table, { id }, meta);
    this.flushOutbox();
    return true;
  }

  async queryLocal(tableName, filters) {
    if (!this.local || typeof this.local.query !== "function") return [];
    const rows = await this.local.query(tableName, filters).catch(() => []);
    return filterLiveRows(tableName, applyFilter(this.normalizeRecordList(tableName, rows), filters));
  }

  async queryRemote(tableName, filters) {
    if (!this.remote || typeof this.remote.query !== "function") return [];
    const rows = await this.remote.query(tableName, normalizeFilter(filters)).catch(() => []);
    return filterLiveRows(tableName, applyFilter(this.normalizeRecordList(tableName, rows), filters));
  }

  refreshRemote(tableName, filters) {
    Promise.resolve()
      .then(() => this.queryRemote(tableName, filters))
      .then(async (rows) => {
        if (!rows.length) return;
        await this.saveLocalRows(tableName, rows);
        this.mergeCache(tableName, rows);
      })
      .catch(() => {});
  }

  bootstrapActiveWatchers() {
    this.watchers.forEach((set, tableName) => {
      set.forEach((watcher) => {
        if (!watcher || watcher.bootstrap === false) return;
        this.bootstrapWatcher(tableName, watcher).catch(() => {});
      });
    });
  }

  buildBootstrapQueries(tableName, watcher = {}) {
    const table = String(tableName || "");
    const filters = normalizeFilter(watcher.filters || {});
    const hasExplicitFilters = Object.keys(filters).length > 0;
    const userId = normalizeToken(
      watcher.userId ||
      filters.userId ||
      filters.user_id ||
      readStoredSession().userId ||
      "",
    );
    const conversationId = normalizeToken(
      watcher.conversationId ||
      filters.conversationId ||
      filters.conversation_id ||
      "",
    );

    if (!this.tables.includes(table) && !hasExplicitFilters) return [];

    if (table === "messages") {
      if (conversationId) return [Object.assign({}, filters, { conversation_id: conversationId })];
      if (hasExplicitFilters) return [filters];
      if (userId) return [{}];
      return [];
    }

    if (table === "notifications") {
      if (hasExplicitFilters) return [filters];
      if (userId) return [{ user_id: userId }];
      return [];
    }

    if (table === "conversations") {
      if (hasExplicitFilters) return [filters];
      if (!userId) return [];
      return [
        { participant_1: userId },
        { participant_2: userId },
        { participant1: userId },
        { participant2: userId },
        { user_id: userId },
        { recipient_id: userId },
      ];
    }

    return hasExplicitFilters ? [filters] : [{}];
  }

  bootstrapWatcher(tableName, watcher = {}) {
    if (!this.remote || typeof this.remote.query !== "function") return Promise.resolve([]);
    const queries = this.buildBootstrapQueries(tableName, watcher);
    if (!queries.length) return Promise.resolve([]);
    const key = `${tableName}:${JSON.stringify(queries)}`;
    if (this.bootstrapRequests.has(key)) return this.bootstrapRequests.get(key);
    const request = Promise.all(queries.map((filters) => this.queryRemote(tableName, filters)))
      .then(async (chunks) => {
        const rows = uniqueRows(chunks.flatMap((chunk) => coerceArray(chunk)));
        if (!rows.length) return [];
        await this.saveLocalRows(tableName, rows);
        this.mergeCache(tableName, rows);
        return rows;
      })
      .finally(() => {
        setTimeout(() => this.bootstrapRequests.delete(key), 1500);
      });
    this.bootstrapRequests.set(key, request);
    return request;
  }

  async saveLocalRows(tableName, rows) {
    if (!this.local || typeof this.local.save !== "function") return;
    const cleanRows = this.normalizeRecordList(tableName, rows);
    if (cleanRows.length) await this.local.save(tableName, cleanRows).catch(() => {});
  }

  listCache(tableName, filters = null) {
    return clone(applyFilter(this.cache.get(tableName) || [], filters));
  }

  normalizeRows(tableName, rows) {
    return filterLiveRows(tableName, this.normalizeRecordList(tableName, rows))
      .sort((left, right) => compareRows(tableName, left, right));
  }

  replaceCache(tableName, rows, options = {}) {
    const list = this.normalizeRows(tableName, rows);
    this.cache.set(tableName, clone(list));
    if (!options.silent) this.scheduleEmit(tableName);
  }

  mergeCache(tableName, rows, options = {}) {
    this.normalizeRecordList(tableName, rows).forEach((row) => this.upsertCache(tableName, row));
    if (!options.silent) this.scheduleEmit(tableName);
  }

  applyRemoteSnapshot(tableName, rows, meta = {}) {
    const list = filterLiveRows(tableName, this.normalizeRecordList(tableName, rows));
    const current = this.cache.get(tableName) || [];
    const isAuthoritativeClear =
      meta &&
      (meta.clear === true ||
        meta.full === true ||
        meta.authoritative === true ||
        meta.source === "delete" ||
        meta.action === "clear");

    // Android/local-file starts from IndexedDB, then WS may emit an empty first
    // frame before auth/live-data scoping is complete. Never let that transient
    // empty frame erase visible chat data.
    if (!list.length && current.length && !isAuthoritativeClear) {
      this.config.logger.debug?.(`[MasStoreV3] Ignored empty remote snapshot for ${tableName}; keeping local cache`);
      return;
    }

    if (list.length) {
      this.mergeCache(tableName, list);
      this.saveLocalRows(tableName, list);
      return;
    }

    this.replaceCache(tableName, list);
  }

  applyRemoteDelta(tableName, record, meta = {}) {
    const table = String(tableName || "");
    this.rememberCursor(table, meta.cursor || meta.patch?.cursor || null, meta);
    this.notify("patch", {
      table,
      action: meta.action,
      record: clone(record),
      recordRef: clone(meta.recordRef || null),
      cursor: clone(meta.cursor || meta.patch?.cursor || null),
      eventId: meta.eventId || "",
      batch: !!meta.batch,
    });
    const normalizedRecord = record && typeof record === "object" ? this.normalizeRecordIdentity(table, record) : record;
    const id =
      normalizedRecord && (normalizedRecord.id || normalizedRecord.key) ||
      meta.recordRef && (meta.recordRef.id || meta.recordRef.key || meta.recordRef.recordKey) ||
      null;
    if (isDeleteAction(meta.action)) {
      if (id != null) {
        this.removeCache(table, id);
        if (this.local && typeof this.local.remove === "function") {
          this.local.remove(table, id).catch(() => {});
        }
        this.scheduleEmit(table);
      }
      return;
    }
    if (!normalizedRecord || typeof normalizedRecord !== "object" || id == null) return;
    const patchRecord = meta.patch && meta.patch.changed && typeof meta.patch.changed === "object"
      ? Object.assign({}, { id }, meta.patch.changed)
      : normalizedRecord;
    this.upsertCache(table, patchRecord);
    this.saveLocalRows(table, [this.listCache(table).find((row) => row && String(row.id) === String(id)) || patchRecord]);
    this.scheduleEmit(table);
  }

  upsertCache(tableName, record) {
    const normalized = this.normalizeRecordIdentity(tableName, record);
    if (!normalized || normalized.id == null) return;
    const rows = this.listCache(tableName);
    const key = String(normalized.id);
    const index = rows.findIndex((row) => row && String(row.id) === key);
    if (index >= 0) rows[index] = Object.assign({}, rows[index], clone(normalized));
    else rows.push(clone(normalized));
    this.cache.set(tableName, this.normalizeRows(tableName, rows));
  }

  removeCache(tableName, id) {
    const key = String(id);
    const rows = this.listCache(tableName).filter((row) => !(row && String(row.id) === key));
    this.cache.set(tableName, this.normalizeRows(tableName, rows));
  }

  scheduleEmit(tableName) {
    const table = String(tableName || "");
    if (!table) return;
    if (this.emitTimers.has(table)) return;
    const flush = () => {
      this.emitTimers.delete(table);
      this.emit(table);
    };
    if (typeof requestAnimationFrame === "function") {
      this.emitTimers.set(table, requestAnimationFrame(flush));
      return;
    }
    this.emitTimers.set(table, setTimeout(flush, 16));
  }

  emit(tableName) {
    const handlers = this.watchers.get(tableName);
    if (!handlers || !handlers.size) return;
    handlers.forEach((watcher) => {
      this.deliverWatcher(tableName, watcher, { table: tableName, source: "mas-store-v3" });
    });
  }

  deliverWatcher(tableName, watcher, meta) {
    const rows = this.listCache(tableName, watcher.filters);
    if (watcher.dedupe) {
      const signature = rowsSignature(rows);
      if (signature === watcher.lastSignature) return;
      watcher.lastSignature = signature;
    }
    try {
      watcher.handler(rows, meta);
    } catch (_error) {}
  }

  on(eventName, handler) {
    const event = String(eventName || "");
    if (!event || typeof handler !== "function") return function noop() {};
    if (!this.events.has(event)) this.events.set(event, new Set());
    this.events.get(event).add(handler);
    return () => {
      const set = this.events.get(event);
      if (set) set.delete(handler);
    };
  }

  notify(eventName, payload) {
    const set = this.events.get(eventName);
    if (!set || !set.size) return;
    set.forEach((handler) => {
      try { handler(clone(payload)); } catch (_error) {}
    });
  }

  setConnectionState(nextState) {
    if (this.connectionState === nextState) return;
    this.connectionState = nextState;
    this.notify("status", this.getStatus());
  }

  getStatus() {
    return {
      ready: this.readyState,
      connection: this.connectionState,
      pending: this.outbox.length,
      tables: this.tables.slice(),
      branchId: this.config.branchId || "",
      moduleId: this.config.moduleId || "",
      cursors: this.getCursors(),
    };
  }

  loadCursors() {
    if (typeof window === "undefined" || !window.localStorage || !this.cursorKey) return {};
    try {
      const parsed = JSON.parse(window.localStorage.getItem(this.cursorKey) || "{}");
      return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
    } catch (_error) {
      return {};
    }
  }

  persistCursors() {
    if (typeof window === "undefined" || !window.localStorage || !this.cursorKey) return;
    try {
      window.localStorage.setItem(this.cursorKey, JSON.stringify(this.cursors || {}));
    } catch (_error) {}
  }

  getCursors() {
    return clone(this.cursors || {});
  }

  mergeCursors(nextCursors) {
    if (!nextCursors || typeof nextCursors !== "object") return;
    Object.keys(nextCursors).forEach((tableName) => {
      this.rememberCursor(tableName, nextCursors[tableName]);
    });
  }

  cursorSequence(cursor) {
    if (!cursor) return 0;
    if (typeof cursor === "number" && Number.isFinite(cursor)) return cursor;
    if (typeof cursor === "string") {
      const parsed = Number(cursor.replace(/^[^0-9-]*/, "").split(/[^0-9.-]/)[0]);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    if (typeof cursor === "object") {
      const parsed = Number(cursor.sequence || cursor.seq || cursor.cursor || cursor.version || 0);
      return Number.isFinite(parsed) ? parsed : 0;
    }
    return 0;
  }

  rememberCursor(tableName, cursor, meta = {}) {
    const table = String(tableName || "");
    if (!table || !cursor) return;
    const nextCursor = typeof cursor === "object"
      ? Object.assign({}, cursor)
      : { sequence: this.cursorSequence(cursor), value: cursor };
    if (meta.eventId && !nextCursor.eventId) nextCursor.eventId = meta.eventId;
    if (meta.sequence && !nextCursor.sequence) nextCursor.sequence = meta.sequence;
    if (!nextCursor.updatedAt) nextCursor.updatedAt = nowIso();
    const current = this.cursors && this.cursors[table] ? this.cursors[table] : null;
    if (this.cursorSequence(current) > this.cursorSequence(nextCursor)) return;
    this.cursors = Object.assign({}, this.cursors || {}, { [table]: nextCursor });
    this.persistCursors();
    this.notify("status", this.getStatus());
  }

  loadOutbox() {
    if (typeof window === "undefined" || !window.localStorage || !this.outboxKey) return [];
    try {
      const parsed = JSON.parse(window.localStorage.getItem(this.outboxKey) || "[]");
      return Array.isArray(parsed) ? parsed.filter((job) => job && job.table && job.action) : [];
    } catch (_error) {
      return [];
    }
  }

  persistOutbox() {
    if (typeof window === "undefined" || !window.localStorage || !this.outboxKey) return;
    try {
      window.localStorage.setItem(this.outboxKey, JSON.stringify(this.outbox.slice(-500)));
    } catch (_error) {}
    this.notify("status", this.getStatus());
  }

  enqueueMutation(action, table, record, meta = {}) {
    if (!this.remote) return;
    const id = record && record.id != null ? String(record.id) : createId("mutation");
    const job = {
      id: createId("job"),
      action,
      table,
      record: clone(record),
      meta: clone(meta || {}),
      recordId: id,
      attempts: 0,
      createdAt: nowIso(),
      nextAttemptAt: 0,
    };
    this.outbox.push(job);
    this.persistOutbox();
  }

  startOutboxLoop() {
    if (this.flushTimer) return;
    this.flushTimer = setInterval(() => this.flushOutbox(), this.config.retryIntervalMs);
    if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
      const onlineHandler = () => {
        this.connect();
        this.flushOutbox();
      };
      window.addEventListener("online", onlineHandler);
      this.onlineUnsubscribe = () => window.removeEventListener("online", onlineHandler);
    }
  }

  async flushOutbox() {
    if (this.flushLock || !this.remote || !this.outbox.length) return;
    this.flushLock = true;
    try {
      const remaining = [];
      for (const job of this.outbox) {
        if (!job || Number(job.nextAttemptAt || 0) > Date.now()) {
          remaining.push(job);
          continue;
        }
        try {
          await this.applyRemoteMutation(job);
          this.setConnectionState("connected");
        } catch (error) {
          job.attempts = Number(job.attempts || 0) + 1;
          if (job.attempts < this.config.maxRetries) {
            job.lastError = error?.message || String(error || "remote mutation failed");
            job.nextAttemptAt = Date.now() + Math.min(60000, this.config.retryIntervalMs * Math.pow(2, Math.min(job.attempts, 5)));
            remaining.push(job);
          } else {
            this.config.logger.warn?.(`[MasStoreV3] Dropping failed ${job.action} for ${job.table}/${job.recordId}:`, error);
            this.notify("error", { job: clone(job), error: error?.message || String(error || "") });
          }
          this.setConnectionState("offline");
        }
      }
      this.outbox = remaining;
      this.persistOutbox();
    } finally {
      this.flushLock = false;
    }
  }

  async applyRemoteMutation(job) {
    if (!this.remote) throw new Error("remote store unavailable");
    if (job.action === "delete") {
      if (typeof this.remote.delete !== "function") throw new Error("remote delete unavailable");
      return this.remote.delete(job.table, { id: job.recordId }, job.meta || {});
    }
    if (typeof this.remote.save === "function") return this.remote.save(job.table, job.record, job.meta || {});
    if (typeof this.remote.update === "function") return this.remote.update(job.table, job.record, job.meta || {});
    if (typeof this.remote.insert === "function") return this.remote.insert(job.table, job.record, job.meta || {});
    throw new Error("remote save unavailable");
  }
}

const defaultStore = new MasStoreV3();

export { MasStoreV3, DEFAULT_TABLES };
export default defaultStore;
