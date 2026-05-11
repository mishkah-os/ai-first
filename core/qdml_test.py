"""
QDML Test: Split mas.core.js into bulks, store in DB, reassemble, verify.
"""
import sys, os, time, hashlib, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from qdml_local import QDMLEngine

MAS_CORE = os.path.join(os.path.dirname(__file__), "..", "mas-front", "mas.core.js")
MAS_TOKENS = os.path.join(os.path.dirname(__file__), "..", "mas-front", "mas.tokens.css")

BULK_MAP_JS = [
    {"name":"umd_open",           "start":1,   "end":5,    "exports":"",                              "depends":"",                              "reveal":"0:4"},
    {"name":"constants",          "start":7,   "end":13,   "exports":"VOID,SVG_TAGS,HEAD_ONLY,RTL_LANGS","depends":"",                           "reveal":"0:6"},
    {"name":"hooks",              "start":15,  "end":18,   "exports":"hook,emit",                     "depends":"",                              "reveal":"0:3"},
    {"name":"i18n",               "start":20,  "end":30,   "exports":"t",                             "depends":"",                              "reveal":"0:1,3,8:10"},
    {"name":"component_registry", "start":32,  "end":56,   "exports":"component,resolveComponent,prefixGkey","depends":"",                      "reveal":"0:1,3:5,8:9"},
    {"name":"module_system",      "start":58,  "end":124,  "exports":"createModuleD,createModuleCtx,registerModule","depends":"component_registry","reveal":"0:2,14:16,60:62"},
    {"name":"vdom_core",          "start":126, "end":209,  "exports":"h,normKids,D,_dHelpers",        "depends":"component_registry",            "reveal":"0:2,35:36,62:63,80:81"},
    {"name":"head_manager",       "start":210, "end":254,  "exports":"Head",                          "depends":"",                              "reveal":"0:2,14:15"},
    {"name":"render_engine",      "start":256, "end":313,  "exports":"render,setProps",                "depends":"constants,head_manager",        "reveal":"0:2,24:25"},
    {"name":"patch_engine",       "start":315, "end":397,  "exports":"same,patch,patchKids",           "depends":"render_engine,head_manager",    "reveal":"0:3,40:42"},
    {"name":"scroll_env",         "start":399, "end":434,  "exports":"captureScroll,restoreScroll,applyEnv","depends":"constants",               "reveal":"0:2,14:15,25:26"},
    {"name":"delegation",         "start":436, "end":497,  "exports":"parseOrders,delegate,KNOWN_EVENTS","depends":"hooks",                      "reveal":"0:8,10:11,26:28"},
    {"name":"app_factory",        "start":499, "end":695,  "exports":"createApp",                      "depends":"module_system,vdom_core,render_engine,patch_engine,scroll_env,delegation","reveal":"0:2,60:62,140:143","overflow":True},
    {"name":"hydration",          "start":697, "end":726,  "exports":"hydrateNode",                    "depends":"render_engine",                 "reveal":"0:5"},
    {"name":"lazy_loader",        "start":728, "end":771,  "exports":"load,loaded,lazyModule",         "depends":"component_registry,module_system","reveal":"0:3,14:16"},
    {"name":"ssr",                "start":773, "end":812,  "exports":"renderToString,renderHeadToString","depends":"constants,vdom_core",         "reveal":"0:5"},
    {"name":"router_exports",     "start":814, "end":905,  "exports":"createRouter,go",                "depends":"",                              "reveal":"0:3,47:48,79:80,88:93"},
]

BULK_MAP_CSS = [
    {"name":"reset",       "start":14, "end":16,  "exports":"","depends":"","reveal":"0:2"},
    {"name":"light_vars",  "start":18, "end":86,  "exports":"","depends":"","reveal":"0:3,12:14,32:34"},
    {"name":"dark_vars",   "start":88, "end":110, "exports":"","depends":"light_vars","reveal":"0:3"},
    {"name":"typography",  "start":112,"end":119, "exports":"","depends":"","reveal":"0:3"},
    {"name":"card",        "start":121,"end":128, "exports":"","depends":"","reveal":"0:2"},
    {"name":"input",       "start":130,"end":143, "exports":"","depends":"","reveal":"0:2,10:13"},
    {"name":"btn_badge",   "start":145,"end":170, "exports":"","depends":"","reveal":"0:3,10:11,18:20"},
    {"name":"utilities",   "start":172,"end":191, "exports":"","depends":"","reveal":"0:5"},
]

