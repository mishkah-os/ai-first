import { deepClone } from '../utils.js';

export function normalizeLang(lang, fallback = 'ar') {
  if (!lang || typeof lang !== 'string') return fallback;
  const normalized = lang.trim().toLowerCase();
  return normalized || fallback;
}

function primaryKeyFields(store, tableName) {
  if (!store || !tableName) return [];
  if (typeof store.resolvePrimaryKeyFields === 'function') {
    try {
      const fields = store.resolvePrimaryKeyFields(tableName);
      if (Array.isArray(fields) && fields.length) return fields;
    } catch (_error) {}
  }
  try {
    const table = store.schemaEngine?.getTable?.(tableName);
    const fields = Array.isArray(table?.fields)
      ? table.fields.filter((field) => field && field.primaryKey).map((field) => field.name || field.columnName).filter(Boolean)
      : [];
    if (fields.length) return fields;
  } catch (_error) {}
  return ['id'];
}

function tableExists(store, tableName) {
  const target = String(tableName || '').toLowerCase();
  return Array.isArray(store?.tables) && store.tables.some((name) => String(name || '').toLowerCase() === target);
}

function langTableFields(store, langTableName) {
  try {
    const table = store?.schemaEngine?.getTable?.(langTableName);
    return Array.isArray(table?.fields)
      ? table.fields.map((field) => field && (field.name || field.columnName)).filter(Boolean)
      : [];
  } catch (_error) {
    return [];
  }
}

export function resolveRecordIdentity(store, tableName, record) {
  if (!record || typeof record !== 'object') return null;
  const ref = typeof store?.getRecordReference === 'function'
    ? store.getRecordReference(tableName, record)
    : null;
  if (ref?.key) return ref.key;
  if (ref?.id) return ref.id;
  if (ref?.uuid) return ref.uuid;
  if (ref?.uid) return ref.uid;
  const primaryFields = primaryKeyFields(store, tableName);
  for (const field of primaryFields) {
    if (record[field] !== undefined && record[field] !== null && record[field] !== '') {
      return record[field];
    }
  }
  return record.id || record.uuid || record.uid || null;
}

export function resolveTranslationReferenceField(store, baseName) {
  const langTableName = `${baseName}_lang`;
  const fields = langTableFields(store, langTableName);
  const primaryFields = primaryKeyFields(store, baseName);
  for (const field of primaryFields) {
    if (fields.includes(field)) return field;
  }
  const legacy = `${baseName}_id`;
  if (fields.includes(legacy)) return legacy;
  const tableParts = String(baseName || '').split('_').filter(Boolean);
  const singular = tableParts.length ? `${tableParts[tableParts.length - 1].replace(/s$/i, '')}_id` : '';
  if (singular && fields.includes(singular)) return singular;
  return fields.find((field) => String(field || '').toLowerCase().endsWith('_id')) || legacy;
}

export function extractReferenceId(record, baseName, store = null) {
  if (!record || typeof record !== 'object') return null;
  const directKey = resolveTranslationReferenceField(store, baseName);
  if (record[directKey]) return record[directKey];
  for (const field of primaryKeyFields(store, baseName)) {
    if (record[field]) return record[field];
  }
  const legacyKey = `${baseName}_id`;
  if (record[legacyKey]) return record[legacyKey];
  const camelKey = `${baseName}Id`;
  if (record[camelKey]) return record[camelKey];
  for (const key of Object.keys(record)) {
    if (key === 'id') continue;
    if (key.toLowerCase().endsWith('_id') && record[key]) {
      return record[key];
    }
  }
  return record.id || null;
}

export function isIgnoredField(key, baseName, store = null) {
  const normalized = key.toLowerCase();
  const ignoredPrimary = new Set(primaryKeyFields(store, baseName).map((field) => String(field || '').toLowerCase()));
  const ignoredFk = resolveTranslationReferenceField(store, baseName).toLowerCase();
  return (
    normalized === 'id' ||
    normalized === 'lang' ||
    normalized === 'is_auto' ||
    normalized === 'display_name' ||
    normalized === 'created_at' ||
    normalized === 'updated_at' ||
    normalized === `${baseName.toLowerCase()}_id` ||
    normalized === ignoredFk ||
    ignoredPrimary.has(normalized) ||
    normalized === 'created_date' ||
    normalized === 'modified_date'
  );
}

function flattenTranslationsMap(map) {
  const output = {};
  for (const [table, records] of map.entries()) {
    const tableObj = {};
    for (const [recordId, fields] of records.entries()) {
      tableObj[recordId] = deepClone(fields);
    }
    output[table] = tableObj;
  }
  return output;
}

