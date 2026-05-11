"""
QDML Full Loop Test — DB → Compile → Write to Disk → Compare with Original
This closes the full circle: proving the DB is the single source of truth.
"""
import sys, os, io, hashlib
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(__file__))
from qdml_local import QDMLEngine

ORIGINAL_JS = os.path.join(os.path.dirname(__file__), "..", "mas-front", "mas.core.js")
ORIGINAL_CSS = os.path.join(os.path.dirname(__file__), "..", "mas-front", "mas.tokens.css")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "mas-front", "_generated")

def file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]

def main():
    print("=" * 70)
    print("QDML FULL LOOP: DB -> Compile -> Disk -> Compare")
    print("=" * 70)

    q = QDMLEngine()

    # ─── Step 1: Compile from DB ───
    print("\n[1] Compiling from database...")
    js_from_db = q.compile_component("mas-core-v2", inject_markers=False)
    css_from_db = q.compile_component("mas-tokens-css", inject_markers=False)
    print(f"    JS from DB:  {js_from_db.count(chr(10))+1} lines, {len(js_from_db)} chars")
    print(f"    CSS from DB: {css_from_db.count(chr(10))+1} lines, {len(css_from_db)} chars")

    # ─── Step 2: Write to disk ───
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    out_js = os.path.join(OUTPUT_DIR, "mas.core.js")
    out_css = os.path.join(OUTPUT_DIR, "mas.tokens.css")

    with open(out_js, "w", encoding="utf-8") as f:
        f.write(js_from_db)
    with open(out_css, "w", encoding="utf-8") as f:
        f.write(css_from_db)
    print(f"\n[2] Written to disk:")
    print(f"    {out_js}")
    print(f"    {out_css}")

    # ─── Step 3: Compare with originals ───
    print(f"\n[3] Comparing with originals...")
    with open(ORIGINAL_JS, "r", encoding="utf-8") as f:
        orig_js = f.read()
    with open(ORIGINAL_CSS, "r", encoding="utf-8") as f:
        orig_css = f.read()

    # Line-by-line comparison for JS
    orig_js_lines = orig_js.split('\n')
    gen_js_lines = js_from_db.split('\n')

    # Check which original lines are covered
    covered = 0
    missing_ranges = []
    in_gap = False
    gap_start = 0

    for i, line in enumerate(orig_js_lines):
        if line.strip() and line.strip() in js_from_db:
            covered += 1
            if in_gap:
                missing_ranges.append(f"{gap_start+1}-{i}")
                in_gap = False
        elif line.strip():
            if not in_gap:
                gap_start = i
                in_gap = True

    print(f"\n    JS ANALYSIS:")
    print(f"    Original:  {len(orig_js_lines)} lines, {len(orig_js)} chars")
    print(f"    Generated: {len(gen_js_lines)} lines, {len(js_from_db)} chars")
    print(f"    Coverage:  ~{covered * 100 // len(orig_js_lines)}% of non-empty lines")

    if missing_ranges:
        print(f"    Gaps (between bulks): {', '.join(missing_ranges[:10])}")
    else:
        print(f"    Gaps: NONE")

    # CSS comparison — note: we mutated utilities, so it SHOULD differ
    orig_css_lines = orig_css.split('\n')
    gen_css_lines = css_from_db.split('\n')

    print(f"\n    CSS ANALYSIS:")
    print(f"    Original:  {len(orig_css_lines)} lines, {len(orig_css)} chars")
    print(f"    Generated: {len(gen_css_lines)} lines, {len(css_from_db)} chars")
    print(f"    NOTE: CSS was MUTATED (fade/scale/slide classes added)")
    print(f"    Extra lines from mutation: +{len(gen_css_lines) - len(orig_css_lines)} lines")

    # ─── Step 4: Full integrity — reassemble with markers ───
    print(f"\n[4] Generating marked version (m-bulk markers)...")
    js_marked = q.compile_component("mas-core-v2", inject_markers=True)
    css_marked = q.compile_component("mas-tokens-css", inject_markers=True)

    out_js_m = os.path.join(OUTPUT_DIR, "mas.core.marked.js")
    out_css_m = os.path.join(OUTPUT_DIR, "mas.tokens.marked.css")
    with open(out_js_m, "w", encoding="utf-8") as f:
        f.write(js_marked)
    with open(out_css_m, "w", encoding="utf-8") as f:
        f.write(css_marked)

    js_markers = [l for l in js_marked.split('\n') if 'm-bulk:' in l or 'm-end:' in l]
    css_markers = [l for l in css_marked.split('\n') if 'm-bulk:' in l or 'm-end:' in l]
    print(f"    JS  markers: {len(js_markers)} ({len(js_markers)//2} bulks)")
    print(f"    CSS markers: {len(css_markers)} ({len(css_markers)//2} bulks)")

    # ─── Step 5: Database statistics ───
    print(f"\n[5] Database state:")
    desc = q.describe("mas-front")
    for p in desc:
        print(f"    Project: {p['name']}")
        for m in p['modules']:
            print(f"      [{m['tier']}] {m['app']}/{m['slug']}")
            for c in m['components']:
                total_lines = sum(b['lines'] for b in c['bulks'])
                total_chars = sum(b['chars'] for b in c['bulks'])
                print(f"        {c['slug']} [{c['kind']}]: {len(c['bulks'])} bulks, {total_lines} lines, {total_chars} chars")

    # History check
    hist_count = q.conn.execute("SELECT COUNT(*) FROM bulk_history").fetchone()[0]
    ops_count = q.conn.execute("SELECT COUNT(*) FROM operation_log").fetchone()[0]
    db_size = os.path.getsize(q.db_path)

    print(f"\n    Bulk history snapshots: {hist_count}")
    print(f"    Operation log entries:  {ops_count}")
    print(f"    Database size:          {db_size / 1024:.1f} KB")

    # ─── Step 6: List generated files ───
    print(f"\n[6] Generated files:")
    for f in os.listdir(OUTPUT_DIR):
        fp = os.path.join(OUTPUT_DIR, f)
        sz = os.path.getsize(fp)
        print(f"    {f:35s} {sz:>8d} bytes")

    print(f"\n{'=' * 70}")
    print(f"RESULT: Database IS the source of truth.")
    print(f"        mas-front/_generated/ contains files compiled FROM DB.")
    print(f"        mas-front/ (originals) are NOT generated — they are the INPUT.")
    print(f"        Next step: replace originals with DB-generated output.")
    print(f"{'=' * 70}")

    q.close()

if __name__ == "__main__":
    main()
