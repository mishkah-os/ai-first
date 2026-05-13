# QDML Platform — Complete Documentation

## Overview

QDML (Quantum Data Markup Language) is a **code-as-database-records** platform where all source code lives in PostgreSQL. There are no source files — only compiled artifacts. Everything is managed through a unified protocol that AI tools and developers interact with identically.

### Core Principle
> **PostgreSQL is the single source of truth.** Files are compiled outputs. Development happens through protocol commands.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL 14+                             │
│              (Single Source of Truth)                         │
│                                                             │
│  project → module → component → pillar (bulk)               │
│  kit_registry → kit_templates                               │
│  pipelines → app_instances                                  │
│  schema_registry → change_log                               │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼──────────────┐
        │             │              │
  ┌─────▼─────┐ ┌────▼────┐  ┌─────▼─────┐
  │  QDML API │ │   AI    │  │   WS3     │
  │  FastAPI  │ │ Protocol│  │  Relay    │
  │  :8001    │ │ +Bedrock│  │  :8003    │
  │           │ │         │  │           │
  │ • auth    │ │ • create│  │ • pubsub  │
  │ • qdml    │ │ • modify│  │ • sync    │
  │ • compile │ │ • reveal│  │ • cursor  │
  │ • kits    │ │ • test  │  │ • replay  │
  └───────────┘ └─────────┘  └───────────┘
        │
  ┌─────▼─────┐
  │  ERP      │
  │  Engines  │
  │           │
  │ • Invoice │
  │ • Approval│
  │ • Tree    │
  │ • CRUD    │
  └───────────┘
```

---

## Current System Stats

| Metric | Value |
|--------|-------|
| Projects | 6 |
| Modules | 18 |
| Components | 24 |
| Bulks (code units) | 117 |
| Total Lines of Code | 8,037 |
| Database Size | 14.86 MB |
| API Endpoints | 26 |
| Generated Files | 17 |

---

## Projects

| Project | Purpose | Modules | Lines |
|---------|---------|---------|-------|
| `mas-front` | MAS.js framework + Admin | 6 | 1,979 |
| `platform-core` | Quantum + WS Relay engines | 3 | 4,436 |
| `kits` | Mobile/Dashboard/Pipeline kits | 3 | 482 |
| `erp` | Invoice/Approval/Tree/CRUD engines | 4 | 652 |
| `mas-saas` | Multi-tenant SaaS dashboard | 1 | 229 |
| `mostamal-hawaa` | E-commerce mobile app | 1 | 259 |

---

## API Reference

### Authentication

```bash
# Login
POST /api/auth/login
{"username": "admin", "password": "admin123"}
# Returns: {"ok": true, "token": "...", "user": {...}}

# Verify (use header for all protected endpoints)
POST /api/auth/verify
Authorization: Bearer <token>
```

### AI Protocol (Main Developer Interface)

```bash
# Create a new component using AI
POST /api/ai/
{
  "action": "create",
  "target": "project-slug/module-slug/component-slug",
  "prompt": "Create a user registration form with phone validation"
}

# Modify existing component with AI
POST /api/ai/
{
  "action": "modify",
  "selector": {"project": "mas-front", "component": "login-screen", "bulk": "main"},
  "prompt": "Add Google OAuth button and remember-me checkbox"
}

# Reveal component code (sliding window)
POST /api/ai/
{
  "action": "reveal",
  "selector": {"project": "platform-core", "component": "ws3-server"}
}

# Compile component to output file
POST /api/ai/
{
  "action": "compile",
  "selector": {"project": "mas-front", "component": "mas-store"}
}

# Get project overview
POST /api/ai/
{
  "action": "mini",
  "selector": {"project": "erp"},
  "level": 1
}

# Full project tree
POST /api/ai/
{
  "action": "describe",
  "selector": {"project": "mostamal-hawaa"}
}

# Get AI system prompt (for tool integration)
GET /api/ai/system-prompt
```

### Kit System

```bash
# List all available kits
GET /api/kits/

# Get kit details
GET /api/kits/detail/mobile-kit

# Compile kit with custom variables
POST /api/kits/compile-kit/mobile-kit
{
  "variables": {
    "app_name": "My Store",
    "primary_color": "#E91E63",
    "logo": "/assets/my-logo.png"
  }
}

# Create app instance from kit
POST /api/kits/create-app
{
  "kit": "mobile-kit",
  "app_name": "My Store App",
  "variables": {"primary_color": "#2196F3"}
}
```

### Pipeline System

```bash
# List pipelines
GET /api/kits/pipelines

# Execute pipeline
POST /api/kits/pipelines/build-mobile-app/execute
{
  "app_name": "My App",
  "app_id": "my-app",
  "platforms": ["android", "ios"],
  "template": "e-commerce"
}
```

### QDML Protocol (Low-Level)

```bash
# All QDML actions require authentication
Authorization: Bearer <token>

