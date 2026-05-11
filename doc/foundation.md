# AI-First: Complete Architecture Specification

> **Project**: ai-first  
> **Revision**: 4 — 2026-05-09  
> **Status**: Final Architectural Blueprint  
> **Scope**: Full-Stack (Frontend + Backend + DevOps + AI Tooling)

---

## 1. Thesis

Every existing coding system — whether developer tools or AI assistants — operates on **files**. The source of truth is a filesystem, and every tool reverse-engineers structure from text.

**AI-First** eliminates files entirely from the development process. The source of truth is a **relational database**. Code is stored, queried, and mutated as structured records. Files are generated on demand by a compiler — they are build artifacts, never edited directly.

This document defines the **complete system**: frontend rendering, backend ORM, real-time sync, security, deployment, and the AI development environment that builds everything from a schema-first database.

### What We Carry Forward

| System | What Worked | What Failed | What AI-First Takes |
|--------|------------|-------------|-------------------|
| **MAS Store v3** | WS delta sync, IndexedDB cache, outbox queue, cursor-based reconnect replay | No change-log events for deletes, weak security rules, no live/deep data separation | Delta sync protocol, cursor tracking, offline-first outbox |
| **OS Server Runtime** | Schema engine, hybrid store, CRUD API, pubsub manager, module event handler, branch/module isolation | ORM is weaker than Quantum, file-based storage (SQLite/JSON), paging is imprecise | Branch/module isolation model, pubsub architecture, security policy loader |
| **Quantum (ai-auto)** | Schema-driven PostgreSQL ORM, `smart_features` per table, tree engine, translation system, C++ core engine | Separate system from OS runtime (not unified), two codebases to maintain | Schema contract model, smart_features, C++ core engine, `quantum_raw_v1` profile |
| **Ant-Swarm** | Multi-provider AI orchestration, Playwright browser testing, Track3 surgical mutations | Complex setup, many files, not schema-driven | AI provider catalog, Playwright integration, API text interface |

### The Two Fundamental Problems We Solve

1. **No unified source of truth.** OS uses SQLite/JSON files for live data. Quantum uses PostgreSQL for deep data. MAS Store v3 syncs via WebSocket but cannot propagate deletes. The frontend schema (`db` object) and backend schema (SQL tables) are defined independently and drift apart. **AI-First makes the database schema the single source of truth for both frontend and backend.**

2. **No deep sync protocol.** When a record is deleted on the backend, there is nothing that tells the frontend "delete this from IndexedDB." The current `server:patch` events only handle upserts reliably. **AI-First implements a complete change-log with tombstones, cursor-tracked replay, and bidirectional delete propagation.**

---

## 2. Non-Negotiable Principles

| # | Principle | Implication |
|---|-----------|-------------|
| 1 | **Schema-First, Everything-Derived** | A single JSON schema document defines both the PostgreSQL tables AND the frontend IndexedDB stores AND the API endpoints AND the security rules. Nothing exists without a schema definition. |
| 2 | **One Project = One Database** | PostgreSQL database per project. Multi-tenancy and versioning are optional within. |
| 3 | **Holistic Component Retrieval** | A single ID query returns all pillars (schema, template, logic, style) + i18n keys + children. |
| 4 | **Complete Sync Protocol** | Every mutation (create, update, delete) generates a change-log event with cursors. Clients replay from their last cursor on reconnect. Deletes propagate as tombstones. |
| 5 | **Security Rules in Schema** | Each table defines `access_rules` in its schema: who can read, write, delete, which fields are secret, which are locked. The runtime enforces these, not application code. |
| 6 | **C++ Core Engine** | The deep ORM (query builder, tree operations, schema validation, DDL generation) runs as a compiled C++ binary. Python and JS are wrappers. Maximum performance, minimum code. |
| 7 | **Zero Static Files** | No configuration files, no boilerplate. The project starts as a database schema. The system generates everything else: `Dockerfile`, `docker-compose.yml`, `tailwind.config.js`, dependency manifests, migration scripts. |
| 8 | **Blinded Mini Code** | The AI sees structural skeletons first. Full bodies are revealed on explicit request. Shared functions, utils, and global variables are indexed and included in the skeleton. |
| 9 | **i18n Key-First** | All user-facing strings use `t('key')`. Keys are project-global. The compiler validates every key reference. |
| 10 | **Tailwind + CSS Variables** | Theming via CSS custom properties. Tailwind is the utility layer. Raw color values in templates are forbidden. |

