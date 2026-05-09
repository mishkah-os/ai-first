# AI-First Platform — Technical Specification

> **Document**: Platform Architecture  
> **Version**: 1.0 — 2026-05-09  
> **Scope**: The AI-First platform itself — the system that builds and manages projects

---

## 1. What is AI-First?

AI-First is a **development platform** — not an application. It is the system that creates, manages, and deploys other projects. Think of it as an IDE where the database is the filesystem and the AI is the developer.

AI-First itself needs to be built, deployed, and maintained. This document defines **how the platform itself is constructed**: its login system, dashboard, microservices, backend stack, and the infrastructure that powers everything.

### What AI-First is NOT

- It is **not** the projects it builds. The first project it will build is called **MAS-SYS** (documented separately).
- It is **not** a single monolith. It is a **microservice architecture** with clear language boundaries.

---

## 2. Platform Architecture — Microservices

AI-First is composed of **5 microservices**, each with a dedicated programming language chosen for its strengths:

```
┌─────────────────────────────────────────────────────────────┐
│                    AI-FIRST PLATFORM                        │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ Gateway  │  │  QDML    │  │ Compiler │  │  Quantum   │  │
│  │ (Python) │  │ (Python) │  │ (Python) │  │  Core(C++) │  │
│  │ FastAPI  │  │ FastAPI  │  │          │  │            │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └─────┬──────┘  │
│       │              │             │              │         │
│       └──────────────┴─────────────┴──────────────┘         │
│                          │                                  │
│                   ┌──────┴──────┐                           │
│                   │ PostgreSQL  │                           │
│                   │ (Platform)  │                           │
│                   └─────────────┘                           │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              WS Relay (Node.js)                      │   │
│  │         WebSocket live sync for frontends            │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           Frontend (MAS JS + Browser)                │   │
│  │     Login → Dashboard → Project Manager → QDML UI   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 Microservice Definitions

| # | Service | Language | Port | Responsibility |
|---|---------|----------|------|----------------|
| 1 | **Gateway** | Python (FastAPI) | 8000 | Auth, routing, REST API, project CRUD, user management |
| 2 | **QDML Server** | Python (FastAPI) | 8001 | AI protocol endpoints: describe, reveal, mutate, create, search |
| 3 | **Compiler** | Python | 8002 | DB → file compilation, syntax checking, build pipeline |
| 4 | **Quantum Core** | C++ (compiled binary) | stdio | ORM engine: DDL, query builder, schema validation, tree ops, migrations |
| 5 | **WS Relay** | Node.js | 8003 | WebSocket server for live sync (change-log → frontend), IndexedDB delta protocol |

### 2.2 Why These Languages?

| Language | Why | Where |
|----------|-----|-------|
| **C++** | Maximum performance for the ORM core. Query building, DDL generation, tree traversal, and schema validation must be fast. The existing `quantum-cpp` (1900 lines, 66KB) already proves this works. | Quantum Core binary |
| **Python** | Thin, readable wrappers. FastAPI is async, well-documented, and easy for AI to generate and modify. Perfect for orchestration, API routing, and compilation logic. | Gateway, QDML, Compiler |
| **Node.js** | WebSocket is native to Node. The existing `MAS Store v3` and `server.runtime.js` WebSocket infrastructure is proven. Node handles thousands of concurrent WS connections efficiently. | WS Relay |
| **MAS JS** | Our own frontend framework. Schema-driven, VDOM, `t()` i18n, `gkey` delegation. The platform's UI is built with the same framework it helps build. | Frontend |

### 2.3 Single Database Policy

**PostgreSQL is the only database.** No SQLite, no JSON files, no Redis (for now). Every microservice connects to the same PostgreSQL instance (or cluster). This is a non-negotiable decision:

- One ORM to master (Quantum Core)
- One query language (SQL)
- One backup strategy
- One migration tool
- One source of truth

---

## 3. Platform Database Schema

The platform itself has its own database (`ai_first_platform`) with these tables:

```sql
-- ============================================
-- AUTHENTICATION & AUTHORIZATION
-- ============================================