# Stats
POST /api/qdml
{"action": "stats"}

# Mini overview
GET /api/qdml/mini/platform-core

# Create bulk manually
POST /api/qdml
{
  "action": "create_bulk",
  "project": "my-project",
  "component": "my-component",
  "bulk_name": "main",
  "content": "// code here",
  "lang": "javascript"
}

# Mutate (with history tracking)
POST /api/qdml
{
  "action": "mutate_bulk",
  "project": "my-project",
  "component": "my-component",
  "bulk_name": "main",
  "content": "// new code",
  "reason": "Fixed login bug"
}

# Compile
POST /api/qdml
{"action": "compile", "project": "mas-front", "component": "mas-store"}

# History
POST /api/qdml
{"action": "history", "project": "mas-front", "component": "admin-js", "bulk": "boot"}
```

---

## Developer Workflow

### 1. Create a New Project

```bash
# Via AI Protocol
POST /api/ai/
{
  "action": "create",
  "target": "my-saas/frontend/login-page",
  "prompt": "Create a modern login page with email/password, social OAuth, and 2FA support. Arabic RTL. Pink theme."
}
```

The system will:
1. Create project `my-saas` if it doesn't exist
2. Create module `frontend`
3. Create component `login-page`
4. Use Bedrock AI to generate the code
5. Store it as a bulk in PostgreSQL
6. Return mini-code preview

### 2. Modify with AI

```bash
POST /api/ai/
{
  "action": "modify",
  "selector": {"project": "my-saas", "component": "login-page"},
  "prompt": "Add remember-me checkbox and change the primary button to gradient"
}
```

The system:
1. Fetches current code from DB
2. Sends to Bedrock with modification prompt
3. Stores new version (old version saved in history)
4. Returns updated code

### 3. Build & Deploy

```bash
# Compile the component
POST /api/ai/
{"action": "compile", "selector": {"project": "my-saas", "component": "login-page"}}

# Or use a full pipeline
POST /api/kits/pipelines/build-mobile-app/execute
{
  "app_name": "My SaaS",
  "app_id": "my-saas",
  "platforms": ["android", "web"]
}
```

### 4. Create Microservice

```bash
# Create a backend service
POST /api/ai/
{
  "action": "create",
  "target": "my-saas/backend/payment-service",
  "prompt": "Create a payment processing service with Stripe integration, webhook handling, subscription management, and invoice generation. Node.js."
}
```

### 5. Use Kit Templates

```bash
# Start with mobile kit
POST /api/kits/create-app
{
  "kit": "mobile-kit",
  "app_name": "My Store",
  "variables": {
    "app_name": "My Store",
    "primary_color": "#4CAF50",
    "tabs": [
      {"icon": "home", "label": "Home", "route": "/"},
      {"icon": "cart", "label": "Cart", "route": "/cart"},
      {"icon": "user", "label": "Profile", "route": "/profile"}
    ]
  }
}
```

---

## Kit System

### Mobile Kit
Pre-built components for mobile apps:
- **Shell**: Header + Footer tabs + Side menu
- **Auth Screens**: Login, Register, Reset Password, Splash
- **Styles**: Complete mobile CSS with RTL support

### Dashboard Kit
Admin panel components:
- **Layout**: Sidebar + Header + Content area
- **Widgets**: StatsCard, DataTable, ChartWidget
- **Themes**: Light/Dark with toggle

### Offer Kit
Pricing and marketing pages (planned):
- Pricing cards
- Feature comparison tables
- Call-to-action sections

---

## ERP Engines

### Invoice Engine
- Auto-numbering (INV-2026-01001)
- Multi-line items with tax/discount
- PDF generation (HTML-based)
- Quote → Invoice conversion
- Status workflow (draft → sent → paid)

### Approval Engine
- Multi-level workflows
- Auto-approve below threshold
- Escalation support
- Full audit trail

### Tree Coding Engine
- Hierarchical auto-coding (01-01-001)
- Recursive operations
- Path-based queries
- Move/reorder support

### CRUD Table Engine
- Schema-driven table creation
- Automatic DDL generation
- Search, filter, paginate
- Soft delete support
- Type validation

---

## Amazon Bedrock Integration

### Configuration
Credentials are loaded from `/srv/apps/ai5/ai-keys/bedrock.txt` (Base64-encoded BedrockAPIKey format).

### How It Works
1. Developer sends prompt to `POST /api/ai/`
2. System routes to Amazon Bedrock (Claude Sonnet 4)
3. AI generates/modifies code based on prompt + context
4. Code is stored in PostgreSQL as a bulk record
5. Developer can compile, preview, or deploy

### Models Used
- **Generation**: `us.anthropic.claude-sonnet-4-20250514-v1:0` (temperature: 0.7)
- **Modification**: Same model (temperature: 0.3 for precision)
- **Analysis**: Same model (temperature: 0.2 for structured output)

### Live Test Results (Verified Working)
```
Test 1: AI Create → 359 lines generated (Arabic pricing page)
Test 2: AI Modify → Successfully changed plan details + added discount
Test 3: Compile  → 11,511 chars compiled output
```

### Connection Details
- Endpoint: `https://bedrock-runtime.us-east-1.amazonaws.com`
- Auth: Bearer token (BedrockAPIKey)
- Profile: `zsdj-at-099695389098`
- Timeout: 90 seconds for generation

