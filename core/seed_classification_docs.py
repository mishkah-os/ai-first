#!/usr/bin/env python3
"""
Fill classification_registry with complete documentation:
- ai_instructions_md: concise AI-facing instructions
- human_docs_ar: Arabic explanation for developers
- human_docs_en: English detailed docs for developers
"""
import asyncio
import asyncpg
from config import DATABASE_URL, QDML_SCHEMA

DOCS = {
"mas-screen": {
    "ai_instructions_md": """# MAS.js Screen
- Export default object with: state, init(branchId), render(), methods
- Use masStore for data. Never fetch() directly.
- Events: onclick="ObjName.method(event)"
- Render returns HTML string. Call this.render() after state changes.
- Arabic RTL: dir="rtl" on root element
- Loading/error states required""",

    "human_docs_ar": """# شاشة MAS.js 🖥️

## ما هي؟
شاشة كاملة تعمل بإطار MAS.js — تتصل بالبيانات عبر mas-store وتعرض واجهة تفاعلية.

## كيف تعمل؟
1. `init(branchId)` — تتصل بالفرع وتحمّل البيانات
2. `state` — كل البيانات في كائن واحد
3. `render()` — تعيد HTML كنص وتضعه في الصفحة
4. الأحداث عبر `onclick="Screen.method(event)"`
5. أي تغيير في state → استدعي render() مرة أخرى

## مثال بسيط
```javascript
const MyScreen = {
    state: { items: [], loading: true },
    async init(branchId) {
        await masStore.init({ projectId: branchId });
        this.state.items = await masStore.query('my_table', {});
        this.state.loading = false;
        this.render();
    },
    render() {
        document.getElementById('app').innerHTML = `
        <div dir="rtl">${this.state.loading ? 'جاري...' : this.state.items.length + ' عنصر'}</div>`;
    }
};
```

## قواعد مهمة
- لا تستخدم fetch مباشرة — دائماً masStore
- الحالة (state) كائن واحد مسطح
- RTL دائماً
- أضف حالة التحميل وحالة الخطأ""",

    "human_docs_en": """# MAS.js Screen 🖥️

## What is it?
A full-page screen component built with MAS.js framework. Connects to data via mas-store and renders interactive UI.

## Architecture
```
Screen.init(branchId)
  → masStore.init() (connects WebSocket to branch)
  → masStore.query() (loads data from IndexedDB/WS)
  → this.render() (generates HTML, inserts into DOM)

User interaction:
  → onclick handler → modify state → this.render()

Real-time updates:
  → masStore.on('change') → reload affected data → this.render()
```

## Component Structure
- `state: {}` — Single reactive data object
- `init(branchId)` — Setup and initial data load
- `render()` — Returns HTML string, updates DOM
- `loadData()` — Fetches data from masStore
- `handleX(event)` — Event handlers

## Data Access (mas-store API)
```javascript
await masStore.save('table', { id, ...fields });
await masStore.get('table', id);
await masStore.query('table', { status: 'active' });
await masStore.delete('table', id);
masStore.on('change', ({ table, action, delta }) => {});
```

## Rules
1. Never use fetch() — always masStore
2. State is one flat object — never deeply nested
3. Always include loading + error states
4. Arabic RTL support (dir="rtl")
5. Functions named in English camelCase
6. Each render sub-method (renderHeader, renderList) for complex UIs
"""
},

"node-engine": {
    "ai_instructions_md": """# Business Engine
- Export single class with constructor(crud, branchId)
- ALL DB through this.crud: create/read/update/delete/list
- Never write raw SQL
- IDs: crypto.randomUUID()
- Validate at start of each method
- Throw errors, never return null silently""",

    "human_docs_ar": """# محرك أعمال 🏭

## ما هو؟
كلاس يحتوي على منطق الأعمال. لا يتصل بقاعدة البيانات مباشرة — يستخدم SchemaCRUD الذي يولّد الاستعلامات تلقائياً من Schema.

## كيف يعمل؟
1. يستلم `crud` (خدمة CRUD) و `branchId` (معرف الفرع)
2. كل عملية تمر عبر: `this.crud.create(branch, table, data)`
3. لا SQL مكتوب يدوياً — الكل من Schema

## مثال
```javascript
class OrderEngine {
    constructor(crud, branchId) {
        this.crud = crud;
        this.branchId = branchId;
    }
    async createOrder(data) {
        if (!data.customer_name) throw new Error('الاسم مطلوب');
        return await this.crud.create(this.branchId, 'order_header', {
            id: crypto.randomUUID(),
            ...data,
            status: 'new'
        });
    }
}
```

## أوامر CRUD المتاحة
- `create(branch, table, data)` → يُنشئ سجل
- `read(branch, table, id)` → يقرأ سجل
- `update(branch, table, id, data)` → يحدّث
- `delete(branch, table, id)` → يحذف
- `list(branch, table, { where, sort, limit })` → يسرد""",

    "human_docs_en": """# Business Engine 🏭

## What is it?
A class that contains business logic. It does NOT connect to the database directly — it uses SchemaCRUD which auto-generates queries from the schema definition.

## Why schema-driven?
- Add a field to schema → CRUD handles it automatically
- No SQL to maintain
- Works across all branches (each has its own schema)
- Type coercion handled by CRUD layer

## Pattern
```javascript
export class EngineName {
    constructor(crud, branchId) {
        this.crud = crud;         // SchemaCRUD instance
        this.branchId = branchId; // Branch identifier
    }

    async createRecord(data) {
        // 1. Validate
        if (!data.name) throw new Error('name required');

        // 2. Build record
        const record = {
            id: crypto.randomUUID(),
            ...data,
            status: 'active',
            created_at: new Date().toISOString()
        };

        // 3. Save (CRUD generates INSERT from schema)
        return await this.crud.create(this.branchId, 'table_name', record);
    }
}
```

## CRUD Methods
| Method | Purpose | Signature |
|--------|---------|-----------|
| create | Insert new record | crud.create(branch, table, data) |
| read | Get by ID | crud.read(branch, table, id) |
| update | Partial update | crud.update(branch, table, id, changes) |
| delete | Remove | crud.delete(branch, table, id) |
| list | Query with filters | crud.list(branch, table, {where, sort, order, limit, offset}) |
"""
},

"mas-screen-dashboard": {
    "ai_instructions_md": """# Dashboard Screen
- Use DashboardLayout for shell (sidebar+header)
- StatsCard for metrics grid (4 columns)
- DataTable for data lists
- Auto-refresh every 30s
- Show trends with change% on StatsCards
- Arabic labels, English code""",

    "human_docs_ar": """# شاشة داشبورد 📊

## ما هي؟
لوحة تحكم إدارية تعرض إحصائيات ومقاييس وجداول بيانات.
تستخدم Dashboard Kit الذي يوفر مكونات جاهزة.

## المكونات المتاحة
- `DashboardLayout` — الهيكل (قائمة جانبية + هيدر + محتوى)
- `StatsCard` — بطاقة رقم (المبيعات، الطلبات...)
- `DataTable` — جدول بيانات مع بحث وصفحات
- `ChartWidget` — رسم بياني

## البنية
```
┌─ Sidebar ─┐ ┌─────── Main ──────────┐
│ Logo      │ │ Header (title + search)│
│ Menu      │ ├────────────────────────┤
│ - Dashboard│ │ [Stats] [Stats] [Stats]│
│ - Orders   │ │ ┌─ Table ──────────┐  │
│ - Settings │ │ │ ...              │  │
│           │ │ └──────────────────┘  │
└───────────┘ └────────────────────────┘
```""",

    "human_docs_en": """# Dashboard Screen 📊

Built using Dashboard Kit components. Shows real-time metrics and data tables.

## Components
- `StatsCard({ label, value, icon, color, change })` — Metric card
- `DataTable({ title, columns, data, pageSize })` — Sortable table
- `ChartWidget({ title, type, data })` — Chart visualization
- `DashboardLayout(config)` — Full page layout with sidebar

## Data loading pattern
Load aggregated stats from masStore, refresh periodically.
"""
},

"mas-screen-mobile": {
    "ai_instructions_md": """# Mobile Screen
- MobileShell wraps the page (header+tabs+sidemenu)
- Touch targets 44px minimum
- Offline-first (show cached data)
- Pull-to-refresh for lists
- Bottom tabs for navigation
- RTL Arabic support""",

    "human_docs_ar": """# شاشة موبايل 📱

شاشة لتطبيق جوال. تستخدم Mobile Kit.
- هيدر علوي + تابات سفلية + قائمة جانبية
- تصميم لمسي (أزرار كبيرة 44px)
- تعمل بدون إنترنت (تعرض البيانات المخزنة)
- سحب للتحديث في القوائم""",

    "human_docs_en": """# Mobile Screen 📱

Mobile-first screen using Mobile Kit. Includes shell (header, bottom tabs, side menu).
Touch-friendly, offline-first, pull-to-refresh lists.
"""
},

"ws3-handler": {
    "ai_instructions_md": """# WS3 Handler
- Handles WebSocket messages by type
- Routes by branch_id (branch isolation)
- Broadcasts changes to same-branch clients only
- Async message processing
- Never block event loop""",

    "human_docs_ar": """# معالج WebSocket 🔌

يعالج رسائل WebSocket ويوجهها حسب الفرع.
كل فرع له قناة منفصلة — التغييرات لا تتسرب.

## تدفق الرسائل
1. العميل يرسل `{ type: 'crud', branch_id, table, action, data }`
2. المعالج يتحقق من الفرع
3. ينفذ العملية عبر SchemaCRUD
4. يبث النتيجة لكل عملاء نفس الفرع""",

    "human_docs_en": """# WS3 Handler 🔌

Processes WebSocket messages and routes them by branch.
Each branch is isolated — changes never leak between branches.
Broadcasts real-time updates to all clients on the same branch channel.
"""
},

"mas-store-module": {
    "ai_instructions_md": """# mas-store Module
- import masStore from '/lib/mas-store.js'
- CRUD: save/get/delete/query
- Events: masStore.on('change', handler)
- Offline-first: saves locally, syncs via WS
- Never use fetch() directly""",

    "human_docs_ar": """# وحدة mas-store 💾

طبقة البيانات الموحدة. تحفظ محلياً (IndexedDB) وتزامن عبر WebSocket.

## الأوامر
```javascript
await masStore.save('table', { id, ...data });
await masStore.get('table', id);
await masStore.query('table', { filter });
await masStore.delete('table', id);
masStore.on('change', callback);
```""",

    "human_docs_en": """# mas-store Module 💾

Unified data layer. Saves locally to IndexedDB, syncs via WebSocket to PostgreSQL.
Offline-first: works without internet, syncs when reconnected.
"""
},

"config-schema": {
    "ai_instructions_md": """# Schema Definition
- JSON format: { tables: [{ name, fields: [{ name, type, required }] }] }
- Types: string, number, integer, boolean, date, datetime, json, uuid, money
- Always: id (uuid) + created_at + updated_at
- snake_case names""",

    "human_docs_ar": """# تعريف مخطط 📐

يحدد هيكل جداول قاعدة البيانات. يُستخدم لتوليد DDL تلقائياً لكل فرع.""",

    "human_docs_en": """# Schema Definition 📐

Defines database table structure in JSON. Used by BranchManager to auto-generate PostgreSQL DDL per branch.
"""
},

"shared-domain": {
    "ai_instructions_md": """# Domain Logic
- Pure functions only (no side effects)
- No imports except other domain modules
- Named exports for each function
- Used by both frontend and backend""",

    "human_docs_ar": """# منطق مشترك 🧠

دوال نقية (pure functions) تُستخدم في الفرونت والباك.
لا تتصل بقاعدة بيانات ولا DOM — فقط حسابات ومنطق.""",

    "human_docs_en": """# Shared Domain Logic 🧠

Pure functions shared between frontend and backend. No side effects, no DB, no DOM.
Calculate totals, validate transitions, format data.
"""
},

"css-theme": {
    "ai_instructions_md": """# CSS Theme
- Use CSS custom properties (--primary, --radius, etc)
- RTL support: margin-inline-start not margin-left
- Dark mode: [data-theme='dark'] selectors
- Mobile-first responsive""",

    "human_docs_ar": """# ستايلات 🎨
CSS للتصميم. يدعم RTL والوضع المظلم والموبايل.""",
    "human_docs_en": """# CSS Theme 🎨
Styling module. Supports RTL, dark mode, and responsive design using CSS custom properties."""
},

"config-service": {
    "ai_instructions_md": "# Service Config\nPort, env vars, health check, startup command.",
    "human_docs_ar": "# إعدادات خدمة ⚡\nمنفذ الخدمة ومتغيرات البيئة وأمر التشغيل.",
    "human_docs_en": "# Service Config ⚡\nDefines port, environment variables, health check URL, and startup command for a service."
},

"config-deploy": {
    "ai_instructions_md": "# Deploy Config\nDocker, nginx, systemd configuration.",
    "human_docs_ar": "# إعدادات نشر 🚀\nملفات Docker و nginx و systemd.",
    "human_docs_en": "# Deploy Config 🚀\nDeployment configuration: Dockerfiles, nginx sites, systemd service units."
},

"node-service": {
    "ai_instructions_md": """# Node.js Service
- Standalone Node.js service (not engine)
- May have its own HTTP or WS listener
- Used for infrastructure (printer, sync, gateway)""",
    "human_docs_ar": "# خدمة Node.js ⚙️\nخدمة مستقلة (طابعة، بوابة، مزامنة).",
    "human_docs_en": "# Node.js Service ⚙️\nStandalone service for infrastructure: printer bridge, sync gateway, etc."
},

"python-api": {
    "ai_instructions_md": "# Python API\nFastAPI endpoint. Uses asyncpg for PostgreSQL.",
    "human_docs_ar": "# واجهة Python 🐍\nنقطة وصول FastAPI.",
    "human_docs_en": "# Python API 🐍\nFastAPI endpoint using asyncpg for database access."
},

"mas-widget": {
    "ai_instructions_md": """# MAS Widget
- Reusable component (not full page)
- Returns HTML string from a function
- Accepts props as parameters
- Stateless preferred""",
    "human_docs_ar": "# مكون MAS.js 🧩\nمكون قابل لإعادة الاستخدام (ليس صفحة كاملة).",
    "human_docs_en": "# MAS.js Widget 🧩\nReusable component. Function that returns HTML. Accepts props, returns rendered output."
}
}

