# MAS-SYS — First Product Specification

> **Document**: Product Blueprint  
> **Version**: 1.0 — 2026-05-09  
> **Scope**: The first project built BY AI-First as a proof-of-concept  
> **Codename**: MAS-SYS (MAS Storm)

---

## 1. What is MAS-SYS?

MAS-SYS is the **first real project** that the AI-First platform will build. It is not part of AI-First — it is a **separate product** that lives in its own PostgreSQL database, has its own schema, its own components, and its own deployment.

MAS-SYS serves two purposes:
1. **Proof of concept** — Validates that AI-First can build a complete, production-ready application from a database schema using QDML commands
2. **Unified replacement** — Replaces the fragmented OS + Quantum stack with a single, coherent system

### The Relationship

```
AI-First Platform (the builder)
  │
  ├── Platform DB: ai_first_platform
  │     └── projects table → project "mas-sys" → db_name: "aif_mas_sys"
  │
  └── Project DB: aif_mas_sys
        ├── module, component, pillar (component model)
        ├── accounting tables (from Quantum schema)
        ├── change_log (sync protocol)
        └── i18n_key, design_token, etc.
```

**AI-First creates the database, the AI populates it, the compiler generates the files, and MAS-SYS runs independently.**

---

## 2. What MAS-SYS Will Be

MAS-SYS is a **unified ERP/business platform** that combines what OS and Quantum do separately today into a single system:

