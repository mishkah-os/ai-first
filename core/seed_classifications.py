#!/usr/bin/env python3
"""Seed classification registry + AI prompt library"""
import asyncio
import asyncpg
import json
from config import DATABASE_URL, QDML_SCHEMA

CLASSIFICATIONS = [
    ("mas-screen", "MAS.js Screen", "شاشة MAS.js", "🖥️", "Full page screen using MAS.js", ["mas-js","css"], ["mas-quickstart.md"]),
    ("mas-widget", "MAS.js Widget", "مكون MAS.js", "🧩", "Reusable widget", ["mas-js"], ["mas-quickstart.md"]),
    ("mas-screen-dashboard", "Dashboard Screen", "شاشة داشبورد", "📊", "Dashboard using Dashboard Kit", ["mas-js","css","dashboard-kit"], ["mas-quickstart.md","dashboard-kit.md"]),
    ("mas-screen-mobile", "Mobile Screen", "شاشة موبايل", "📱", "Mobile using Mobile Kit", ["mas-js","css","mobile-kit"], ["mas-quickstart.md","mobile-kit.md"]),
    ("mas-store-module", "mas-store Module", "وحدة تخزين", "💾", "Data layer connecting to WS3", ["mas-store","ws3"], ["mas-store.md"]),
    ("css-theme", "CSS Theme", "ستايلات", "🎨", "CSS module for styling", ["css"], []),
    ("node-service", "Node.js Service", "خدمة Node", "⚙️", "Backend Node.js service", ["node","ws3"], ["quantum-crud.md"]),
    ("node-engine", "Business Engine", "محرك أعمال", "🏭", "Schema-driven business engine", ["node","postgresql"], ["quantum-crud.md","schema-driven.md"]),
    ("ws3-handler", "WS3 Handler", "معالج WebSocket", "🔌", "WebSocket real-time handler", ["node","ws3"], ["ws3-protocol.md"]),
    ("python-api", "Python API", "واجهة برمجية", "🐍", "FastAPI endpoint", ["python","fastapi"], []),
    ("config-schema", "Schema Definition", "تعريف مخطط", "📐", "Database schema (JSON)", ["json","postgresql"], ["schema-driven.md"]),
    ("config-service", "Service Config", "إعدادات خدمة", "⚡", "Port, env, nginx config", ["yaml","env"], []),
    ("config-deploy", "Deploy Config", "إعدادات نشر", "🚀", "Docker, systemd config", ["docker","nginx"], []),
    ("shared-domain", "Domain Logic", "منطق مشترك", "🧠", "Pure functions shared front+back", ["javascript"], []),
]