CREATE TABLE platform_user (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    display_name    TEXT NOT NULL,
    avatar_url      TEXT,
    is_active       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE platform_role (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT UNIQUE NOT NULL,   -- 'superadmin', 'admin', 'developer', 'viewer'
    label           TEXT NOT NULL,
    permissions     JSONB DEFAULT '[]',     -- ['project.create', 'project.delete', ...]
    is_system       BOOLEAN DEFAULT false,  -- system roles cannot be deleted
    created_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE user_role (
    user_id         UUID NOT NULL REFERENCES platform_user(id) ON DELETE CASCADE,
    role_id         UUID NOT NULL REFERENCES platform_role(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Seed the superadmin role
INSERT INTO platform_role (slug, label, permissions, is_system)
VALUES ('superadmin', 'Super Administrator', '["*"]', true);

-- ============================================
-- PROJECT MANAGEMENT
-- ============================================

CREATE TABLE project (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL,
    slug            TEXT UNIQUE NOT NULL,
    description     TEXT,
    db_name         TEXT UNIQUE NOT NULL,    -- PostgreSQL database name for this project
    db_created      BOOLEAN DEFAULT false,
    status          TEXT DEFAULT 'draft' CHECK (status IN ('draft','active','archived')),
    stack           JSONB DEFAULT '{}',      -- chosen stack: { frontend: "mas-js", backend: "python", ... }
    schema_doc      JSONB DEFAULT '{}',      -- the master schema document
    owner_id        UUID REFERENCES platform_user(id),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE project_member (
    project_id      UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    user_id         UUID NOT NULL REFERENCES platform_user(id) ON DELETE CASCADE,
    role            TEXT DEFAULT 'developer',
    PRIMARY KEY (project_id, user_id)
);

-- ============================================
-- SERVICE HEALTH & MONITORING
-- ============================================

CREATE TABLE service_check (
    id              BIGSERIAL PRIMARY KEY,
    service_name    TEXT NOT NULL,           -- 'postgresql', 'ant-swarm', 'ws-relay', 'compiler'
    status          TEXT NOT NULL,           -- 'ok', 'error', 'timeout'
    response_ms     INT,
    error_message   TEXT,
    checked_at      TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- AI SESSION TRACKING
-- ============================================

CREATE TABLE ai_session (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL,           -- 'gemini', 'claude', 'gpt'
    model           TEXT,
    status          TEXT DEFAULT 'active',
    commands_count  INT DEFAULT 0,
    started_at      TIMESTAMPTZ DEFAULT now(),
    ended_at        TIMESTAMPTZ
);

CREATE TABLE ai_command_log (
    id              BIGSERIAL PRIMARY KEY,
    session_id      UUID NOT NULL REFERENCES ai_session(id) ON DELETE CASCADE,
    endpoint        TEXT NOT NULL,           -- 'describe', 'reveal', 'mutate', 'create'
    request         JSONB,
    response        JSONB,
    duration_ms     INT,
    success         BOOLEAN DEFAULT true,
    ts              TIMESTAMPTZ DEFAULT now()
);
```

---

## 4. Login System & Permissions

### 4.1 Authentication Flow

```
Browser (MAS JS)
  │
  ├── POST /api/auth/login  { email, password }
  │     └── Gateway validates credentials
  │     └── Returns JWT token + user profile + roles
  │
  ├── GET /api/auth/me  (with JWT header)
  │     └── Returns current user + permissions
  │
  └── POST /api/auth/refresh  (with refresh token)
        └── Returns new JWT
```

### 4.2 Role-Based Access Control (RBAC)

| Role | Permissions | Description |
|------|------------|-------------|
| **superadmin** | `*` (everything) | Full platform control. First user created at bootstrap. |
| **admin** | `project.*`, `user.read`, `user.invite` | Can create/manage projects, invite users |
| **developer** | `project.read`, `project.edit`, `qdml.*` | Can work on assigned projects |
| **viewer** | `project.read` | Read-only access |

### 4.3 First Boot (Bootstrap)

On first launch with an empty database, the platform:
1. Runs migrations to create all tables
2. Seeds the `superadmin` role
3. Prompts for superadmin credentials via CLI or first-visit setup page
4. Creates the first user with `superadmin` role
5. All subsequent users are invited by superadmin

---

## 5. Dashboard (Post-Login)

After login, the superadmin sees the **Dev Observatory Dashboard** built as a MAS JS `dashboard-kit` module:

### 5.1 Dashboard Sections

```
Dashboard
  ├── [1] Service Health Panel
  │     ├── PostgreSQL ────── ● Connected (12ms)
  │     ├── Ant-Swarm API ─── ● Connected (45ms)
  │     ├── WS Relay ──────── ● Running (port 8003)
  │     ├── Compiler ──────── ● Ready
  │     └── Quantum Core ──── ● Binary found (v2.1)
  │
  ├── [2] Projects Panel
  │     ├── Active projects list
  │     ├── [+ New Project] button → AI-guided wizard
  │     └── Per-project: status, component count, last mutation
  │
  ├── [3] AI Activity Feed
  │     ├── Recent QDML commands across all projects
  │     ├── Success/failure rate
  │     └── Active AI sessions
  │
  └── [4] System Info
        ├── Platform version
        ├── Database size
        ├── Connected users
        └── Uptime
```

### 5.2 Service Health Check API

```
GET /api/health/all

Response:
{
  "services": [
    {
      "name": "postgresql",
      "status": "ok",
      "latency_ms": 12,
      "details": { "version": "16.2", "databases": 3 }
    },
    {
      "name": "ant-swarm",
      "status": "ok",
      "latency_ms": 45,
      "details": { "providers": ["gemini", "claude"], "active_sessions": 2 }
    },
    {
      "name": "ws-relay",
      "status": "ok",
      "latency_ms": 3,
      "details": { "connections": 5, "port": 8003 }
    },
    {
      "name": "quantum-core",
      "status": "ok",
      "details": { "binary": "/usr/local/bin/quantum-core", "version": "2.1" }
    }
  ],
  "overall": "ok",
  "checked_at": "2026-05-09T12:00:00Z"
}
```

---

## 6. New Project Creation Flow

When the superadmin clicks **[+ New Project]**, an AI-guided wizard runs:

```
Step 1: Project Identity
  ├── Name: "My ERP System"
  ├── Slug: "my-erp" (auto-generated, editable)
  └── Description: (optional)

Step 2: AI Consultation
  ├── User describes what they want (natural language)
  ├── AI (via Ant-Swarm) analyzes requirements
  ├── AI proposes:
  │     ├── Schema tables needed
  │     ├── Module structure
  │     ├── Suggested components
  │     └── Recommended stack options
  └── User reviews and approves

Step 3: Database Creation
  ├── Platform creates PostgreSQL database: "aif_my_erp"
  ├── Runs component model schema (module, component, pillar, etc.)
  ├── Runs project schema (tables proposed by AI)
  ├── Seeds i18n keys, design tokens
  └── Marks project as 'active'

Step 4: First Components
  ├── AI generates initial module structure
  ├── Creates login screen, dashboard, first CRUD screen
  ├── Compiles and serves preview
  └── User can iterate via QDML
```

---

## 7. Legacy Systems — Deep Technical Analysis

### 7.1 OS System (`d:\git\os`) — What It Is Today

The OS system is a **hybrid WebSocket/REST server** built in Node.js. Here is exactly what it does:

**Server Runtime** (`server.runtime.js` — 800+ lines):
- Creates an HTTP + WebSocket server on a single port
- Maintains a `SchemaEngine` that loads JSON schema files from disk
- Implements a `CrudEngine` with `read`, `save`, `delete` operations against SQLite
- Has a `PubsubManager` that broadcasts changes to connected WS clients
- Supports `branch/module isolation` — each module has its own data scope
- Uses `SECRET_FIELD_MAP` and `LOCKED_TABLE_SET` for security (hardcoded in config)
- Implements `sanitizeRecordForClient()` to strip sensitive fields before sending

**MAS Store v3** (`mas-store-v3.js` — 2000+ lines):
- Frontend IndexedDB abstraction with WS sync
- `flushOutbox()` — queues mutations when offline, flushes on reconnect
- `applyRemoteDelta()` — applies server patches to local IndexedDB
- Cursor-based reconnect: sends `lastCursor` on reconnect, server replays missed patches
- **In-memory buffer only** — no persistent change log on server

**What Works:**
- The WS delta sync protocol is elegant and proven in production
- IndexedDB caching provides true offline-first capability
- The outbox queue handles network failures gracefully
- Branch/module isolation is a clean security boundary

**What Fails:**
1. **No delete propagation.** When `applyRemoteDelta()` receives a patch, it only handles upserts. If a record was deleted on the server while the client was offline, the client never knows. The deleted record stays in IndexedDB forever.
2. **In-memory cursor buffer.** The server stores recent patches in an array with a hard limit (default 1000). If the client was offline longer than the buffer window, it misses changes permanently.
3. **SQLite/JSON storage.** The data store is a mix of SQLite databases and JSON files on disk. No JSONB queries, no FTS, no concurrent writes.
4. **Security is config-based, not schema-based.** `SECRET_FIELD_MAP` is a hardcoded object. Adding a new secret field requires editing server code.
5. **No ORM.** The CrudEngine builds SQL strings manually. No parameterized queries, no type normalization, no reference resolution.

### 7.2 Quantum System (`d:\git\ai-auto`) — What It Is Today

Quantum is a **schema-driven PostgreSQL ORM** with a C++ performance core. Here is exactly what it does:

**Schema Contract** (`schema-contract.js` — 500 lines):
- Reads a master JSON schema file (`accounting_core_schema_v1.json`)
- Normalizes every table: ensures `fields`, `smart_features`, `columnName` consistency
- Derives `display_field` automatically (searches for `name`, `title`, `label_text`, etc.)
- Derives `search_fields` from `is_searchable` columns
- Detects translation tables (`_lang`, `_tr` suffixes) and links them
- Validates the entire schema: checks for duplicates, missing references, tree consistency
- Stamps every table with `quantum_raw_v1` contract fingerprint

**PostgreSQL ORM** (`postgres.js` — 1164 lines):
- Full parameterized query builder with `$1`, `$2` placeholders
- Column alias mapping: `company_id` → `tenant_id`, `begin_date` → `created_at`
- Filter builder: supports `=`, `!=`, `BETWEEN`, `IN`, `LIKE`, `ILIKE`, `IS NULL`
- Reference search: `EXISTS (SELECT 1 FROM referenced_table WHERE ...)` for FK lookups
- Auto-injection: `tenant_id`, `created_at`, `updated_at`, `created_by`, `public_id`
- Batch upsert: `INSERT ... ON CONFLICT DO UPDATE`
- Stored procedure/function executor: introspects `pg_catalog.pg_proc` to find overloads

**C++ Core** (`quantum-cpp/main.cpp` — 1899 lines):
- Full reimplementation of `postgres.js` in C++ using `libpq`
- Direct PostgreSQL connection (no Node.js overhead)
- Socket-based JSON protocol: receives JSON on TCP, returns JSON
- Handles: `read`, `save`, `delete`, `routine` (stored procedures)
- Reference map loading for display labels on FK columns
- Connection pooling (single persistent connection with reconnect)

**Server** (`server.js` — 786 lines):
- HTTP server with document-oriented API (not generic CRUD)
- Document profiles: auto-generates form layouts from schema
- Document workflow: draft → finalize lifecycle
- Auth service with JWT
- Platform service with multi-tenant signup
- Legacy v7 API compatibility layer

**What Works:**
- The schema contract model is excellent — one JSON file describes everything
- `smart_features` per table (display_field, search_fields, tree, translation) is powerful
- The C++ core delivers real performance gains for heavy queries
- Column alias mapping handles legacy field names gracefully
- The document profile system auto-generates UI from schema

**What Fails:**
1. **Separate from OS.** Quantum and OS are two independent systems. They don't share a database, a sync protocol, or a schema format. A project using OS for live data and Quantum for deep data has two codebases to maintain.
2. **No WebSocket.** Quantum is HTTP-only. No live sync, no real-time updates. The frontend must poll or use OS for live data.
3. **No change log.** Like OS, there's no persistent record of what changed. The C++ core executes `DELETE` and the record is gone — no tombstone, no event.
4. **File-based schema.** The schema lives in a JSON file on disk. To modify the schema, you edit a file and restart the server. No runtime schema mutations.
5. **No component model.** Quantum manages data tables, not UI components. There's no concept of "a login form has template + logic + style."

### 7.3 How AI-First Unifies Everything

| Problem | OS Solution | Quantum Solution | AI-First Solution |
|---------|-------------|------------------|-------------------|
| Data storage | SQLite + JSON files | PostgreSQL | **PostgreSQL only** (unified) |
| Schema definition | JSON config files on disk | JSON schema file | **Schema in database** (runtime-mutable) |
| ORM | Manual SQL strings | Parameterized builder (JS + C++) | **Quantum Core C++** (single engine) |
| Live sync | WS delta + IndexedDB | None (HTTP only) | **WS Relay + change_log table** (persistent) |
| Delete propagation | Broken (upsert only) | No sync at all | **Tombstones in change_log** |
| Security rules | Hardcoded config maps | Hardcoded in server | **Schema-defined access_rules** |
| Component model | None | None | **4-pillar DB model** (schema, template, logic, style) |
| AI interaction | File-based Track3 | None | **QDML protocol** (DB-native) |

**The key insight: AI-First takes the best of both systems and eliminates the split.**

- From OS: the WebSocket delta sync protocol, IndexedDB caching, outbox queue, branch isolation
- From Quantum: the schema contract, smart_features, C++ core engine, parameterized ORM
- New in AI-First: persistent change_log with tombstones, schema-defined security, 4-pillar component model, QDML AI protocol

---

## 8. Communication Between Microservices

```
Frontend (MAS JS, browser)
  │
  ├── HTTP REST ──→ Gateway (Python :8000)
  │                    ├── Auth endpoints
  │                    ├── Project CRUD
  │                    ├── Health checks
  │                    └── Proxies to QDML/Compiler when needed
  │
  ├── HTTP REST ──→ QDML Server (Python :8001)
  │                    ├── /qdml/describe
  │                    ├── /qdml/reveal
  │                    ├── /qdml/mutate
  │                    ├── /qdml/create
  │                    └── Calls Quantum Core via stdio pipe
  │
  ├── HTTP REST ──→ Compiler (Python :8002)
  │                    ├── /compile/{project_id}
  │                    ├── /check/syntax
  │                    └── /generate/files
  │
  └── WebSocket ──→ WS Relay (Node.js :8003)
                       ├── Live change_log streaming
                       ├── Cursor-based reconnect replay
                       └── IndexedDB delta sync
```

**Quantum Core** is not a network service. It's a **stdio process**:
- QDML Server spawns `quantum-core` binary as a child process
- Sends JSON via stdin, reads JSON from stdout
- One persistent process per project (connection pooled)

---

## 9. Deployment — Docker Compose

```yaml
# docker-compose.yml for AI-First Platform
version: '3.9'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: aifirst
      POSTGRES_PASSWORD: ${PG_PASSWORD}
      POSTGRES_DB: ai_first_platform
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  gateway:
    build: ./services/gateway
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql://aifirst:${PG_PASSWORD}@postgres:5432/ai_first_platform
      JWT_SECRET: ${JWT_SECRET}
    depends_on:
      - postgres

  qdml:
    build: ./services/qdml
    ports:
      - "8001:8001"
    environment:
      DATABASE_URL: postgresql://aifirst:${PG_PASSWORD}@postgres:5432/ai_first_platform
      QUANTUM_CORE_BIN: /usr/local/bin/quantum-core
    depends_on:
      - postgres

  compiler:
    build: ./services/compiler
    ports:
      - "8002:8002"
    environment:
      DATABASE_URL: postgresql://aifirst:${PG_PASSWORD}@postgres:5432/ai_first_platform
    depends_on:
      - postgres

  ws-relay:
    build: ./services/ws-relay
    ports:
      - "8003:8003"
    environment:
      DATABASE_URL: postgresql://aifirst:${PG_PASSWORD}@postgres:5432/ai_first_platform
    depends_on:
      - postgres

  frontend:
    build: ./services/frontend
    ports:
      - "3000:3000"
    depends_on:
      - gateway

volumes:
  pgdata:
```

---

## 10. Project Directory Structure

```
d:\git\ai-first\
  ├── doc/
  │     ├── ai-first-platform.md      ← This document
  │     ├── mas-sys-product.md         ← First product spec
  │     ├── foundation.md             ← Core architecture (data model, QDML)
  │     └── foundation-ar.md          ← Arabic translation
  │
  ├── services/
  │     ├── gateway/                   ← Python FastAPI (auth, projects, health)
  │     │     ├── Dockerfile
  │     │     ├── requirements.txt
  │     │     ├── main.py
  │     │     ├── auth.py
  │     │     ├── projects.py
  │     │     └── health.py
  │     │
  │     ├── qdml/                      ← Python FastAPI (AI protocol)
  │     │     ├── Dockerfile
  │     │     ├── main.py
  │     │     ├── describe.py
  │     │     ├── reveal.py
  │     │     ├── mutate.py
  │     │     └── quantum_bridge.py    ← stdio interface to C++ binary
  │     │
  │     ├── compiler/                  ← Python (DB → files)
  │     │     ├── Dockerfile
  │     │     ├── main.py
  │     │     ├── strategies/
  │     │     │     ├── single_file.py
  │     │     │     └── module_split.py
  │     │     └── checker.py
  │     │
  │     ├── ws-relay/                  ← Node.js WebSocket
  │     │     ├── Dockerfile
  │     │     ├── package.json
  │     │     ├── server.js
  │     │     └── changelog.js
  │     │
  │     ├── quantum-core/              ← C++ binary
  │     │     ├── Makefile
  │     │     ├── main.cpp
  │     │     └── build/
  │     │
  │     └── frontend/                  ← MAS JS application
  │           ├── Dockerfile
  │           ├── index.html
  │           ├── lib/
  │           │     ├── mas.core.js
  │           │     └── ai-first-store.js
  │           └── modules/
  │                 ├── auth/          ← Login, register, profile
  │                 ├── dashboard/     ← Dashboard kit module
  │                 └── project/       ← Project management screens
  │
  └── docker-compose.yml
```

---

## 11. Project Standardization — One Stack, Zero Exceptions

Every project created by AI-First **must** follow the same technology stack, the same patterns, the same libraries. There is no "choose your framework" step. The AI doesn't decide between React and Vue. The stack is fixed:

### 11.1 The Mandatory Stack

| Layer | Technology | Library | Non-Negotiable |
|-------|-----------|---------|----------------|
| **Frontend Framework** | MAS JS | `mas.core.js` | VDOM, `t()` i18n, `gkey` delegation, `orders` mutations |
| **Frontend Store** | MAS Store | `ai-first-store.js` | IndexedDB, WS sync, change-log with tombstones, offline outbox |
| **Frontend Styling** | Tailwind + CSS Vars | CSS custom properties only | No raw colors. All theming via `design_token` table |
| **UI Components** | MAS UI Kit | Pre-built atoms/molecules | Button, Input, Select, Table, Modal, Toast, Tree — all from kit |
| **Backend ORM** | Quantum Core | C++ binary via stdio | Parameterized SQL, schema validation, DDL, tree ops |
| **Backend API** | Python FastAPI | Auto-generated from schema | CRUD endpoints, access_rules enforcement |
| **Real-time Sync** | WS Relay | Node.js WebSocket | change_log streaming, cursor replay, tombstones |
| **Database** | PostgreSQL 16+ | One DB per project | JSONB, FTS, partitioning |
| **i18n** | Key-first `t()` | i18n_key + i18n_value tables | Every user-facing string uses `t('key')`. No exceptions. |
| **Testing** | Playwright | Browser automation | Integrated with Ant-Swarm for AI feedback loop |

### 11.2 What the AI Gets for Free

When the AI creates a new project, these are **already available** without writing a single line:

```
New Project Created
  │
  ├── MAS JS loaded (VDOM, state, delegation, i18n)
  ├── MAS Store connected (WS, IndexedDB, sync protocol)
  ├── MAS UI Kit available:
  │     ├── MasButton, MasInput, MasSelect
  │     ├── MasTable (sortable, paginated, schema-driven)
  │     ├── MasModal, MasToast, MasConfirm
  │     ├── MasTree (hierarchical data, from smart_features.tree)
  │     ├── MasForm (auto-generated from schema fields)
  │     └── MasNav, MasSidebar, MasTabs
  ├── Auth module (login, session, JWT) — pre-built
  ├── Dashboard kit (health panel, stats, activity feed)
  ├── CRUD generator (schema table → full list/form/detail screen)
  └── Design tokens loaded (colors, spacing, typography from DB)
```

The AI's job is to **compose and customize**, not reinvent. It takes pre-built components, wires them to schema tables, adds business logic, and customizes the UI.

### 11.3 The MAS DSL Contract

Every component follows the exact same MAS DSL structure:

```javascript
// Every component the AI creates follows this pattern. No variation.
MAS.module('invoice-list', {
  // Pillar 1: Schema (state definition)
  db: {
    invoices: [],
    loading: true,
    filters: { status: 'draft' },
    selected: null
  },

  // Pillar 2: Logic (event handlers via orders)
  orders: {
    load: async (ctx) => {
      ctx.db.loading = true;
      ctx.db.invoices = await store.query('invoices', ctx.db.filters);
      ctx.db.loading = false;
    },
    select: (ctx, row) => {
      ctx.db.selected = row;
    },
    delete: async (ctx, id) => {
      await store.delete('invoices', id);
      // Store handles WS sync + change_log automatically
    }
  },

  // Pillar 3: Template (MAS DSL VDOM)
  body: (ctx) => [
    'div.invoice-list', {},
    ['MasTable', {
      data: ctx.db.invoices,
      columns: ctx.schema.invoices.fields,  // Schema-driven columns
      loading: ctx.db.loading,
      onRowClick: (row) => ctx.order('select', row),
      onDelete: (id) => ctx.order('delete', id)
    }]
  ],

  // Pillar 4: Style (Tailwind + CSS vars only)
  style: `
    .invoice-list { @apply p-4 space-y-4; }
  `
});
```

### 11.4 Why Fixed Stack Matters

1. **The AI learns ONE pattern.** Not 50 frameworks. Every component has the same structure: `db`, `orders`, `body`, `style`. The AI's QDML mutations are always the same shape.
2. **Components are interchangeable.** A table built for invoices works identically for users. The schema drives the differences, not the code.
3. **Pre-built kit eliminates 80% of work.** The AI doesn't write a `<button>` — it uses `MasButton`. It doesn't write a `<table>` — it uses `MasTable` with schema columns.
4. **Onboarding is instant.** A new developer (human or AI) opening any project knows exactly where everything is and how it works.

---

## 12. Self-Hosting Decision — Versioned Dogfooding

### 12.1 The Question

Can AI-First manage itself? Can it treat its own codebase as a project and upgrade itself via QDML?

### 12.2 The Answer: Option C — Versioned Dogfooding

**AI-First is built with its own technology stack, CAN develop its next version as a project, but NEVER modifies itself while running.**

```
┌─────────────────────────────────┐
│  AI-First v1.0 (RUNNING)       │
│  ├── Built with: MAS JS        │
│  ├── Backend: Python + C++     │
│  ├── Database: PostgreSQL      │
│  │                              │
│  ├── Project: "mas-sys"         │  ← Normal product project
│  ├── Project: "client-erp"     │  ← Another product
│  └── Project: "ai-first-v2"   │  ← AI develops v2 HERE
│        │                        │
│        ├── AI writes components │
│        ├── AI modifies schema   │
│        ├── Compiler generates   │
│        └── Playwright tests     │
└─────────────┬───────────────────┘
              │
              │  When v2 is ready:
              │  Deploy as NEW instance
              ▼
┌─────────────────────────────────┐
│  AI-First v2.0 (NEW INSTANCE)  │
│  ├── Improved dashboard        │
│  ├── Better QDML protocol      │
│  └── New features              │
└─────────────────────────────────┘
```

### 12.3 Why Not Full Self-Hosting?

| Risk | Description |
|------|-------------|
| **Chicken-and-egg** | If AI-First mutates itself and breaks, it cannot fix itself because it's broken |
| **Runtime corruption** | Modifying running code is dangerous. A bad pillar mutation could crash the QDML server |
| **No rollback** | If the running instance is the only instance, there's no safe fallback |
| **Testing gap** | You can't properly test changes to the platform while using the platform to test |

### 12.4 Why Versioned Dogfooding Works

| Benefit | Description |
|---------|-------------|
| **Same stack** | AI-First v1 is built with MAS JS + PostgreSQL + the same patterns. We eat our own food. |
| **Safe iteration** | v2 is a separate project in a separate database. Break it all you want — v1 keeps running |
| **AI-driven upgrades** | The AI literally builds the next version of the platform using the current version. Recursive improvement. |
| **Full testing** | v2 can be compiled, deployed to staging, tested with Playwright, validated — then promoted |
| **Clean versioning** | Each major version is a clean deployment. No accumulated cruft from live patching |

### 12.5 What This Means Practically

1. **AI-First v1.0** is built by humans (us) using MAS JS + Python + C++ + PostgreSQL
2. Inside v1.0, we create a project called `ai-first-v2`
3. The AI develops v2's components, schema, and logic using QDML
4. The compiler generates v2's files
5. We deploy v2 as a separate Docker stack
6. v2 becomes the active platform
7. Repeat: v2 creates project `ai-first-v3`...

**The platform improves itself recursively, safely, without ever risking the running instance.**
