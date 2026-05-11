"""
QDML Master Build — Complete system generation.
Creates EVERYTHING from scratch: JS, CSS, HTML, MD docs.
All output goes to mas-front/_generated/
Fixes: CSS markers use /* */ not //
"""
import sys, os, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from qdml_engine import QDMLEngine

MAS_FRONT = os.path.join(os.path.dirname(__file__), "..", "mas-front")
MAS_CORE = os.path.join(MAS_FRONT, "mas.core.js")
MAS_TOKENS = os.path.join(MAS_FRONT, "mas.tokens.css")
MAS_QUICK = os.path.join(MAS_FRONT, "quickstart.html")
OUTPUT = os.path.join(MAS_FRONT, "_generated")

BULK_JS = [
    {"name":"umd_open",           "start":1,   "end":5,    "exports":"","depends":"","reveal":"0:4"},
    {"name":"constants",          "start":7,   "end":13,   "exports":"VOID,SVG_TAGS,HEAD_ONLY,RTL_LANGS","depends":"","reveal":"0:6"},
    {"name":"hooks",              "start":15,  "end":18,   "exports":"hook,emit","depends":"","reveal":"0:3"},
    {"name":"i18n",               "start":20,  "end":30,   "exports":"t","depends":"","reveal":"0:1,3,8:10"},
    {"name":"component_registry", "start":32,  "end":56,   "exports":"component,resolveComponent,prefixGkey","depends":"","reveal":"0:1,3:5"},
    {"name":"module_system",      "start":58,  "end":124,  "exports":"createModuleD,createModuleCtx,registerModule","depends":"component_registry","reveal":"0:2,14:16"},
    {"name":"vdom_core",          "start":126, "end":209,  "exports":"h,normKids,D,_dHelpers","depends":"component_registry","reveal":"0:2,35:36,80:81"},
    {"name":"head_manager",       "start":210, "end":254,  "exports":"Head","depends":"","reveal":"0:2,14:15"},
    {"name":"render_engine",      "start":256, "end":313,  "exports":"render,setProps","depends":"constants,head_manager","reveal":"0:2,24:25"},
    {"name":"patch_engine",       "start":315, "end":397,  "exports":"same,patch,patchKids","depends":"render_engine,head_manager","reveal":"0:3,40:42"},
    {"name":"scroll_env",         "start":399, "end":434,  "exports":"captureScroll,restoreScroll,applyEnv","depends":"constants","reveal":"0:2,25:26"},
    {"name":"delegation",         "start":436, "end":497,  "exports":"parseOrders,delegate,KNOWN_EVENTS","depends":"hooks","reveal":"0:8,26:28"},
    {"name":"app_factory",        "start":499, "end":695,  "exports":"createApp","depends":"module_system,vdom_core,render_engine,patch_engine,scroll_env,delegation","reveal":"0:2,140:143","overflow":True},
    {"name":"hydration",          "start":697, "end":726,  "exports":"hydrateNode","depends":"render_engine","reveal":"0:5"},
    {"name":"lazy_loader",        "start":728, "end":771,  "exports":"load,loaded,lazyModule","depends":"component_registry,module_system","reveal":"0:3"},
    {"name":"ssr",                "start":773, "end":812,  "exports":"renderToString,renderHeadToString","depends":"constants,vdom_core","reveal":"0:5"},
    {"name":"router_exports",     "start":814, "end":905,  "exports":"createRouter,go","depends":"","reveal":"0:3,79:80,88:93"},
]

BULK_CSS = [
    {"name":"reset",       "start":14, "end":16,  "exports":"","depends":"","reveal":"0:2"},
    {"name":"light_vars",  "start":18, "end":86,  "exports":"","depends":"","reveal":"0:3,12:14"},
    {"name":"dark_vars",   "start":88, "end":110, "exports":"","depends":"light_vars","reveal":"0:3"},
    {"name":"typography",  "start":112,"end":119, "exports":"","depends":"","reveal":"0:3"},
    {"name":"card",        "start":121,"end":128, "exports":"","depends":"","reveal":"0:2"},
    {"name":"input",       "start":130,"end":143, "exports":"","depends":"","reveal":"0:2"},
    {"name":"btn_badge",   "start":145,"end":170, "exports":"","depends":"","reveal":"0:3"},
    {"name":"utilities",   "start":172,"end":191, "exports":"","depends":"","reveal":"0:5"},
]

BULK_HTML = [
    {"name":"head",          "start":1,   "end":9,   "exports":"","depends":"","reveal":"0:8"},
    {"name":"shell_module",  "start":10,  "end":24,  "exports":"","depends":"","reveal":"0:3,8:10"},
    {"name":"counter_module","start":26,  "end":54,  "exports":"","depends":"","reveal":"0:3,8:10"},
    {"name":"todo_module",   "start":56,  "end":101, "exports":"","depends":"","reveal":"0:3,8:12"},
    {"name":"body_router",   "start":103, "end":133, "exports":"","depends":"","reveal":"0:3,6:8"},
    {"name":"mount_close",   "start":135, "end":148, "exports":"","depends":"","reveal":"0:13"},
]