def read_lines(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.readlines()

def extract_bulk(all_lines, start, end):
    chunk = all_lines[start-1:end]
    return "".join(chunk)

def main():
    start_total = time.perf_counter()
    print("=" * 60)
    print("QDML PROTOCOL TEST — mas-front library")
    print("=" * 60)

    # Delete old DB
    db_path = os.path.join(os.path.dirname(__file__), "qdml.db")
    if os.path.exists(db_path):
        os.remove(db_path)

    engine = QDMLEngine()

    # ═══ Step 1: Create Project ═══
    print("\n[1] Creating project...")
    pid = engine.create_project("MAS Frontend", "mas-front", "MAS JS Framework — VDOM + Module System")

    # ═══ Step 2: Create Modules ═══
    print("[2] Creating modules...")
    engine.create_module("mas-front", "MAS Core", "mas-core", tier="frontend", app="mas-framework")
    engine.create_module("mas-front", "MAS Tokens", "mas-tokens", tier="frontend", app="mas-framework")

    # ═══ Step 3: Create Components ═══
    print("[3] Creating components...")
    engine.create_component("mas-core", "MAS Core V2", "mas-core-v2", kind="library", target="mas-js")
    engine.create_component("mas-tokens", "MAS Design Tokens", "mas-tokens-css", kind="library", target="css")

    # ═══ Step 4: Split mas.core.js into Bulks ═══
    print("[4] Splitting mas.core.js into bulks...")
    js_lines = read_lines(MAS_CORE)
    print(f"    Source: {len(js_lines)} lines, {sum(len(l) for l in js_lines)} chars")

    for i, bk in enumerate(BULK_MAP_JS):
        content = extract_bulk(js_lines, bk["start"], bk["end"])
        engine.create_bulk("mas-core-v2", bk["name"], content, lang="javascript",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"],
            exports=bk["exports"], overflow=bk.get("overflow", False))
        lines = content.count('\n') + 1
        print(f"    B{i+1:02d} {bk['name']:25s} lines:{bk['start']:3d}-{bk['end']:3d} ({lines:3d}L) {'⚠️ OVERFLOW' if bk.get('overflow') else '✅'}")

    # ═══ Step 5: Split mas.tokens.css into Bulks ═══
    print("\n[5] Splitting mas.tokens.css into bulks...")
    css_lines = read_lines(MAS_TOKENS)
    print(f"    Source: {len(css_lines)} lines, {sum(len(l) for l in css_lines)} chars")

    for i, bk in enumerate(BULK_MAP_CSS):
        content = extract_bulk(css_lines, bk["start"], bk["end"])
        engine.create_bulk("mas-tokens-css", bk["name"], content, lang="css",
            bulk_order=i, reveal=bk["reveal"], depends=bk["depends"], exports=bk["exports"])
        lines = content.count('\n') + 1
        print(f"    T{i+1:02d} {bk['name']:15s} lines:{bk['start']:3d}-{bk['end']:3d} ({lines:3d}L) ✅")

    # ═══ Step 6: Store Documentation as Artifacts ═══
    print("\n[6] Storing documentation artifacts...")
    rules_path = os.path.join(os.path.dirname(__file__), "MAS_V2_RULES.md")
    if os.path.exists(rules_path):
        with open(rules_path, "r", encoding="utf-8") as f:
            engine.create_artifact("mas-front", "MAS_V2_RULES.md", f.read(), "./doc", "readme")
        print("    MAS_V2_RULES.md ✅")

    # ═══ Step 7: Compile (reassemble) ═══
    print("\n[7] Compiling (reassembling)...")
    compiled_js = engine.compile_component("mas-core-v2", inject_markers=False)
    compiled_css = engine.compile_component("mas-tokens-css", inject_markers=False)

    # ═══ Step 8: Verify ═══
    print("\n[8] Verifying...")
    original_js = "".join(js_lines)
    original_css = "".join(css_lines)

    # Check: compiled should be a subset of original (we only took specific line ranges)
    js_hash_orig = hashlib.sha256(original_js.encode()).hexdigest()[:16]
    js_hash_comp = hashlib.sha256(compiled_js.encode()).hexdigest()[:16]
    css_hash_orig = hashlib.sha256(original_css.encode()).hexdigest()[:16]
    css_hash_comp = hashlib.sha256(compiled_css.encode()).hexdigest()[:16]

    # Count total lines in bulks vs original
    compiled_js_lines = compiled_js.count('\n')
    compiled_css_lines = compiled_css.count('\n')

    print(f"    JS  original: {len(js_lines):4d} lines | compiled: {compiled_js_lines:4d} lines | coverage: {compiled_js_lines*100//len(js_lines)}%")
    print(f"    CSS original: {len(css_lines):4d} lines | compiled: {compiled_css_lines:4d} lines | coverage: {compiled_css_lines*100//len(css_lines)}%")
    print(f"    JS  hash: orig={js_hash_orig} comp={js_hash_comp}")
    print(f"    CSS hash: orig={css_hash_orig} comp={css_hash_comp}")

    # ═══ Step 9: Mini-Code ═══
    print("\n[9] Mini-Code Level 0:")
    print("-" * 50)
    print(engine.mini("mas-front", level=0))
    print("-" * 50)

    print("\n[10] Mini-Code Level 1:")
    print("-" * 50)
    print(engine.mini("mas-front", level=1))
    print("-" * 50)

    # ═══ Step 10: Metrics ═══
    print("\n[11] Operation Metrics:")
    print(f"    {'Operation':<25s} {'Count':>5s} {'OK':>4s} {'Fail':>5s} {'Avg(ms)':>8s} {'Total(ms)':>10s}")
    print("    " + "-" * 60)
    for m in engine.metrics():
        print(f"    {m['operation']:<25s} {m['count']:>5d} {m['ok']:>4d} {m['fail']:>5d} {m['avg_ms']:>8.2f} {m['total_ms']:>10.2f}")

    total_ops = sum(m["count"] for m in engine.metrics())
    total_time = (time.perf_counter() - start_total) * 1000

    print(f"\n{'=' * 60}")
    print(f"TOTAL: {total_ops} operations in {total_time:.1f}ms")
    print(f"DB Size: {os.path.getsize(db_path) / 1024:.1f} KB")
    print(f"{'=' * 60}")

    engine.close()

if __name__ == "__main__":
    main()
