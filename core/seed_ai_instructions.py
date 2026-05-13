#!/usr/bin/env python3
"""
AI Instructions — Complete, detailed prompts for every classification + task type.
These are injected into every AI request so the AI understands our protocol fully.
"""
import asyncio
import asyncpg
import json
from config import DATABASE_URL, QDML_SCHEMA

# ═══════════════════════════════════════════════════════════════════════
# QDML PROTOCOL OVERVIEW (injected in EVERY request as base context)
# ═══════════════════════════════════════════════════════════════════════

QDML_PROTOCOL_BASE = """## QDML Protocol Overview

You are working inside QDML Platform — a system where ALL code lives in PostgreSQL as structured records.
There are NO source files. Files are compiled outputs only.

### Hierarchy
- PROJECT (has icon, name, description)
  - MODULE (has tier: frontend|backend|shared, groups related components)
    - COMPONENT (has classification, description, one or more bulks)
      - BULK (actual code, 50-150 lines max, has exports, depends, human_summary)

### Key Rules
1. Each BULK is atomic — it does ONE thing and exports specific functions/classes
2. DEPENDS declares what other bulks this bulk needs
3. EXPORTS declares what this bulk provides to others
4. Function names must be descriptive English (camelCase)
5. All UI supports Arabic RTL (dir="rtl")
6. Currency is SAR (Saudi Riyal) unless specified otherwise

### Data Flow
- Frontend uses `masStore` (IndexedDB + WebSocket sync)
- masStore connects to WS3 server via WebSocket
- WS3 routes CRUD to correct branch schema in PostgreSQL
- Each branch has isolated PostgreSQL schema (pos_dar, pos_clubhouse, etc.)
- Changes broadcast to all clients in same branch via WebSocket

### Naming Conventions
- Files/components: kebab-case (order-engine, pos-main-screen)
- Functions/methods: camelCase (calculateTotal, handlePayment)
- Constants: UPPER_SNAKE (ORDER_STATUS, MAX_RETRY)
- Database tables: snake_case (order_header, menu_items)
- CSS classes: kebab-case (order-card, menu-grid)
"""

# ═══════════════════════════════════════════════════════════════════════
# TASK-SPECIFIC INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════

TASK_INSTRUCTIONS = {
    "create": """### CREATE Task Instructions

You are creating a NEW component from scratch.

Output requirements:
1. Return ONLY executable code — no explanations, no markdown fences
2. Code must be self-contained within a single bulk
3. Must include all necessary imports at the top
4. Must export a default object or class
5. Include a brief JSDoc comment at the very top (1-2 lines max describing purpose)

Quality requirements:
- Every function must have a clear, descriptive name
- State must be in a single object (easy to inspect)
- Error handling: throw descriptive errors, never silently fail
- No hardcoded values — use config objects or function parameters
""",

    "update": """### UPDATE Task Instructions

You are modifying an EXISTING component. You will receive its current code (mini_code).

Output requirements:
1. Return the COMPLETE modified code — not a diff, not a patch
2. Preserve ALL existing functionality unless explicitly asked to remove
3. Keep the same structure, style, and naming conventions
4. Do NOT rename existing functions or change export signatures
5. Add new code in the appropriate section (state with state, methods with methods)

Quality requirements:
- If adding a feature, add it in the logical position
- If fixing a bug, fix only the bug — don't refactor surroundings
- Preserve all existing comments and JSDoc
- Keep function order consistent with the original
""",

    "structure": """### STRUCTURE Task Instructions

You are designing the MODULE and COMPONENT structure for a project or feature.

Output requirements:
1. Return valid JSON matching this schema:
{
  "modules": [
    {
      "name": "Display Name",
      "slug": "kebab-case",
      "tier": "frontend|backend|shared",
      "components": [
        {
          "name": "Display Name",
          "slug": "kebab-case",
          "classification": "must match a classification code",
          "description": "Human-readable purpose (Arabic OK)"
        }
      ]
    }
  ]
}

Design rules:
- Frontend and backend are SEPARATE modules — never mix
- Each component does ONE thing
- Max 5 modules, max 5 components per module for a single request
- Classification must be one of: mas-screen, mas-widget, mas-screen-dashboard, mas-screen-mobile, mas-store-module, css-theme, node-service, node-engine, ws3-handler, python-api, config-schema, config-service, shared-domain
"""
}

# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICATION-SPECIFIC DETAILED PROMPTS
# ═══════════════════════════════════════════════════════════════════════

CLASSIFICATION_PROMPTS = {

# ─── MAS.js Screen ───
"mas-screen": {
    "create": """## Classification: MAS.js Screen (🖥️)

You are building a full-page screen component using MAS.js framework.

### Architecture Pattern
```javascript
// brief-description.js
import masStore from '/lib/mas-store.js';

const ScreenName = {
    state: {
        // All reactive data here — flat object, no nesting beyond 2 levels
        branch_id: null,
        loading: true,
        items: [],
        selectedId: null,
        error: null
    },

    async init(branchId) {
        this.state.branch_id = branchId;
        await masStore.init({ projectId: branchId });
        // Load initial data
        await this.loadData();
        // Subscribe to changes
        masStore.on('change', (e) => this.handleChange(e));
        // First render
        this.render();
    },

    async loadData() {
        this.state.loading = true;
        this.render();
        try {
            this.state.items = await masStore.query('table_name', {}) || [];
        } catch (e) {
            this.state.error = e.message;
        }
        this.state.loading = false;
        this.render();
    },

    handleChange(event) {
        // Real-time update handler
        if (event.table === 'relevant_table') {
            this.loadData(); // Refresh
        }
    },

    render() {
        const app = document.getElementById('app');
        if (!app) return;
        const { items, loading, error } = this.state;

        app.innerHTML = `
        <div class="screen-name" dir="rtl">
            ${loading ? '<div class="loading">جاري التحميل...</div>' : ''}
            ${error ? `<div class="error">${error}</div>` : ''}
            ${!loading && !error ? this.renderContent() : ''}
        </div>`;
    },

    renderContent() {
        // Break complex renders into sub-methods
        return `<div>...</div>`;
    },

    // Event handlers — named after the action they perform
    async handleAction(e) {
        const id = e.target.closest('[data-id]')?.dataset.id;
        // Do something
    }
};

export default ScreenName;
```

### MAS.js Rules
1. No framework imports needed — MAS.js is loaded globally
2. Use `masStore` for ALL data operations (never fetch() directly)
3. Events use `onclick="ScreenName.method(event)"` pattern
4. Render returns HTML string (template literals)
5. State changes → call this.render() to update DOM
6. Use `data-id`, `data-action` attributes for event delegation

### CSS Guidelines
- Use CSS custom properties: var(--primary), var(--radius), etc.
- RTL support: use margin-inline-start not margin-left
- Mobile-first: base styles for mobile, @media for desktop
- Dark mode: [data-theme="dark"] .class { }
""",

    "update": """## Classification: MAS.js Screen — UPDATE

You will receive the current screen code. Apply the requested modification.

Rules:
- Keep the EXACT same object structure (state, init, render, methods)
- If adding UI elements, add them in render() or a new renderX() method
- If adding data, add to state object and load in loadData()
- If adding actions, add a new method and reference in HTML
- NEVER change the export default or init() signature
- Return the COMPLETE code — the system replaces the entire bulk
"""
},

# ─── Dashboard Screen ───
"mas-screen-dashboard": {
    "create": """## Classification: Dashboard Screen (📊)

You are building a dashboard screen using QDML Dashboard Kit components.

### Available Components
```javascript
// Layout wrapper
DashboardLayout({ logo, appName, menuItems, user, pageTitle, content })

// Stats cards (grid of 4)
StatsCard({ label, value, icon, color, change })

// Data table with pagination
DataTable({ title, columns, data, pageSize })

// Chart placeholder
ChartWidget({ title, type, data, height })
```

### Pattern
```javascript
import masStore from '/lib/mas-store.js';

const DashboardScreen = {
    state: { stats: {}, tableData: [], loading: true },

    async init(branchId) {
        await masStore.init({ projectId: branchId });
        await this.loadStats();
        setInterval(() => this.loadStats(), 30000); // Refresh every 30s
        this.render();
    },

    async loadStats() {
        // Aggregate data from masStore
    },

    render() {
        document.getElementById('app').innerHTML = `
        <div class="dashboard" dir="rtl">
            <header>...</header>
            <div class="stats-grid">
                ${StatsCard({label: 'المبيعات', value: this.state.stats.sales, icon: 'dollar-sign', color: '#4CAF50', change: 12})}
                ...
            </div>
            <div class="tables-grid">
                ${DataTable({title: '...', columns: [...], data: this.state.tableData})}
            </div>
        </div>`;
    }
};
export default DashboardScreen;
```

### Dashboard Rules
- Always show key metrics at top (StatsCard grid)
- Tables below with search and export
- Auto-refresh data (30s default)
- Show loading states
- Arabic labels, English function names
""",
    "update": """## Dashboard Screen — UPDATE
Same rules as mas-screen update. Preserve layout structure.
Add/modify widgets in their appropriate grid section.
"""
},

# ─── Mobile Screen ───
"mas-screen-mobile": {
    "create": """## Classification: Mobile Screen (📱)

You are building a mobile screen using QDML Mobile Kit.

### Available Components
```javascript
MobileShell({ app_name, logo, tabs, menuItems, headerActions, theme, rtl })
AuthScreens.login(config)
AuthScreens.register(config)
AuthScreens.splash(config)
```

### Pattern
```javascript
import masStore from '/lib/mas-store.js';

const MobileScreen = {
    state: { /* ... */ },
    async init(branchId) { /* ... */ },
    render() {
        const shell = MobileShell({
            app_name: 'اسم التطبيق',
            tabs: [...],
            rtl: true
        });
        document.getElementById('app').innerHTML = shell.render(this.renderContent());
    },
    renderContent() { return `<div class="page">...</div>`; }
};
export default MobileScreen;
```

### Mobile Rules
- Touch targets minimum 44px
- No hover-only interactions
- Bottom navigation (tabs)
- Pull-to-refresh for lists
- Skeleton loading (not spinners)
- Images: lazy load, aspect-ratio fixed
- Font size minimum 14px
""",
    "update": """## Mobile Screen — UPDATE
Preserve MobileShell wrapper. Modify only the content inside renderContent().
Keep tab navigation intact. Return complete code.
"""
},

# ─── Node Engine ───
"node-engine": {
    "create": """## Classification: Business Engine (🏭)

You are building a schema-driven backend engine.

### Architecture Pattern
```javascript
// engine-name.js
export class EngineName {
    constructor(crud, branchId) {
        this.crud = crud;      // SchemaCRUD instance
        this.branchId = branchId;
    }

    async createItem(data) {
        // 1. Validate
        if (!data.name) throw new Error('name is required');

        // 2. Prepare record
        const record = {
            id: crypto.randomUUID(),
            ...data,
            status: 'active',
            created_at: new Date().toISOString()
        };

        // 3. Save via CRUD (schema-driven, no raw SQL)
        return await this.crud.create(this.branchId, 'table_name', record);
    }

    async getItem(id) {
        return await this.crud.read(this.branchId, 'table_name', id);
    }

    async updateItem(id, updates) {
        return await this.crud.update(this.branchId, 'table_name', id, updates);
    }

    async listItems(filters = {}) {
        return await this.crud.list(this.branchId, 'table_name', {
            where: filters,
            sort: 'created_at',
            order: 'DESC'
        });
    }
}
```

### Engine Rules
1. ALL database access through this.crud — NEVER write raw SQL
2. this.crud methods: create(branch, table, data), read(branch, table, id), update(branch, table, id, data), delete(branch, table, id), list(branch, table, opts)
3. IDs always crypto.randomUUID()
4. Timestamps always new Date().toISOString()
5. Validate inputs at the start of each method
6. Throw descriptive errors (never return null silently)
7. Each method does ONE operation
8. Export a single class
""",
    "update": """## Engine — UPDATE
Add new methods at the end of the class. Do not modify constructor or existing methods.
Preserve all imports and exports. Return complete class code.
"""
},

# ─── WS3 Handler ───
"ws3-handler": {
    "create": """## Classification: WS3 Handler (🔌)

You are building a WebSocket message handler for real-time operations.

### Pattern
```javascript
export class HandlerName {
    constructor(ws3Server, dependencies) {
        this.ws3 = ws3Server;
        // Store dependencies
    }

    init() {
        // Register message handlers
        this.ws3.on('message_type', (ws, msg) => this.handleType(ws, msg));
    }

    async handleType(ws, msg) {
        // Process message
        // Broadcast to relevant clients
        this.broadcast(branchId, { type: 'event', data: result });
    }

    broadcast(branchId, message) {
        // Send to all clients in branch
    }
}
```

### WS3 Rules
- Messages are JSON: { type, branch_id, ...data }
- Always validate branch_id before processing
- Broadcast changes to same-branch clients only
- Never block the event loop — use async/await
- Handle disconnections gracefully
""",
    "update": """## WS3 Handler — UPDATE
Add new message handlers. Register in init(). Return complete code.
"""
},

# ─── mas-store Module ───
"mas-store-module": {
    "create": """## Classification: mas-store Module (💾)

You are building a data layer module that uses mas-store.

### mas-store API
```javascript
import masStore from '/lib/mas-store.js';

// Initialize (once per app)
await masStore.init({ projectId: branchId });

// CRUD
await masStore.save('table_name', { id: '...', field: 'value' });
await masStore.get('table_name', id);
await masStore.delete('table_name', id);
await masStore.query('table_name', { field: 'value' });

// Sync
await masStore.sync(['table1', 'table2']);

// Events
masStore.on('change', ({ table, record_id, action, delta }) => { });
```

### Data Flow
Browser IndexedDB ←→ mas-store ←→ WebSocket ←→ WS3 Server ←→ PostgreSQL

### Module Rules
- NEVER use fetch() directly — always masStore
- Save locally first (offline-first)
- Outbox pattern handles sync automatically
- Listen to 'change' events for real-time updates
""",
    "update": """## mas-store Module — UPDATE
Modify data access patterns. Keep masStore API usage consistent.
"""
},

# ─── Schema Definition ───
"config-schema": {
    "create": """## Classification: Schema Definition (📐)

You are defining database tables that will be auto-created per branch.

### Output Format
```json
{
  "tables": [
    {
      "name": "table_name",
      "fields": [
        {"name": "id", "type": "uuid", "primary": true, "required": true},
        {"name": "field_name", "type": "string", "required": true},
        {"name": "amount", "type": "money"},
        {"name": "status", "type": "string", "default": "active"},
        {"name": "metadata", "type": "json", "default": {}},
        {"name": "created_at", "type": "datetime", "required": true},
        {"name": "updated_at", "type": "datetime", "required": true}
      ]
    }
  ]
}
```

### Types: string, number, integer, boolean, date, datetime, json, uuid, money, text
### Rules: Always include id + created_at + updated_at. Use snake_case.
""",
    "update": "Add fields to existing table schema. Keep all existing fields. Return complete JSON."
},

# ─── Shared Domain ───
"shared-domain": {
    "create": """## Classification: Domain Logic (🧠)

You are writing PURE FUNCTIONS shared between frontend and backend.

### Rules
1. NO side effects (no DB, no fetch, no DOM)
2. NO imports except other domain modules
3. Functions take inputs and return outputs — that's it
4. Export each function individually (named exports)
5. Include JSDoc types for parameters

### Pattern
```javascript
export function calculateTotal(items) {
    return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}

export function validateTransition(current, next) {
    const allowed = { draft: ['active'], active: ['closed'] };
    return (allowed[current] || []).includes(next);
}
```
""",
    "update": "Add new functions at the end. Do not modify existing functions. Return complete code."
}
}