---

## Testing

### Quick Health Check
```bash
curl http://localhost:8001/health
```

### Full System Test
```bash
# Start server
python3 main.py &

# 1. Login
TOKEN=$(curl -s -X POST http://localhost:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")

# 2. Test AI Create
curl -X POST http://localhost:8001/api/ai/ \
  -H "Content-Type: application/json" \
  -d '{"action":"create","target":"test/pages/hello","prompt":"Create a hello world page"}'

# 3. Test AI Modify
curl -X POST http://localhost:8001/api/ai/ \
  -H "Content-Type: application/json" \
  -d '{"action":"modify","selector":{"project":"test","component":"hello"},"prompt":"Add a counter button"}'

# 4. Test Compile
curl -X POST http://localhost:8001/api/ai/ \
  -H "Content-Type: application/json" \
  -d '{"action":"compile","selector":{"project":"test","component":"hello"}}'

# 5. Test Kit
curl -X POST http://localhost:8001/api/kits/compile-kit/mobile-kit \
  -H "Content-Type: application/json" \
  -d '{"variables":{"app_name":"Test App"}}'

# 6. Test Pipeline
curl -X POST http://localhost:8001/api/kits/pipelines/build-mobile-app/execute \
  -H "Content-Type: application/json" \
  -d '{"app_name":"Test","app_id":"test","platforms":["android"]}'
```

---

## UI/UX Recommendations for Admin Interface

### 1. Project Manager View
```
┌────────────────────────────────────────────────┐
│ [+New Project]  [Search...]           [Admin ▼]│
├────────────────────────────────────────────────┤
│ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐          │
│ │ mas  │ │ erp  │ │ kits │ │saas  │          │
│ │front │ │      │ │      │ │      │          │
│ │ 1979L│ │ 652L │ │ 482L │ │ 229L │          │
│ │ 8comp│ │ 4comp│ │ 3comp│ │ 1comp│          │
│ └──────┘ └──────┘ └──────┘ └──────┘          │
└────────────────────────────────────────────────┘
```
- Card per project showing stats
- Click to open project workspace
- Drag to reorder

### 2. Component Editor (AI-Driven)
```
┌─────────────────────────────────────────────────────┐
│ [← Back] my-saas / frontend / login-page   [Compile]│
├──────────────────────┬──────────────────────────────┤
│ Module Tree          │ Code Editor                   │
│ ├─ frontend          │ // login-page — main bulk     │
│ │  ├─ login-page ◀   │ function LoginPage() {        │
│ │  ├─ register       │   return `<div class="...">   │
│ │  └─ dashboard      │     <form>...</form>          │
│ ├─ backend           │   </div>`;                    │
│ │  ├─ auth-service   │ }                             │
│ │  └─ payment        │                               │
│ └─ shared            │ [AI: "Add forgot password"]   │
│    └─ utils          │ [▶ Generate] [History] [Diff] │
├──────────────────────┴──────────────────────────────┤
│ 📝 AI Prompt: "Add forgot password link below form" │
│ [Send to AI] [Preview] [Compile & Deploy]           │
└─────────────────────────────────────────────────────┘
```

### 3. Kit Builder
```
┌─────────────────────────────────────────┐
│ Kit: Mobile App                         │
│ Template: E-commerce                    │
├─────────────────────────────────────────┤
│ Variables:                              │
│   App Name: [My Store          ]        │
│   Logo:     [📁 Upload]                │
│   Primary:  [#E91E63] ■                │
│   Language: [Arabic ▼]                  │
│   Tabs:     [+ Add Tab]                │
│                                         │
│ [Preview]  [Generate]  [Deploy →]       │
└─────────────────────────────────────────┘
```

### 4. Pipeline Dashboard
```
┌─────────────────────────────────────────┐
│ Pipeline: build-mobile-app              │
│ Status: ████████░░ 80% — Building       │
├─────────────────────────────────────────┤
│ ✅ validate        2ms                  │
│ ✅ select-template 5ms                  │
│ ✅ generate-code   1200ms               │
│ 🔄 build           ...running           │
│ ⬜ sign                                 │
│ ⬜ deploy                               │
├─────────────────────────────────────────┤
│ [Cancel] [Retry Failed] [View Logs]     │
└─────────────────────────────────────────┘
```