def read_lines(p):
    with open(p, "r", encoding="utf-8") as f:
        return f.readlines()

def extract(lines, s, e):
    return "".join(lines[s-1:e])

def marker_open(lang, name):
    if lang == "css": return f"/* m-bulk:{name} */"
    if lang == "html": return f"<!-- m-bulk:{name} -->"
    return f"// m-bulk:{name}"

def marker_close(lang, name):
    if lang == "css": return f"/* m-end:{name} */"
    if lang == "html": return f"<!-- m-end:{name} -->"
    return f"// m-end:{name}"

def compile_with_markers(q, comp_slug, lang):
    cid = q.conn.execute("SELECT id FROM component WHERE slug=?", (comp_slug,)).fetchone()["id"]
    bulks = q.conn.execute("SELECT bulk_name,content FROM pillar WHERE component_id=? AND kind='bulk' ORDER BY bulk_order", (cid,)).fetchall()
    parts = []
    for b in bulks:
        parts.append(marker_open(lang, b["bulk_name"]))
        parts.append(b["content"])
        parts.append(marker_close(lang, b["bulk_name"]))
    return "\n".join(parts)

def main():
    start = time.perf_counter()
    print("=" * 70)
    print("QDML MASTER BUILD — Full System Generation")
    print("=" * 70)

    db_path = os.path.join(os.path.dirname(__file__), "qdml.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    q = QDMLEngine()

    # ═══ PROJECT ═══
    q.create_project("MAS Frontend", "mas-front", "MAS JS V2 Framework")

    # ═══ MODULES ═══
    q.create_module("mas-front", "MAS Core", "mas-core", tier="frontend", app="mas-framework")
    q.create_module("mas-front", "MAS Tokens", "mas-tokens", tier="frontend", app="mas-framework")
    q.create_module("mas-front", "MAS Quickstart", "mas-quickstart", tier="frontend", app="mas-demo")
    q.create_module("mas-front", "MAS Docs", "mas-docs", tier="frontend", app="mas-framework")

    # ═══ COMPONENTS ═══
    q.create_component("mas-core", "MAS Core V2", "mas-core-v2", kind="library", target="mas-js")
    q.create_component("mas-tokens", "MAS Design Tokens", "mas-tokens-css", kind="library", target="css")
    q.create_component("mas-quickstart", "Quickstart Demo", "quickstart-html", kind="screen", target="html")
    q.create_component("mas-docs", "MAS V2 Rules", "mas-v2-rules", kind="doc", target="markdown")
    q.create_component("mas-docs", "MAS API Docs", "mas-api-docs", kind="doc", target="markdown")

    # ═══ JS BULKS ═══
    print("\n[JS] Splitting mas.core.js...")
    js_lines = read_lines(MAS_CORE)
    for i, bk in enumerate(BULK_JS):
        content = extract(js_lines, bk["start"], bk["end"])
        q.create_bulk("mas-core-v2", bk["name"], content, lang="javascript",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"],
            exports=bk["exports"], overflow=bk.get("overflow", False))
    print(f"     17 bulks created from {len(js_lines)} lines")

    # ═══ CSS BULKS ═══
    print("[CSS] Splitting mas.tokens.css...")
    css_lines = read_lines(MAS_TOKENS)
    for i, bk in enumerate(BULK_CSS):
        content = extract(css_lines, bk["start"], bk["end"])
        q.create_bulk("mas-tokens-css", bk["name"], content, lang="css",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"], exports=bk["exports"])
    print(f"     8 bulks created from {len(css_lines)} lines")

    # ═══ HTML BULKS ═══
    print("[HTML] Splitting quickstart.html...")
    html_lines = read_lines(MAS_QUICK)
    for i, bk in enumerate(BULK_HTML):
        content = extract(html_lines, bk["start"], bk["end"])
        q.create_bulk("quickstart-html", bk["name"], content, lang="html",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"], exports=bk["exports"])
    print(f"     6 bulks created from {len(html_lines)} lines")

    # ═══ DOCUMENTATION (stored as bulks) ═══
    print("[MD] Creating documentation...")
    rules_path = os.path.join(os.path.dirname(__file__), "MAS_V2_RULES.md")
    with open(rules_path, "r", encoding="utf-8") as f:
        rules_content = f.read()
    q.create_bulk("mas-v2-rules", "full_doc", rules_content, lang="markdown", bulk_order=0, reveal="0:10")

    api_doc = """# MAS JS V2 — API Reference

## Core API
| Method | Signature | Description |
|--------|-----------|-------------|
| `app` | `app(bodyFn, db, orders)` | Create application instance |
| `component` | `component(name, fn, memo?)` | Register reusable component |
| `module` | `module(name, config)` | Register self-contained module |
| `hook` | `hook(name, fn)` | Subscribe to lifecycle events |
| `router` | `router(app, routes, opts?)` | Create hash/history router |
| `load` | `load(url)` | Lazy-load external script |
| `t` | `t(db, key)` | i18n translation lookup |

## Module Config
```js
module('name', {
  db: {},           // initial state (namespaced)
  persist: [],      // keys auto-saved to localStorage
  orders: {},       // gkey -> handler map
  ui: ($, D) => {}, // render function
  css: '',          // scoped styles (auto-injected)
  fetch: ($) => {}, // auto-called on mount
  memo: false       // skip re-render if props unchanged
})
```

## ctx ($) API
| Method | What |
|--------|------|
| `$.db` | current module state |
| `$.set({k:v})` | merge + re-render |
| `$.push(key, item)` | append to array |
| `$.drop(key, id)` | remove from array |
| `$.patch(key, id, changes)` | update item in array |
| `$.toggle(key)` | flip boolean |
| `$.bind(e)` | auto-bind input by name |
| `$.id(e)` | get data-id from closest parent |
| `$.item(key, e)` | find item by data-id |
| `$.setEnv(k, v)` | set environment variable |

## D (DSL) API
```js
D.div({class:'x'}, [children])  // create element
D.show(condition, vnode)        // conditional render
D.unless(condition, vnode)      // inverse conditional
D.myComponent({props})          // render registered component
D.h('tag', attrs, children)     // explicit tag creation
```

## Lifecycle Hooks
```js
MAS.hook('onRender', ({db, root}) => {})
MAS.hook('onState', ({prev, next}) => {})
MAS.hook('onError', ({error, gkey}) => {})
```
"""
    q.create_bulk("mas-api-docs", "full_doc", api_doc, lang="markdown", bulk_order=0, reveal="0:15")
    print(f"     2 doc components created")

    # ═══ COMPILE & WRITE ═══
    print("\n[COMPILE] Generating all files...")
    os.makedirs(OUTPUT, exist_ok=True)

    files = [
        ("mas.core.js",        q.compile_component("mas-core-v2"),             "js"),
        ("mas.core.marked.js", q.compile_component("mas-core-v2", inject_markers=True), "js"),
        ("mas.tokens.css",     q.compile_component("mas-tokens-css"),          "css"),
        ("mas.tokens.marked.css", q.compile_component("mas-tokens-css", inject_markers=True), "css"),
        ("quickstart.html",    q.compile_component("quickstart-html"),         "html"),
        ("quickstart.marked.html", q.compile_component("quickstart-html", inject_markers=True), "html"),
        ("MAS_V2_RULES.md",   q.compile_component("mas-v2-rules"),            "md"),
        ("API_REFERENCE.md",  q.compile_component("mas-api-docs"),            "md"),
    ]

    for fname, content, ftype in files:
        fpath = os.path.join(OUTPUT, fname)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        lines = content.count('\n') + 1
        size = os.path.getsize(fpath)
        print(f"     {fname:35s} {lines:5d} lines  {size:>8d} bytes")

    # ═══ MINI-CODE ═══
    print("\n[MINI-CODE] Level 1:")
    print("-" * 50)
    print(q.mini("mas-front", level=1))
    print("-" * 50)

    # ═══ METRICS ═══
    print("\n[METRICS]")
    print(f"    {'Operation':<25s} {'Count':>5s} {'OK':>4s} {'Fail':>5s} {'Avg(ms)':>8s} {'Total(ms)':>10s}")
    print("    " + "-" * 60)
    for m in q.metrics():
        print(f"    {m['operation']:<25s} {m['count']:>5d} {m['ok']:>4d} {m['fail']:>5d} {m['avg_ms']:>8.2f} {m['total_ms']:>10.2f}")

    total_ops = sum(m["count"] for m in q.metrics())
    total_time = (time.perf_counter() - start) * 1000
    db_size = os.path.getsize(db_path)

    print(f"\n{'=' * 70}")
    print(f"MASTER BUILD COMPLETE")
    print(f"  Operations: {total_ops} in {total_time:.0f}ms")
    print(f"  DB Size:    {db_size / 1024:.1f} KB")
    print(f"  Files:      {len(files)} generated in _generated/")
    print(f"  Bulks:      JS=17  CSS=8  HTML=6  MD=2  TOTAL=33")
    print(f"{'=' * 70}")

    q.close()

if __name__ == "__main__":
    main()