async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    print("═══ Filling Classification Documentation ═══\n")

    count = 0
    for code, docs in DOCS.items():
        await conn.execute(f"""
            UPDATE {QDML_SCHEMA}.classification_registry
            SET ai_instructions_md = $1,
                human_docs_ar = $2,
                human_docs_en = $3
            WHERE code = $4
        """, docs["ai_instructions_md"], docs["human_docs_ar"], docs["human_docs_en"], code)
        count += 1
        print(f"  ✅ {code}: AI({len(docs['ai_instructions_md'])}c) AR({len(docs['human_docs_ar'])}c) EN({len(docs['human_docs_en'])}c)")

    print(f"\n✅ {count} classifications fully documented")

    # Summary
    total = await conn.fetch(f"""
        SELECT code, icon, length(ai_instructions_md) as ai, length(human_docs_ar) as ar, length(human_docs_en) as en
        FROM {QDML_SCHEMA}.classification_registry ORDER BY code
    """)
    print(f"\n📋 Documentation Summary:")
    print(f"   {'Code':<25} {'Icon':<4} {'AI':>5} {'AR':>5} {'EN':>5}")
    for r in total:
        print(f"   {r['code']:<25} {r['icon']:<4} {r['ai'] or 0:>5} {r['ar'] or 0:>5} {r['en'] or 0:>5}")

    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())
