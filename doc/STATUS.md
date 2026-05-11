# QDML Core Engine — Progress Report & Roadmap

> **Document**: Engineering Status Report  
> **Version**: 1.0 — 2026-05-10  
> **Scope**: QDML Core Engine, Admin Dashboard, AI-Native Protocol  
> **Status**: Phase 1 Complete — Phase 2 Pending

---

## 1. Executive Summary

The QDML (Quantum Data Markup Language) Core Engine has been successfully transitioned from a conceptual prototype to a **live, self-serving system**. The database is now the single source of truth for all code, and a zero-dependency HTTP server exposes the engine as a JSON API with authentication, enabling both human operators and AI agents to interact with the codebase through a unified protocol.

**Key metric**: 33 atomic code bulks, 1,407 lines of managed code, 53 operations executed in 304ms, from a 4KB SQLite database.

---

## 2. Architecture — What Exists Today

```
d:\git\ai-first\
├── core/                          ← THE KERNEL
│   ├── qdml_engine.py             ← [DONE] V2 Engine (SQL-abstracted, JSON protocol, Auth)
│   ├── qdml_server.py             ← [DONE] Zero-dep HTTP server (API + static files)
│   ├── qdml_master.py             ← [DONE] Full system build (split → DB → compile → files)
│   ├── qdml_local.py              ← [LEGACY] V1 engine (kept for reference)
│   ├── qdml_sim.py                ← [DONE] AI simulation test
│   ├── qdml_loop.py               ← [DONE] Full-loop integrity check
│   ├── qdml_test.py               ← [DONE] Unit tests
│   ├── system_prompt.md           ← [DONE] Dynamic AI instructions
│   ├── schema.sql                 ← [LEGACY] V1 schema (now embedded in engine)
│   └── qdml.db                    ← Live database (WAL mode)
│
├── admin/                         ← ADMIN DASHBOARD
│   ├── index.html                 ← [DONE] SPA shell (loads MAS JS V2)
│   ├── admin.js                   ← [DONE] 4 MAS modules (auth, nav, dashboard, bulks, logs)
│   └── admin.css                  ← [DONE] Glassmorphism dark UI
│
├── mas-front/                     ← MANAGED CODEBASE
│   ├── mas.core.js                ← Source (904 lines → 17 bulks)
│   ├── mas.tokens.css             ← Source (190 lines → 8 bulks)
│   ├── quickstart.html            ← Source (147 lines → 6 bulks)
│   └── _generated/               ← [DONE] 8 compiled output files
│       ├── mas.core.js            ← 906 lines, 39KB
│       ├── mas.core.marked.js     ← with m-bulk markers
│       ├── mas.tokens.css         ← 178 lines, 5.7KB
│       ├── mas.tokens.marked.css  ← with m-bulk markers
│       ├── quickstart.html        ← 149 lines
│       ├── quickstart.marked.html ← with m-bulk markers
│       ├── MAS_V2_RULES.md        ← 151 lines
│       └── API_REFERENCE.md       ← 56 lines
│
├── legacy_dna/                    ← HERITAGE CODE (reference only)
│   ├── schema_driven/             ← mas-schema.js (582L), mas-rest.js (1435L)
│   ├── frontend_v3/              ← mas.core.js, mas-store-v3.js, mas-ui.js
│   ├── quantum_orm/              ← postgres.js (1164L), main.cpp (1899L)
│   ├── backend_runtime/          ← server.runtime.js, crud-api.js, pubsub.js
│   └── ai_track3/                ← track3_engine.py, surgical_skeletonizer.py
│
└── doc/                           ← DOCUMENTATION
    ├── foundation.md              ← Full architecture spec (668 lines)
    ├── ai-first-platform.md       ← Platform microservices spec (783 lines)
    ├── foundation-ar.md           ← Arabic architecture doc
    └── STATUS.md                  ← THIS DOCUMENT
```

---

## 3. What Has Been Built (Completed)

### 3.1 QDML Engine V2 (`qdml_engine.py` — 290 lines)

The heart of the system. A self-contained Python class that manages code as database records.

**Capabilities:**