PROMPTS = [
    ("mas-screen", "create",
     "You are building a screen for QDML Platform using MAS.js.\n\nRules:\n- Function-based components\n- Single state object\n- Event handling via data-action\n- Arabic RTL (dir=\"rtl\")\n- Use masStore for data\n- CSS custom properties\n- Functions < 30 lines\n- Descriptive English names\n- Export default object with init() and render()\n\nPattern:\nconst Screen = {\n    state: {},\n    async init(branchId) {},\n    render() { return `<div>...</div>`; }\n};\nexport default Screen;",
     "Create a new screen. Generate complete working code.",
     '["project_slug","module_slug","component_slug"]',
     '["mas-quickstart.md"]'),

    ("mas-screen", "update",
     "You are modifying an existing MAS.js screen.\n\nRules:\n- Preserve ALL existing functionality\n- Same coding style\n- Do not remove imports/exports\n- Return COMPLETE modified code",
     "Modify the code. Return full updated code.",
     '["current_code","modification_request"]',
     '[]'),

    ("mas-screen-dashboard", "create",
     "You are building a dashboard using QDML Dashboard Kit.\n\nRules:\n- Use DashboardLayout for shell\n- StatsCard for metrics\n- DataTable for tables\n- Arabic RTL\n- Connect to masStore\n- Include refresh\n\nWidgets: StatsCard, DataTable, ChartWidget\nLayout: DashboardLayout({ logo, appName, menuItems, user, pageTitle })",
     "Create dashboard. User describes metrics/tables.",
     '["project_slug","module_slug"]',
     '["mas-quickstart.md","dashboard-kit.md"]'),

    ("mas-screen-mobile", "create",
     "You are building a mobile screen using QDML Mobile Kit.\n\nRules:\n- MobileShell for shell\n- AuthScreens for auth\n- Arabic RTL\n- Touch-friendly (44px min)\n- Offline-first\n\nAvailable: MobileShell, AuthScreens, ProductCard",
     "Create mobile screen.",
     '["project_slug","module_slug"]',
     '["mas-quickstart.md","mobile-kit.md"]'),

    ("node-engine", "create",
     "You are building a schema-driven engine for QDML.\n\nRules:\n- Receives SchemaCRUD + branchId\n- ALL DB via this.crud (never raw SQL)\n- Async methods\n- crypto.randomUUID() for IDs\n- Export single class\n- Each method does ONE thing\n\nPattern:\nexport class Engine {\n    constructor(crud, branchId) { this.crud = crud; this.branchId = branchId; }\n    async method(data) { return await this.crud.create(...); }\n}",
     "Create backend engine.",
     '["project_slug","schema_tables"]',
     '["quantum-crud.md"]'),

    ("node-engine", "update",
     "You are modifying a schema-driven engine.\n\nRules:\n- Preserve all methods\n- Same class structure\n- Add new methods at end\n- Return COMPLETE code",
     "Modify engine. Return full code.",
     '["current_code","modification_request"]',
     '[]'),

    ("config-schema", "create",
     "You are defining a database schema.\n\nRules:\n- Valid JSON: {name, fields: [{name, type, required, primary, default}]}\n- Types: string, number, integer, boolean, date, datetime, json, uuid, money\n- Always include: id (uuid), created_at, updated_at\n- snake_case names",
     "Define schema tables/fields.",
     '["project_slug"]',
     '["schema-driven.md"]'),

    ("mas-screen", "structure",
     "You are designing project structure.\n\nOutput JSON:\n{\"modules\": [{\"name\", \"slug\", \"tier\": \"frontend|backend|shared\", \"components\": [{\"name\", \"slug\", \"classification\", \"description\"}]}]}\n\nRules:\n- Max 5 modules, 5 components each\n- classification must match registry codes\n- Descriptions human-readable",
     "Design project structure.",
     '["project_slug","project_description"]',
     '[]'),
]

PROJECT_ICONS = {
    "mas-front": "🎨", "platform-core": "⚡", "kits": "📦",
    "erp": "💼", "mas-saas": "☁️", "mostamal-hawaa": "🛍️", "pos": "🍽️"
}


async def main():
    conn = await asyncpg.connect(DATABASE_URL)

    print("═══ Seeding Classifications ═══")
    for code, name, name_ar, icon, desc, stack, docs in CLASSIFICATIONS:
        await conn.execute(f"""
            INSERT INTO {QDML_SCHEMA}.classification_registry (code, name, name_ar, icon, description, stack, md_docs)
            VALUES ($1,$2,$3,$4,$5,$6::jsonb,$7::jsonb)
            ON CONFLICT (code) DO UPDATE SET name=$2, name_ar=$3, icon=$4, description=$5, stack=$6::jsonb, md_docs=$7::jsonb
        """, code, name, name_ar, icon, desc, json.dumps(stack), json.dumps(docs))
    print(f"  ✅ {len(CLASSIFICATIONS)} classifications")

    print("\n═══ Seeding AI Prompt Library ═══")
    for classification, task_type, system_prompt, instructions, ctx, mds in PROMPTS:
        await conn.execute(f"""
            INSERT INTO {QDML_SCHEMA}.ai_prompt_library (classification, task_type, system_prompt, user_instructions, required_context, md_attachments)
            VALUES ($1,$2,$3,$4,$5::jsonb,$6::jsonb)
            ON CONFLICT (classification, task_type) DO UPDATE SET system_prompt=$3, user_instructions=$4, required_context=$5::jsonb, md_attachments=$6::jsonb
        """, classification, task_type, system_prompt, instructions, ctx, mds)
    print(f"  ✅ {len(PROMPTS)} prompt templates")

    print("\n═══ Project Icons ═══")
    for slug, icon in PROJECT_ICONS.items():
        await conn.execute(f"UPDATE {QDML_SCHEMA}.project SET icon=$1 WHERE slug=$2", icon, slug)
    print(f"  ✅ {len(PROJECT_ICONS)} icons set")

    await conn.close()
    print("\n✅ Foundation ready for AI-first workflow")


if __name__ == "__main__":
    asyncio.run(main())
