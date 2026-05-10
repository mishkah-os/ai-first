import Hydrator from '../backend/hydrator.js';
import {
    jsonResponse, readBody, resolveBranchId, normalizeIdentifier,
    buildTranslationBundle, normalizeTableName, sanitizeRecordForClient
} from '../utils/helpers.js';
import { findRecordUsingValue, buildRecordCursor, normalizeCursorInput } from './utils.js';
import { refreshDisplayNameCache } from './display-name-cache.js';
import { persistRecord, deleteRecord, isManagedTable, appendSyncTransactionLog } from '../database/sqlite-ops.js';
import { filterRecordForScope, filterTableRowsForScope } from './client-scope.js';
import { SECURITY_POLICY } from '../config/index.js';
import { getAqaratSession } from '../auth/aqarat-auth.js';

export function createCrudApi({
    ensureModuleStore,
    persistModuleStore,
    invalidateSyncState,
    schemaManager,
    DEFAULT_MODULE_ID,
    logger,
    emitCrudLiveEvent
}) {
    function parseCookieHeader(header) {
        if (typeof header !== 'string' || !header.trim()) return {};
        const cookies = {};
        for (const rawEntry of header.split(';')) {
            const entry = rawEntry.trim();
            if (!entry) continue;
            const idx = entry.indexOf('=');
            if (idx <= 0) continue;
            const key = entry.slice(0, idx).trim();
            const value = entry.slice(idx + 1).trim();
            if (!key) continue;
            try {
                cookies[key] = decodeURIComponent(value);
            } catch (_error) {
                cookies[key] = value;
            }
        }
        return cookies;
    }

    function normalizeScopeToken(value) {
        return value === undefined || value === null ? '' : String(value).trim();
    }

    function resolveBearerToken(req) {
        const auth = normalizeScopeToken(req && req.headers && req.headers.authorization);
        if (/^Bearer\s+/i.test(auth)) return auth.replace(/^Bearer\s+/i, '').trim();
        return '';
    }

    function resolveSessionUserId(token) {
        const session = token ? getAqaratSession(token) : null;
        const user = session && session.user ? session.user : null;
        return normalizeScopeToken(user && (user.id || user.user_id || user.userId));
    }

    function buildRequestScope(req, url, body = null) {
        const requestCookies = parseCookieHeader(req.headers?.cookie || '');
        const token = normalizeScopeToken(
            resolveBearerToken(req) ||
            url.searchParams.get('token') ||
            url.searchParams.get('auth_token') ||
            url.searchParams.get('_auth_token') ||
            (body && (body._auth_token || body.auth_token || body.token)) ||
            ''
        );
        const sessionUserId = resolveSessionUserId(token);
        const claimedUserId = normalizeScopeToken(
            requestCookies.UserUniid ||
            requestCookies.userId ||
            requestCookies.user_id ||
            url.searchParams.get('_scope_user_id') ||
            url.searchParams.get('user_id') ||
            url.searchParams.get('userId') ||
            (body && (body._scope_user_id || body.userId || body.user_id)) ||
            ''
        );
        return {
            userId: sessionUserId || claimedUserId || null,
            userUuid: sessionUserId || claimedUserId || null,
            cookies: requestCookies,
            session: sessionUserId ? { userId: sessionUserId, user_id: sessionUserId } : {}
        };
    }

    // Helper: Resolve Lang Param
    function resolveLangParam(url) {
        return url.searchParams.get('lang') || null;
    }

    // Helper: List Available Languages
    function listAvailableLanguages(store) {
        // Basic implementation: check if store has translation tables or just return defaults
        // Logic inferred from standard usage
        return ['ar', 'en'];
    }

    function resolvePrimaryKeyFields(store, tableName) {
        if (typeof store?.resolvePrimaryKeyFields === 'function') {
            try {
                const fields = store.resolvePrimaryKeyFields(tableName);
                if (Array.isArray(fields) && fields.length) return fields;
            } catch (_error) {}
        }
        try {
            const table = store?.schemaEngine?.getTable?.(tableName);
            const fields = Array.isArray(table?.fields)
                ? table.fields.filter((field) => field && field.primaryKey).map((field) => field.name || field.columnName).filter(Boolean)
                : [];
            if (fields.length) return fields;
        } catch (_error) {}
        return ['id'];
    }

    function resolveRecordPrimaryValue(store, tableName, record) {
        if (!record || typeof record !== 'object') return null;
        const ref = typeof store?.getRecordReference === 'function'
            ? store.getRecordReference(tableName, record)
            : null;
        if (ref?.key) return ref.key;
        if (ref?.id) return ref.id;
        if (ref?.uuid) return ref.uuid;
        if (ref?.uid) return ref.uid;
        for (const field of resolvePrimaryKeyFields(store, tableName)) {
            if (record[field] !== undefined && record[field] !== null && record[field] !== '') {
                return record[field];
            }
        }
        return record.id || record.uuid || record.uid || null;
    }

    function resolveLangFkColumn(store, tableName) {
        const langTable = `${tableName}_lang`;
        const langFields = (() => {
            try {
                const table = store?.schemaEngine?.getTable?.(langTable);
                return Array.isArray(table?.fields)
                    ? table.fields.map((field) => field && (field.name || field.columnName)).filter(Boolean)
                    : [];
            } catch (_error) {
                return [];
            }
        })();
        const primaryFields = resolvePrimaryKeyFields(store, tableName);
        const legacy = `${tableName}_id`;
        return primaryFields.find((field) => langFields.includes(field)) ||
            (langFields.includes(legacy) ? legacy : null) ||
            langFields.find((field) => String(field || '').toLowerCase().endsWith('_id')) ||
            legacy;
    }

    function parseRowTimestamp(record) {
        if (!record || typeof record !== 'object') return null;
        const fields = ['updatedAt', 'updated_at', 'createdAt', 'created_at', 'serverAt', 'server_at'];
        for (const field of fields) {
            const raw = record[field];
            if (raw === undefined || raw === null || raw === '') continue;
            const time = typeof raw === 'number' ? raw : Date.parse(raw);
            if (Number.isFinite(time)) return time;
        }
        return null;
    }

    function applyTimeWindowFilters(rows, source = {}) {
        let filtered = Array.isArray(rows) ? rows : [];
        const beforeValue =
            source.beforeUpdatedAt ||
            source.updatedBefore ||
            source.olderThan ||
            source.before ||
            null;
        const sinceValue =
            source.sinceUpdatedAt ||
            source.updatedAfter ||
            source.after ||
            source.since ||
            null;

        if (beforeValue) {
            const before = Date.parse(beforeValue);
            if (Number.isFinite(before)) {
                filtered = filtered.filter((row) => {
                    const time = parseRowTimestamp(row);
                    return time === null || time < before;
                });
            }
        }

        if (sinceValue) {
            const since = Date.parse(sinceValue);
            if (Number.isFinite(since)) {
                filtered = filtered.filter((row) => {
                    const time = parseRowTimestamp(row);
                    return time === null || time >= since;
                });
            }
        }

        return filtered;
    }

    const DEFAULT_PUBLIC_IDENTITY_FIELDS = [
        'id',
        'user_id',
        'userId',
        'uuid',
        'role',
        'username',
        'user_name',
        'slug',
        'profile_slug',
        'display_name',
        'displayName',
        'full_name',
        'fullName',
        'name',
        'avatar_url',
        'avatar',
        'photo_url',
        'primary_image_url',
        'logo_url',
        'createdAt',
        'created_at',
        'updatedAt',
        'updated_at'
    ];
    const PUBLIC_IDENTITY_FIELD_MAP = new Map();
    Object.entries(SECURITY_POLICY.publicIdentity || {}).forEach(([tableName, config]) => {
        const normalizedName = normalizeTableName(tableName);
        if (!normalizedName || (config && config.enabled === false)) return;
        const fields = Array.isArray(config?.fields) && config.fields.length
            ? config.fields.map((field) => String(field))
            : DEFAULT_PUBLIC_IDENTITY_FIELDS;
        PUBLIC_IDENTITY_FIELD_MAP.set(normalizedName, fields);
    });
    if (!PUBLIC_IDENTITY_FIELD_MAP.has('users')) {
        PUBLIC_IDENTITY_FIELD_MAP.set('users', DEFAULT_PUBLIC_IDENTITY_FIELDS);
    }
    const PUBLIC_IDENTITY_TABLES = new Set(PUBLIC_IDENTITY_FIELD_MAP.keys());

    function truthyFlag(value) {
        return value === true || value === 1 || value === '1' || String(value || '').toLowerCase() === 'true';
    }

    function wantsPublicIdentity(tableName, url, body = null) {
        if (!PUBLIC_IDENTITY_TABLES.has(normalizeTableName(tableName))) return false;
        return truthyFlag(url.searchParams.get('_public_identity')) ||
            truthyFlag(url.searchParams.get('publicIdentity')) ||
            truthyFlag(body && (body._public_identity || body.publicIdentity));
    }

    function publicIdentityFieldsForTable(tableName) {
        return PUBLIC_IDENTITY_FIELD_MAP.get(normalizeTableName(tableName)) || DEFAULT_PUBLIC_IDENTITY_FIELDS;
    }

    function isEmailLike(value) {
        return typeof value === 'string' && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
    }

    function safePublicString(value) {
        if (value === undefined || value === null) return '';
        const normalized = String(value).trim();
        return normalized && !isEmailLike(normalized) ? normalized : '';
    }

    function stripPublicIdentityFields(tableName, record) {
        if (!record || typeof record !== 'object') return record;
        const sanitized = {};
        const fields = publicIdentityFieldsForTable(tableName);
        for (const field of fields) {
            if (record[field] !== undefined && record[field] !== null) sanitized[field] = record[field];
        }
        ['display_name', 'displayName', 'full_name', 'fullName', 'name', 'username', 'user_name', 'slug', 'profile_slug'].forEach((field) => {
            if (sanitized[field] !== undefined) {
                const value = safePublicString(sanitized[field]);
                if (value) sanitized[field] = value;
                else delete sanitized[field];
            }
        });
        if (!sanitized.id && (record.user_id || record.userId || record.uuid)) {
            sanitized.id = record.user_id || record.userId || record.uuid;
        }
        if (!sanitized.user_id && sanitized.id) sanitized.user_id = sanitized.id;
        if (!sanitized.username && sanitized.user_name) sanitized.username = sanitized.user_name;
        if (!sanitized.user_name && sanitized.username) sanitized.user_name = sanitized.username;
        const displayName = safePublicString(sanitized.display_name || sanitized.displayName || sanitized.full_name || sanitized.fullName || sanitized.name || sanitized.username || '');
        if (displayName) {
            if (!sanitized.display_name) sanitized.display_name = displayName;
            if (!sanitized.name) sanitized.name = displayName;
        }
        return sanitized;
    }

    function publicIdentityColumns(tableName, columnsOrder, columnsMeta) {
        const fieldSet = new Set(publicIdentityFieldsForTable(tableName));
        return {
            columnsOrder: (Array.isArray(columnsOrder) ? columnsOrder : []).filter((field) => fieldSet.has(field)),
            columnsMeta: (Array.isArray(columnsMeta) ? columnsMeta : []).filter((column) => column && fieldSet.has(column.name))
        };
    }

    async function emitMutation(store, branchId, moduleId, tableName, action, record, options = {}) {
        if (typeof emitCrudLiveEvent !== 'function') return;
        try {
            const recordRef = store && typeof store.getRecordReference === 'function'
                ? store.getRecordReference(tableName, record || options.recordRef || {})
                : { id: record && record.id };
            await emitCrudLiveEvent({
                branchId,
                moduleId,
                tableName,
                action,
                record,
                recordRef,
                version: store && store.version,
                deleted: action === 'module:delete',
                source: 'universal-crud'
            });
        } catch (error) {
            logger.warn({ err: error, branchId, moduleId, tableName }, 'Failed to emit CRUD live event');
        }
    }

    async function handleUniversalCrudApi(req, res, url) {
        // Pattern: /api/v1/crud/:action/:table or /api/v1/crud/:table/:id

        // Clean path: remove prefix
        const pathStr = url.pathname.replace('/api/v1/crud/', '');
        const segments = pathStr.split('/').filter(Boolean);

        // Heuristic:
        // If segment 1 is "match" -> segment 2 is table -> search logic
        // If segment 2 is ID -> segment 1 is table -> get logic

        let action = 'list';
        let tableName = '';
        let id = null;

        if (segments[0] === 'tables') {
            action = 'meta-tables';
        } else if (segments[0] === 'match' && segments[1]) {
            action = 'search';
            tableName = segments[1];
        } else if (segments.length === 2 && segments[1] === 'search') {
            // POST /:table/search
            action = 'search';
            tableName = segments[0];
        } else if (segments.length === 2) {
            tableName = segments[0];
            id = segments[1];
            action = 'get';
        } else if (segments.length === 1) {
            tableName = segments[0];
            action = 'list';
        } else {
            jsonResponse(res, 404, { error: 'invalid-crud-path' });
            return;
        }

        if (req.method === 'POST' && action === 'list') {
            action = 'create';
        }
        if (req.method === 'PUT' && action === 'get') {
            action = 'update';
        }
        if (req.method === 'DELETE' && action === 'get') {
            action = 'delete';
        }

        // Context Resolving
        const branchId = resolveBranchId(url);
        const moduleId = url.searchParams.get('module') || DEFAULT_MODULE_ID;
        // Note: 'clinic' matches the schema name.

        // ── Security: restricted tables ──────────────────────────────────────
        const restrictedTables = SECURITY_POLICY && typeof SECURITY_POLICY.restrictedTables === 'object'
            ? SECURITY_POLICY.restrictedTables || {}
            : {};
        const restrictedRule = restrictedTables[normalizeTableName(tableName)] || restrictedTables[tableName] || null;
        const scope = buildRequestScope(req, url);

        function stripSecretFields(tbl, record, options = {}) {
            if (!record || typeof record !== 'object') return record;
            if (options.publicIdentity === true && PUBLIC_IDENTITY_TABLES.has(normalizeTableName(tbl))) {
                return stripPublicIdentityFields(tbl, record);
            }
            const secretFields = new Map([
                ['users', new Set(['password_hash', 'last_login', 'phone', 'email'])]
            ]);
            const secretSet = secretFields.get(normalizeTableName(tbl));
            if (!secretSet || !secretSet.size) return { ...record };
            const sanitized = {};
            for (const key of Object.keys(record)) {
                if (secretSet.has(String(key))) continue;
                sanitized[key] = record[key];
            }
            return sanitized;
        }

        const restrictedListAction = restrictedRule && restrictedRule.allowList === false && (action === 'list' || action === 'search');
        if (restrictedListAction && !(req.method === 'POST' && action === 'search') && !wantsPublicIdentity(tableName, url)) {
            jsonResponse(res, 403, { error: 'table-restricted', message: 'جدول المستخدمين يتطلب الوصول بالمعرّف (ID) فقط' });
            return;
        }
        // ─────────────────────────────────────────────────────────────────────

        try {
            const store = await ensureModuleStore(branchId, moduleId);

            // 1. Get/Init Smart Schema using Schema Manager
            let smart;
            try {
                smart = await schemaManager.getOrLoadSmartSchema(branchId, moduleId);
            } catch (error) {
                jsonResponse(res, 500, { error: 'schema-error', message: error.message, moduleId });
                return;
            }

            // 2. Hydrator
            const hydrator = new Hydrator(smart, store);
            const lang = resolveLangParam(url) || 'ar'; // Default Arabi
            const fallbackLang = url.searchParams.get('fallbackLang') || 'ar';

            // 3. Handlers
            if (req.method === 'GET') {

                if (action === 'meta-tables') {
                    const tableTypes = Array.isArray(smart.tableTypes) ? smart.tableTypes : [];

                    const isArabic = text => /[\u0600-\u06FF]/.test(String(text || ''));
                    const humanize = name => String(name || '')
                        .replace(/_/g, ' ')
                        .trim()
                        .replace(/\s+/g, ' ')
                        .replace(/\b\w/g, c => c.toUpperCase());

                    const classifyModule = (tableName) => {
                        const explicit = smart.getTableType(tableName);
                        if (explicit) return explicit;
                        const name = String(tableName || '').toLowerCase();
                        const settingsKeys = ['company', 'branch', 'clinic', 'department', 'room', 'device', 'item', 'service', 'doctor', 'patient', 'type', 'station', 'tariff', 'package'];
                        if (settingsKeys.some(key => name.includes(key))) return 'settings';
                        if (name.includes('report') || name.includes('history') || name.includes('trail')) return 'reports';
                        if (name.includes('log')) return 'logs';
                        return 'operations';
                    };

                    const resolveLabels = (def) => {
                        const translations = (def && def.translations) ? (def.translations.label || def.translations.name || {}) : {};
                        const labels = Object.assign({}, translations);
                        const raw = def.label || '';
                        const arabic = def.label_ar || (isArabic(raw) ? raw : null) || humanize(def.name);
                        const english = def.label_en || (!isArabic(raw) ? raw : null) || humanize(def.name);
                        labels.ar = labels.ar || arabic;
                        labels.en = labels.en || english;
                        return labels;
                    };

                    const tables = [];
                    for (const [tName, def] of smart.tables.entries()) {
                        const labels = resolveLabels(def);
                        const icon = smart.getTableIcon(tName) || (def.icon) || (labels.ar ? labels.ar.charAt(0) : def.name.charAt(0)).toUpperCase();

                        // Extract FK references from schema
                        const fkReferences = [];
                        if (def.fields && Array.isArray(def.fields)) {
                            def.fields.forEach(field => {
                                if (field.references && field.references.table) {
                                    fkReferences.push({
                                        columnName: field.columnName || field.name,
                                        targetTable: field.references.table
                                    });
                                }
                            });
                        }

                        // Extract module_id and settings from smart_features
                        const smartFeatures = def.smart_features || {};
                        const tableModuleId = smartFeatures.module_id || null;
                        const settings = smartFeatures.settings || null;

                        tables.push({
                            id: def.name,
                            name: def.name,
                            label: labels.ar || def.label || def.name,
                            labels,
                            icon,
                            type: classifyModule(def.name),
                            is_translatable: def.is_translatable,
                            module_id: tableModuleId,
                            settings: settings,
                            fkReferences: fkReferences
                        });
                    }

                    // Extract modules from schema
                    const modules = Array.isArray(smart.schema?.modules) ? smart.schema.modules : [];

                    jsonResponse(res, 200, { tables, tableTypes, modules });
                    return;
                }

                if (action === 'get') {
                    // Find by ID
                    const found = findRecordUsingValue(store, tableName, id);
                    if (!found || !filterRecordForScope(tableName, found.record, { ...scope, tables: store.data || {} })) {
                        jsonResponse(res, 404, { error: 'record-not-found', id });
                        return;
                    }

                    const hydrated = await hydrator.hydrate(tableName, [found.record], lang, fallbackLang);
                    const translationBundle = buildTranslationBundle(store, tableName, id);
                    const columnsOrder = hydrator.getColumnsOrder(tableName);
                    const columnsMeta = hydrator.getColumnsMeta(tableName);
                    jsonResponse(res, 200, {
                        record: stripSecretFields(tableName, hydrated[0]),
                        translations: translationBundle.translations,
                        translationFields: translationBundle.fields,
                        languages: listAvailableLanguages(store),
                        columnsOrder,
                        columnsMeta
                    });
                    return;
                }

                if (action === 'search' || action === 'list') {
                    const publicIdentity = wantsPublicIdentity(tableName, url);
                    // Get All
                    const rows = filterTableRowsForScope(tableName, store.listTable(tableName) || [], {
                        ...scope,
                        tables: store.data || {}
                    });
                    const columnsOrder = hydrator.getColumnsOrder(tableName);
                    const columnsMeta = hydrator.getColumnsMeta(tableName);

                    // Filter by 'q'
                    const q = url.searchParams.get('q');
                    let filtered = applyTimeWindowFilters(rows, {
                        before: url.searchParams.get('before') || null,
                        beforeUpdatedAt: url.searchParams.get('beforeUpdatedAt') || null,
                        updatedBefore: url.searchParams.get('updatedBefore') || null,
                        since: url.searchParams.get('since') || null,
                        sinceUpdatedAt: url.searchParams.get('sinceUpdatedAt') || null,
                        updatedAfter: url.searchParams.get('updatedAfter') || null
                    });

                    const wantsMeta = url.searchParams.get('withMeta') === '1';

                    if (q && q.trim()) {
                        const term = q.trim().toLowerCase();
                        // Smart Search: Hydrate -> Filter (MVP)
                        const hydratedAll = await hydrator.hydrate(tableName, rows, lang, fallbackLang);

                        filtered = hydratedAll.filter(row => {
                            const searchable = new Set(['display_name']);
                            if (Array.isArray(columnsMeta) && columnsMeta.length) {
                                columnsMeta.forEach((col) => {
                                    if (col && col.name && col.is_searchable !== false) {
                                        searchable.add(col.name);
                                    }
                                });
                            } else {
                                ['name', 'title', 'code', 'phone', 'mobile'].forEach((name) => searchable.add(name));
                            }
                            return Array.from(searchable).some(field => {
                                const val = row[field];
                                if (typeof val === 'string' && val.toLowerCase().includes(term)) return true;
                                if (typeof val === 'number' && String(val).includes(term)) return true;
                                return false;
                            });
                        });
                    } else {
                        filtered = await hydrator.hydrate(tableName, rows, lang, fallbackLang);
                    }

                    // Cursor-based pagination support
                    const cursor = url.searchParams.get('cursor');
                    const useCursor = cursor !== null && cursor !== undefined;
                    
                    if (useCursor) {
                        // Sort by timestamp DESC
                        filtered.sort((a, b) => {
                            const timeA = parseRowTimestamp(a);
                            const timeB = parseRowTimestamp(b);
                            return (timeB || 0) - (timeA || 0);
                        });
                        
                        // Filter records older than cursor
                        if (cursor) {
                            const cursorTime = Date.parse(cursor);
                            if (Number.isFinite(cursorTime)) {
                                filtered = filtered.filter(row => {
                                    const rowTime = parseRowTimestamp(row);
                                    return rowTime !== null && rowTime < cursorTime;
                                });
                            }
                        }
                        
                        // Take limit + 1 to check hasMore
                        const limit = Number(url.searchParams.get('limit')) || 20;
                        const hasMore = filtered.length > limit;
                        const items = filtered.slice(0, limit).map((row) => stripSecretFields(tableName, row, { publicIdentity }));
                        const nextCursor = items.length > 0 ? (items[items.length - 1].updatedAt || items[items.length - 1].updated_at || items[items.length - 1].createdAt || items[items.length - 1].created_at) : null;
                        
                        const responseColumns = publicIdentity
                            ? publicIdentityColumns(tableName, columnsOrder, columnsMeta)
                            : { columnsOrder, columnsMeta };
                        
                        jsonResponse(res, 200, {
                            items,
                            nextCursor,
                            hasMore,
                            count: items.length,
                            columnsOrder: responseColumns.columnsOrder,
                            columnsMeta: responseColumns.columnsMeta
                        });
                        return;
                    }

                    // Traditional offset-based pagination
                    const total = filtered.length;
                    const page = Number(url.searchParams.get('page')) || 1;
                    const limit = Number(url.searchParams.get('limit')) || 20;
                    const start = (page - 1) * limit;
                    const paginated = filtered
                        .slice(start, start + limit)
                        .map((row) => stripSecretFields(tableName, row, { publicIdentity }));

                    const responseColumns = publicIdentity
                        ? publicIdentityColumns(tableName, columnsOrder, columnsMeta)
                        : { columnsOrder, columnsMeta };
                    const response = {
                        data: paginated,
                        count: total,
                        page,
                        limit,
                        columnsOrder: responseColumns.columnsOrder,
                        columnsMeta: responseColumns.columnsMeta
                    };
                    if (wantsMeta) {
                        response.meta = {
                            total,
                            fetched: paginated.length,
                            source: 'direct-store'
                        };
                    }
                    jsonResponse(res, 200, response);
                    return;
                }
            }

            // Write Operations
            if (req.method === 'POST' && action === 'create') {
                const body = await readBody(req).catch(() => ({}));
                let payload = body;
                if (!payload || typeof payload !== 'object') {
                    jsonResponse(res, 400, { error: 'invalid-payload' });
                    return;
                }

                // Extract _lang if present (optional i18n support)
                const langData = payload._lang && typeof payload._lang === 'object' ? payload._lang : null;
                if (langData) {
                    delete payload._lang; // Remove from base record payload
                }

                // TODO: Apply system fields logic if available (pending Step 12)
                // if (typeof applySystemFields === 'function') {
                //     payload = applySystemFields(payload, { created: true });
                // }

                if (!payload.id) {
                    // Try to generate ID via sequence? Or just createId?
                    // server.runtime.js used createId usually, or relying on store.insert to handle ID check?
                    // store.insert generates ID if missing usually.
                }

                // Normalize aliases for job order tables (legacy snake_case / alternate ids).
                if (tableName === 'job_order_header' && payload && typeof payload === 'object') {
                    if (!payload.id && payload.jobOrderId) payload.id = payload.jobOrderId;
                    if (!payload.id && payload.job_order_id) payload.id = payload.job_order_id;
                    if (!payload.orderId && payload.order_id) payload.orderId = payload.order_id;
                }
                if (tableName === 'job_order_detail' && payload && typeof payload === 'object') {
                    if (!payload.id && payload.detailId) payload.id = payload.detailId;
                    if (!payload.id && payload.detail_id) payload.id = payload.detail_id;
                    if (!payload.jobOrderId && payload.job_order_id) payload.jobOrderId = payload.job_order_id;
                    if (!payload.orderLineId && payload.order_line_id) payload.orderLineId = payload.order_line_id;
                    if (!payload.itemId && payload.item_id) payload.itemId = payload.item_id;
                }

                // If client sends POST with an existing key, treat it as upsert/merge
                // instead of hard insert to avoid replacing/invalidating sparse patches.
                let result;
                const lookupKey = payload && (payload.id ?? payload.jobOrderId ?? payload.job_order_id);
                if (lookupKey != null) {
                    const existing = findRecordUsingValue(store, tableName, lookupKey);
                    if (existing && existing.record) {
                        result = store.save(tableName, payload, { source: 'universal-crud' }).record;
                    } else {
                        result = store.insert(tableName, payload, { source: 'universal-crud' });
                    }
                } else {
                    result = store.insert(tableName, payload, { source: 'universal-crud' });
                }
                const recordId = resolveRecordPrimaryValue(store, tableName, result) || result.id || result.Id || result.uuid;

                // If _lang was provided, create translation entries
                if (langData && recordId) {
                    const langTable = `${tableName}_lang`;
                    const fkColumn = resolveLangFkColumn(store, tableName);

                    // Check if lang table exists
                    if (store.tables && store.tables.includes(langTable)) {
                        for (const [lang, fields] of Object.entries(langData)) {
                            if (fields && typeof fields === 'object') {
                                const langRecord = {
                                    id: result.id ? undefined : null, // Let store.insert generate ID
                                    [fkColumn]: recordId,
                                    lang: lang,
                                    ...fields
                                };
                                try {
                                    store.insert(langTable, langRecord, { source: 'universal-crud:lang' });
                                } catch (err) {
                                    logger.warn({ err, tableName, lang }, 'Failed to insert lang record');
                                }
                            }
                        }
                    }
                }

                await refreshDisplayNameCache({
                    store,
                    smartSchema: smart,
                    tableName,
                    recordId,
                    logger
                });

                await persistModuleStore(store);
                if (typeof invalidateSyncState === 'function') {
                    invalidateSyncState(branchId, moduleId);
                }
                if (isManagedTable(tableName)) {
                    const sqliteContext = { branchId, moduleId };
                    try {
                        persistRecord(tableName, result, sqliteContext);
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'create',
                            status: 'success',
                            stage: 'sqlite-upsert',
                            payload: { id: recordId }
                        }, sqliteContext);
                    } catch (sqliteError) {
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'create',
                            status: 'failed',
                            stage: 'sqlite-upsert',
                            errorMessage: sqliteError?.message || 'sqlite persist failed',
                            payload: { id: recordId }
                        }, sqliteContext);
                        logger.warn({ err: sqliteError, branchId, moduleId, tableName, recordId }, 'Failed to persist CRUD create to SQLite');
                    }
                }
                Hydrator.invalidateAll(store);

                const hydrated = await hydrator.hydrate(tableName, [result], lang, fallbackLang);
                await emitMutation(store, branchId, moduleId, tableName, 'module:save', stripSecretFields(tableName, hydrated[0] || result, {
                    publicIdentity: PUBLIC_IDENTITY_TABLES.has(normalizeTableName(tableName))
                }));

                const translationBundle = buildTranslationBundle(store, tableName, recordId);
                jsonResponse(res, 201, {
                    record: hydrated[0],
                    translations: translationBundle.translations,
                    translationFields: translationBundle.fields,
                    languages: listAvailableLanguages(store)
                });
                return;
            }

            if (req.method === 'PUT' && action === 'update') {
                const body = await readBody(req).catch(() => ({}));
                const payload = body;
                if (!payload || typeof payload !== 'object') {
                    jsonResponse(res, 400, { error: 'invalid-payload' });
                    return;
                }

                // Extract _lang if present (optional i18n support)
                const langData = payload._lang && typeof payload._lang === 'object' ? payload._lang : null;
                if (langData) {
                    delete payload._lang; // Remove from base record payload
                }

                // Verify existence
                const found = findRecordUsingValue(store, tableName, id);
                if (!found) {
                    jsonResponse(res, 404, { error: 'record-not-found', id });
                    return;
                }

                // Merge payload
                const merged = { ...found.record, ...payload };
                // Ensure ID match
                if (merged.id !== id) merged.id = id;

                // TODO: System fields update
                // if (typeof applySystemFields === 'function') {
                //      merged = applySystemFields(merged, { updated: true });
                // }

                const savedResult = store.save(tableName, merged, { source: 'universal-crud' });
                const savedRecord = savedResult.record;
                const recordId = resolveRecordPrimaryValue(store, tableName, savedRecord) || savedRecord.id || savedRecord.Id || savedRecord.uuid;

                // If _lang was provided, upsert translation entries
                if (langData && recordId) {
                    const langTable = `${tableName}_lang`;
                    const fkColumn = resolveLangFkColumn(store, tableName);

                    // Check if lang table exists
                    if (store.tables && store.tables.includes(langTable)) {
                        for (const [lang, fields] of Object.entries(langData)) {
                            if (fields && typeof fields === 'object') {
                                // Try to find existing lang record
                                const existingLangRows = (store.listTable(langTable) || []);
                                const existingLang = existingLangRows.find(row =>
                                    row[fkColumn] === recordId && row.lang === lang
                                );

                                if (existingLang) {
                                    // Update existing
                                    const updatedLang = { ...existingLang, ...fields };
                                    try {
                                        store.save(langTable, updatedLang, { source: 'universal-crud:lang' });
                                    } catch (err) {
                                        logger.warn({ err, tableName, lang }, 'Failed to update lang record');
                                    }
                                } else {
                                    // Insert new
                                    const langRecord = {
                                        [fkColumn]: recordId,
                                        lang: lang,
                                        ...fields
                                    };
                                    try {
                                        store.insert(langTable, langRecord, { source: 'universal-crud:lang' });
                                    } catch (err) {
                                        logger.warn({ err, tableName, lang }, 'Failed to insert lang record');
                                    }
                                }
                            }
                        }
                    }
                }

                await refreshDisplayNameCache({
                    store,
                    smartSchema: smart,
                    tableName,
                    recordId,
                    logger
                });

                await persistModuleStore(store);
                if (typeof invalidateSyncState === 'function') {
                    invalidateSyncState(branchId, moduleId);
                }
                if (isManagedTable(tableName)) {
                    const sqliteContext = { branchId, moduleId };
                    try {
                        persistRecord(tableName, savedRecord, sqliteContext);
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'update',
                            status: 'success',
                            stage: 'sqlite-upsert',
                            payload: { id: recordId }
                        }, sqliteContext);
                    } catch (sqliteError) {
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'update',
                            status: 'failed',
                            stage: 'sqlite-upsert',
                            errorMessage: sqliteError?.message || 'sqlite persist failed',
                            payload: { id: recordId }
                        }, sqliteContext);
                        logger.warn({ err: sqliteError, branchId, moduleId, tableName, recordId }, 'Failed to persist CRUD update to SQLite');
                    }
                }
                Hydrator.invalidateAll(store);

                const hydrated = await hydrator.hydrate(tableName, [savedRecord], lang, fallbackLang);
                await emitMutation(store, branchId, moduleId, tableName, 'module:save', stripSecretFields(tableName, hydrated[0] || savedRecord, {
                    publicIdentity: PUBLIC_IDENTITY_TABLES.has(normalizeTableName(tableName))
                }));
                const translationBundle = buildTranslationBundle(store, tableName, recordId);
                jsonResponse(res, 200, {
                    record: hydrated[0],
                    translations: translationBundle.translations,
                    translationFields: translationBundle.fields,
                    languages: listAvailableLanguages(store)
                });
                return;
            }

            if (req.method === 'DELETE' && action === 'delete') {
                let translationsRemoved = 0;
                const langTable = `${tableName}_lang`;
                const fkColumn = resolveLangFkColumn(store, tableName);
                const foundForDelete = findRecordUsingValue(store, tableName, id);
                const recordId = resolveRecordPrimaryValue(store, tableName, foundForDelete?.record) || id;
                if (store.tables && store.tables.includes(langTable)) {
                    const langRows = (store.listTable(langTable) || []).filter((row) => String(row[fkColumn]) === String(recordId));
                    for (const row of langRows) {
                        store.remove(langTable, { id: row.id });
                        translationsRemoved += 1;
                    }
                }

                const removed = store.remove(tableName, foundForDelete?.ref?.primaryKey || { id });

                await refreshDisplayNameCache({
                    store,
                    smartSchema: smart,
                    tableName,
                    recordId,
                    logger,
                    skipSelf: true
                });

                await persistModuleStore(store);
                if (typeof invalidateSyncState === 'function') {
                    invalidateSyncState(branchId, moduleId);
                }
                if (isManagedTable(tableName)) {
                    const sqliteContext = { branchId, moduleId };
                    try {
                        deleteRecord(tableName, recordId, sqliteContext);
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'delete',
                            status: 'success',
                            stage: 'sqlite-delete',
                            payload: { id: recordId }
                        }, sqliteContext);
                    } catch (sqliteError) {
                        appendSyncTransactionLog({
                            tableName,
                            recordId,
                            action: 'delete',
                            status: 'failed',
                            stage: 'sqlite-delete',
                            errorMessage: sqliteError?.message || 'sqlite delete failed',
                            payload: { id: recordId }
                        }, sqliteContext);
                        logger.warn({ err: sqliteError, branchId, moduleId, tableName, recordId }, 'Failed to delete CRUD record from SQLite');
                    }
                }
                Hydrator.invalidateAll(store);
                await emitMutation(store, branchId, moduleId, tableName, 'module:delete', stripSecretFields(tableName, removed.record || { id: recordId }, {
                    publicIdentity: PUBLIC_IDENTITY_TABLES.has(normalizeTableName(tableName))
                }), {
                    recordRef: foundForDelete?.ref || { id: recordId }
                });

                jsonResponse(res, 200, {
                    deleted: removed.record || { id: recordId },
                    translationsRemoved
                });
                return;
            }

            // POST /search
            if (req.method === 'POST' && action === 'search') {
                const body = await readBody(req).catch(() => ({}));
                const searchScope = buildRequestScope(req, url, body);
                const publicIdentity = wantsPublicIdentity(tableName, url, body);
                if (restrictedListAction && !publicIdentity) {
                    jsonResponse(res, 403, { error: 'table-restricted', message: 'جدول المستخدمين يتطلب الوصول بالمعرّف (ID) فقط' });
                    return;
                }
                const q = body.q || '';
                const page = body.page || 1;
                const limit = body.limit || 100;
                const reservedKeys = new Set([
                    'q',
                    'page',
                    'limit',
                    'cursor',
                    'fresh',
                    'cacheMode',
                    'withMeta',
                    'live',
                    'history',
                    'historyMode',
                    'before',
                    'beforeUpdatedAt',
                    'updatedBefore',
                    'olderThan',
                    'since',
                    'sinceUpdatedAt',
                    'updatedAfter',
                    '_auth_token',
                    'auth_token',
                    'token',
                    '_scope_user_id',
                    '_public_identity',
                    'publicIdentity'
                ]);
                const exactFilters = Object.entries(body || {}).filter(([key, value]) => {
                    if (reservedKeys.has(key)) return false;
                    return value !== undefined && value !== null && value !== '';
                });

                let rows = filterTableRowsForScope(tableName, store.listTable(tableName) || [], {
                    ...searchScope,
                    tables: store.data || {}
                });
                rows = applyTimeWindowFilters(rows, body || {});

                if (exactFilters.length) {
                    rows = rows.filter((row) => {
                        if (!row || typeof row !== 'object') return false;
                        return exactFilters.every(([key, value]) => {
                            const current = row[key];
                            if (Array.isArray(current)) {
                              return current.some((entry) => String(entry) === String(value));
                            }
                            if (current && typeof current === 'object') {
                              if (current.id !== undefined && String(current.id) === String(value)) return true;
                              return false;
                            }
                            return String(current) === String(value);
                        });
                    });
                }

                // Apply search filter
                if (q && q.trim()) {
                    const term = q.trim().toLowerCase();
                    const hydratedAll = await hydrator.hydrate(tableName, rows, lang, fallbackLang);
                    rows = hydratedAll.filter(row => {
                        const columnsMeta = hydrator.getColumnsMeta(tableName);
                        const searchable = new Set(['display_name']);
                        if (Array.isArray(columnsMeta) && columnsMeta.length) {
                            columnsMeta.forEach((col) => {
                                if (col && col.name && col.is_searchable !== false) {
                                    searchable.add(col.name);
                                }
                            });
                        } else {
                            ['name', 'title', 'code', 'phone', 'mobile'].forEach((name) => searchable.add(name));
                        }
                        return Array.from(searchable).some(field => {
                            const val = row[field];
                            if (typeof val === 'string' && val.toLowerCase().includes(term)) return true;
                            if (typeof val === 'number' && String(val).includes(term)) return true;
                            return false;
                        });
                    });
                } else {
                    rows = await hydrator.hydrate(tableName, rows, lang, fallbackLang);
                }

                // Pagination
                const total = rows.length;
                const start = (page - 1) * limit;
                const paginated = rows
                    .slice(start, start + limit)
                    .map((row) => stripSecretFields(tableName, row, { publicIdentity }));

                const columnsOrder = hydrator.getColumnsOrder(tableName);
                const columnsMeta = hydrator.getColumnsMeta(tableName);
                const responseColumns = publicIdentity
                    ? publicIdentityColumns(tableName, columnsOrder, columnsMeta)
                    : { columnsOrder, columnsMeta };
                jsonResponse(res, 200, {
                    data: paginated,
                    count: total,
                    page,
                    limit,
                    columnsOrder: responseColumns.columnsOrder,
                    columnsMeta: responseColumns.columnsMeta
                });
                return;
            }
        } catch (error) {
            logger.error({ err: error, branchId, moduleId, tableName }, 'Universal CRUD Error');
            jsonResponse(res, 500, { error: 'universal-crud-error', message: error.message });
            return;
        }
        jsonResponse(res, 405, { error: 'method-not-allowed' });
    }

    return {
        handleUniversalCrudApi
    };
}