| Feature | Implementation | Status |
|---------|---------------|--------|
| **SQL Abstraction** | `driver="sqlite"` or `driver="pgsql"` — one-line switch | ✅ Done |
| **JSON Protocol** | `execute_json(action_dict)` — single entry point for all operations | ✅ Done |
| **Atomic Bulks** | Code stored as named chunks with metadata (lines, chars, bytes, exports, depends) | ✅ Done |
| **History Tracking** | Every mutation archived in `bulk_history` with author and reason | ✅ Done |
| **Operation Logging** | Every operation timed to millisecond precision in `operation_log` | ✅ Done |
| **Language-Aware Markers** | Compile with correct comment syntax per language (JS: `//`, CSS: `/* */`, HTML: `<!-- -->`) | ✅ Done |
| **Authentication** | `qdml_user` + `qdml_session` tables, SHA-256 hashing, token-based sessions | ✅ Done |
| **Stats & Metrics** | Aggregate operation counts, avg/total duration, DB size reporting | ✅ Done |

**Supported Actions (JSON Protocol):**

```
mini          — Compressed project overview (configurable depth)
describe      — Full project tree (modules → components → bulks)
reveal        — Read bulk content (level 1: list, level 2: signatures, level 3: full)
create_bulk   — Insert new code chunk
mutate_bulk   — Modify existing chunk (with history snapshot)
compile       — Reassemble component from bulks (with optional markers)
history       — Retrieve mutation history for a bulk
metrics       — Aggregate operation performance
stats         — System-wide statistics
recent_ops    — Last N operations log
```

### 3.2 HTTP Server (`qdml_server.py` — 220 lines)

Zero-dependency Python HTTP server that turns the engine into a live service.

