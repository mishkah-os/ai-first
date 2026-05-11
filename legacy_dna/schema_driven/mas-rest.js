;(function (global) {
  if (!global) return;
  var host = global.MAS || global.Mishkah || global.Mishka || global.mas || global.mishkah || {};
  global.MAS = host;
  global.Mishkah = host;
  global.Mishka = host;
  global.mas = host;
  global.mishkah = host;
  if (global.MASAutoConfig && !global.MishkahAutoConfig) global.MishkahAutoConfig = global.MASAutoConfig;
  if (global.MishkahAutoConfig && !global.MASAutoConfig) global.MASAutoConfig = global.MishkahAutoConfig;
})(typeof window !== 'undefined' ? window : (typeof globalThis !== 'undefined' ? globalThis : this));
(function (global) {
    'use strict';

    var M = global.Mishkah || {};
    global.Mishkah = M;

    var API_BASE = '/api/v1';
    var BOOT_CONFIG = global.MISHKAH_REST_CONFIG || {};
    var BASE_DOMAIN = BOOT_CONFIG.baseDomain || global.MISHKAH_BASE_DOMAIN || global.BASE_DOMAIN || global.basedomain || '';
    var HydrationConfig = {
        mode: BOOT_CONFIG.hydration || 'hydrated' // hydrated | raw
    };
    var HydrationResolver = typeof BOOT_CONFIG.hydrationResolver === 'function'
        ? BOOT_CONFIG.hydrationResolver
        : null;
    var DEFAULT_BRANCH = global.MISHKAH_BRANCH || global.BRANCH_ID || 'pt';
    var DEFAULT_MODULE = global.MISHKAH_MODULE || global.MODULE_ID || '';
    var RequestDefaults = {
        headers: Object.assign({}, BOOT_CONFIG.headers || {}),
        credentials: BOOT_CONFIG.credentials || null
    };
    var Utils = (global.Mishkah && global.Mishkah.utils) || {};
    var StableStringify = Utils.JSON && typeof Utils.JSON.stableStringify === 'function'
        ? Utils.JSON.stableStringify
        : function (obj) { try { return JSON.stringify(obj); } catch (_e) { return ''; } };

    var AdapterRegistry = new Map();
    var QueueRegistry = new Map();
    var QueueListeners = new Set();
    var SyncRegistry = new Map();
    var SyncListeners = new Set();
    var PolicyResolver = null;
    var Inflight = new Map();

    var CacheConfig = {
        enabled: true,
        policy: 'stale-while-revalidate', // cache-only | network-first | stale-while-revalidate | network-only
        ttlMs: 60 * 1000
    };

    var QueueConfig = {
        enabled: true,
        maxRetries: 5,
        baseDelayMs: 2000,
        maxDelayMs: 60000,
        retryIntervalMs: 50000,
        logLimit: 200
    };

    var SyncConfig = {
        enabled: false,
        endpoint: '/api/sync',
        autoBootstrap: false,
        intervalMs: 60000,
        useEtag: true,
        immediate: true
    };

    function parseTimestamp(value) {
        if (value === undefined || value === null) return null;
        if (value instanceof Date) {
            var dateTs = value.getTime();
            return Number.isFinite(dateTs) ? dateTs : null;
        }
        if (typeof value === 'number' && Number.isFinite(value)) {
            if (value > 1e12) return Math.round(value);
            if (value > 1e9) return Math.round(value * 1000);
            return Math.round(value);
        }
        if (typeof value === 'string') {
            var trimmed = value.trim();
            if (!trimmed) return null;
            if (/^-?\d+(?:\.\d+)?$/.test(trimmed)) {
                var numeric = Number(trimmed);
                if (Number.isFinite(numeric)) return parseTimestamp(numeric);
            }
            var parsed = Date.parse(trimmed);
            return Number.isNaN(parsed) ? null : parsed;
        }
        return null;
    }

    function cloneValue(value) {
        if (value === null || value === undefined) return value;
        if (typeof global.structuredClone === 'function') {
            try { return global.structuredClone(value); } catch (_e) { }
        }
        try { return JSON.parse(JSON.stringify(value)); } catch (_err) { }
        if (Array.isArray(value)) return value.slice();
        if (value && typeof value === 'object') return Object.assign({}, value);
        return value;
    }

    function coerceArray(value) {
        if (Array.isArray(value)) return value;
        if (!value || typeof value !== 'object') return [];
        if (Array.isArray(value.rows)) return value.rows;
        if (Array.isArray(value.items)) return value.items;
        if (Array.isArray(value.list)) return value.list;
        if (Array.isArray(value.data)) return value.data;
        if (Array.isArray(value.values)) return value.values;
        if (Array.isArray(value.records)) return value.records;
        if (Array.isArray(value.tables)) return value.tables;
        return [];
    }

    function extractRecord(value, fallback) {
        if (value && typeof value === 'object' && value.record && typeof value.record === 'object') {
            return value.record;
        }
        if (value && typeof value === 'object' && !Array.isArray(value) && value.id) {
            return value;
        }
        if (fallback && typeof fallback === 'object' && fallback.record && typeof fallback.record === 'object') {
            return fallback.record;
        }
        if (fallback && typeof fallback === 'object' && !Array.isArray(fallback) && fallback.id) {
            return fallback;
        }
        return null;
    }

    function getAdapter(namespace) {
        if (!global.MishkahIndexedDB || typeof global.MishkahIndexedDB.createAdapter !== 'function') return null;
        var ns = namespace || 'default';
        if (AdapterRegistry.has(ns)) return AdapterRegistry.get(ns);
        var adapter = global.MishkahIndexedDB.createAdapter({
            namespace: ns,
            name: 'mishkah-rest-cache',
            version: 1
        });
        AdapterRegistry.set(ns, adapter);
        return adapter;
    }

    function resolveBranchFromSession() {
        try {
            var raw = global.localStorage ? global.localStorage.getItem('mishkah_user') : null;
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            return parsed && (parsed.brname || parsed.branch_id || parsed.branchId) || null;
        } catch (_e) {
            return null;
        }
    }

    function resolveModuleFromSession() {
        try {
            var raw = global.localStorage ? global.localStorage.getItem('mishkah_user') : null;
            if (!raw) return null;
            var parsed = JSON.parse(raw);
            return parsed && (parsed.module || parsed.module_id || parsed.moduleId || parsed.modname) || null;
        } catch (_e) {
            return null;
        }
    }

    function getEffectiveBranch(options) {
        return (options && options.branch) || resolveBranchFromSession() || DEFAULT_BRANCH;
    }

    function getEffectiveModule(options) {
        return (options && options.module) || resolveModuleFromSession() || DEFAULT_MODULE || '';
    }

    function getContext(options) {
        var branch = getEffectiveBranch(options) || 'default';
        var moduleId = getEffectiveModule(options) || 'default';
        return {
            branch: branch,
            module: moduleId,
            key: branch + '::' + moduleId
        };
    }

    function isAbsoluteUrl(url) {
        return /^https?:\/\//i.test(String(url || ''));
    }

    function joinUrl(base, path) {
        if (!base) return path;
        if (!path) return base;
        var b = String(base).replace(/\/+$/, '');
        var p = String(path);
        if (!p.startsWith('/')) p = '/' + p;
        return b + p;
    }

    function stripQuery(endpoint) {
        var value = String(endpoint || '');
        var index = value.indexOf('?');
        return index === -1 ? value : value.slice(0, index);
    }

    function appendQueryParam(endpoint, key, value) {
        if (value === undefined || value === null || value === '') return endpoint;
        var needle = key + '=';
        if (endpoint.indexOf(needle) !== -1) return endpoint;
        var separator = endpoint.indexOf('?') === -1 ? '?' : '&';
        return endpoint + separator + encodeURIComponent(key) + '=' + encodeURIComponent(value);
    }

    function shouldAttachModule(endpoint) {
        var path = stripQuery(endpoint);
        return path === '/crud/tables' || path.indexOf('/crud/') === 0;
    }

    function withContext(endpoint, options) {
        var next = String(endpoint || '');
        var branch = getEffectiveBranch(options);
        var moduleId = getEffectiveModule(options);
        if (branch) next = appendQueryParam(next, 'branch', branch);
        if (moduleId && shouldAttachModule(next)) next = appendQueryParam(next, 'module', moduleId);
        return next;
    }

    function buildApiUrl(endpoint, options) {
        var effectiveEndpoint = withContext(endpoint, options);
        if (isAbsoluteUrl(effectiveEndpoint)) return effectiveEndpoint;
        var baseDomain = (options && options.baseDomain) || BASE_DOMAIN || '';
        if (isAbsoluteUrl(API_BASE)) {
            return joinUrl(API_BASE, effectiveEndpoint.replace(/^\//, ''));
        }
        if (baseDomain) {
            return joinUrl(baseDomain, API_BASE) + effectiveEndpoint;
        }
        return API_BASE + effectiveEndpoint;
    }

    function buildSyncUrl(options) {
        var endpoint = (options && options.syncEndpoint) || SyncConfig.endpoint || '/api/sync';
        var ctx = getContext(options);
        if (!ctx.branch || !ctx.module || ctx.module === 'default') {
            throw new Error('Sync requires both branch and module.');
        }
        var suffix = '/' + encodeURIComponent(ctx.branch) + '/' + encodeURIComponent(ctx.module);
        if (isAbsoluteUrl(endpoint)) {
            return endpoint.replace(/\/+$/, '') + suffix;
        }
        var relative = endpoint.charAt(0) === '/' ? endpoint : ('/' + endpoint);
        var baseDomain = (options && options.baseDomain) || BASE_DOMAIN || '';
        if (baseDomain) {
            return joinUrl(baseDomain, relative) + suffix;
        }
        return relative + suffix;
    }

    function getGlobalDevApiKey() {
        var config = global.APP_CONFIG || {};
        var restConfig = global.MISHKAH_REST_CONFIG || {};
        return (restConfig.devApiKey || restConfig.apiKey || config.devApiKey || config.apiKey || global.DEV_API_KEY || global.API_KEY || '').trim();
    }

    function applyGlobalAuthHeaders(headers) {
        var apiKey = getGlobalDevApiKey();
        if (!apiKey) return headers;
        if (!headers['x-api-key'] && !headers['X-API-KEY']) {
            headers['x-api-key'] = apiKey;
        }
        if (!headers['X-DEV-API-KEY'] && !headers['x-dev-api-key']) {
            headers['X-DEV-API-KEY'] = apiKey;
        }
        return headers;
    }

    function buildFetchConfig(method, data, options) {
        options = options || {};
        var headers = applyGlobalAuthHeaders(Object.assign({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }, RequestDefaults.headers || {}, options.headers || {}));

        if (!headers.Authorization) {
            try {
                var token = global.localStorage ? global.localStorage.getItem('mishkah_token') : null;
                if (token) headers.Authorization = 'Bearer ' + token;
            } catch (_e) { }
        }

        var config = {
            method: method,
            headers: headers
        };
        var credentials = options.credentials || RequestDefaults.credentials;
        if (credentials) config.credentials = credentials;
        if (data !== undefined && data !== null && method !== 'GET' && method !== 'HEAD') {
            config.body = JSON.stringify(data);
        }
        return config;
    }

    function requestRaw(endpoint, method, data, options) {
        var config = buildFetchConfig(method, data, options);
        var url = buildApiUrl(endpoint, options);
        return fetch(url, config).then(function (response) {
            if (!response.ok) {
                return response.json().catch(function () { return {}; }).then(function (err) {
                    var msg = err.error || err.message || ('HTTP ' + response.status);
                    var error = new Error(msg);
                    error.status = response.status;
                    error.statusText = response.statusText || '';
                    error.endpoint = endpoint;
                    error.method = method;
                    throw error;
                });
            }
            return response.json();
        });
    }

    function getQueueState(options) {
        var ctx = getContext(options);
        if (!QueueRegistry.has(ctx.key)) {
            QueueRegistry.set(ctx.key, {
                key: ctx.key,
                branch: ctx.branch,
                module: ctx.module,
                items: [],
                logs: [],
                loading: null,
                processing: false
            });
        }
        return QueueRegistry.get(ctx.key);
    }

    function emitQueueUpdate(options) {
        var state = getQueueState(options);
        var stats = {
            pending: state.items.filter(function (it) { return it.status === 'pending'; }).length,
            failed: state.items.filter(function (it) { return it.status === 'failed'; }).length
        };
        QueueListeners.forEach(function (handler) {
            try {
                handler({
                    key: state.key,
                    branch: state.branch,
                    module: state.module,
                    stats: stats,
                    items: state.items.slice(),
                    logs: state.logs.slice()
                });
            } catch (_e) { }
        });
    }

    function computeBackoff(retries) {
        var base = QueueConfig.baseDelayMs;
        var delay = base * Math.pow(2, Math.max(0, retries - 1));
        var jitter = Math.floor(delay * (0.8 + Math.random() * 0.4));
        return Math.min(QueueConfig.maxDelayMs, jitter);
    }

    async function loadQueue(options) {
        var state = getQueueState(options);
        if (state.loading) return state.loading;
        var adapter = getAdapter(state.key);
        if (!adapter) {
            state.items = state.items || [];
            state.logs = state.logs || [];
            emitQueueUpdate(state);
            return Promise.resolve(state);
        }
        state.loading = Promise.all([
            adapter.load('__queue__'),
            adapter.load('__queue_logs__')
        ]).then(function (results) {
            var queuePayload = results[0];
            var logPayload = results[1];
            state.items = (queuePayload && queuePayload.data && queuePayload.data.items) || [];
            state.logs = (logPayload && logPayload.data && logPayload.data.logs) || [];
            emitQueueUpdate(state);
            return state;
        }).catch(function () {
            state.items = state.items || [];
            state.logs = state.logs || [];
            emitQueueUpdate(state);
            return state;
        });
        return state.loading;
    }

    async function saveQueue(options) {
        var state = getQueueState(options);
        var adapter = getAdapter(state.key);
        if (!adapter) return;
        await adapter.save('__queue__', { items: state.items }, { metadata: { savedAt: Date.now() }, mergeMetadata: false });
        await adapter.save('__queue_logs__', { logs: state.logs }, { metadata: { savedAt: Date.now() }, mergeMetadata: false });
    }

    function logQueueFailure(options, item, error) {
        var state = getQueueState(options);
        var entry = {
            id: 'log-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
            time: new Date().toISOString(),
            method: item.method,
            endpoint: item.endpoint,
            error: (error && error.message) || String(error || 'unknown-error'),
            retries: item.retries || 0,
            itemId: item.id
        };
        state.logs.unshift(entry);
        if (state.logs.length > QueueConfig.logLimit) state.logs.length = QueueConfig.logLimit;
    }

    function getSyncState(options) {
        var ctx = getContext(options);
        if (!SyncRegistry.has(ctx.key)) {
            SyncRegistry.set(ctx.key, {
                key: ctx.key,
                branch: ctx.branch,
                module: ctx.module,
                version: null,
                updatedAt: null,
                etag: null,
                serverId: null,
                tables: [],
                lastSyncAt: null,
                loading: null,
                syncing: null,
                timerId: null,
                loaded: false,
                error: null
            });
        }
        return SyncRegistry.get(ctx.key);
    }

    function snapshotSyncState(state) {
        return {
            key: state.key,
            branch: state.branch,
            module: state.module,
            version: state.version,
            updatedAt: state.updatedAt,
            etag: state.etag,
            serverId: state.serverId,
            tables: Array.isArray(state.tables) ? state.tables.slice() : [],
            lastSyncAt: state.lastSyncAt,
            error: state.error || null
        };
    }

    function emitSyncUpdate(options, extra) {
        var state = getSyncState(options);
        var payload = Object.assign({}, snapshotSyncState(state), extra || {});
        SyncListeners.forEach(function (handler) {
            try { handler(payload); } catch (_e) { }
        });
    }

    async function loadSyncMetadata(options) {
        var state = getSyncState(options);
        if (state.loaded) return state;
        if (state.loading) return state.loading;
        var adapter = getAdapter(state.key);
        if (!adapter) {
            state.loaded = true;
            return Promise.resolve(state);
        }
        state.loading = adapter.load('__sync_meta__').then(function (payload) {
            var data = payload && payload.data && typeof payload.data === 'object' ? payload.data : {};
            state.version = data.version !== undefined ? data.version : state.version;
            state.updatedAt = data.updatedAt || state.updatedAt;
            state.etag = data.etag || state.etag;
            state.serverId = data.serverId || state.serverId;
            state.tables = Array.isArray(data.tables) ? data.tables.slice() : [];
            state.lastSyncAt = data.lastSyncAt || state.lastSyncAt;
            state.loaded = true;
            return state;
        }).catch(function () {
            state.loaded = true;
            return state;
        });
        return state.loading;
    }

    async function readTableCache(tableName, options) {
        var ctx = getContext(options);
        var adapter = getAdapter(ctx.key);
        if (!adapter) return null;
        await loadSyncMetadata(ctx);
        var payload = await adapter.load(tableName).catch(function () { return null; });
        if (!payload || !Array.isArray(payload.data)) return null;
        return {
            data: payload.data.slice(),
            meta: payload.meta || {}
        };
    }

    function normalizeComparableValue(value) {
        if (value && typeof value === 'object') {
            if (value.id !== undefined) return value.id;
            if (value.value !== undefined) return value.value;
        }
        return value;
    }

    function matchesSearch(row, params) {
        if (!row || typeof row !== 'object') return false;
        var body = params || {};
        var skipKeys = {
            page: true,
            limit: true,
            q: true,
            withMeta: true,
            cacheMode: true,
            cache: true,
            seed: true,
            fresh: true,
            hydration: true,
            branch: true,
            module: true
        };
        var q = body.q !== undefined && body.q !== null ? String(body.q).trim().toLowerCase() : '';
        if (q) {
            var haystacks = [];
            Object.keys(row).forEach(function (key) {
                var value = row[key];
                if (value === undefined || value === null) return;
                if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
                    haystacks.push(String(value).toLowerCase());
                    return;
                }
                if (value && typeof value === 'object') {
                    if (value.name !== undefined) haystacks.push(String(value.name).toLowerCase());
                    if (value.display_name !== undefined) haystacks.push(String(value.display_name).toLowerCase());
                }
            });
            if (!haystacks.some(function (entry) { return entry.indexOf(q) !== -1; })) return false;
        }
        for (var key in body) {
            if (!Object.prototype.hasOwnProperty.call(body, key)) continue;
            if (skipKeys[key]) continue;
            var actual = normalizeComparableValue(row[key]);
            var expected = normalizeComparableValue(body[key]);
            if (expected === undefined || expected === null || expected === '') continue;
            if (Array.isArray(actual)) {
                if (actual.indexOf(expected) === -1) return false;
                continue;
            }
            if (String(actual) !== String(expected)) return false;
        }
        return true;
    }

    function buildSearchResponse(rows, params) {
        var page = Number(params && params.page);
        var limit = Number(params && params.limit);
        page = Number.isFinite(page) && page > 0 ? page : 1;
        limit = Number.isFinite(limit) && limit > 0 ? limit : rows.length || 1000;
        var start = Math.max(0, (page - 1) * limit);
        var sliced = rows.slice(start, start + limit);
        return {
            data: sliced,
            count: rows.length,
            page: page,
            limit: limit
        };
    }

    async function resolveLocalSearch(tableName, params, options) {
        var cached = await readTableCache(tableName, options);
        if (!cached || !Array.isArray(cached.data)) return null;
        var rows = cached.data.filter(function (row) {
            return matchesSearch(row, params || {});
        });
        return buildSearchResponse(rows, params || {});
    }

    async function resolveLocalGet(tableName, id, options) {
        var cached = await readTableCache(tableName, options);
        if (!cached || !Array.isArray(cached.data)) return null;
        var match = cached.data.find(function (row) {
            return row && String(row.id) === String(id);
        }) || null;
        return match ? { record: cloneValue(match) } : null;
    }

    function getCrudTableName(endpoint) {
        var path = stripQuery(endpoint);
        if (!path || path.indexOf('/crud/') !== 0) return null;
        var parts = path.split('/');
        return parts.length >= 3 ? parts[2] : null;
    }

    function getCrudRecordId(endpoint) {
        var path = stripQuery(endpoint);
        if (!path || path.indexOf('/crud/') !== 0) return null;
        var parts = path.split('/');
        if (parts.length < 4) return null;
        if (parts[3] === 'search') return null;
        return decodeURIComponent(parts[3]);
    }

    function buildCrudCreateEndpoint(endpoint) {
        var value = String(endpoint || '');
        var queryIndex = value.indexOf('?');
        var query = queryIndex === -1 ? '' : value.slice(queryIndex);
        var path = stripQuery(value);
        if (!path || path.indexOf('/crud/') !== 0) return null;
        var parts = path.split('/');
        if (parts.length < 4 || !parts[2] || parts[3] === 'search') return null;
        return '/crud/' + encodeURIComponent(parts[2]) + query;
    }

    function isNotFoundError(error) {
        if (!error) return false;
        if (Number(error.status) === 404) return true;
        return /(^|\s)404(\s|$)|not[- ]found/i.test(String(error.message || ''));
    }

    function buildCacheKey(method, endpoint, data) {
        var bodyKey = data ? StableStringify(data) : '';
        return [method, endpoint, bodyKey].join('::');
    }

    function isCrudRead(method, endpoint) {
        if (!endpoint) return false;
        if (method === 'GET') return stripQuery(endpoint).indexOf('/crud/') === 0;
        if (method === 'POST' && stripQuery(endpoint).indexOf('/crud/') === 0 && stripQuery(endpoint).indexOf('/search') !== -1) return true;
        return false;
    }

    function isSafeRead(method, endpoint) {
        var path = stripQuery(endpoint);
        if (method === 'GET') return true;
        if (path === '/languages') return true;
        if (path === '/crud/tables') return true;
        return isCrudRead(method, endpoint);
    }

    async function cacheLoad(adapter, key) {
        if (!adapter || !CacheConfig.enabled) return null;
        var payload = await adapter.load(key).catch(function () { return null; });
        if (!payload || !payload.data) return null;
        var meta = payload.meta || {};
        var savedAt = meta.savedAt || payload.updatedAt || 0;
        var ttl = meta.ttlMs || CacheConfig.ttlMs;
        var isExpired = ttl && savedAt ? (Date.now() - savedAt > ttl) : false;
        return { data: payload.data, meta: meta, expired: isExpired };
    }

    async function maybeHydratePayload(endpoint, payload, options) {
        if (!payload || options && options.hydration === 'raw') return payload;
        if (typeof HydrationResolver !== 'function') return payload;
        var tableName = getCrudTableName(endpoint);
        if (!tableName) return payload;
        try {
            return await HydrationResolver(tableName, payload, options || {});
        } catch (_e) {
            return payload;
        }
    }

    async function cacheSave(adapter, key, data, options) {
        if (!adapter || !CacheConfig.enabled) return null;
        var meta = {
            savedAt: Date.now(),
            ttlMs: (options && options.ttlMs) || CacheConfig.ttlMs,
            source: 'rest'
        };
        return adapter.save(key, data, { metadata: meta, mergeMetadata: false });
    }

    async function cacheClearByTable(adapter, tableName) {
        if (!adapter || !CacheConfig.enabled) return;
        var keys = await adapter.keys().catch(function () { return []; });
        var tag = '::/crud/' + tableName;
        var tasks = keys.filter(function (k) {
            return k.indexOf(tag) !== -1;
        }).map(function (k) { return adapter.clear(k); });
        await Promise.all(tasks);
    }

    async function updateSyncedTableCache(tableName, method, requestData, responseData, options, recordId) {
        var ctx = getContext(options);
        var adapter = getAdapter(ctx.key);
        if (!adapter) return;
        var existing = await adapter.load(tableName).catch(function () { return null; });
        var rows = Array.isArray(existing && existing.data) ? existing.data.slice() : [];
        var existingMeta = (existing && existing.meta) || {};
        var changed = false;

        if (method === 'DELETE') {
            var before = rows.length;
            rows = rows.filter(function (row) {
                return !row || String(row.id) !== String(recordId);
            });
            changed = before !== rows.length;
        } else {
            var record = extractRecord(responseData, requestData);
            if (record && record.id !== undefined && record.id !== null) {
                var nextRecord = cloneValue(record);
                var index = rows.findIndex(function (row) {
                    return row && String(row.id) === String(nextRecord.id);
                });
                if (index === -1) rows.unshift(nextRecord);
                else rows[index] = nextRecord;
                changed = true;
            }
        }

        if (!changed) return;
        await adapter.save(tableName, rows, {
            metadata: Object.assign({}, existingMeta, {
                updatedAt: Date.now(),
                lastSyncAt: Date.now(),
                source: 'rest-write'
            }),
            mergeMetadata: true
        });
    }

    async function applySyncSnapshotToCache(state, payload) {
        var adapter = getAdapter(state.key);
        var snapshot = payload && payload.snapshot && typeof payload.snapshot === 'object'
            ? payload.snapshot
            : {};
        var tables = snapshot.tables && typeof snapshot.tables === 'object'
            ? snapshot.tables
            : {};
        var nextTableNames = Object.keys(tables);
        var previousTables = Array.isArray(state.tables) ? state.tables.slice() : [];
        var version = payload && payload.version !== undefined ? payload.version : state.version;
        var updatedAt = payload && payload.updatedAt ? payload.updatedAt : state.updatedAt;
        var etag = payload && payload.etag ? payload.etag : state.etag;
        var syncMeta = {
            branch: state.branch,
            module: state.module,
            version: version,
            updatedAt: updatedAt,
            etag: etag,
            serverId: payload && payload.serverId ? payload.serverId : state.serverId,
            tables: nextTableNames,
            lastSyncAt: Date.now(),
            source: 'sync'
        };

        if (adapter) {
            await Promise.all(previousTables.filter(function (tableName) {
                return nextTableNames.indexOf(tableName) === -1;
            }).map(function (tableName) {
                return adapter.clear(tableName).catch(function () { });
            }));

            for (var i = 0; i < nextTableNames.length; i++) {
                var tableName = nextTableNames[i];
                var rows = Array.isArray(tables[tableName]) ? tables[tableName] : [];
                await adapter.save(tableName, rows, {
                    metadata: {
                        schemaVersion: version === undefined || version === null ? null : String(version),
                        updatedAt: parseTimestamp(updatedAt) || Date.now(),
                        lastSyncAt: Date.now(),
                        serverHash: etag || null,
                        source: 'sync'
                    },
                    mergeMetadata: false
                });
            }

            await adapter.save('__sync_meta__', syncMeta, {
                metadata: {
                    schemaVersion: version === undefined || version === null ? null : String(version),
                    updatedAt: parseTimestamp(updatedAt) || Date.now(),
                    lastSyncAt: Date.now(),
                    serverHash: etag || null,
                    source: 'sync'
                },
                mergeMetadata: false
            });
        }

        state.version = syncMeta.version;
        state.updatedAt = syncMeta.updatedAt;
        state.etag = syncMeta.etag;
        state.serverId = syncMeta.serverId;
        state.tables = syncMeta.tables.slice();
        state.lastSyncAt = syncMeta.lastSyncAt;
        state.error = null;

        emitSyncUpdate(state, { status: 'applied' });
        return snapshotSyncState(state);
    }

    async function pullSyncSnapshot(options) {
        var state = getSyncState(options);
        await loadSyncMetadata(state);
        if (state.syncing) return state.syncing;
        state.syncing = (async function () {
            var headers = applyGlobalAuthHeaders(Object.assign({
                'Accept': 'application/json'
            }, RequestDefaults.headers || {}, (options && options.headers) || {}));
            if (SyncConfig.useEtag && state.etag) {
                headers['If-None-Match'] = state.etag;
            }
            var config = {
                method: 'GET',
                headers: headers
            };
            var credentials = (options && options.credentials) || RequestDefaults.credentials;
            if (credentials) config.credentials = credentials;
            var response = await fetch(buildSyncUrl(options), config);
            if (response.status === 304) {
                state.lastSyncAt = Date.now();
                state.error = null;
                emitSyncUpdate(state, { status: 'not-modified' });
                return Object.assign({ status: 'not-modified' }, snapshotSyncState(state));
            }
            if (!response.ok) {
                var err = await response.json().catch(function () { return {}; });
                throw new Error(err.error || err.message || ('HTTP ' + response.status));
            }
            var json = await response.json();
            state.etag = response.headers && typeof response.headers.get === 'function'
                ? (response.headers.get('ETag') || state.etag || null)
                : (state.etag || null);
            return applySyncSnapshotToCache(state, Object.assign({}, json, { etag: state.etag }));
        })().catch(function (error) {
            state.error = error && error.message ? error.message : String(error || 'sync-failed');
            emitSyncUpdate(state, { status: 'error', error: state.error });
            throw error;
        }).finally(function () {
            state.syncing = null;
        });
        return state.syncing;
    }

    function ensureSyncTimer(options) {
        var state = getSyncState(options);
        if (!SyncConfig.enabled) return state;
        if (state.timerId) clearInterval(state.timerId);
        if (!Number.isFinite(SyncConfig.intervalMs) || SyncConfig.intervalMs <= 0) return state;
        state.timerId = setInterval(function () {
            pullSyncSnapshot(state).catch(function () { });
        }, SyncConfig.intervalMs);
        return state;
    }

    async function maybeBootstrapSyncFromRepo(tableName, params, options) {
        if (!SyncConfig.enabled) return null;
        var ctx = getContext(options);
        if (!ctx.module || ctx.module === 'default') return null;
        await pullSyncSnapshot(ctx).catch(function () { return null; });
        return resolveLocalSearch(tableName, params, ctx);
    }

    function resolveTablePolicy(tableName) {
        if (typeof PolicyResolver === 'function') {
            try { return PolicyResolver(tableName) || null; } catch (_e) { }
        }
        return null;
    }

    async function processQueue(options) {
        var state = getQueueState(options);
        if (state.processing) return;
        state.processing = true;
        try {
            await loadQueue(state);
            var now = Date.now();
            for (var i = 0; i < state.items.length; i++) {
                var item = state.items[i];
                if (!item || item.status === 'failed') continue;
                if (item.nextRetryAt && item.nextRetryAt > now) continue;
                try {
                    var responseData = await requestRaw(item.endpoint, item.method, item.data, item.options || {});
                    var tableName = getCrudTableName(item.endpoint);
                    if (tableName) {
                        await cacheClearByTable(getAdapter(state.key), tableName);
                        await updateSyncedTableCache(tableName, item.method, item.data, responseData, state, getCrudRecordId(item.endpoint));
                    }
                    state.items.splice(i, 1);
                    i -= 1;
                } catch (err) {
                    if (item.method === 'PUT' && isNotFoundError(err)) {
                        var createEndpoint = buildCrudCreateEndpoint(item.endpoint);
                        if (createEndpoint) {
                            try {
                                var createdData = await requestRaw(createEndpoint, 'POST', item.data, item.options || {});
                                var createdTableName = getCrudTableName(createEndpoint);
                                if (createdTableName) {
                                    await cacheClearByTable(getAdapter(state.key), createdTableName);
                                    await updateSyncedTableCache(createdTableName, 'POST', item.data, createdData, state, null);
                                }
                                state.items.splice(i, 1);
                                i -= 1;
                                continue;
                            } catch (fallbackErr) {
                                err = fallbackErr;
                            }
                        }
                    }
                    item.retries = (item.retries || 0) + 1;
                    item.lastError = (err && err.message) || String(err || 'error');
                    item.updatedAt = Date.now();
                    if (item.retries >= QueueConfig.maxRetries) {
                        item.status = 'failed';
                        logQueueFailure(state, item, err);
                    } else {
                        item.status = 'pending';
                        item.nextRetryAt = Date.now() + computeBackoff(item.retries);
                        logQueueFailure(state, item, err);
                    }
                }
            }
            await saveQueue(state);
            emitQueueUpdate(state);
        } finally {
            state.processing = false;
        }
    }

    function enqueueRequest(options, method, endpoint, data, requestOptions, error) {
        if (!QueueConfig.enabled) return null;
        var state = getQueueState(options);
        var item = {
            id: 'q-' + Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
            method: method,
            endpoint: endpoint,
            data: data,
            options: {
                branch: state.branch,
                module: state.module,
                headers: requestOptions && requestOptions.headers ? Object.assign({}, requestOptions.headers) : {},
                credentials: requestOptions && requestOptions.credentials ? requestOptions.credentials : undefined
            },
            status: 'pending',
            retries: 0,
            createdAt: Date.now(),
            updatedAt: Date.now(),
            lastError: error ? (error.message || String(error)) : null,
            nextRetryAt: Date.now() + computeBackoff(1)
        };
        state.items.push(item);
        logQueueFailure(state, item, error || new Error('queued'));
        saveQueue(state);
        emitQueueUpdate(state);
        return item;
    }

    function buildQuery(params) {
        if (!params || typeof params !== 'object') return '';
        var entries = Object.entries(params).filter(function (pair) {
            return pair[1] !== undefined && pair[1] !== null;
        });
        if (!entries.length) return '';
        var query = entries.map(function (pair) {
            return encodeURIComponent(pair[0]) + '=' + encodeURIComponent(pair[1]);
        }).join('&');
        return query ? ('?' + query) : '';
    }

    var REST = {
        configure: function (opts) {
            opts = opts || {};
            if (opts.apiBase) API_BASE = opts.apiBase;
            if (opts.baseDomain) BASE_DOMAIN = opts.baseDomain;
            if (opts.hydration) HydrationConfig.mode = opts.hydration;
            if (typeof opts.hydrationResolver === 'function') HydrationResolver = opts.hydrationResolver;
            if (opts.defaultBranch) DEFAULT_BRANCH = opts.defaultBranch;
            if (opts.defaultModule !== undefined) DEFAULT_MODULE = opts.defaultModule;
            if (typeof opts.policyResolver === 'function') PolicyResolver = opts.policyResolver;
            if (opts.headers && typeof opts.headers === 'object') {
                RequestDefaults.headers = Object.assign({}, RequestDefaults.headers || {}, opts.headers);
            }
            if (opts.credentials) RequestDefaults.credentials = opts.credentials;
            if (opts.cache && typeof opts.cache === 'object') {
                if (opts.cache.enabled !== undefined) CacheConfig.enabled = !!opts.cache.enabled;
                if (opts.cache.policy) CacheConfig.policy = opts.cache.policy;
                if (Number.isFinite(opts.cache.ttlMs)) CacheConfig.ttlMs = opts.cache.ttlMs;
            }
            if (opts.queue && typeof opts.queue === 'object') {
                if (opts.queue.enabled !== undefined) QueueConfig.enabled = !!opts.queue.enabled;
                if (Number.isFinite(opts.queue.maxRetries)) QueueConfig.maxRetries = opts.queue.maxRetries;
                if (Number.isFinite(opts.queue.baseDelayMs)) QueueConfig.baseDelayMs = opts.queue.baseDelayMs;
                if (Number.isFinite(opts.queue.maxDelayMs)) QueueConfig.maxDelayMs = opts.queue.maxDelayMs;
                if (Number.isFinite(opts.queue.retryIntervalMs)) QueueConfig.retryIntervalMs = opts.queue.retryIntervalMs;
                if (Number.isFinite(opts.queue.logLimit)) QueueConfig.logLimit = opts.queue.logLimit;
            }
            if (opts.sync && typeof opts.sync === 'object') {
                if (opts.sync.enabled !== undefined) SyncConfig.enabled = !!opts.sync.enabled;
                if (opts.sync.endpoint) SyncConfig.endpoint = opts.sync.endpoint;
                if (opts.sync.autoBootstrap !== undefined) SyncConfig.autoBootstrap = !!opts.sync.autoBootstrap;
                if (opts.sync.useEtag !== undefined) SyncConfig.useEtag = !!opts.sync.useEtag;
                if (opts.sync.immediate !== undefined) SyncConfig.immediate = !!opts.sync.immediate;
                if (Number.isFinite(opts.sync.intervalMs)) SyncConfig.intervalMs = opts.sync.intervalMs;
            }
            if (SyncConfig.enabled) {
                ensureSyncTimer({});
                if (SyncConfig.autoBootstrap && SyncConfig.immediate) {
                    pullSyncSnapshot({}).catch(function () { });
                }
            }
        },
        setPolicyResolver: function (fn) {
            PolicyResolver = typeof fn === 'function' ? fn : null;
        },
        setHydrationResolver: function (fn) {
            HydrationResolver = typeof fn === 'function' ? fn : null;
        },
        request: async function (endpoint, method, data, options) {
            options = options || {};
            var cacheMode = options.cacheMode || options.cache || null;
            if (cacheMode === false) cacheMode = 'no-store';
            var config = buildFetchConfig(method, data, options);
            var url = buildApiUrl(endpoint, options);
            var canCache = CacheConfig.enabled && cacheMode !== 'no-store' && isSafeRead(method, endpoint);
            var ctx = getContext(options);
            var adapter = canCache ? getAdapter(ctx.key) : null;
            var cacheKey = canCache ? buildCacheKey(method, endpoint, data) : null;
            var policy = cacheMode || CacheConfig.policy;
            var cached = null;

            if (canCache && policy !== 'network-only') {
                cached = await cacheLoad(adapter, cacheKey);
                if (cached && policy === 'cache-only') {
                    return await maybeHydratePayload(endpoint, cached.data, options);
                }
                if (!cached && options.seed && policy === 'cache-only') {
                    policy = 'network-first';
                }
                if (cached && policy === 'stale-while-revalidate') {
                    (async function () {
                        try {
                            var resp = await fetch(url, config);
                            if (!resp.ok) return;
                            var json = await resp.json();
                            await cacheSave(adapter, cacheKey, json, { ttlMs: options.ttlMs });
                            if (typeof options.onCacheUpdate === 'function') {
                                options.onCacheUpdate(json, { source: 'network' });
                            }
                        } catch (_e) { }
                    })();
                    return await maybeHydratePayload(endpoint, cached.data, options);
                }
            }

            var inflightKey = ctx.key + '::' + cacheKey;
            if (canCache && policy !== 'network-only' && Inflight.has(inflightKey)) {
                return Inflight.get(inflightKey);
            }

            try {
                var inflightPromise = (async function () {
                    var response = await fetch(url, config);

                    if (!response.ok) {
                        var errorData = await response.json().catch(function () { return {}; });
                        if (cached && (policy === 'network-first' || policy === 'stale-while-revalidate')) {
                            return cached.data;
                        }
                        throw new Error(errorData.message || errorData.error || ('HTTP ' + response.status));
                    }

                    var json = await response.json();
                    if (canCache) {
                        await cacheSave(adapter, cacheKey, json, { ttlMs: options.ttlMs });
                    } else if (method !== 'GET' && stripQuery(endpoint).indexOf('/crud/') === 0) {
                        var tableName = getCrudTableName(endpoint);
                        if (tableName) {
                            await cacheClearByTable(getAdapter(ctx.key), tableName);
                            await updateSyncedTableCache(tableName, method, data, json, ctx, getCrudRecordId(endpoint));
                        }
                    }
                    return await maybeHydratePayload(endpoint, json, options);
                })();
                if (canCache && policy !== 'network-only') {
                    Inflight.set(inflightKey, inflightPromise);
                }
                var inflightResult = await inflightPromise;
                Inflight.delete(inflightKey);
                return inflightResult;
            } catch (error) {
                Inflight.delete(inflightKey);
                if (cached && policy !== 'network-only') {
                    return await maybeHydratePayload(endpoint, cached.data, options);
                }
                if (QueueConfig.enabled && !isSafeRead(method, endpoint) && options.queue !== false) {
                    var writeTable = getCrudTableName(endpoint);
                    if (writeTable) {
                        await updateSyncedTableCache(writeTable, method, data, null, ctx, getCrudRecordId(endpoint));
                    }
                    enqueueRequest(ctx, method, endpoint, data, options, error);
                    processQueue(ctx);
                    if (options.queue === 'throw') throw error;
                    return { queued: true, error: error.message || String(error) };
                }
                throw error;
            }
        },

        get: function (url, opts) { return this.request(url, 'GET', null, opts); },
        post: function (url, data, opts) { return this.request(url, 'POST', data, opts); },
        put: function (url, data, opts) { return this.request(url, 'PUT', data, opts); },
        del: function (url, opts) { return this.request(url, 'DELETE', null, opts); },

        repo: function (tableName) {
            var root = '/crud/' + tableName;

            return {
                search: async function (params) {
                    var body = Object.assign({}, params || {});
                    var tablePolicy = resolveTablePolicy(tableName) || {};
                    var defaultRead = (tablePolicy.read || (tablePolicy.mode === 'offline-first' ? 'cache-only' : null)) || CacheConfig.policy || null;
                    var cacheMode = body.cacheMode || body.cache || (body.fresh ? 'network-only' : (defaultRead || 'network-first'));
                    var seed = tablePolicy.initial_seed === true;
                    var hydration = body.hydration || HydrationConfig.mode;
                    var requestOptions = {
                        cacheMode: cacheMode,
                        seed: seed,
                        branch: body.branch,
                        module: body.module
                    };

                    if (cacheMode === 'cache-only' || cacheMode === 'stale-while-revalidate') {
                        var localResult = await resolveLocalSearch(tableName, body, requestOptions);
                        if (localResult) {
                            if (cacheMode === 'stale-while-revalidate' && SyncConfig.enabled) {
                                pullSyncSnapshot(requestOptions).catch(function () { });
                            }
                            return await maybeHydratePayload(root + '/search', localResult, { hydration: hydration });
                        }
                        if (SyncConfig.enabled) {
                            var bootstrapped = await maybeBootstrapSyncFromRepo(tableName, body, requestOptions);
                            if (bootstrapped) {
                                return await maybeHydratePayload(root + '/search', bootstrapped, { hydration: hydration });
                            }
                        }
                    }

                    delete body.cacheMode;
                    delete body.cache;
                    delete body.fresh;
                    delete body.hydration;
                    delete body.branch;
                    delete body.module;
                    var queryParams = {};
                    if (body.q !== undefined) {
                        queryParams.q = body.q;
                    }
                    if (body.withMeta !== undefined) {
                        queryParams.withMeta = body.withMeta;
                    }
                    if (hydration === 'raw') {
                        queryParams.raw = 1;
                    }
                    var qs = buildQuery(queryParams);
                    try {
                        return await REST.post(root + '/search' + qs, body, requestOptions);
                    } catch (error) {
                        var localFallback = await resolveLocalSearch(tableName, body, requestOptions);
                        if (localFallback) {
                            return await maybeHydratePayload(root + '/search', localFallback, { hydration: hydration });
                        }
                        throw error;
                    }
                },
                get: async function (id, params) {
                    var opts = Object.assign({}, params || {});
                    var tablePolicy = resolveTablePolicy(tableName) || {};
                    var defaultRead = (tablePolicy.read || (tablePolicy.mode === 'offline-first' ? 'cache-only' : null)) || CacheConfig.policy || null;
                    var cacheMode = (opts && (opts.cacheMode || opts.cache)) || defaultRead || null;
                    var seed = tablePolicy.initial_seed === true;
                    var hydration = opts.hydration || HydrationConfig.mode;
                    var requestOptions = {
                        cacheMode: cacheMode,
                        seed: seed,
                        branch: opts.branch,
                        module: opts.module
                    };

                    if (cacheMode === 'cache-only' || cacheMode === 'stale-while-revalidate') {
                        var localRecord = await resolveLocalGet(tableName, id, requestOptions);
                        if (localRecord) {
                            if (cacheMode === 'stale-while-revalidate' && SyncConfig.enabled) {
                                pullSyncSnapshot(requestOptions).catch(function () { });
                            }
                            return await maybeHydratePayload(root + '/' + id, localRecord, { hydration: hydration });
                        }
                        if (SyncConfig.enabled) {
                            await pullSyncSnapshot(requestOptions).catch(function () { return null; });
                            localRecord = await resolveLocalGet(tableName, id, requestOptions);
                            if (localRecord) {
                                return await maybeHydratePayload(root + '/' + id, localRecord, { hydration: hydration });
                            }
                        }
                    }

                    delete opts.cacheMode;
                    delete opts.cache;
                    delete opts.hydration;
                    if (hydration === 'raw') {
                        opts.raw = 1;
                    }
                    var qs = buildQuery(opts);
                    try {
                        return await REST.get(root + '/' + id + qs, requestOptions);
                    } catch (error) {
                        var localFallback = await resolveLocalGet(tableName, id, requestOptions);
                        if (localFallback) {
                            return await maybeHydratePayload(root + '/' + id, localFallback, { hydration: hydration });
                        }
                        throw error;
                    }
                },
                create: function (data, params) {
                    var requestOptions = {
                        branch: params && params.branch,
                        module: params && params.module
                    };
                    var queryParams = Object.assign({}, params || {});
                    delete queryParams.branch;
                    delete queryParams.module;
                    var qs = buildQuery(queryParams);
                    return REST.post(root + qs, data, requestOptions);
                },
                update: function (id, data, params) {
                    var requestOptions = {
                        branch: params && params.branch,
                        module: params && params.module
                    };
                    var queryParams = Object.assign({}, params || {});
                    delete queryParams.branch;
                    delete queryParams.module;
                    var qs = buildQuery(queryParams);
                    return REST.put(root + '/' + id + qs, data, requestOptions);
                },
                delete: function (id, params) {
                    var requestOptions = {
                        branch: params && params.branch,
                        module: params && params.module
                    };
                    var queryParams = Object.assign({}, params || {});
                    delete queryParams.branch;
                    delete queryParams.module;
                    var qs = buildQuery(queryParams);
                    return REST.del(root + '/' + id + qs, requestOptions);
                }
            };
        },

        system: {
            tables: function (opts) {
                return REST.get('/crud/tables', opts);
            }
        },

        languages: function () {
            return REST.get('/languages', { cacheMode: 'stale-while-revalidate' });
        },

        rpc: async function (methodName, data, options) {
            options = options || {};
            var config = buildFetchConfig('POST', data || {}, options);

            var endpoint = '/api/rpc/' + methodName;
            var branch = getEffectiveBranch(options);
            if (branch && endpoint.indexOf('branch=') === -1) {
                endpoint = appendQueryParam(endpoint, 'branch', branch);
            }

            try {
                var response = await fetch(endpoint, config);

                if (!response.ok) {
                    var errorData = await response.json().catch(function () { return {}; });
                    throw new Error(errorData.error || errorData.message || ('HTTP ' + response.status));
                }

                return await response.json();
            } catch (error) {
                throw error;
            }
        }
    };

    REST.queue = {
        ready: function (options) {
            return loadQueue(options || {});
        },
        list: function (options) {
            var state = getQueueState(options || {});
            return {
                items: state.items.slice(),
                logs: state.logs.slice(),
                branch: state.branch,
                module: state.module
            };
        },
        stats: function (options) {
            var state = getQueueState(options || {});
            return {
                branch: state.branch,
                module: state.module,
                pending: state.items.filter(function (it) { return it.status === 'pending'; }).length,
                failed: state.items.filter(function (it) { return it.status === 'failed'; }).length
            };
        },
        retryAll: function (options) {
            var state = getQueueState(options || {});
            state.items.forEach(function (it) {
                if (!it || it.status !== 'failed') return;
                it.status = 'pending';
                it.nextRetryAt = Date.now();
            });
            saveQueue(state);
            emitQueueUpdate(state);
            return processQueue(state);
        },
        clear: function (options) {
            var state = getQueueState(options || {});
            state.items = [];
            state.logs = [];
            saveQueue(state);
            emitQueueUpdate(state);
        },
        onUpdate: function (handler) {
            if (typeof handler !== 'function') return function () { };
            QueueListeners.add(handler);
            return function () { QueueListeners.delete(handler); };
        },
        process: function (options) {
            return processQueue(options || {});
        }
    };

    REST.cache = {
        clearAll: async function (options) {
            var ctx = getContext(options || {});
            var adapter = getAdapter(ctx.key);
            if (!adapter) return;
            var keys = await adapter.keys().catch(function () { return []; });
            await Promise.all(keys.map(function (k) { return adapter.clear(k); }));
        },
        clearTable: async function (tableName, options) {
            var ctx = getContext(options || {});
            await cacheClearByTable(getAdapter(ctx.key), tableName);
            var adapter = getAdapter(ctx.key);
            if (adapter) await adapter.clear(tableName).catch(function () { });
        },
        rebuildTable: async function (tableName, options) {
            options = options || {};
            if (SyncConfig.enabled) {
                await pullSyncSnapshot(options).catch(function () { return null; });
                return readTableCache(tableName, options).then(function (payload) {
                    return payload ? payload.data : [];
                });
            }
            var repo = REST.repo(tableName);
            return repo.search(Object.assign({}, options, { cacheMode: 'network-only', fresh: true }));
        },
        loadTable: async function (tableName, options) {
            var payload = await readTableCache(tableName, options || {});
            return payload ? payload.data : [];
        },
        destroy: async function (options) {
            var ctx = getContext(options || {});
            var adapter = getAdapter(ctx.key);
            if (!adapter) return;
            await adapter.destroy().catch(function () { });
            AdapterRegistry.delete(ctx.key);
        }
    };

    REST.sync = {
        status: async function (options) {
            var state = getSyncState(options || {});
            await loadSyncMetadata(state);
            return snapshotSyncState(state);
        },
        bootstrap: function (options) {
            return pullSyncSnapshot(options || {});
        },
        start: async function (options) {
            var opts = Object.assign({}, options || {});
            if (opts.enabled !== undefined) SyncConfig.enabled = !!opts.enabled;
            if (!SyncConfig.enabled) return this.status(opts);
            ensureSyncTimer(opts);
            if (opts.immediate !== false && SyncConfig.immediate !== false) {
                return pullSyncSnapshot(opts);
            }
            return this.status(opts);
        },
        stop: function (options) {
            var state = getSyncState(options || {});
            if (state.timerId) {
                clearInterval(state.timerId);
                state.timerId = null;
            }
            return snapshotSyncState(state);
        },
        table: async function (tableName, options) {
            var payload = await readTableCache(tableName, options || {});
            return payload ? payload.data : [];
        },
        record: async function (tableName, id, options) {
            var payload = await resolveLocalGet(tableName, id, options || {});
            return payload && payload.record ? payload.record : null;
        },
        onUpdate: function (handler) {
            if (typeof handler !== 'function') return function () { };
            SyncListeners.add(handler);
            return function () { SyncListeners.delete(handler); };
        }
    };

    if (typeof window !== 'undefined') {
        window.addEventListener('online', function () {
            Promise.resolve(processQueue({})).finally(function () {
                if (SyncConfig.enabled) {
                    pullSyncSnapshot({}).catch(function () { });
                }
            });
        });
        setInterval(function () {
            processQueue({});
        }, QueueConfig.retryIntervalMs);
    }

    M.REST = REST;

})(window);
