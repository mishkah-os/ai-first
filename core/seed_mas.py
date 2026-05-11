"""
Seed MAS JS Framework into PostgreSQL via QDML Engine.
Reads source files and registers them as atomic bulks.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DATABASE_URL, QDML_SCHEMA
import asyncpg
from qdml_engine import QDMLEngine

MAS_FRONT = os.path.join(os.path.dirname(__file__), "..", "mas-front")
MAS_CORE = os.path.join(MAS_FRONT, "mas.core.js")
MAS_TOKENS = os.path.join(MAS_FRONT, "mas.tokens.css")
MAS_QUICK = os.path.join(MAS_FRONT, "quickstart.html")

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


def read_lines(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.readlines()


def extract(lines, start, end):
    return "".join(lines[start-1:end])


async def main():
    print("=" * 60)
    print("QDML SEED — Registering MAS Frontend in PostgreSQL")
    print("=" * 60)

    pool = await asyncpg.create_pool(
        DATABASE_URL,
        min_size=2, max_size=5,
        server_settings={"search_path": f"{QDML_SCHEMA},public"}
    )
    engine = QDMLEngine(pool, schema=QDML_SCHEMA)

    # ═══ PROJECT ═══
    print("\n[1/7] Creating project...")
    project_id = await engine.create_project("MAS Frontend", "mas-front", "MAS JS V2 Framework + Design Tokens + Quickstart")
    print(f"       Project: mas-front ({project_id})")

    # ═══ MODULES ═══
    print("[2/7] Creating modules...")
    await engine.create_module("mas-front", "MAS Core", "mas-core", tier="frontend", app="mas-framework")
    await engine.create_module("mas-front", "MAS Tokens", "mas-tokens", tier="frontend", app="mas-framework")
    await engine.create_module("mas-front", "MAS Quickstart", "mas-quickstart", tier="frontend", app="mas-demo")
    print("       3 modules created")

    # ═══ COMPONENTS ═══
    print("[3/7] Creating components...")
    await engine.create_component("mas-core", "MAS Core V2", "mas-core-v2", kind="library", target="mas-js", project_slug="mas-front")
    await engine.create_component("mas-tokens", "MAS Design Tokens", "mas-tokens-css", kind="library", target="mas-js", project_slug="mas-front")
    await engine.create_component("mas-quickstart", "Quickstart Demo", "quickstart-html", kind="screen", target="mas-js", project_slug="mas-front")
    print("       3 components created")

    # ═══ JS BULKS ═══
    print("[4/7] Registering JavaScript bulks...")
    js_lines = read_lines(MAS_CORE)
    for i, bk in enumerate(BULK_JS):
        content = extract(js_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "mas-core-v2", bk["name"], content, lang="javascript",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"],
            exports=bk["exports"], overflow=bk.get("overflow", False),
            project_slug="mas-front"
        )
    print(f"       {len(BULK_JS)} JS bulks from {len(js_lines)} source lines")

    # ═══ CSS BULKS ═══
    print("[5/7] Registering CSS bulks...")
    css_lines = read_lines(MAS_TOKENS)
    for i, bk in enumerate(BULK_CSS):
        content = extract(css_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "mas-tokens-css", bk["name"], content, lang="css",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"],
            exports=bk["exports"],
            project_slug="mas-front"
        )
    print(f"       {len(BULK_CSS)} CSS bulks from {len(css_lines)} source lines")

    # ═══ HTML BULKS ═══
    print("[6/7] Registering HTML bulks...")
    html_lines = read_lines(MAS_QUICK)
    for i, bk in enumerate(BULK_HTML):
        content = extract(html_lines, bk["start"], bk["end"])
        await engine.create_bulk(
            "quickstart-html", bk["name"], content, lang="html",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"],
            exports=bk["exports"],
            project_slug="mas-front"
        )
    print(f"       {len(BULK_HTML)} HTML bulks from {len(html_lines)} source lines")

    # ═══ COMPILE TEST ═══
    print("[7/7] Testing compilation...")
    js_code = await engine.compile_component("mas-core-v2", project_slug="mas-front")
    css_code = await engine.compile_component("mas-tokens-css", project_slug="mas-front")
    html_code = await engine.compile_component("quickstart-html", project_slug="mas-front")

    print(f"       JS:   {js_code.count(chr(10))+1} lines, {len(js_code)} chars")
    print(f"       CSS:  {css_code.count(chr(10))+1} lines, {len(css_code)} chars")
    print(f"       HTML: {html_code.count(chr(10))+1} lines, {len(html_code)} chars")

    # ═══ STATS ═══
    stats = await engine.stats()
    print(f"\n{'=' * 60}")
    print(f"DONE: {stats['projects']} projects | {stats['modules']} modules | {stats['components']} components | {stats['bulks']} bulks | {stats['total_lines']} lines")
    print(f"DB Size: {stats['db_size_mb']} MB")
    print(f"{'=' * 60}")

    await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