function mergeWithFallback(primary, fallback) {
  const merged = new Map();
  const tables = new Set([...(fallback?.keys?.() ? fallback.keys() : []), ...(primary?.keys?.() ? primary.keys() : [])]);
  for (const table of tables) {
    const primaryRecords = primary?.get(table) || new Map();
    const fallbackRecords = fallback?.get(table) || new Map();
    const recordIds = new Set([...(fallbackRecords.keys ? fallbackRecords.keys() : []), ...(primaryRecords.keys ? primaryRecords.keys() : [])]);
    const recordMap = new Map();
    for (const recordId of recordIds) {
      const fallbackFields = fallbackRecords.get(recordId) || {};
      const primaryFields = primaryRecords.get(recordId) || {};
      recordMap.set(recordId, { ...fallbackFields, ...primaryFields });
    }
    merged.set(table, recordMap);
  }
  return merged;
}

function hasTranslationTable(store, tableName) {
  return tableExists(store, `${tableName}_lang`);
}

function buildFallbackFromRecord(record, baseName, store = null) {
  const fallback = {};
  if (!record || typeof record !== 'object') return fallback;
  for (const [key, value] of Object.entries(record)) {
    if (isIgnoredField(key, baseName, store)) continue;
    if (value === null || value === undefined) continue;
    fallback[key] = value;
  }
  return fallback;
}

export function attachTranslationsToRows(store, tableName, rows, { lang = 'ar', fallbackLang = 'ar' } = {}) {
  if (!Array.isArray(rows) || !store || !tableName) return rows;
  if (!hasTranslationTable(store, tableName)) return rows;

  const normalizedLang = normalizeLang(lang, fallbackLang);
  const normalizedFallback = normalizeLang(fallbackLang);
  const { translations } = loadTranslationsPayload(store, { lang: normalizedLang, fallbackLang: normalizedFallback });

  const tableTranslations = translations?.[tableName] || translations?.[tableName.toLowerCase()] || null;
  return rows.map((row) => {
    const refId = resolveRecordIdentity(store, tableName, row);
    const translationFields = refId && tableTranslations ? tableTranslations[refId] || tableTranslations[String(refId)] : null;
    const baseFallback = buildFallbackFromRecord(row, tableName, store);
    const fallbackFields = translationFields && Object.keys(translationFields).length
      ? { ...baseFallback, ...translationFields }
      : baseFallback;

    if (!fallbackFields || !Object.keys(fallbackFields).length) return row;

    const clone = deepClone(row);
    const i18nContainer =
      clone.i18n && typeof clone.i18n === 'object' && !Array.isArray(clone.i18n) ? deepClone(clone.i18n) : {};
    const langContainer =
      i18nContainer.lang && typeof i18nContainer.lang === 'object' && !Array.isArray(i18nContainer.lang)
        ? { ...i18nContainer.lang }
        : {};

    langContainer[normalizedLang] = { ...fallbackFields };
    i18nContainer.lang = langContainer;
    clone.i18n = i18nContainer;
    return clone;
  });
}

export function loadTranslationsPayload(store, { lang = 'ar', fallbackLang = 'ar' } = {}) {
  const normalizedLang = normalizeLang(lang);
  const normalizedFallback = normalizeLang(fallbackLang);
  const translationsByLang = new Map();
  const translationTables = (store?.tables || []).filter((name) => typeof name === 'string' && name.endsWith('_lang'));

  for (const tableName of translationTables) {
    const baseName = tableName.replace(/_lang$/i, '');
    const records = store.listTable(tableName) || [];
    for (const record of records) {
      const language = normalizeLang(record?.lang, normalizedFallback);
      const refId = extractReferenceId(record, baseName, store);
      if (!refId) continue;
      if (!translationsByLang.has(language)) {
        translationsByLang.set(language, new Map());
      }
      const tableMap = translationsByLang.get(language);
      if (!tableMap.has(baseName)) {
        tableMap.set(baseName, new Map());
      }
      const recordMap = tableMap.get(baseName);
      if (!recordMap.has(refId)) {
        recordMap.set(refId, {});
      }
      const fieldMap = recordMap.get(refId);
      for (const [key, value] of Object.entries(record || {})) {
        if (isIgnoredField(key, baseName, store)) continue;
        if (value === null || value === undefined) continue;
        fieldMap[key] = value;
      }
      recordMap.set(refId, fieldMap);
      tableMap.set(baseName, recordMap);
      translationsByLang.set(language, tableMap);
    }
  }

  const fallbackMap = translationsByLang.get(normalizedFallback) || new Map();
  const primaryMap = translationsByLang.get(normalizedLang) || new Map();
  const merged = mergeWithFallback(primaryMap, fallbackMap);

  return {
    lang: normalizedLang,
    fallbackLang: normalizedFallback,
    translations: flattenTranslationsMap(merged),
    availableLanguages: Array.from(translationsByLang.keys())
  };
}
