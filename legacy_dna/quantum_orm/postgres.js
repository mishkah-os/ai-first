const crypto = require('node:crypto');

function hasDatabaseConfig(env) {
  const source = env || process.env;
  return !!(source.DATABASE_URL || source.PGHOST || source.PGDATABASE);
}

function loadPgModule() {
  try {
    return require('pg');
  } catch (_error) {
    return null;
  }
}

function quoteIdent(name) {
  const value = String(name || '').trim();
  if (!value) throw new Error('Identifier is required');
  return `"${value.replace(/"/g, '""')}"`;
}

function normalizeName(value) {
  return String(value || '').trim();
}

function parseIntegerLike(value) {
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number.parseInt(String(value), 10);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseBooleanLike(value) {
  if (value === null || value === undefined || value === '') return null;
  if (typeof value === 'boolean') return value;
  const normalized = String(value).trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
  return null;
}

function unwrapInputValue(value) {
  if (value && typeof value === 'object' && !Array.isArray(value)) {
    if (Object.prototype.hasOwnProperty.call(value, 'id')) return value.id;
  }
  return value;
}

function escapeLike(value) {
  return String(value || '').replace(/[\\%_]/g, '\\$&');
}

const CROCKFORD = '0123456789ABCDEFGHJKMNPQRSTVWXYZ';

function encodeBase32(buffer) {
  let bits = 0;
  let value = 0;
  let output = '';
  for (const byte of buffer) {
    value = (value << 8) | byte;
    bits += 8;
    while (bits >= 5) {
      output += CROCKFORD[(value >>> (bits - 5)) & 31];
      bits -= 5;
    }
  }
  if (bits > 0) {
    output += CROCKFORD[(value << (5 - bits)) & 31];
  }
  return output;
}

function generatePublicId(length) {
  const target = Number.parseInt(length, 10);
  const size = Number.isFinite(target) && target > 0 ? target : 26;
  return encodeBase32(crypto.randomBytes(Math.ceil((size * 5) / 8))).slice(0, size);
}

function findColumn(objectInfo, name) {
  const target = normalizeName(name).toLowerCase();
  if (!target) return null;
  return (objectInfo.columns || []).find((column) => {
    const colName = normalizeName(column.name).toLowerCase();
    const transName = normalizeName(column.trans_name).toLowerCase();
    return colName === target || transName === target;
  }) || null;
}

function buildColumnAliasMap(objectInfo) {
  const map = new Map();
  for (const column of objectInfo.columns || []) {
    const canonical = normalizeName(column.name);
    if (!canonical) continue;
    map.set(canonical.toLowerCase(), canonical);
    if (column.trans_name) map.set(normalizeName(column.trans_name).toLowerCase(), canonical);

    if (canonical === 'id') map.set('id', canonical);
    if (canonical === 'tenant_id') {
      map.set('company_id', canonical);
      map.set('compid', canonical);
    }
    if (canonical === 'created_at') {
      map.set('begin_date', canonical);
    }
    if (canonical === 'updated_at') {
      map.set('last_update', canonical);
    }
    if (canonical === 'created_by') {
      map.set('user_insert', canonical);
    }
  }
  return map;
}

function resolveColumnName(objectInfo, inputName) {
  const map = buildColumnAliasMap(objectInfo);
  return map.get(normalizeName(inputName).toLowerCase()) || null;
}

function getPrimaryKeyColumn(objectInfo) {
  return (objectInfo.columns || []).find((column) => column.is_primary_key) || null;
}

function getContextIdentity(context) {
  const cookies = (context && context.cookies) || {};
  return {
    tenantId: parseIntegerLike(
      cookies.tenant_id ??
      cookies.TenantID ??
      cookies.company_id ??
      cookies.Company_ID ??
      cookies.CompId ??
      (context && context.tenantId)
    ),
    userId: parseIntegerLike(
      cookies.user_id ??
      cookies.UserID ??
      cookies.user_insert ??
      (context && context.userId)
    )
  };
}

function normalizeValueForColumn(column, value) {
  const scalar = unwrapInputValue(value);
  if (scalar === undefined) return undefined;
  if (scalar === null || scalar === '') return null;

  switch (String(column.data_type || '').toLowerCase()) {
    case 'bit': {
      const boolValue = parseBooleanLike(scalar);
      return boolValue === null ? null : boolValue;
    }
    case 'bigint':
    case 'int':
    case 'smallint': {
      const parsed = Number.parseInt(String(scalar), 10);
      return Number.isFinite(parsed) ? parsed : null;
    }
    case 'decimal':
    case 'numeric': {
      const parsed = Number.parseFloat(String(scalar));
      return Number.isFinite(parsed) ? parsed : null;
    }
    case 'date':
    case 'datetime':
    case 'datetime2':
      return scalar instanceof Date ? scalar.toISOString() : String(scalar);
    default:
      return typeof scalar === 'string' ? scalar : String(scalar);
  }
}

function normalizeSelectedColumns(objectInfo, columnsCsv) {
  if (!columnsCsv) return objectInfo.columns || [];

  const names = String(columnsCsv)
    .split(',')
    .map((part) => resolveColumnName(objectInfo, part))
    .filter(Boolean);

  if (!names.length) return objectInfo.columns || [];

  if (!names.includes('id')) {
    names.unshift('id');
  }

  const wanted = new Set(names);
  return (objectInfo.columns || []).filter((column) => wanted.has(column.name));
}

function normalizeOrderTerms(objectInfo, rawOrder) {
  if (!rawOrder) return [];

  return String(rawOrder)
    .split(',')
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .map((item) => {
      const parts = item.split(/\s+/).filter(Boolean);
      const name = resolveColumnName(objectInfo, parts[0]);
      if (!name) return null;
      const direction = String(parts[1] || 'asc').toLowerCase() === 'desc' ? 'DESC' : 'ASC';
      return `${quoteIdent(name)} ${direction}`;
    })
    .filter(Boolean);
}

function normalizeFilterList(filters) {
  if (!filters) return [];
  if (Array.isArray(filters)) return filters;
  if (typeof filters !== 'string') return [];
  try {
    const parsed = JSON.parse(filters);
    return Array.isArray(parsed) ? parsed : [];
  } catch (_error) {
    return [];
  }
}

function buildReferenceSearchColumns(registry, column) {
  const referencedObject = registry.getObject(column.ReferencedTable);
  if (!referencedObject) return [];
  return String(column.search_columns || 'name')
    .split(',')
    .map((item) => resolveColumnName(referencedObject, item))
    .filter(Boolean);
}

function buildDirectFilterSql(column, cond, rawValue, values) {
  const fieldSql = `t.${quoteIdent(column.name)}`;
  const normalizedCond = String(cond || '=').trim().toLowerCase();

  if (normalizedCond === 'is null') return `${fieldSql} IS NULL`;
  if (normalizedCond === 'is not null') return `${fieldSql} IS NOT NULL`;

  if (normalizedCond === 'between') {
    const parts = Array.isArray(rawValue)
      ? rawValue
      : String(rawValue || '').split(/\s+and\s+/i);
    if (parts.length < 2) return null;
    const left = normalizeValueForColumn(column, parts[0]);
    const right = normalizeValueForColumn(column, parts[1]);
    values.push(left, right);
    return `${fieldSql} BETWEEN $${values.length - 1} AND $${values.length}`;
  }

  if (normalizedCond === 'in' || normalizedCond === 'not in') {
    const list = Array.isArray(rawValue)
      ? rawValue
      : String(rawValue || '')
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    if (!list.length) return null;
    const placeholders = list.map((item) => {
      values.push(normalizeValueForColumn(column, item));
      return `$${values.length}`;
    });
    return `${fieldSql} ${normalizedCond === 'not in' ? 'NOT IN' : 'IN'} (${placeholders.join(', ')})`;
  }

  if (normalizedCond === 'like' || normalizedCond === 'contains') {
    values.push(`%${escapeLike(rawValue)}%`);
    return `${fieldSql}::text ILIKE $${values.length} ESCAPE '\\'`;
  }

  if (normalizedCond === 'startswith') {
    values.push(`${escapeLike(rawValue)}%`);
    return `${fieldSql}::text ILIKE $${values.length} ESCAPE '\\'`;
  }

  if (normalizedCond === 'endswith') {
    values.push(`%${escapeLike(rawValue)}`);
    return `${fieldSql}::text ILIKE $${values.length} ESCAPE '\\'`;
  }

  const sqlOperator = ({
    '=': '=',
    '==': '=',
    '!=': '<>',
    '<>': '<>',
    '>': '>',
    '>=': '>=',
    '<': '<',
    '<=': '<='
  })[normalizedCond];

  if (!sqlOperator) return null;
  values.push(normalizeValueForColumn(column, rawValue));
  return `${fieldSql} ${sqlOperator} $${values.length}`;
}

function buildReferenceFilterSql(column, cond, rawValue, values, registry) {
  const searchColumns = buildReferenceSearchColumns(registry, column);
  if (!searchColumns.length) return null;

  const refTable = quoteIdent(column.ReferencedTable);
  const refColumnName = normalizeName(column.ReferencedColumnName || 'id') || 'id';
  const joinSql = `r.${quoteIdent(refColumnName)} = t.${quoteIdent(column.name)}`;
  const normalizedCond = String(cond || 'like').trim().toLowerCase();

  const clauses = [];
  for (const searchColumn of searchColumns) {
    const searchSql = `r.${quoteIdent(searchColumn)}::text`;
    if (normalizedCond === 'like' || normalizedCond === 'contains') {
      values.push(`%${escapeLike(rawValue)}%`);
      clauses.push(`${searchSql} ILIKE $${values.length} ESCAPE '\\'`);
      continue;
    }
    values.push(String(rawValue || ''));
    const operator = normalizedCond === '!=' || normalizedCond === '<>' ? '<>' : '=';
    clauses.push(`${searchSql} ${operator} $${values.length}`);
  }

  if (!clauses.length) return null;
  return `EXISTS (SELECT 1 FROM ${refTable} r WHERE ${joinSql} AND (${clauses.join(' OR ')}))`;
}

function buildWhereClause(objectInfo, filters, values, registry, context) {
  const normalized = normalizeFilterList(filters);
  const parts = [];
  let hasTenantFilter = false;

  for (const filter of normalized) {
    if (!filter || typeof filter !== 'object') continue;
    const columnName = resolveColumnName(objectInfo, filter.column_name);
    const column = columnName ? findColumn(objectInfo, columnName) : null;
    if (!column) continue;

    if (column.name === 'tenant_id') hasTenantFilter = true;

    const rawLogic = String(filter.logic || filter.cond_type || 'AND').trim().toUpperCase();
    const logic = rawLogic === 'OR' ? 'OR' : 'AND';
    const sql = filter.column_name_type === 'name' && column.ReferencedTable
      ? buildReferenceFilterSql(column, filter.cond, filter.value, values, registry)
      : buildDirectFilterSql(column, filter.cond, filter.value, values);

    if (sql) parts.push({ logic, sql });
  }

  const contextIdentity = getContextIdentity(context);
  if (!hasTenantFilter && contextIdentity.tenantId !== null && findColumn(objectInfo, 'tenant_id')) {
    values.push(contextIdentity.tenantId);
    parts.push({ logic: 'AND', sql: `t."tenant_id" = $${values.length}` });
  }

  if (!parts.length) return '';

  return ` WHERE ${parts.map((item, index) => `${index ? `${item.logic} ` : ''}(${item.sql})`).join(' ')}`;
}

function normalizeRowInput(objectInfo, row, context) {
  const out = {};
  const aliasMap = buildColumnAliasMap(objectInfo);
  const columnMap = new Map((objectInfo.columns || []).map((column) => [column.name, column]));
  const contextIdentity = getContextIdentity(context);

  for (const [key, value] of Object.entries(row || {})) {
    const canonical = aliasMap.get(normalizeName(key).toLowerCase());
    if (!canonical) continue;
    const column = columnMap.get(canonical);
    if (!column) continue;
    const normalized = normalizeValueForColumn(column, value);
    if (normalized !== undefined) out[canonical] = normalized;
  }

  const hasId = out.id !== null && out.id !== undefined && out.id !== '';

  if (!hasId && columnMap.has('public_id') && (out.public_id === null || out.public_id === undefined || out.public_id === '')) {
    const publicField = columnMap.get('public_id');
    out.public_id = generatePublicId(publicField.max_length || 26);
  }

  if (!hasId && contextIdentity.tenantId !== null && columnMap.has('tenant_id') && (out.tenant_id === null || out.tenant_id === undefined)) {
    out.tenant_id = contextIdentity.tenantId;
  }

  if (!hasId && columnMap.has('created_at') && (out.created_at === null || out.created_at === undefined)) {
    out.created_at = new Date().toISOString();
  }
  if (hasId && columnMap.has('updated_at')) {
    out.updated_at = new Date().toISOString();
  }

  if (!hasId && contextIdentity.userId !== null && columnMap.has('created_by') && (out.created_by === null || out.created_by === undefined)) {
    out.created_by = contextIdentity.userId;
  }
  if (hasId && contextIdentity.userId !== null && columnMap.has('updated_by')) {
    out.updated_by = contextIdentity.userId;
  }

  return out;
}

function buildWritableColumns(entryColumns, objectInfo, normalizedRows) {
  const requested = Array.isArray(entryColumns) ? entryColumns : [];
  const requestedNames = requested
    .map((item) => resolveColumnName(objectInfo, item && item.name))
    .filter(Boolean);
  const requestedSet = new Set(requestedNames);

  const output = [];
  for (const column of objectInfo.columns || []) {
    if (column.is_identity && column.name === 'id') continue;
    const present = normalizedRows.some((row) => Object.prototype.hasOwnProperty.call(row, column.name));
    if (requestedSet.size && !requestedSet.has(column.name) && !present) continue;
    if (present) {
      output.push(column);
    }
  }

  return output;
}

function getRecordsetType(column) {
  switch (String(column.data_type || '').toLowerCase()) {
    case 'bit':
      return 'boolean';
    case 'date':
      return 'date';
    case 'datetime':
    case 'datetime2':
      return 'timestamptz';
    case 'decimal':
    case 'numeric':
      return 'numeric';
    case 'bigint':
      return 'bigint';
    case 'int':
      return 'integer';
    case 'smallint':
      return 'smallint';
    default:
      return 'text';
  }
}

function buildRecordsetDefinition(columns) {
  return columns
    .map((column) => `${quoteIdent(column.name)} ${column.postgres_type}`)
    .join(', ');
}

function buildUpdateAssignments(columns) {
  return columns
    .filter((column) => column.name !== 'id' && column.name !== 'created_at' && column.name !== 'created_by')
    .map((column) => `${quoteIdent(column.name)} = s.${quoteIdent(column.name)}`)
    .join(', ');
}

function formatCellForOutput(column, value) {
  if (value === null || value === undefined) return null;
  if (String(column.data_type || '').toLowerCase() === 'bit') return value ? 1 : 0;
  return value;
}

function normalizeRoutineRow(row) {
  const out = {};
  for (const [key, value] of Object.entries(row || {})) {
    const finalValue = typeof value === 'boolean' ? (value ? 1 : 0) : value;
    out[key] = finalValue;
    if (key === 'id' && !Object.prototype.hasOwnProperty.call(out, 'ID')) {
      out.ID = finalValue;
    }
  }
  return out;
}

function buildRoutineResponse(data, sql, parms, startedAt, extra) {
  const rows = Array.isArray(data) ? data.map(normalizeRoutineRow) : [];
  const recordsAffected = extra && Object.prototype.hasOwnProperty.call(extra, 'recordsAffected')
    ? extra.recordsAffected
    : (extra && Object.prototype.hasOwnProperty.call(extra, 'RecordsAffected') ? extra.RecordsAffected : (rows.length || 0));
  return {
    data: rows,
    sl: sql || '',
    Error: null,
    RecordsAffected: Number.parseInt(recordsAffected, 10) || 0,
    msec: Date.now() - startedAt,
    parms: Array.isArray(parms) ? parms : [],
    ...(extra || {})
  };
}

function normalizeRoutineTypeName(typeName) {
  return String(typeName || '').trim().toLowerCase();
}

function isNumericRoutineType(typeName) {
  const normalized = normalizeRoutineTypeName(typeName);
  return [
    'smallint',
    'integer',
    'bigint',
    'real',
    'double precision',
    'numeric',
    'decimal'
  ].includes(normalized);
}

function isBooleanRoutineType(typeName) {
  return normalizeRoutineTypeName(typeName) === 'boolean';
}

function isJsonRoutineType(typeName) {
  const normalized = normalizeRoutineTypeName(typeName);
  return normalized === 'json' || normalized === 'jsonb';
}

function isArrayRoutineType(typeName) {
  return normalizeRoutineTypeName(typeName).endsWith('[]');
}

function parseJsonIfPossible(value) {
  if (typeof value !== 'string') return value;
  const trimmed = value.trim();
  if (!trimmed) return value;
  if (!['{', '[', '"'].includes(trimmed[0]) && !['true', 'false', 'null'].includes(trimmed) && !/^-?\d+(\.\d+)?$/.test(trimmed)) {
    return value;
  }

  try {
    return JSON.parse(trimmed);
  } catch (_error) {
    return value;
  }
}

function normalizeRoutineParamValue(rawValue, argMeta) {
  const typeName = normalizeRoutineTypeName(argMeta && argMeta.type_name);
  const parsedValue = parseJsonIfPossible(rawValue);

  if (parsedValue === null || parsedValue === undefined || parsedValue === '') return null;

  if (isJsonRoutineType(typeName)) {
    return typeof parsedValue === 'string' ? parseJsonIfPossible(parsedValue) : parsedValue;
  }

  if (isArrayRoutineType(typeName)) {
    if (Array.isArray(parsedValue)) return parsedValue;
    if (typeof parsedValue === 'string') {
      const reparsed = parseJsonIfPossible(parsedValue);
      if (Array.isArray(reparsed)) return reparsed;
      return String(parsedValue)
        .split(',')
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return [parsedValue];
  }

  if (isBooleanRoutineType(typeName)) {
    return parseBooleanLike(parsedValue);
  }

  if (isNumericRoutineType(typeName)) {
    const numeric = Number(parsedValue);
    return Number.isFinite(numeric) ? numeric : null;
  }

  if (typeof parsedValue === 'object') {
    return JSON.stringify(parsedValue);
  }

  return parsedValue;
}

function isSetReturningRoutine(routine) {
  const resultType = String((routine && routine.result_type) || '').trim().toUpperCase();
  return resultType.startsWith('TABLE(') || resultType.startsWith('SETOF ') || resultType === 'RECORD';
}

function getRoutineKindLabel(routine) {
  return routine && routine.prokind === 'p' ? 'proc' : 'fun';
}

async function loadReferenceMaps(runtime, registry, objectInfo, rows, selectedColumns) {
  const references = new Map();

  for (const column of selectedColumns.filter((item) => item.ReferencedTable)) {
    const ids = [...new Set(
      rows
        .map((row) => row[column.name])
        .filter((value) => value !== null && value !== undefined && value !== '')
        .map((value) => String(value))
    )];

    if (!ids.length) continue;

    const referencedObject = registry.getObject(column.ReferencedTable);
    if (!referencedObject) continue;

    const displayColumns = buildReferenceSearchColumns(registry, column);
    const refColumnName = normalizeName(column.ReferencedColumnName || 'id') || 'id';
    const selectColumns = [`${quoteIdent(refColumnName)}::text AS __id`]
      .concat(displayColumns.map((name) => `${quoteIdent(name)} AS ${quoteIdent(name)}`))
      .join(', ');

    const sql = `SELECT ${selectColumns} FROM ${quoteIdent(column.ReferencedTable)} WHERE ${quoteIdent(refColumnName)}::text = ANY($1::text[])`;
    const result = await runtime.query(sql, [ids]);
    const valueMap = new Map();

    for (const row of result.rows) {
      const text = displayColumns
        .map((name) => row[name])
        .filter((value) => value !== null && value !== undefined && String(value).trim() !== '')
        .join(' - ') || row.__id;
      valueMap.set(String(row.__id), text);
    }

    references.set(column.name, valueMap);
  }

  return references;
}

function normalizeOutputRows(rows, selectedColumns, referenceMaps) {
  return rows.map((row) => {
    const out = {};
    for (const column of selectedColumns) {
      const rawValue = row[column.name];
      if (column.ReferencedTable) {
        out[column.name] = rawValue === null || rawValue === undefined || rawValue === ''
          ? null
          : {
              id: rawValue,
              value: (referenceMaps.get(column.name) || new Map()).get(String(rawValue)) || String(rawValue)
            };
        continue;
      }

      const finalValue = formatCellForOutput(column, rawValue);
      if (column.name === 'id') {
        out.ID = finalValue;
      } else {
        out[column.name] = finalValue;
      }
    }
    return out;
  });
}

function buildPlaceholderList(startIndex, count) {
  return Array.from({ length: count }, (_, index) => `$${startIndex + index}`);
}

function buildPoolOptions(env) {
  const source = env || process.env;
  if (source.DATABASE_URL) {
    return {
      connectionString: source.DATABASE_URL,
      max: Number.parseInt(source.PGPOOL_MAX || '10', 10) || 10
    };
  }

  return {
    host: source.PGHOST || '127.0.0.1',
    port: Number.parseInt(source.PGPORT || '5432', 10),
    database: source.PGDATABASE || 'ai_auto',
    user: source.PGUSER || 'ai_auto',
    password: source.PGPASSWORD || '',
    max: Number.parseInt(source.PGPOOL_MAX || '10', 10) || 10
  };
}

function createPostgresRuntime(env) {
  const source = env || process.env;
  let pool = null;
  const routineCache = new Map();

  function isConfigured() {
    return hasDatabaseConfig(source);
  }

  function getDriverName() {
    return loadPgModule() ? 'pg' : 'unavailable';
  }

  function getPool() {
    if (!isConfigured()) return null;
    if (pool) return pool;
    const pg = loadPgModule();
    if (!pg) {
      throw new Error('PostgreSQL driver is not installed. Install package "pg" or OS package "node-pg".');
    }
    pool = new pg.Pool(buildPoolOptions(source));
    return pool;
  }

  async function query(text, values) {
    const activePool = getPool();
    if (!activePool) {
      throw new Error('DATABASE_URL / PG* variables are not configured.');
    }
    return activePool.query(text, values || []);
  }

  async function listRoutineCandidates(name) {
    const routineName = normalizeName(name);
    if (!routineName) return [];
    if (routineCache.has(routineName)) return routineCache.get(routineName);

    const sql = `
      SELECT
        p.oid,
        n.nspname AS schema_name,
        p.proname AS routine_name,
        p.prokind,
        p.pronargdefaults AS default_count,
        pg_catalog.pg_get_function_result(p.oid) AS result_type,
        COALESCE(
          json_agg(
            json_build_object(
              'position', a.ordinality,
              'type_name', pg_catalog.format_type(a.type_oid, NULL),
              'mode', COALESCE((p.proargmodes)[a.ordinality], 'i'),
              'name', COALESCE((p.proargnames)[a.ordinality], '')
            )
            ORDER BY a.ordinality
          ) FILTER (WHERE a.type_oid IS NOT NULL),
          '[]'::json
        ) AS args
      FROM pg_catalog.pg_proc p
      JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
      LEFT JOIN LATERAL unnest(
        CASE
          WHEN p.proallargtypes IS NOT NULL THEN p.proallargtypes
          WHEN p.pronargs > 0 THEN string_to_array(p.proargtypes::text, ' ')::oid[]
          ELSE ARRAY[]::oid[]
        END
      ) WITH ORDINALITY AS a(type_oid, ordinality) ON TRUE
      WHERE p.proname = $1
        AND n.nspname NOT IN ('pg_catalog', 'information_schema')
      GROUP BY p.oid, n.nspname, p.proname, p.prokind, p.pronargdefaults
      ORDER BY CASE WHEN n.nspname = 'public' THEN 0 ELSE 1 END, p.oid
    `;

    const result = await query(sql, [routineName]);
    const candidates = result.rows.map((row) => {
      const args = Array.isArray(row.args) ? row.args : [];
      const inputArgs = args.filter((arg) => ['i', 'b', 'v'].includes(String(arg.mode || 'i').toLowerCase()));
      return {
        oid: row.oid,
        schema_name: row.schema_name,
        routine_name: row.routine_name,
        prokind: row.prokind,
        result_type: row.result_type,
        default_count: Number.parseInt(row.default_count, 10) || 0,
        args,
        inputArgs
      };
    });

    routineCache.set(routineName, candidates);
    return candidates;
  }

  async function getRoutineCandidate(name, preferredKind, paramCount) {
    const candidates = await listRoutineCandidates(name);
    const desiredKinds = preferredKind === 'proc' ? ['p', 'f'] : ['f'];

    for (const kind of desiredKinds) {
      const match = candidates.find((candidate) => {
        if (candidate.prokind !== kind) return false;
        const minArgs = Math.max(candidate.inputArgs.length - candidate.default_count, 0);
        const maxArgs = candidate.inputArgs.length;
        return paramCount >= minArgs && paramCount <= maxArgs;
      });
      if (match) return match;
    }

    return null;
  }

  function buildRoutineSql(routine, providedCount, mode) {
    const args = routine.inputArgs.slice(0, providedCount);
    const placeholders = args.map((arg, index) => `$${index + 1}::${arg.type_name}`).join(', ');
    const qualifiedName = `${quoteIdent(routine.schema_name)}.${quoteIdent(routine.routine_name)}`;

    if (mode === 'call') {
      return `CALL ${qualifiedName}(${placeholders})`;
    }

    if (mode === 'select_scalar') {
      return `SELECT ${qualifiedName}(${placeholders}) AS value`;
    }

    return `SELECT * FROM ${qualifiedName}(${placeholders})`;
  }

  async function executeRoutine(kind, name, params) {
    const startedAt = Date.now();

    // Handle named parameters (object)
    if (params && typeof params === 'object' && !Array.isArray(params)) {
      const candidates = await listRoutineCandidates(name);
      const routine = candidates.find((c) => c.prokind === 'f') || candidates[0];
      if (!routine) {
        throw new Error(`Unknown routine: ${name}`);
      }

      const namedParams = params;
      const namedParamsLower = {};
      for (const key in namedParams) {
        if (Object.prototype.hasOwnProperty.call(namedParams, key)) {
          namedParamsLower[key.toLowerCase()] = namedParams[key];
        }
      }

      const rawParams = routine.inputArgs.map((arg) => {
        const argNameLower = (arg.name || '').toLowerCase();
        return Object.prototype.hasOwnProperty.call(namedParamsLower, argNameLower)
          ? namedParamsLower[argNameLower]
          : null;
      });

      const values = routine.inputArgs.map((arg, index) => normalizeRoutineParamValue(rawParams[index], arg));

      if (routine.prokind === 'p') {
        const sql = buildRoutineSql(routine, values.length, 'call');
        const result = await query(sql, values);
        return buildRoutineResponse(result.rows || [], sql, params, startedAt, {
          RecordsAffected: result.rowCount || 0,
          routine_kind: 'proc',
          routine_name: routine.routine_name,
          routine_schema: routine.schema_name
        });
      }

      const setMode = isSetReturningRoutine(routine) ? 'select_rows' : 'select_scalar';
      const sql = buildRoutineSql(routine, values.length, setMode);
      const result = await query(sql, values);

      if (setMode === 'select_scalar') {
        const scalar = result.rows[0] ? result.rows[0].value : null;
        return buildRoutineResponse(
          scalar === null || scalar === undefined ? [] : [{ value: scalar }],
          sql,
          params,
          startedAt,
          {
            RecordsAffected: result.rowCount || (scalar === null || scalar === undefined ? 0 : 1),
            scalar,
            routine_kind: getRoutineKindLabel(routine),
            routine_name: routine.routine_name,
            routine_schema: routine.schema_name
          }
        );
      }

      return buildRoutineResponse(result.rows || [], sql, params, startedAt, {
        RecordsAffected: result.rowCount || (result.rows || []).length,
        routine_kind: getRoutineKindLabel(routine),
        routine_name: routine.routine_name,
        routine_schema: routine.schema_name
      });
    }

    // Handle positional parameters (array)
    const rawParams = Array.isArray(params) ? params : [];
    const routine = await getRoutineCandidate(name, kind, rawParams.length);
    if (!routine) {
      throw new Error(`Unknown ${kind} routine or wrong parameters count: ${name}`);
    }

    const argsMeta = routine.inputArgs.slice(0, rawParams.length);
    const values = argsMeta.map((arg, index) => normalizeRoutineParamValue(rawParams[index], arg));

    if (routine.prokind === 'p') {
      const sql = buildRoutineSql(routine, values.length, 'call');
      const result = await query(sql, values);
      return buildRoutineResponse(result.rows || [], sql, rawParams, startedAt, {
        RecordsAffected: result.rowCount || 0,
        routine_kind: 'proc',
        routine_name: routine.routine_name,
        routine_schema: routine.schema_name
      });
    }

    const setMode = isSetReturningRoutine(routine) ? 'select_rows' : 'select_scalar';
    const sql = buildRoutineSql(routine, values.length, setMode);
    const result = await query(sql, values);

    if (setMode === 'select_scalar') {
      const scalar = result.rows[0] ? result.rows[0].value : null;
      return buildRoutineResponse(
        scalar === null || scalar === undefined ? [] : [{ value: scalar }],
        sql,
        rawParams,
        startedAt,
        {
          RecordsAffected: result.rowCount || (scalar === null || scalar === undefined ? 0 : 1),
          scalar,
          routine_kind: kind === 'proc' ? 'proc' : 'fun',
          routine_name: routine.routine_name,
          routine_schema: routine.schema_name
        }
      );
    }

    return buildRoutineResponse(result.rows || [], sql, rawParams, startedAt, {
      RecordsAffected: result.rowCount || (result.rows || []).length,
      routine_kind: getRoutineKindLabel(routine),
      routine_name: routine.routine_name,
      routine_schema: routine.schema_name
    });
  }

  async function getFunctionSchema(name) {
    const candidates = await listRoutineCandidates(normalizeName(name));
    const fn = candidates.find((c) => c.prokind === 'f') || candidates[0];
    if (!fn) return null;

    // Build parameter list (input args only)
    const parameters = fn.inputArgs.map((arg, index) => ({
      name: '@' + (arg.name || `p${index + 1}`),
      data_type: arg.type_name,
      column_id: index + 1
    }));

    // Build output columns from OUT/TABLE args
    const outArgs = fn.args.filter((arg) => ['o', 't'].includes(String(arg.mode || '').toLowerCase()));
    const columns = outArgs.map((arg, index) => ({
      column_id: index + 1,
      name: arg.name || `col${index + 1}`,
      trans_name: arg.name || `col${index + 1}`,
      data_type: arg.type_name,
      type: arg.type_name,
      is_nullable: true,
      is_identity: false,
      is_primary_key: false,
      is_table_show: true,
      is_edit_show: false,
      is_searchable: false
    }));

    return {
      name: fn.routine_name,
      object_id: fn.oid,
      type_desc: 'SQL_TABLE_VALUED_FUNCTION',
      trans_name: fn.routine_name,
      columns,
      parameters,
      table_childs: [],
      allcolumns: columns.map((c) => c.name).join(',')
    };
  }

  async function readObject(payload, registry, context) {
    const objectInfo = registry.getObject(payload.Name || payload.name);
    if (!objectInfo) throw new Error(`Unknown object: ${payload.Name || payload.name}`);

    const options = payload.Options || {};
    const selectedColumns = normalizeSelectedColumns(objectInfo, options.Columns || options.columns);
    const selectSql = selectedColumns
      .map((column) => `t.${quoteIdent(column.name)} AS ${quoteIdent(column.name)}`)
      .join(', ');

    const values = [];
    const whereSql = buildWhereClause(objectInfo, payload.Filters, values, registry, context);
    const orderTerms = normalizeOrderTerms(objectInfo, options.Order || options.order);
    const top = Number.parseInt(options.Top ?? options.top ?? 100, 10);
    const page = Number.parseInt(options.Page ?? options.page ?? 1, 10);
    const limit = Number.isFinite(top) && top > 0 ? top : 100;
    const pageNumber = Number.isFinite(page) && page > 0 ? page : 1;
    const offset = (pageNumber - 1) * limit;
    const orderSql = orderTerms.length
      ? ` ORDER BY ${orderTerms.join(', ')}`
      : (findColumn(objectInfo, 'id') ? ' ORDER BY t."id" DESC' : '');

    values.push(limit, offset);
    const sql = `SELECT ${selectSql} FROM ${quoteIdent(objectInfo.name)} t${whereSql}${orderSql} LIMIT $${values.length - 1} OFFSET $${values.length}`;
    const countSql = `SELECT COUNT(*)::int AS total FROM ${quoteIdent(objectInfo.name)} t${whereSql}`;

    const [rowsResult, countResult] = await Promise.all([
      query(sql, values),
      query(countSql, values.slice(0, values.length - 2))
    ]);

    const referenceMaps = await loadReferenceMaps({ query }, registry, objectInfo, rowsResult.rows, selectedColumns);
    const data = normalizeOutputRows(rowsResult.rows, selectedColumns, referenceMaps);
    const fullResult = {
      data,
      columns: selectedColumns,
      count: (countResult.rows[0] && countResult.rows[0].total) || 0,
      top: limit,
      page: pageNumber,
      allcolumns: selectedColumns.map((column) => column.name).join(','),
      table_childs: objectInfo.table_childs || [],
      request_info: {
        action: 'read',
        name: objectInfo.name,
        filters: normalizeFilterList(payload.Filters),
        params: payload.Params || null,
        options
      }
    };

    if (options.DataOnly === true || options.DataOnly === 'true' || options.dataOnly === true || options.dataOnly === 'true') {
      return data;
    }

    return fullResult;
  }

  async function saveObjects(payload, registry, context) {
    const entries = Array.isArray(payload.Data) ? payload.Data : [];
    const results = [];

    for (const entry of entries) {
      const objectName = normalizeName(entry && (entry.name || entry.Name || payload.Name || payload.name));
      const objectInfo = registry.getObject(objectName);
      if (!objectInfo) {
        results.push({
          name: objectName,
          insertResult: `Unknown object: ${objectName}`,
          updateResult: `Unknown object: ${objectName}`,
          countInsertResult: 0,
          countUpdateResult: 0,
          insertSQL: '',
          updateSQL: '',
          accepted: false
        });
        continue;
      }

      const incomingRows = Array.isArray(entry && entry.data) ? entry.data : [];
      const normalizedRows = incomingRows.map((row) => normalizeRowInput(objectInfo, row, context));
      const writableColumns = buildWritableColumns(entry.columns, objectInfo, normalizedRows).map((column) => ({
        ...column,
        postgres_type: getRecordsetType(column)
      }));

      const pkColumn = getPrimaryKeyColumn(objectInfo);
      if (!pkColumn) throw new Error(`Primary key is missing for ${objectInfo.name}`);

      const rowsJson = JSON.stringify(normalizedRows);
      const dataColumns = [pkColumn]
        .concat(writableColumns.filter((column) => column.name !== pkColumn.name))
        .filter((column, index, items) => items.findIndex((item) => item.name === column.name) === index)
        .map((column) => ({
          ...column,
          postgres_type: column.postgres_type || getRecordsetType(column)
        }));

      const recordsetSql = buildRecordsetDefinition(dataColumns);
      const updateColumns = dataColumns.filter((column) => column.name !== pkColumn.name);
      const updateAssignments = buildUpdateAssignments(updateColumns);
      const insertColumns = updateColumns;
      const insertColumnSql = insertColumns.map((column) => quoteIdent(column.name)).join(', ');
      const insertSelectSql = insertColumns.map((column) => `s.${quoteIdent(column.name)}`).join(', ');
      const insertWithIdColumns = [pkColumn].concat(insertColumns);
      const insertWithIdColumnSql = insertWithIdColumns.map((column) => quoteIdent(column.name)).join(', ');
      const insertWithIdSelectSql = insertWithIdColumns.map((column) => `s.${quoteIdent(column.name)}`).join(', ');

      const updateSql = updateAssignments
        ? `WITH source AS (
             SELECT * FROM jsonb_to_recordset($1::jsonb) AS s(${recordsetSql})
           )
           UPDATE ${quoteIdent(objectInfo.name)} AS t
           SET ${updateAssignments}
           FROM source AS s
           WHERE s.${quoteIdent(pkColumn.name)} IS NOT NULL
             AND t.${quoteIdent(pkColumn.name)} = s.${quoteIdent(pkColumn.name)}`
        : '';

      const insertSql = insertColumns.length
        ? `WITH source AS (
             SELECT * FROM jsonb_to_recordset($1::jsonb) AS s(${recordsetSql})
           ),
           inserted_with_id AS (
             INSERT INTO ${quoteIdent(objectInfo.name)} (${insertWithIdColumnSql})
             SELECT ${insertWithIdSelectSql}
             FROM source AS s
             WHERE s.${quoteIdent(pkColumn.name)} IS NOT NULL
               AND NOT EXISTS (
                 SELECT 1
                 FROM ${quoteIdent(objectInfo.name)} AS t
                 WHERE t.${quoteIdent(pkColumn.name)} = s.${quoteIdent(pkColumn.name)}
               )
             RETURNING 1
           ),
           inserted_without_id AS (
             INSERT INTO ${quoteIdent(objectInfo.name)} (${insertColumnSql})
             SELECT ${insertSelectSql}
             FROM source AS s
             WHERE s.${quoteIdent(pkColumn.name)} IS NULL
             RETURNING 1
           )
           SELECT
             (SELECT COUNT(*)::int FROM inserted_with_id) + (SELECT COUNT(*)::int FROM inserted_without_id) AS inserted_count`
        : '';

      let countUpdateResult = 0;
      let countInsertResult = 0;

      if (updateSql) {
        const updateResult = await query(updateSql, [rowsJson]);
        countUpdateResult = updateResult.rowCount || 0;
      }

      if (insertSql) {
        const insertResult = await query(insertSql, [rowsJson]);
        countInsertResult = (insertResult.rows[0] && insertResult.rows[0].inserted_count) || 0;
      }

      results.push({
        name: objectInfo.name,
        insertResult: String(countInsertResult),
        updateResult: String(countUpdateResult),
        countInsertResult,
        countUpdateResult,
        insertSQL: insertSql.replace(/\s+/g, ' ').trim(),
        updateSQL: updateSql.replace(/\s+/g, ' ').trim(),
        accepted: true
      });
    }

    return results;
  }

  async function deleteObject(name, rowid, registry, context) {
    const objectInfo = registry.getObject(name);
    if (!objectInfo) throw new Error(`Unknown object: ${name}`);
    const pkColumn = getPrimaryKeyColumn(objectInfo);
    if (!pkColumn) throw new Error(`Primary key is missing for ${name}`);

    const values = [normalizeValueForColumn(pkColumn, rowid)];
    let sql = `DELETE FROM ${quoteIdent(objectInfo.name)} WHERE ${quoteIdent(pkColumn.name)} = $1`;
    const tenantColumn = findColumn(objectInfo, 'tenant_id');
    const contextIdentity = getContextIdentity(context);
    if (tenantColumn && contextIdentity.tenantId !== null) {
      values.push(contextIdentity.tenantId);
      sql += ` AND "tenant_id" = $2`;
    }

    const result = await query(sql, values);
    return {
      ok: true,
      deleted: result.rowCount > 0,
      contract_only: false,
      name: objectInfo.name,
      rowid
    };
  }

  return {
    isConfigured,
    getDriverName,
    query,
    executeRoutine,
    getFunctionSchema,
    readObject,
    saveObjects,
    deleteObject
  };
}

module.exports = {
  createPostgresRuntime,
  hasDatabaseConfig
};