---

## 3. Unified Data Model

### 3.1 The Schema Document (Single Source of Truth)

This is the master document. Everything — database tables, API endpoints, frontend stores, security rules — is derived from this single JSON schema.

```json
{
  "meta": {
    "project": "my-erp",
    "version": "1.0.0",
    "contracts": {
      "quantum_raw_v1": {
        "fingerprint": "quantum-raw-v1",
        "transport_profile": "cpp-core"
      }
    }
  },
  "schema": {
    "tables": [
      {
        "name": "invoices",
        "sqlName": "invoices",
        "fields": [
          { "name": "id", "columnName": "id", "type": "uuid", "primaryKey": true },
          { "name": "tenant_id", "columnName": "tenant_id", "type": "uuid", "references": { "table": "tenants", "column": "id" } },
          { "name": "customer_id", "columnName": "customer_id", "type": "uuid", "references": { "table": "customers", "column": "id" } },
          { "name": "total", "columnName": "total", "type": "decimal", "default": 0 },
          { "name": "status", "columnName": "status", "type": "text", "default": "draft" },
          { "name": "created_at", "columnName": "created_at", "type": "timestamptz" },
          { "name": "updated_at", "columnName": "updated_at", "type": "timestamptz" }
        ],
        "smart_features": {
          "display_field": "doc_no",
          "search_fields": ["doc_no", "status"],
          "is_translatable": false,
          "tree": null
        },
        "storage": {
          "live": true,
          "deep_paging": true,
          "window_days": 30,
          "top_n": 50
        },
        "access_rules": {
          "read": { "scope": "tenant", "field": "tenant_id" },
          "write": { "roles": ["admin", "accountant"] },
          "delete": { "roles": ["admin"] },
          "secret_fields": [],
          "locked": false
        }
      }
    ]
  }
}
```

### 3.2 What the Schema Generates

```
Schema Document (JSON)
  ├── PostgreSQL DDL (CREATE TABLE, indexes, constraints)
  ├── Frontend IndexedDB stores (keyPath, indexes)
  ├── API endpoints (/api/v1/{table})
  ├── Security middleware (access_rules enforcement)
  ├── CRUD operations (auto-generated)
  ├── WS live subscriptions (storage.live tables)
  ├── Deep paging queries (storage.deep_paging tables)
  ├── i18n translation tables ({table}_lang)
  └── Tree operations (smart_features.tree enabled tables)
```

### 3.3 Component Model (Frontend)

Every UI component is stored in the database with holistic retrieval:

