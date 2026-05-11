"""Bootstrap: Register the full system tree in PostgreSQL."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

# Full system tree: module -> [(name, slug, kind, target)]
TREE = {
    "quantum-core": ("C++ ORM Core", 1, [
        ("String Utils",        "str-utils",        "library", "cpp"),
        ("JSON Helpers",        "json-helpers",     "library", "cpp"),
        ("Column Meta",         "column-meta",      "library", "cpp"),
        ("Alias Resolver",      "alias-resolver",   "library", "cpp"),
        ("Value Normalizer",    "value-normalizer", "library", "cpp"),
        ("Filter Engine",       "filter-engine",    "library", "cpp"),
        ("Query Builder",       "query-builder",    "library", "cpp"),
        ("Row Normalizer",      "row-normalizer",   "library", "cpp"),
        ("PG Runtime",          "pg-runtime",       "library", "cpp"),
        ("CRUD Handler",        "crud-handler",     "library", "cpp"),
        ("Routine Handler",     "routine-handler",  "library", "cpp"),
        ("Change Logger",       "change-logger",    "library", "cpp"),
        ("HTTP Listener",       "http-listener",    "service", "cpp"),
    ]),
    "api-gateway": ("Python API Gateway", 2, [
        ("Config",              "api-config",       "library", "python"),
        ("Auth Models",         "auth-models",      "library", "python"),
        ("Auth Service",        "auth-service",     "service", "python"),
        ("Permission Gate",     "perm-gate",        "library", "python"),
        ("Route Registry",      "route-registry",   "service", "python"),
        ("CPP Proxy",           "cpp-proxy",        "service", "python"),
        ("Health Check",        "health-check",     "service", "python"),
        ("App Entry",           "api-entry",        "service", "python"),
    ]),
    "ws-relay": ("Node.js WS Relay", 3, [
        ("WS Server",           "ws-server",        "service", "node"),
        ("Client Manager",      "client-mgr",       "library", "node"),
        ("Delta Engine",        "delta-engine",     "service", "node"),
        ("PubSub",              "pubsub",           "service", "node"),
        ("PG Listener",         "pg-listener",      "service", "node"),
    ]),
    "mas-core": ("MAS Core Framework", 4, [
        ("VDOM Engine",         "vdom-engine",      "library", "mas-js"),
        ("DSL Factory",         "dsl-factory",      "library", "mas-js"),
        ("App Factory",         "app-factory",      "library", "mas-js"),
        ("Event Delegator",     "event-delegator",  "library", "mas-js"),
        ("i18n Runtime",        "i18n-runtime",     "library", "mas-js"),
    ]),
    "mas-data": ("MAS Data Store", 5, [
        ("HTTP Client",         "http-client",      "library", "mas-js"),
        ("Data Store",          "data-store",       "library", "mas-js"),
        ("WS Client",           "ws-client",        "library", "mas-js"),
        ("Sync Engine",         "sync-engine",      "library", "mas-js"),
    ]),
    "mas-ui": ("MAS UI Kit", 6, [
        ("Button",              "ui-button",        "widget", "mas-js"),
        ("Input",               "ui-input",         "widget", "mas-js"),
        ("Select",              "ui-select",        "widget", "mas-js"),
        ("Table",               "ui-table",         "widget", "mas-js"),
        ("Modal",               "ui-modal",         "widget", "mas-js"),
        ("Drawer",              "ui-drawer",        "widget", "mas-js"),
        ("Tabs",                "ui-tabs",          "widget", "mas-js"),
        ("Toast",               "ui-toast",         "widget", "mas-js"),
        ("Card",                "ui-card",          "widget", "mas-js"),
        ("Form",                "ui-form",          "widget", "mas-js"),
        ("Theme Switcher",      "ui-theme",         "widget", "mas-js"),
        ("Lang Switcher",       "ui-lang",          "widget", "mas-js"),
    ]),
}

async def main():
    e = CoreEngine(DSN)
    await e.connect()
    await e.init_schema()
    await e.wipe()
    print("DB wiped. Registering tree...\n")

    total_comps = 0
    for slug, (name, order, comps) in TREE.items():
        mid = await e.create_module(name, slug, sort_order=order)
        print(f"  Module: {name} ({slug}) id={mid}")
        for cname, cslug, kind, target in comps:
            cid = await e.create_component(slug, cname, cslug, kind=kind, target=target)
            print(f"    + {cname} [{target}] id={cid}")
            total_comps += 1

    print(f"\nTree registered: {len(TREE)} modules, {total_comps} components")

    # Verify
    tree = await e.describe()
    print(f"\n{'='*50}")
    for mod in tree:
        print(f"\n  {mod['module']} ({mod['slug']})")
        for c in mod["components"]:
            print(f"    - {c['name']} [{c['target']}] ({c['kind']})")

    counts = await e.count()
    print(f"\nDB: {counts}")
    await e.close()

if __name__ == "__main__":
    asyncio.run(main())