| Current State | MAS-SYS Replacement |
|--------------|---------------------|
| OS handles live data via WS + SQLite | MAS-SYS uses WS + PostgreSQL (via AI-First's WS Relay) |
| Quantum handles deep data via HTTP + PostgreSQL | MAS-SYS uses the same PostgreSQL for everything |
| OS has its own schema engine (JSON files) | MAS-SYS schema lives in the database |
| Quantum has its own schema contract (JSON file) | Same database schema, derived from AI-First |
| Two separate auth systems | One auth system from the project schema |
| Two separate frontends | One MAS JS frontend built by AI-First |

---

## 3. MAS-SYS Schema (What the AI Will Build)

When a superadmin creates the "MAS-SYS" project in AI-First, the AI will be asked to generate the following schema. This is the target — the schema the AI should produce through QDML commands:

### 3.1 Core Business Tables

```json
{
  "meta": {
    "project": "mas-sys",
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
        "name": "companies",
        "fields": [
          { "name": "id", "columnName": "id", "type": "bigint", "primaryKey": true },
          { "name": "name", "columnName": "name", "type": "text" },
          { "name": "tax_id", "columnName": "tax_id", "type": "text" },
          { "name": "address", "columnName": "address", "type": "text" },
          { "name": "phone", "columnName": "phone", "type": "text" },
          { "name": "logo_url", "columnName": "logo_url", "type": "text" },
          { "name": "is_active", "columnName": "is_active", "type": "bit", "default": true }
        ],
        "smart_features": {
          "display_field": "name",
          "search_fields": ["name", "tax_id"]
        },
        "storage": { "live": true, "deep_paging": false },
        "access_rules": {
          "read": { "scope": "tenant" },
          "write": { "roles": ["superadmin"] },
          "delete": { "roles": ["superadmin"] }
        }
      },
      {
        "name": "branches",
        "fields": [
          { "name": "id", "columnName": "id", "type": "bigint", "primaryKey": true },
          { "name": "tenant_id", "columnName": "tenant_id", "type": "bigint", "references": { "table": "companies", "column": "id" } },
          { "name": "name", "columnName": "name", "type": "text" },
          { "name": "code", "columnName": "code", "type": "text" },
          { "name": "is_active", "columnName": "is_active", "type": "bit", "default": true }
        ],
        "smart_features": {
          "display_field": "name",
          "search_fields": ["name", "code"]
        },
        "storage": { "live": true },
        "access_rules": {
          "read": { "scope": "tenant", "field": "tenant_id" },
          "write": { "roles": ["superadmin", "admin"] }
        }
      },
      {
        "name": "users",
        "fields": [
          { "name": "id", "columnName": "id", "type": "bigint", "primaryKey": true },
          { "name": "tenant_id", "columnName": "tenant_id", "type": "bigint", "references": { "table": "companies", "column": "id" } },
          { "name": "login_name", "columnName": "login_name", "type": "text" },
          { "name": "display_name", "columnName": "display_name", "type": "text" },
          { "name": "password_hash", "columnName": "password_hash", "type": "text" },
          { "name": "role", "columnName": "role", "type": "text", "default": "user" },
          { "name": "branch_id", "columnName": "branch_id", "type": "bigint", "references": { "table": "branches", "column": "id" } },
          { "name": "is_active", "columnName": "is_active", "type": "bit", "default": true }
        ],
        "smart_features": {
          "display_field": "display_name",
          "search_fields": ["login_name", "display_name"]
        },
        "access_rules": {
          "read": { "scope": "tenant" },
          "write": { "roles": ["superadmin", "admin"] },
          "secret_fields": ["password_hash"]
        }
      }
    ]
  }
}
```

### 3.2 Modules the AI Will Create

| Module | Components | Purpose |
|--------|-----------|---------|
| **auth** | LoginScreen, SessionManager | Authentication and session |
| **dashboard** | DashboardScreen, StatCard, RecentActivity | Post-login home |
| **company** | CompanySettings, BranchList, BranchForm | Multi-company/branch management |
| **users** | UserList, UserForm, RoleManager | User and role management |
| **accounting** | ChartOfAccounts (tree), JournalEntry, TrialBalance | Core accounting (from Quantum schema) |

---

## 4. How the AI Builds MAS-SYS

This is the actual sequence of QDML commands the AI will execute to build MAS-SYS from scratch:

### Phase 1: Schema & Database

```
Human: "Build an ERP system called MAS-SYS with companies, branches, users, and accounting"

AI → QDML:
  POST /qdml/create
  {
    "type": "schema",
    "tables": [ ...companies, branches, users, accounts... ]
  }
  → Platform creates PostgreSQL database "aif_mas_sys"
  → Quantum Core generates DDL and executes CREATE TABLE statements
  → change_log table is created automatically
```

### Phase 2: Module Structure

```
AI → QDML:
  POST /qdml/create
  {
    "type": "module",
    "modules": [
      { "name": "auth", "slug": "auth", "sort_order": 1 },
      { "name": "dashboard", "slug": "dashboard", "sort_order": 2 },
      { "name": "company", "slug": "company", "sort_order": 3 },
      { "name": "users", "slug": "users", "sort_order": 4 },
      { "name": "accounting", "slug": "accounting", "sort_order": 5 }
    ]
  }
```

### Phase 3: Components & Pillars

```
AI → QDML:
  POST /qdml/create
  {
    "type": "component",
    "module": "auth",
    "components": [
      {
        "name": "LoginScreen",
        "slug": "login-screen",
        "kind": "screen",
        "pillars": {
          "schema": "{ state: { email: '', password: '', error: null, loading: false } }",
          "template": "div.login-container > ...",
          "logic": "{ onSubmit: async (ctx) => { ... } }",
          "style": ".login-container { ... }"
        }
      }
    ]
  }
```

### Phase 4: Compile & Test

```
AI → QDML:
  POST /qdml/compile
  { "project_id": "mas-sys", "strategy": "single-file" }
  → Compiler reads all components from DB
  → Generates valid MAS JS module files
  → Runs syntax checker
  → Returns: { success: true, files: [...], warnings: [] }

AI → Playwright:
  → Opens compiled app in browser
  → Tests login flow
  → Takes screenshots
  → Reports results back
```

---

## 5. Success Criteria

MAS-SYS is considered successful when:

| # | Criterion | Measurement |
|---|-----------|-------------|
| 1 | AI creates the database schema from natural language | QDML `/create` succeeds, tables exist in PostgreSQL |
| 2 | AI builds login screen with working auth | User can log in via browser, JWT is issued |
| 3 | AI builds dashboard with live data | Dashboard shows real data from PostgreSQL via WS |
| 4 | AI builds CRUD screens for companies/users | Records can be created, read, updated, deleted |
| 5 | Delete propagation works | Delete on server → frontend removes from IndexedDB |
| 6 | Offline-first works | App works without network, syncs when reconnected |
| 7 | i18n works | All strings use `t()`, language switch works |
| 8 | The entire app was built without editing files | Zero manual file edits — all via QDML |

---

## 6. What MAS-SYS Proves

If MAS-SYS succeeds, it proves:

1. **Database-as-filesystem works.** Code stored as structured data is superior to code stored as text files.
2. **AI can build real applications via QDML.** The protocol is sufficient for complete application development.
3. **The unified stack works.** No more OS vs Quantum split. One database, one ORM, one sync protocol.
4. **Delete propagation is solved.** The change_log + tombstone system fixes MAS Store v3's critical gap.
5. **Schema-driven security works.** Access rules in the schema are enforced automatically without application code.

MAS-SYS is not the destination — it is the **proof that the AI-First approach is viable** for building any future project.