```sql
-- MODULE: Feature boundary
CREATE TABLE module (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    sort_order  INT DEFAULT 0,
    meta        JSONB DEFAULT '{}'
);

-- COMPONENT: The atomic addressable unit
CREATE TABLE component (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'organism'
                CHECK (kind IN ('screen','organism','molecule','atom','kit')),
    lang        TEXT NOT NULL DEFAULT 'js',
    meta        JSONB DEFAULT '{}',
    UNIQUE(module_id, slug)
);

-- COMPONENT_CHILD: Composition
CREATE TABLE component_child (
    parent_id   UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    child_id    UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    slot        TEXT NOT NULL DEFAULT 'body',
    sort_order  INT DEFAULT 0,
    PRIMARY KEY (parent_id, child_id, slot)
);

-- PILLAR: The four separated concerns
CREATE TABLE pillar (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id    UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN ('schema','template','logic','style')),
    body            TEXT NOT NULL DEFAULT '',
    body_hash       TEXT GENERATED ALWAYS AS (md5(body)) STORED,
    line_count      INT GENERATED ALWAYS AS (
                        array_length(string_to_array(body, E'\n'), 1)
                    ) STORED,
    version         INT NOT NULL DEFAULT 1,
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, type)
);

-- SHARED FUNCTIONS & UTILS
CREATE TABLE shared_function (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID REFERENCES module(id) ON DELETE SET NULL,  -- NULL = project-global
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'util', -- 'util', 'helper', 'formatter', 'validator'
    lang        TEXT NOT NULL DEFAULT 'js',
    body        TEXT NOT NULL DEFAULT '',
    signature   TEXT,  -- e.g., '(items: Array, key: string) => object'
    description TEXT,
    UNIQUE(slug)
);

-- GLOBAL VARIABLES & CONSTANTS
CREATE TABLE global_var (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID REFERENCES module(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    value_type  TEXT NOT NULL DEFAULT 'string', -- 'string', 'number', 'object', 'array'
    value       TEXT NOT NULL,
    scope       TEXT NOT NULL DEFAULT 'project', -- 'project', 'module', 'screen'
    UNIQUE(name)
);

-- i18n: Project-global key registry
CREATE TABLE i18n_key (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    namespace   TEXT NOT NULL DEFAULT 'global',
    key_path    TEXT NOT NULL,
    meta        JSONB DEFAULT '{}',
    UNIQUE(namespace, key_path)
);

CREATE TABLE i18n_value (
    key_id      UUID NOT NULL REFERENCES i18n_key(id) ON DELETE CASCADE,
    lang_code   TEXT NOT NULL,
    value       TEXT NOT NULL,
    PRIMARY KEY (key_id, lang_code)
);

-- DESIGN TOKENS
CREATE TABLE design_token (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category    TEXT NOT NULL,
    name        TEXT NOT NULL,
    value       TEXT NOT NULL,
    theme       TEXT NOT NULL DEFAULT 'default',
    UNIQUE(category, name, theme)
);

-- MUTATION LOG
CREATE TABLE mutation_log (
    id          BIGSERIAL PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id   UUID NOT NULL,
    action      TEXT NOT NULL,
    before_hash TEXT,
    after_hash  TEXT,
    diff        JSONB,
    actor       TEXT DEFAULT 'ai',
    model       TEXT,
    ts          TIMESTAMPTZ DEFAULT now()
);

-- CHANGE LOG (for sync protocol)
CREATE TABLE change_log (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('insert', 'update', 'delete')),
    delta       JSONB,
    cursor_seq  BIGINT NOT NULL,
    tombstone   BOOLEAN DEFAULT false,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_changelog_cursor ON change_log(cursor_seq);
CREATE INDEX idx_changelog_table ON change_log(table_name, cursor_seq);
```

---

## 4. Backend Architecture

### 4.1 The C++ Core Engine