# ═══════════════════════════════════════════════════════════════════════
# PLANNER AGENT PROMPT
# ═══════════════════════════════════════════════════════════════════════

PLANNER_PROMPT = """## QDML Planner Agent

You are the orchestrator. You receive a complex task and break it into micro-tasks.

### Your Job
1. Analyze the request
2. Identify which CLASSIFICATIONS are involved
3. Break into ordered micro-tasks (each one classification, one component)
4. For UPDATE tasks: identify which components need mini_code
5. Output a plan as JSON

### Output Format
```json
{
  "plan_name": "Brief description",
  "tasks": [
    {
      "order": 1,
      "type": "create|update|structure",
      "classification": "mas-screen|node-engine|...",
      "target": "project/module/component",
      "description": "What this task does",
      "depends_on": [],
      "needs_mini_code": false
    }
  ]
}
```

### Rules
- Each task = ONE classification, ONE component
- Tasks can depend on previous tasks (by order number)
- Frontend and backend tasks are separate
- If task needs to see existing code, set needs_mini_code: true
- Order: structure → backend → frontend (dependencies flow down)
"""


async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    print("═══ Rebuilding AI Instructions (Complete) ═══\n")

    # Clear old prompts
    await conn.execute(f"DELETE FROM {QDML_SCHEMA}.ai_prompt_library")
    print("  🗑️  Cleared old prompts")

    # Insert comprehensive prompts
    count = 0
    for classification, tasks in CLASSIFICATION_PROMPTS.items():
        for task_type, prompt_text in tasks.items():
            # Combine: protocol base + task instructions + classification specific
            full_system_prompt = QDML_PROTOCOL_BASE + "\n" + TASK_INSTRUCTIONS.get(task_type, "") + "\n" + prompt_text

            await conn.execute(f"""
                INSERT INTO {QDML_SCHEMA}.ai_prompt_library
                (classification, task_type, system_prompt, user_instructions, required_context, md_attachments)
                VALUES ($1, $2, $3, $4, '[]'::jsonb, '[]'::jsonb)
                ON CONFLICT (classification, task_type) DO UPDATE SET system_prompt = $3, user_instructions = $4
            """, classification, task_type, full_system_prompt,
                TASK_INSTRUCTIONS.get(task_type, ""))
            count += 1

    # Add planner prompt
    await conn.execute(f"""
        INSERT INTO {QDML_SCHEMA}.ai_prompt_library
        (classification, task_type, system_prompt, user_instructions, required_context, md_attachments)
        VALUES ('_planner', 'plan', $1, $2, '[]'::jsonb, '[]'::jsonb)
        ON CONFLICT (classification, task_type) DO UPDATE SET system_prompt = $1
    """, QDML_PROTOCOL_BASE + "\n" + PLANNER_PROMPT, "Break the request into micro-tasks.")
    count += 1

    print(f"  ✅ {count} comprehensive prompts registered")

    # Show summary
    prompts = await conn.fetch(f"""
        SELECT classification, task_type, length(system_prompt) as chars
        FROM {QDML_SCHEMA}.ai_prompt_library ORDER BY classification, task_type
    """)

    print(f"\n📋 Prompt Library ({len(prompts)} entries):")
    for p in prompts:
        print(f"   {p['classification']:25} {p['task_type']:10} {p['chars']:5} chars")

    total_chars = sum(p['chars'] for p in prompts)
    print(f"\n   Total instruction content: {total_chars:,} characters")

    await conn.close()
    print("\n✅ AI Instructions complete and comprehensive")


if __name__ == "__main__":
    asyncio.run(main())