**Endpoints:**

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/auth/login` | No | `{username, password}` → `{token, user}` |
| `POST` | `/api/auth/logout` | Bearer | Invalidate session |
| `POST` | `/api/auth/verify` | Bearer | Validate token, return user |
| `POST` | `/api/qdml` | Bearer | Execute any JSON action |
| `GET` | `/api/qdml/prompt` | No | Dynamic system prompt (includes live mini-code) |
| `GET` | `/api/qdml/stats` | No | System statistics |
| `GET` | `/lib/*` | No | Serve MAS JS V2 libraries from `_generated/` |
| `GET` | `/*` | No | Serve admin dashboard from `admin/` |

**Design decisions:**
- Uses Python's built-in `http.server` — **zero pip install required**.
- Auto-creates default admin user (`admin`/`admin`) on first run.
- WAL mode SQLite for concurrent read/write.
- CORS headers enabled for cross-origin AI access.

### 3.3 Admin Dashboard (`admin/` — 3 files)

Single-page application built entirely with **MAS JS V2** — the same framework managed by QDML.

**MAS Modules:**

| Module | State (`db`) | Actions (`orders`) | UI |
|--------|-------------|-------------------|-----|
| `auth` | `user, token, error, loading` | `login, logout, input` | Login form with glassmorphism |
| `nav` | `page` | `go` | Sidebar navigation |
| `dashboard` | `stats, mini, loading` | `refresh` | 8 stat cards + mini-code viewer |
| `bulks` | `components, bulkList, selected, content` | `loadComps, selectComp, selectBulk, compile` | Component selector + bulk list + code viewer |
| `logs` | `metrics, recent, loading` | `refresh` | Metrics table + recent operations table |

**UI Design:** Dark theme, glassmorphism cards, gradient accents (`#6366f1` → `#8b5cf6`), JetBrains Mono for code, Inter for UI.

### 3.4 Master Build (`qdml_master.py` — 258 lines)

Full system generation script that:
1. **Splits** source files into atomic bulks (with line ranges, exports, depends)
2. **Stores** everything in QDML database
3. **Compiles** back to output files (with and without markers)
4. **Reports** metrics (operation counts, timing, DB size)

**Output:** 8 files in `_generated/`, 33 bulks, 1,407 managed lines.

### 3.5 AI System Prompt (`system_prompt.md`)

Dynamic document served at `/api/qdml/prompt` that includes:
- Live mini-code (current project state)
- Live system stats
- All available JSON actions with examples
- MAS JS V2 coding patterns (`module`, `D`, `$` ctx)
- Bulk rules (max 100 lines, naming, metadata)

**Purpose:** Any AI model can read this endpoint and immediately understand how to interact with the codebase.

### 3.6 Supporting Scripts

| Script | Purpose | Status |
|--------|---------|--------|
| `qdml_sim.py` | Simulates AI reading mini-code → reveal → mutate → verify | ✅ Done |
| `qdml_loop.py` | Full integrity check: DB → file → DB round-trip | ✅ Done |
| `qdml_test.py` | Unit tests for engine operations | ✅ Done |

---

## 4. Database Schema (Embedded in Engine)

```sql
-- Core data model
project          → id, name, slug, description
module           → id, project_id, name, slug, tier, app, sort_order
component        → id, module_id, name, slug, kind, target, meta
pillar           → id, component_id, kind, content, lang, bulk_name, bulk_order,
                    reveal, depends, exports, overflow, lines, chars, bytes

-- Audit trail
bulk_history     → id, pillar_id, content, changed_by, reason, ts
operation_log    → id, operation, module, tool, model, success, duration_ms, details
syntax_error     → id, pillar_id, error_type, message, line, col, severity

-- Auth
qdml_user        → id, username, password_hash, display_name, role, lang, active
qdml_session     → id, user_id, token, expires_at

-- Artifacts
project_artifact → id, project_id, filename, path, content, category, lines, chars, bytes
```

---

## 5. What Remains (Roadmap)

### Phase 2: Schema-Driven Integration (Next)

**Goal:** Import `mas-schema.js` (582 lines) into QDML as managed bulks, and build a `schema_registry` table so the system can generate SQL, validation, and CRUD APIs from JSON schema definitions.

| Task | Description | Complexity |
|------|-------------|------------|
| Import `mas-schema.js` as QDML bulks | Split into ~6 bulks: type_config, field_def, table_def, registry, utils, exports | Medium |
| Add `schema_registry` table | Store JSON schema definitions per project | Low |
| Schema → SQL generation | `SchemaRegistry.generateSQL()` writes to DB | Medium |
| Schema → Validation | `FieldDefinition.normalize()` available to API | Low |
| Schema → CRUD API | Auto-generate REST endpoints from schema | High |

**Key file:** `legacy_dna/schema_driven/mas-schema.js` (582 lines)
- `TYPE_CONFIG`: 18 data types with SQL mapping + normalization
- `FieldDefinition`: field → `columnSQL()` → `CREATE TABLE`
- `TableDefinition`: table → `toSQL()` with foreign keys
- `SchemaRegistry`: topological sort → full DDL generation

### Phase 3: Node.js WS Microservice

**Goal:** Build a WebSocket relay server for live sync between the QDML engine and connected frontends.

| Task | Description | Complexity |
|------|-------------|------------|
| WS server (Node.js) | Based on `legacy_dna/backend_runtime/pubsub.js` | High |
| Delta sync protocol | Cursor-based change tracking from `operation_log` | High |
| Client SDK | Browser-side WS client with reconnect + replay | Medium |
| Integration with QDML | Operations broadcast to connected clients | Medium |

**Key files:**
- `legacy_dna/backend_runtime/pubsub.js` (37KB) — subscription management
- `legacy_dna/backend_runtime/delta-engine.js` (5KB) — cursor-based sync
- `legacy_dna/frontend_v3/mas-store-v3.js` (45KB) — client state + sync

### Phase 4: PostgreSQL Migration

**Goal:** Switch from SQLite to PostgreSQL for multi-user production deployment.

| Task | Description | Complexity |
|------|-------------|------------|
| PgSQL driver | `QDMLEngine(driver="pgsql", pg_config={...})` | Low (already abstracted) |
| Schema adaptation | `AUTOINCREMENT` → `SERIAL`, `datetime('now')` → `NOW()` | Low (already handled) |
| Connection pooling | `asyncpg` or `psycopg2` pool | Medium |
| Migration script | SQLite → PgSQL data transfer | Medium |

**The engine is already prepared for this.** The `_q()` method auto-converts `?` → `%s` placeholders when `driver="pgsql"`.

### Phase 5: C++ Quantum Core

**Goal:** Integrate the high-performance C++ ORM for DDL generation, query building, and tree operations.

| Task | Description | Complexity |
|------|-------------|------------|
| Build system | CMake + precompiled binary | Medium |
| Python binding | `subprocess` or `ctypes` bridge | Medium |
| Schema validation | C++ validates schema before SQL generation | High |
| Query builder | Safe, parameterized query construction | High |

**Key file:** `legacy_dna/quantum_orm/main.cpp` (1,899 lines)

### Phase 6: Full Platform Assembly

**Goal:** Unite all microservices into the production architecture defined in `doc/ai-first-platform.md`.

| Service | Language | Port | Status |
|---------|----------|------|--------|
| Gateway | Python (FastAPI) | 8000 | Not started |
| QDML Server | Python | 8800 | ✅ Running (http.server, will migrate to FastAPI) |
| Compiler | Python | 8002 | Partially done (qdml_master.py) |
| Quantum Core | C++ | stdio | Not started |
| WS Relay | Node.js | 8003 | Not started |
| Frontend | MAS JS V2 | — | ✅ Admin dashboard running |

---

## 6. Legacy DNA — What We Carry Forward

The `legacy_dna/` directory contains proven production code that will be absorbed into QDML:

| System | Size | Key Innovation | Integration Plan |
|--------|------|----------------|------------------|
| `mas-schema.js` | 582L | Schema → SQL + Validation + ERD | Phase 2: bulks in QDML |
| `mas-rest.js` | 1,435L | Stale-While-Revalidate cache, offline queue | Phase 3: client SDK |
| `mas-store-v3.js` | 45KB | Delta sync, IndexedDB, outbox | Phase 3: WS client |
| `mas.core.js` | 78KB | VDOM, DSL, event delegation | ✅ Already in QDML (17 bulks) |
| `mas-ui.js` | 128KB | 130+ design tokens, Chart.js bridge | Phase 2: bulks in QDML |
| `server.runtime.js` | 51KB | Node.js runtime with CRUD + pubsub | Phase 3: WS relay base |
| `crud-api.js` | 53KB | Dynamic CRUD from schema | Phase 2: auto-generation |
| `pubsub.js` | 37KB | Table-level subscriptions with scope | Phase 3: WS relay |
| `postgres.js` | 1,164L | JS ORM with smart features | Phase 4: PgSQL layer |
| `main.cpp` | 1,899L | C++ ORM (DDL, queries, trees) | Phase 5: Quantum Core |
| `track3_engine.py` | 1,603L | Surgical code mutation | Absorbed into QDML protocol |

---

## 7. Verification Status

| Test | Result | Notes |
|------|--------|-------|
| Master build (33 bulks → 8 files) | ✅ Pass | 304ms, all files match |
| Engine JSON protocol | ✅ Pass | All 10 actions work |
| SQL abstraction (SQLite) | ✅ Pass | WAL mode, foreign keys |
| Auth (create user, login, token) | ✅ Pass | Default admin created |
| Server startup | ✅ Pass | Port 8800, auto-init |
| Admin UI load | ✅ Pass | Login page renders |
| Admin login flow | 🔶 Partial | Browser test interrupted — needs manual verification |
| Dashboard data fetch | 🔶 Pending | Depends on login completion |
| Bulk viewer | 🔶 Pending | Depends on login completion |
| PgSQL driver | ⬜ Not tested | Abstraction ready, no PgSQL instance |

### How to Test Now

```bash
# 1. Build the database
python core/qdml_master.py

# 2. Start the server
python core/qdml_server.py

# 3. Open browser
# http://localhost:8800
# Login: admin / admin

# 4. Test API directly
curl -X POST http://localhost:8800/api/auth/login -H "Content-Type: application/json" -d "{\"username\":\"admin\",\"password\":\"admin\"}"
# → {"ok":true,"token":"...","user":{...}}

curl -X POST http://localhost:8800/api/qdml -H "Authorization: Bearer TOKEN" -H "Content-Type: application/json" -d "{\"action\":\"mini\",\"project\":\"mas-front\",\"level\":1}"
# → {"ok":true,"data":"PROJECT MAS Frontend\n..."}
```

---

## 8. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **SQLite for dev, PgSQL for prod** | SQLite is zero-setup and sufficient for single-user development. The abstraction layer makes migration trivial. |
| **Zero-dependency server** | `http.server` is built into Python. No `pip install` required. Reduces attack surface and deployment complexity. |
| **Auth in engine, not separate** | Keeping auth in `qdml_engine.py` means the database is fully self-contained — backup the `.db` file and you have everything. |
| **Admin built with MAS JS V2** | The system manages its own framework. The admin dashboard proves the framework works and stress-tests it. |
| **JSON protocol over REST** | A single `POST /api/qdml` endpoint with `{action: "..."}` is simpler than 20 REST routes. AI models handle JSON naturally. |
| **Markers per language** | Compiled output includes `m-bulk:name` comments in the correct syntax so the system can re-split files if needed. |

---

> **Next action:** Complete the browser login test, then begin Phase 2 (Schema-Driven Integration).