The deep ORM runs as a compiled C++ binary (inheriting from Quantum's `quantum-cpp`). It handles:

- **DDL Generation**: Schema JSON → `CREATE TABLE` statements
- **Query Builder**: Parameterized SQL with joins, filters, pagination, tree traversal
- **Schema Validation**: Validates records against the schema contract before write
- **Tree Operations**: Hierarchical data (chart of accounts, categories) with `parent_id` traversal
- **Migration Engine**: Diff two schema versions → generate `ALTER TABLE` statements

The C++ binary exposes a **stdio JSON protocol**:
```
→ {"op":"query","table":"invoices","filters":{"status":"draft"},"page":1,"limit":50}
← {"rows":[...],"total":142,"page":1,"pages":3}

→ {"op":"ddl","schema":{...}}
← {"sql":"CREATE TABLE invoices (...);","migrations":["ALTER TABLE ..."]}

→ {"op":"validate","table":"invoices","record":{...}}
← {"valid":true,"errors":[]}
```

### 4.2 Python Server (FastAPI)

The API server is a thin Python layer over the C++ core:

```
FastAPI Server
  ├── /api/v1/{table}           ← CRUD (delegates to C++ core)
  ├── /api/v1/{table}/{id}      ← Single record
  ├── /api/v1/schema            ← Schema introspection
  ├── /qdml/describe            ← AI protocol
  ├── /qdml/reveal              ← AI protocol
  ├── /qdml/mutate              ← AI protocol
  ├── /qdml/create              ← AI protocol
  ├── /qdml/compile             ← AI protocol
  ├── /qdml/search              ← AI protocol
  └── /ws/v3                    ← WebSocket (live sync)
```

### 4.3 Sync Protocol (Fixing MAS Store v3)

The current MAS Store v3 has two critical gaps:
1. **No delete propagation**: When a record is deleted on the backend, the frontend doesn't know.
2. **No authoritative change log**: The cursor system tracks sequence numbers but doesn't store a persistent log of what changed.

AI-First implements a **complete change-log**:

```
Backend Mutation
  ↓
  ├── Write to PostgreSQL table
  ├── Write to change_log (action: insert/update/delete)
  ├── If delete: set tombstone=true in change_log
  ├── Assign cursor_seq (monotonic)
  └── Broadcast to WS clients:
      {
        "type": "server:patch",
        "table": "invoices",
        "action": "delete",       ← NEW: explicit delete action
        "record": null,
        "recordRef": { "id": "uuid" },
        "cursor": { "sequence": 1542 },
        "tombstone": true          ← NEW: tombstone flag
      }

Client Reconnect
  ↓
  ├── Send lastCursors: { "invoices": 1500, "users": 1200 }
  ├── Server queries: SELECT * FROM change_log WHERE cursor_seq > $1
  ├── Server sends batch:
      {
        "type": "server:patch.batch",
        "patches": [
          { "table": "invoices", "action": "update", "record": {...} },
          { "table": "invoices", "action": "delete", "tombstone": true, "recordRef": {"id":"..."} }
        ]
      }
  └── Client applies: upserts AND deletes from IndexedDB
```

### 4.4 Security Rules Engine

Security is defined in the schema, not in application code:

```json
{
  "access_rules": {
    "read": {
      "scope": "tenant",           
      "field": "tenant_id"          
    },
    "write": {
      "roles": ["admin", "accountant"],
      "own_records": true,          
      "own_field": "created_by"     
    },
    "delete": {
      "roles": ["admin"]
    },
    "secret_fields": ["password_hash", "internal_notes"],
    "locked": false                 
  }
}
```

The runtime enforces these automatically:
- **Read scoping**: `SELECT * FROM invoices WHERE tenant_id = $user_tenant_id`
- **Role checking**: Before write/delete, verify the user's role matches
- **Field sanitization**: Secret fields are stripped from API responses
- **Table locking**: Locked tables reject all mutations

---

## 5. Frontend Architecture (Firebase-Like)

### 5.1 AI-First Store (Replacing MAS Store v3)

The frontend store is a thin reactive layer over IndexedDB, with complete sync:

```javascript
// The AI writes this in component logic. The store is auto-generated from schema.
const store = AIFirstStore.init({
  schema: projectSchema,  // Auto-loaded from /api/v1/schema
  ws: '/ws/v3',
  auth: { token, userId }
});

// Watch with full sync (inserts, updates, AND deletes)
store.watch('invoices', (rows, meta) => {
  // meta.action: 'snapshot' | 'upsert' | 'delete'
  // If delete: the row is ALREADY removed from `rows`
  ctx.setState({ invoices: rows });
}, { filters: { status: 'draft' } });

// CRUD
await store.save('invoices', { ...record });
await store.delete('invoices', recordId);

// Deep paging (non-live, historical data)
const page = await store.query('invoices', {
  live: false,
  page: 3,
  limit: 50,
  filters: { status: 'posted' },
  before: '2026-01-01'
});
```

### 5.2 Schema-Driven IndexedDB

The IndexedDB stores are auto-generated from the schema document:

```javascript
// Auto-generated from schema.tables
const dbConfig = {
  name: 'my-erp',
  version: schema.meta.version_int,
  stores: schema.tables.reduce((acc, table) => {
    acc[table.name] = {
      keyPath: 'id',
      indexes: table.fields
        .filter(f => f.references || f.type === 'uuid')
        .map(f => ({ name: f.columnName, keyPath: f.columnName }))
    };
    return acc;
  }, {})
};
```

---

## 6. The QDML Protocol (Enhanced)

### 6.1 Mini Code with Shared Functions & Global Variables

When the AI requests `describe`, it receives not only the component tree but also the shared function index and global variables:

```json
{
  "modules": [
    {
      "id": "mod-1", "name": "auth",
      "components": [
        { "id": "cmp-1", "name": "LoginScreen", "kind": "screen",
          "pillars": ["schema","template","logic"],
          "children": [
            { "id": "cmp-2", "name": "AuthInput", "kind": "atom" }
          ]
        }
      ]
    }
  ],
  "shared_functions": [
    { "id": "fn-1", "name": "formatCurrency", "signature": "(amount: number, currency: string) => string", "module": null },
    { "id": "fn-2", "name": "validatePhone", "signature": "(phone: string) => boolean", "module": "auth" }
  ],
  "global_vars": [
    { "name": "API_BASE", "type": "string", "scope": "project" },
    { "name": "SUPPORTED_LANGS", "type": "array", "scope": "project" }
  ],
  "i18n_namespaces": ["auth", "common", "errors"],
  "design_tokens": { "color": 12, "spacing": 8, "radius": 4 },
  "backend_schema_tables": ["users", "invoices", "products"]
}
```

The AI sees the **complete architecture** — frontend components, backend tables, shared utilities, and global configuration — in one blinded view before diving into any specific component.

### 6.2 Backend Table Awareness

When mutating a component, the AI also sees which backend tables are available. This enables the AI to wire up API calls correctly:

```json
// reveal response includes backend context
{
  "component": { "id": "cmp-1", "name": "InvoiceList", ... },
  "pillars": { ... },
  "connected_tables": [
    { "table": "invoices", "access": "read,write", "live": true },
    { "table": "customers", "access": "read", "live": false }
  ]
}
```

---

## 7. DevOps & Runtime

### 7.1 Dynamic File Generation

The system generates ALL infrastructure files from the database:

```
generate(project_id)
  ├── Dockerfile
  ├── docker-compose.yml
  ├── requirements.txt (Python deps)
  ├── package.json (Node deps for frontend)
  ├── tailwind.config.js (from design_token table)
  ├── index.css (CSS variables from design_token)
  ├── schema.sql (from schema document)
  ├── migrations/*.sql (from schema diffs)
  ├── src/server.py (FastAPI, auto-generated)
  └── dist/ (compiled frontend)
```

**These files are mirrors.** They are regenerated on every `generate` command. The database is always the source of truth.

### 7.2 Dev Observatory

Inspired by the Ant-Swarm platform, AI-First includes a built-in development observatory:

```
Dev Observatory
  ├── Project Status Dashboard
  │   ├── Component count, module count
  │   ├── Schema table count
  │   ├── Mutation log (recent changes)
  │   └── Change log (sync status)
  ├── Live Preview
  │   ├── Compile & serve on demand
  │   ├── Hot reload on DB change
  │   └── Multiple strategy preview (single-file, module-split)
  ├── Syntax Checker
  │   ├── Validate all pillar bodies on save
  │   ├── Check i18n key references
  │   ├── Validate template DSL
  │   └── Report errors back to AI
  ├── Test Runner
  │   ├── Playwright browser tests
  │   ├── API endpoint tests
  │   └── Schema validation tests
  └── AI Agent Interface
      ├── QDML command console
      ├── Mutation history viewer
      └── Rollback controls
```

### 7.3 Build Pipeline

```
Database Change
  → Syntax Check (validate pillars, i18n, schema)
  → Compile (DB → files via strategy)
  → Build (Tailwind purge, bundle)
  → Test (Playwright, API tests)
  → Report (errors → AI or human)
  → Deploy (Docker build & push)
```

### 7.4 Docker Generation

```dockerfile
# Auto-generated from database
FROM python:3.12-slim
COPY quantum-core /usr/local/bin/quantum-core
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY generated/ /app/
WORKDIR /app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## 8. AI Agent Architecture

### 8.1 Agent Roles

| Agent | Responsibility | Tools |
|-------|---------------|-------|
| **Architect** | Schema design, module structure, table relationships | `qdml/describe`, `qdml/create` |
| **Frontend** | Component pillars (template, logic, style) | `qdml/reveal`, `qdml/mutate` |
| **Backend** | Schema tables, access rules, API logic | `qdml/schema`, `qdml/mutate` |
| **QA** | Run tests, validate syntax, report errors | `test/run`, `check/syntax` |
| **DevOps** | Generate Docker, deploy, manage environments | `generate`, `deploy` |

### 8.2 Integration with Ant-Swarm

AI-First mounts as a **text API provider** on the Ant-Swarm platform:

```
Ant-Swarm
  ├── AI Provider (Gemini, Claude, etc.)
  │   └── Sends QDML commands via API text interface
  ├── Playwright Integration
  │   └── Tests the compiled frontend in a real browser
  └── AI-First QDML Server
      └── Receives commands, mutates DB, returns results
```

The Ant-Swarm API text interface provides:
1. **AI text generation**: The AI sends natural language → receives QDML commands
2. **Browser testing**: Playwright validates the compiled output
3. **Error feedback loop**: Syntax errors and test failures are fed back to the AI

---

## 9. Languages & Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Core Engine** | C++ (compiled binary) | Maximum performance for ORM, query building, schema validation, tree operations |
| **Backend Server** | Python (FastAPI) | Thin wrapper over C++ core. Simple, async, well-understood |
| **Frontend Framework** | MAS JS (our own) | Schema-driven, VDOM, `t()` i18n, `gkey` delegation |
| **Frontend Store** | AI-First Store (JS) | Firebase-like API, IndexedDB, WS sync with change-log |
| **Database** | PostgreSQL 16+ | JSONB, FTS, partitioning, concurrent access |
| **Styling** | Tailwind CSS + CSS Variables | AI-native utility classes, DB-driven theming |
| **Testing** | Playwright | Real browser testing, integrated with Ant-Swarm |
| **Deployment** | Docker + Linux | Auto-generated Dockerfiles, Linux target |

---

## 10. Execution Plan

### Phase 1: The Core (Week 1-2)
| Step | Task | Output |
|------|------|--------|
| 1 | Design the master schema document format (extend Quantum's contract) | `schema-contract.json` |
| 2 | Build C++ core engine: DDL generator + query builder + schema validator | `quantum-core` binary |
| 3 | Create PostgreSQL schema for component model (module, component, pillar, etc.) | `schema.sql` |
| 4 | Build Python FastAPI QDML server | `server.py` |
| 5 | Implement change_log table + sync protocol | Change-log with tombstones |

### Phase 2: Frontend Store (Week 2-3)
| Step | Task | Output |
|------|------|--------|
| 6 | Build AI-First Store (replaces MAS Store v3) | `ai-first-store.js` |
| 7 | Implement complete delta sync with delete propagation | WS v3 compatible |
| 8 | Build simple compiler (single-file strategy) | `compiler.py` |
| 9 | Seed a test project (2 modules, 5 components) | Working end-to-end demo |

### Phase 3: AI Integration (Week 3-4)
| Step | Task | Output |
|------|------|--------|
| 10 | Mount QDML as Ant-Swarm text API provider | API integration |
| 11 | Build syntax checker (pillar validation, i18n check) | `checker.py` |
| 12 | Integrate Playwright test runner | Browser test pipeline |
| 13 | Build Dev Observatory (status dashboard, live preview) | Web UI |

### Phase 4: First Real Project (Week 4+)
| Step | Task | Output |
|------|------|--------|
| 14 | AI builds a complete ERP module from scratch using AI-First | Proof of concept |
| 15 | Test full cycle: schema → DB → components → compile → test → deploy | End-to-end validation |
| 16 | Build Docker generation from DB | Auto-deployment |

---

## 11. Agreements & Decisions Log

| # | Decision | Status |
|---|----------|--------|
| 1 | Schema-first: one JSON document drives everything (DB, API, frontend, security) | ✅ Final |
| 2 | PostgreSQL only. One database per project. | ✅ Final |
| 3 | C++ core engine for ORM, query builder, DDL, tree operations | ✅ Final |
| 4 | Python (FastAPI) as the server wrapper | ✅ Final |
| 5 | Complete change-log with tombstones for delete propagation | ✅ Final |
| 6 | Security rules defined in schema, enforced by runtime | ✅ Final |
| 7 | Shared functions and global variables indexed in Mini Code | ✅ Final |
| 8 | Frontend module = backend module. Same ID, same source of truth | ✅ Final |
| 9 | Zero static files. Everything generated from DB | ✅ Final |
| 10 | Ant-Swarm integration for AI text API + Playwright testing | ✅ Final |
| 11 | Docker + Linux deployment. Dockerfiles auto-generated | ✅ Final |
| 12 | Dev Observatory: built-in dashboard, live preview, error reporting | ✅ Final |
| 13 | Tailwind CSS + CSS Variables for styling | ✅ Final |
| 14 | i18n key-first with `t()`. Compiler validates all key references | ✅ Final |
| 15 | Mutation log + change log: every change is tracked and reversible | ✅ Final |