---

## Future Development Recommendations

### Phase 1: UI Polish (High Priority)
1. **Real-time code preview** — WebSocket-driven live preview
2. **Split-pane editor** — Code + preview side by side
3. **AI chat sidebar** — Conversational code modifications
4. **Diff viewer** — Before/after comparison with history
5. **Component marketplace** — Browse and install from kit library

### Phase 2: Build System
1. **Webpack/Rollup integration** — Bundle generated files
2. **Source maps** — Debug compiled output back to bulks
3. **Hot Module Replacement** — Change bulk → instant preview
4. **Multi-target compilation** — Same component → web/mobile/desktop

### Phase 3: Collaboration
1. **Real-time collaborative editing** — CRDT-based
2. **Branch/merge for bulks** — Git-like workflow in DB
3. **Code review system** — Request review on mutations
4. **Role-based access per module** — Frontend dev can't edit backend

### Phase 4: AI Enhancement
1. **Auto-complete in editor** — Bedrock-powered suggestions
2. **Code quality scoring** — AI reviews on every mutation
3. **Auto-test generation** — AI writes tests for new components
4. **Dependency analysis** — AI suggests optimizations
5. **Natural language deployment** — "Deploy my app to production"

### Phase 5: Enterprise Features
1. **Multi-tenant isolation** — PostgreSQL schemas per customer
2. **Custom domains** — White-label deployed apps
3. **Usage metering** — Track API calls, builds, storage
4. **SSO integration** — SAML/OIDC for enterprise auth
5. **Audit compliance** — Full operation trail with retention

---

## File Structure

```
/srv/apps/ai-first/
├── core/
│   ├── main.py                    # FastAPI entry point
│   ├── qdml_engine.py             # Core engine (async PostgreSQL)
│   ├── bedrock_client.py          # Amazon Bedrock integration
│   ├── config.py                  # Configuration & env vars
│   ├── schema.sql                 # Database DDL
│   ├── routes/
│   │   ├── auth.py                # Authentication endpoints
│   │   ├── qdml.py                # QDML protocol endpoints
│   │   ├── compile.py             # Compilation endpoints
│   │   ├── ai.py                  # AI protocol endpoints
│   │   └── kits.py                # Kit system endpoints
│   ├── seed_admin.py              # Admin dashboard seeder
│   ├── seed_mas.py                # MAS.js framework seeder
│   ├── seed_os_kernel.py          # OS WebSocket kernel seeder
│   ├── seed_quantum.py            # Quantum engine seeder
│   ├── seed_ws3.py                # WS3 relay seeder
│   ├── seed_complete.py           # mas-store + kits + pipeline
│   ├── seed_erp_engines.py        # ERP 4 engines seeder
│   └── seed_saas_and_apps.py      # MAS-SAAS + Mostamal Hawaa
├── mas-front/
│   └── _generated/                # Compiled output files
│       ├── mas.core.js            # MAS.js framework (905 lines)
│       ├── admin.js               # Admin dashboard (352 lines)
│       ├── shared/mas-store.js    # Unified data store (271 lines)
│       ├── kits/mobile-kit.js     # Mobile kit (267 lines)
│       ├── kits/dashboard-kit.js  # Dashboard kit (110 lines)
│       ├── kits/pipeline-engine.js# Pipeline engine (102 lines)
│       ├── saas/saas-dashboard.js # SaaS dashboard (228 lines)
│       ├── mostamal/mostamal-app.js # Mostamal Hawaa (258 lines)
│       └── ws3-relay/index.js     # WebSocket relay (173 lines)
├── erp/
│   └── _generated/
│       ├── invoice-engine-core.js # Invoice engine (218 lines)
│       ├── approval-engine-core.js# Approval engine (126 lines)
│       ├── tree-engine-core.js    # Tree coding (148 lines)
│       └── crud-engine-core.js    # CRUD engine (156 lines)
└── DOCUMENTATION.md               # This file
```

---

## Quick Start

```bash
# 1. Start the API
cd /srv/apps/ai-first/core
python3 main.py

# 2. Start WS3 Relay (optional, for real-time sync)
cd /srv/apps/ai-first/mas-front/_generated/ws3-relay
node index.js

# 3. Access
open http://localhost:8001        # API root
open http://localhost:8001/docs   # Swagger UI
open http://localhost:8001/health # Status
```

---

## License & Credits
Built with QDML Protocol on PostgreSQL 14+, FastAPI, Node.js, and Amazon Bedrock.
