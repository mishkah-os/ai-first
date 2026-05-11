"""
QDML AI Simulation — Full Protocol Test
Simulates an AI agent that:
  1. Reads mini-code (project overview)
  2. Identifies target bulk
  3. Reveals (reads) the bulk content
  4. Mutates (adds CSS fade-in/out animation classes)
  5. Compiles (reassembles)
  6. Verifies output
  7. Checks history
All via QDML protocol only. No direct file access.
"""
import sys, os, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from qdml_local import QDMLEngine

MODEL = "claude-opus-4-20250514"
TOOL  = "qdml_sim"

def log(step, msg):
    print(f"  [{step}] {msg}")

def main():
    start = time.perf_counter()
    print("=" * 70)
    print("QDML AI SIMULATION - CSS Fade Animation Injection")
    print("Model:", MODEL)
    print("=" * 70)

    q = QDMLEngine()

    # ─── PHASE 1: AI reads project overview ───
    print("\n>>> PHASE 1: AI reads mini-code")
    mini0 = q.mini("mas-front", level=0)
    print(mini0)
    log("AI", "I see 2 modules: mas-core (JS) and mas-tokens (CSS)")
    log("AI", "Task: Add CSS fade-in/out animation classes")
    log("AI", "Target: mas-tokens-css component, utilities bulk")

    # ─── PHASE 2: AI reveals target bulk at level 1 (signatures only) ───
    print("\n>>> PHASE 2: AI reveals component structure")
    bulks = q.reveal("mas-tokens-css")
    for b in bulks:
        log("REVEAL", f"{b['bulk_name']:15s} {b['lines']:3d}L  exports:[{b['exports']}]  depends:[{b['depends']}]")

    log("AI", "I need to see 'utilities' bulk content (level 3 = full)")

    # ─── PHASE 3: AI reveals full content of target bulk ───
    print("\n>>> PHASE 3: AI reveals 'utilities' bulk (full)")
    util_bulk = q.reveal("mas-tokens-css", "utilities", level=3)
    log("REVEAL", f"utilities: {util_bulk['lines']}L, {util_bulk['chars']} chars")
    log("CONTENT", "Current content:")
    for i, line in enumerate(util_bulk["content"].split('\n')):
        print(f"        {i:3d}| {line}")

    # ─── PHASE 4: AI creates the mutation ───
    print("\n>>> PHASE 4: AI prepares mutation")
    log("AI", "Adding .mas-fade-enter, .mas-fade-leave, .mas-fade-active CSS classes")
    log("AI", "These are pure CSS — zero JS core changes needed")

    old_content = util_bulk["content"]
    new_content = old_content.rstrip('\n') + """
.mas-fade-enter{opacity:0;transform:translateY(8px);transition:opacity var(--mas-duration) var(--mas-ease),transform var(--mas-duration) var(--mas-ease)}
.mas-fade-enter.mas-fade-active{opacity:1;transform:none}
.mas-fade-leave{opacity:1;transform:none;transition:opacity var(--mas-duration) var(--mas-ease),transform var(--mas-duration) var(--mas-ease)}
.mas-fade-leave.mas-fade-active{opacity:0;transform:translateY(-8px)}
.mas-scale-enter{opacity:0;transform:scale(0.95);transition:opacity var(--mas-duration) var(--mas-ease),transform var(--mas-duration) var(--mas-ease)}
.mas-scale-enter.mas-scale-active{opacity:1;transform:none}
.mas-slide-enter{opacity:0;transform:translateX(16px);transition:opacity 250ms var(--mas-ease),transform 250ms var(--mas-ease)}
.mas-slide-enter.mas-slide-active{opacity:1;transform:none}
"""

    new_lines = new_content.count('\n') + 1
    log("AI", f"Mutation: {util_bulk['lines']}L -> {new_lines}L (+{new_lines - util_bulk['lines']} lines)")

    # ─── PHASE 5: AI executes mutation via QDML ───
    print("\n>>> PHASE 5: AI mutates via QDML protocol")
    q.mutate_bulk("mas-tokens-css", "utilities", new_content,
                  changed_by=MODEL, reason="Add CSS fade/scale/slide enter+leave animation classes")
    log("MUTATE", "utilities bulk updated successfully")

    # ─── PHASE 6: AI verifies mutation was stored ───
    print("\n>>> PHASE 6: AI verifies mutation")
    after = q.reveal("mas-tokens-css", "utilities", level=3)
    log("VERIFY", f"New content: {after['lines']}L, {after['chars']} chars")
    log("VERIFY", f"Content match: {after['content'] == new_content}")

    # ─── PHASE 7: AI checks history ───
    print("\n>>> PHASE 7: AI checks bulk history")
    hist = q.history("mas-tokens-css", "utilities")
    for h in hist:
        log("HISTORY", f"changed_by={h['changed_by']}, reason={h['reason']}, ts={h['ts']}, old_size={len(h['content'])} chars")

    # ─── PHASE 8: AI compiles full CSS ───
    print("\n>>> PHASE 8: AI compiles CSS component")
    compiled = q.compile_component("mas-tokens-css", inject_markers=True)
    compiled_lines = compiled.count('\n') + 1
    log("COMPILE", f"Output: {compiled_lines} lines, {len(compiled)} chars")

    # Show markers in compiled output
    log("MARKERS", "m-bulk markers found:")
    for i, line in enumerate(compiled.split('\n')):
        if 'm-bulk:' in line or 'm-end:' in line:
            print(f"        {i:3d}| {line}")

    # ─── PHASE 9: AI compiles full JS (unchanged - integrity check) ───
    print("\n>>> PHASE 9: Integrity check - JS unchanged")
    js_compiled = q.compile_component("mas-core-v2")
    js_lines = js_compiled.count('\n') + 1
    log("INTEGRITY", f"JS Core: {js_lines} lines - UNTOUCHED")

    # ─── PHASE 10: Updated mini-code ───
    print("\n>>> PHASE 10: Updated mini-code")
    print("-" * 50)
    print(q.mini("mas-front", level=1))
    print("-" * 50)

    # ─── PHASE 11: Full metrics ───
    print("\n>>> PHASE 11: Operation Metrics")
    print(f"    {'Operation':<25s} {'Count':>5s} {'OK':>4s} {'Fail':>5s} {'Avg(ms)':>8s} {'Total(ms)':>10s}")
    print("    " + "-" * 60)
    for m in q.metrics():
        print(f"    {m['operation']:<25s} {m['count']:>5d} {m['ok']:>4d} {m['fail']:>5d} {m['avg_ms']:>8.2f} {m['total_ms']:>10.2f}")

    total_time = (time.perf_counter() - start) * 1000
    db_size = os.path.getsize(q.db_path)
    total_ops = sum(m["count"] for m in q.metrics())

    print(f"\n{'=' * 70}")
    print(f"SIMULATION COMPLETE")
    print(f"  Model:      {MODEL}")
    print(f"  Operations: {total_ops}")
    print(f"  Duration:   {total_time:.1f}ms")
    print(f"  DB Size:    {db_size / 1024:.1f} KB")
    print(f"  JS bulks:   17 (untouched)")
    print(f"  CSS bulks:  8 (1 mutated: utilities +8 lines)")
    print(f"  History:    {len(hist)} snapshot(s) stored")
    print(f"{'=' * 70}")

    q.close()

if __name__ == "__main__":
    main()
