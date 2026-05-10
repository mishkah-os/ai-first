# Old System DNA — Architectural Heritage & Lessons

> **Purpose:** This document preserves the "precise" core logic of the legacy systems (`ai-auto`, `os`, `mostamal_hawaa`). It serves as a reference for the AI-First Kernel to understand the provenance of its features while ensuring a clean break from legacy technical debt.

---

## 1. Frontend Core DNA (Mostamal Hawaa)

### 1.1 Local Data Adapter (The Proxy Pattern)
**Source:** `os/static/app/mostamal_hawaa/src/core/db.js`
**The Success:** Seamless integration between IndexedDB (Local) and REST/WS (Remote).
**The DNA:**
```javascript
function createLocalAdapter(db) {
  return {
    async query(tableName) {
      const tx = db.transaction("records", "readonly");
      const index = tx.objectStore("records").index("table");
      const rows = await index.getAll(String(tableName));
      return rows.map(e => e.row);
    },
    async save(tableName, rows) {
      const tx = db.transaction("records", "readwrite");
      const store = tx.objectStore("records");
      rows.forEach(row => store.put({ key: `${tableName}:${row.id}`, table: tableName, row }));
    }
  };
}
```
**Legacy Weakness:** Manual synchronization logic was scattered across `MasStoreV3`. The new `mas-data.js` must make this transparent and atomic.

### 1.2 i18n Runtime
**The Success:** Dynamic dictionary building from database labels.
```javascript
function buildI18n(rows) {
  const dict = {};
  rows.forEach(row => {
    const key = row.label_key || row.key;
    const lang = row.lang.toLowerCase();
    if (!dict[key]) dict[key] = {};
    dict[key][lang] = row.text || row.value;
  });
  return dict;
}
```

---

## 2. Backend & Sync DNA (OS Runtime)

### 2.1 Atomic Event Logging
**Source:** `os/src/eventStore.js`
**The Success:** Using a transaction-log (append-only) for every mutation.
**The DNA:**
```javascript
async function appendEvent(options, entry) {
  const meta = await loadMeta(context);
  const sequence = Number(meta.totalEvents || 0) + 1;
  const line = { id, sequence, action, table, record, recordedAt: now() };
  await appendFile(context.logPath, `${JSON.stringify(line)}\n`, 'utf8');
  await writeMeta(context, { ...meta, totalEvents: sequence });
}
```
**The Improvement:** In AI-First, this is handled by the **C++ ORM Core** directly in PostgreSQL via the `change_log` table, eliminating the need for flat-file management.

### 2.2 Sync Policy (Insert-Only / Protected Tables)
**Source:** `os/src/runtime/sync-manager.js`
**The Success:** Preventing data loss by blocking destructive syncs on critical tables (POS/Orders).
```javascript
const POS_DELETE_PROTECTED_TABLES = new Set([
    'order_header', 'order_line', 'order_payment', 'job_order_header'
]);
function ensureInsertOnlySnapshot(store, incoming) {
    // Blocks the snapshot if it removes keys existing in the current state
}
```

---

## 3. Schema-Driven Normalization

**Source:** `os/static/app/mostamal_hawaa/src/shared/logic/schema.js`
**The DNA:**
```javascript
function identityValue(schema, tableName, record) {
  const primary = primaryFields(schema, tableName);
  for (const field of primary) {
    if (record[field]) return String(record[field]);
  }
  return String(record.id || record.uuid || "");
}
```

---

## 4. Why AI-First is Stronger (The Clean Break)

| Feature | Old System (Legacy) | AI-First (Nucleus) |
|---------|---------------------|--------------------|
| **Source of Truth** | Files + Local Storage + DB | **PostgreSQL Only** (All code is data) |
| **Logic Location** | Scattered in `src/` folders | **Atomic Pillars** inside Components |
| **Mutation** | Direct JS object manipulation | **QDML Protocol** with full audit trail |
| **Sync** | Complex JSON snapshots | **Real-time Delta Streams** via C++ |
| **Architecture** | Monolithic JS Runtime | **Unified Symphony** (C++, Py, Node, MAS) |

---

## 5. Precise Fragments to Migrate
- **Business Logic:** The specific table derivations (`deriveTables`) for Mostamal Hawaa are precise and should be ported as a `logic` pillar in the new frontend modules.
- **Component Kit:** The aesthetics of the `mostamal_hawaa_admin` UI are proven; the CSS tokens should be the base for `mas-ui.js`.

> [!IMPORTANT]
> **Warning:** Do not copy the "Manual File Management" from the old systems. AI-First MUST remain zero-file. The `old_system.md` is a map, not a template.
