#!/usr/bin/env python3
"""
test_track3.py — Comprehensive tests for Track 3 MAS Engine.
Tests MiniCodeBuilder, ArrayProtocolParser, MutationApplier, and FeedbackLoop
across all three test project languages: Python, JavaScript, C++.
"""

import json
import os
import shutil
import sys
import tempfile

# Make sure we can import from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from track3_engine import (
    MiniCodeBuilder,
    RevealManager,
    ArrayProtocolParser,
    MutationApplier,
    FeedbackLoop,
    AIProviderClient,
)

TEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "track3_test_projects")

PASS = 0
FAIL = 0


def check(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name} — {detail}")


# ══════════════════════════════════════════════════════════════
# TEST 1: MiniCodeBuilder — Analyze all three languages
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 1: MiniCodeBuilder — Analyze Test Projects")
print("=" * 60)

builder = MiniCodeBuilder()
test_files = [
    os.path.join(TEST_DIR, "calculator.py"),
    os.path.join(TEST_DIR, "server.js"),
    os.path.join(TEST_DIR, "matrix.cpp"),
]

# Verify test files exist
for f in test_files:
    check(f"File exists: {os.path.basename(f)}", os.path.exists(f), f"Not found: {f}")

analysis = builder.analyze(test_files, root_dir=TEST_DIR)

check("Analysis returns dict", isinstance(analysis, dict))
check("Analysis has 'files' key", "files" in analysis)
check("Analysis has 'root' key", "root" in analysis)

files_found = [f["path"] for f in analysis.get("files", [])]
print(f"\n  📂 Files analyzed: {files_found}")

# Check each language was analyzed
check("Python file analyzed", any("calculator.py" in f for f in files_found),
      f"Got: {files_found}")
check("JS file analyzed", any("server.js" in f for f in files_found),
      f"Got: {files_found}")
check("C++ file analyzed", any("matrix.cpp" in f for f in files_found),
      f"Got: {files_found}")

# Check blocks per file
for file_data in analysis.get("files", []):
    blocks = file_data.get("blocks", [])
    path = file_data["path"]
    print(f"\n  📄 {path} — {len(blocks)} blocks, lang={file_data.get('language', '?')}")
    for b in blocks:
        print(f"     [{b['id']}] {b['type']}: {b.get('signature', b.get('name', '?'))}")
        print(f"              lines={b['lines']}, blinded={b['blinded']}, content_len={len(b.get('content', ''))}")

    check(f"{path}: has blocks", len(blocks) > 0, f"0 blocks found")
    check(f"{path}: blocks have IDs", all(b.get("id") for b in blocks))
    check(f"{path}: blocks have content", all(len(b.get("content", "")) > 0 for b in blocks))


# ══════════════════════════════════════════════════════════════
# TEST 2: RevealManager — Build prompts blinded and revealed
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 2: RevealManager — Prompt Building")
print("=" * 60)

# Test blinded prompt
blinded_prompt = RevealManager.build_prompt(
    analysis=analysis,
    revealed_ids=[],
    instruction="Add error handling to the calculator",
)
check("Blinded prompt generated", len(blinded_prompt) > 100)
check("Blinded prompt contains instruction", "Add error handling" in blinded_prompt)
check("Blinded prompt contains '...' (blinded blocks)", "..." in blinded_prompt)
print(f"  📏 Blinded prompt length: {len(blinded_prompt)} chars")

# Test revealed prompt — reveal first block from each file
reveal_ids = []
for file_data in analysis.get("files", []):
    if file_data.get("blocks"):
        reveal_ids.append(file_data["blocks"][0]["id"])

revealed_prompt = RevealManager.build_prompt(
    analysis=analysis,
    revealed_ids=reveal_ids,
    instruction="Add error handling to the calculator",
)
check("Revealed prompt generated", len(revealed_prompt) > len(blinded_prompt),
      f"revealed={len(revealed_prompt)} vs blinded={len(blinded_prompt)}")
check("Revealed prompt has line numbers", "| " in revealed_prompt)
print(f"  📏 Revealed prompt length: {len(revealed_prompt)} chars")
print(f"  🔓 Revealed IDs: {reveal_ids}")

# Test with history
history = [
    {"type": "read_request", "ids": reveal_ids},
    {"type": "info", "content": "I need to see more"},
]
history_prompt = RevealManager.build_prompt(
    analysis=analysis,
    revealed_ids=reveal_ids,
    instruction="Add error handling",
    history=history,
)
check("History prompt contains PREVIOUS ROUNDS", "PREVIOUS ROUNDS" in history_prompt)


# ══════════════════════════════════════════════════════════════
# TEST 3: ArrayProtocolParser — Parse various AI responses
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 3: ArrayProtocolParser — Response Parsing")
print("=" * 60)

parser = ArrayProtocolParser()

# Test read request
read_response = '["read", ["BLK_abc123", "BLK_def456"]]'
parsed = parser.parse(read_response)
check("Read request parsed", parsed["type"] == "read", f"Got: {parsed}")
check("Read IDs correct", parsed.get("ids") == ["BLK_abc123", "BLK_def456"])

# Test mutation response
mutation_response = json.dumps([
    ["BLK_abc123", [
        ["r", "3:5", "new code line 1\nnew code line 2"],
        ["d", "8"],
        ["i", "1", "# inserted comment"],
    ]]
])
parsed = parser.parse(mutation_response)
check("Mutation parsed", parsed["type"] == "mutations", f"Got: {parsed}")
check("Mutation has 1 block", len(parsed.get("blocks", [])) == 1)
ops = parsed["blocks"][0]["ops"]
check("Has 3 operations", len(ops) == 3, f"Got {len(ops)}: {ops}")
check("Replace op correct", ops[0]["action"] == "replace" and ops[0]["lines"] == [3, 4, 5])
check("Delete op correct", ops[1]["action"] == "delete" and ops[1]["lines"] == [8])
check("Insert op correct", ops[2]["action"] == "insert" and ops[2]["line"] == 1)

# Test markdown-wrapped JSON
markdown_response = '```json\n["read", ["BLK_xyz"]]\n```'
parsed = parser.parse(markdown_response)
check("Markdown JSON parsed", parsed["type"] == "read")

# Test plain text response
text_response = "I need more information about this project."
parsed = parser.parse(text_response)
check("Plain text recognized", parsed["type"] == "text")

# Test multi-block mutations
multi_mut = json.dumps([
    ["BLK_a", [["r", "1", "line A"]]],
    ["BLK_b", [["d", "2:4"]]],
    ["BLK_c", [["i", "3", "inserted"]]],
])
parsed = parser.parse(multi_mut)
check("Multi-block mutation", parsed["type"] == "mutations" and len(parsed["blocks"]) == 3)

# Test complex delete specs
complex_delete = json.dumps([["BLK_x", [["d", [3, "5:8", 12]]]]])
parsed = parser.parse(complex_delete)
ops = parsed["blocks"][0]["ops"]
check("Complex delete parsed", ops[0]["lines"] == [3, 5, 6, 7, 8, 12],
      f"Got: {ops[0].get('lines')}")


# ══════════════════════════════════════════════════════════════
# TEST 4: MutationApplier — Dry run on calculator.py
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 4: MutationApplier — Dry Run (Python)")
print("=" * 60)

# Work on a copy so we don't touch original
tmp_dir = tempfile.mkdtemp(prefix="track3_test_")
tmp_calc = os.path.join(tmp_dir, "calculator.py")
shutil.copy2(os.path.join(TEST_DIR, "calculator.py"), tmp_calc)

# Re-analyze the copy
tmp_analysis = builder.analyze([tmp_calc], root_dir=tmp_dir)
check("Temp analysis works", len(tmp_analysis.get("files", [])) > 0)

# Find a block to mutate
py_file = tmp_analysis["files"][0]
blocks = py_file["blocks"]
print(f"  📦 Found {len(blocks)} blocks in temp calculator.py")

# Try to insert a docstring edit via replace on the first suitable block
target_block = None
for b in blocks:
    if b.get("content") and len(b["content"].splitlines()) > 3:
        target_block = b
        break

if target_block:
    print(f"  🎯 Target block: [{target_block['id']}] {target_block.get('name', '?')}")
    print(f"     Lines: {target_block['lines']}, Content lines: {len(target_block['content'].splitlines())}")

    # Mutation: insert a comment before line 1 of this block
    mutations = [{"id": target_block["id"], "ops": [
        {"action": "insert", "line": 1, "code": "    # [Track3 Test] Added by test_track3.py"},
    ]}]

    applier = MutationApplier(backup_dir=os.path.join(tmp_dir, "backup"))
    result = applier.apply(tmp_analysis, mutations, dry_run=True)

    check("Dry run succeeded", result["success"], f"Errors: {result.get('errors')}")
    check("Preview generated", len(result.get("preview", {})) > 0)
    check("No files actually modified", len(result.get("files_modified", [])) == 0)

    # Check the preview content
    if result.get("preview"):
        preview_content = list(result["preview"].values())[0]
        check("Insertion in preview", "Track3 Test" in preview_content,
              f"Preview doesn't contain the inserted line")
        print(f"  📏 Preview length: {len(preview_content)} chars")
else:
    print("  ⚠️ No suitable block found for mutation test")


# ══════════════════════════════════════════════════════════════
# TEST 5: MutationApplier — Actual write on temp copy
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 5: MutationApplier — Actual Write (Python)")
print("=" * 60)

if target_block:
    result_write = applier.apply(tmp_analysis, mutations, dry_run=False)
    check("Write succeeded", result_write["success"], f"Errors: {result_write.get('errors')}")
    check("File listed as modified", len(result_write.get("files_modified", [])) > 0)

    # Verify the file was actually changed
    with open(tmp_calc, 'r') as f:
        modified_content = f.read()
    check("File actually contains insertion", "Track3 Test" in modified_content)

    # Verify backup was created
    backup_dir = os.path.join(tmp_dir, "backup")
    if os.path.exists(backup_dir):
        backups = os.listdir(backup_dir)
        check("Backup created", len(backups) > 0, f"Backup dir: {os.listdir(backup_dir)}")
    else:
        check("Backup dir exists", False, "No backup directory created")

# Cleanup temp dir
shutil.rmtree(tmp_dir, ignore_errors=True)


# ══════════════════════════════════════════════════════════════
# TEST 6: MutationApplier — Syntax Error Detection
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 6: MutationApplier — Syntax Error Detection")
print("=" * 60)

tmp_dir2 = tempfile.mkdtemp(prefix="track3_test2_")
tmp_calc2 = os.path.join(tmp_dir2, "bad_calc.py")
shutil.copy2(os.path.join(TEST_DIR, "calculator.py"), tmp_calc2)

tmp_analysis2 = builder.analyze([tmp_calc2], root_dir=tmp_dir2)
blocks2 = tmp_analysis2["files"][0]["blocks"]

target2 = None
for b in blocks2:
    if b.get("content") and len(b["content"].splitlines()) > 2:
        target2 = b
        break

if target2:
    # Insert broken Python syntax
    bad_mutations = [{"id": target2["id"], "ops": [
        {"action": "insert", "line": 1, "code": "    def broken(self, :::"},
    ]}]
    applier2 = MutationApplier()
    result_bad = applier2.apply(tmp_analysis2, bad_mutations, dry_run=True)
    check("Syntax error detected", not result_bad["success"],
          f"Expected failure but got success. Errors: {result_bad.get('errors')}")
    check("Error message present", len(result_bad.get("errors", [])) > 0)
    if result_bad.get("errors"):
        print(f"  📝 Error: {result_bad['errors'][0]}")

shutil.rmtree(tmp_dir2, ignore_errors=True)


# ══════════════════════════════════════════════════════════════
# TEST 7: JS and C++ Analysis Deep Dive
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 7: JS and C++ Analysis Deep Dive")
print("=" * 60)

for file_data in analysis.get("files", []):
    path = file_data["path"]
    lang = file_data.get("language", "?")
    blocks = file_data.get("blocks", [])

    print(f"\n  📄 {path} (lang={lang})")

    if "server.js" in path:
        # JS should have: parseBody, handleLogin, handleRegister, handleListUsers, RateLimiter (class or methods)
        block_names = [b.get("name", "") for b in blocks]
        block_types = [b.get("type", "") for b in blocks]
        print(f"     Block names: {block_names}")
        print(f"     Block types: {block_types}")
        check("JS: multiple blocks found", len(blocks) >= 3,
              f"Only {len(blocks)} blocks")
        check("JS: blocks have signatures", all(b.get("signature") for b in blocks))

    elif "matrix.cpp" in path:
        block_names = [b.get("name", "") for b in blocks]
        block_types = [b.get("type", "") for b in blocks]
        print(f"     Block names: {block_names}")
        print(f"     Block types: {block_types}")
        check("C++: multiple blocks found", len(blocks) >= 3,
              f"Only {len(blocks)} blocks")
        check("C++: blocks have signatures", all(b.get("signature") for b in blocks))


# ══════════════════════════════════════════════════════════════
# TEST 8: AIProviderClient — Catalog loading
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 8: AIProviderClient — Catalog")
print("=" * 60)

client = AIProviderClient()
providers = client.list_providers()
check("Providers loaded", len(providers) > 0, f"Got {len(providers)} providers")

for p in providers:
    print(f"  🔌 {p['id']}: {p['label']} — {len(p.get('models', []))} models, has_key={p.get('has_key')}")
    check(f"{p['id']}: has models", len(p.get("models", [])) > 0)

core_providers = {"gemini", "vertex_ai", "groq", "deepseek", "openai", "anthropic"}
found_providers = {p["id"] for p in providers}
check("Core providers present", core_providers.issubset(found_providers),
      f"Missing: {core_providers - found_providers}")


# ══════════════════════════════════════════════════════════════
# TEST 9: FeedbackLoop — Start session
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 9: FeedbackLoop — Session Init")
print("=" * 60)

loop = FeedbackLoop(client)
state = loop.start(
    file_paths=test_files,
    root_dir=TEST_DIR,
    instruction="Add input validation to the calculator",
    provider_id="gemini",
    model_id="gemini-2.5-flash",
)

check("State created", isinstance(state, dict))
check("State status = ready", state.get("status") == "ready")
check("State has analysis", "analysis" in state and len(state["analysis"].get("files", [])) > 0)
check("State round = 0", state.get("round") == 0)
check("State has empty history", state.get("history") == [])
check("State has empty revealed_ids", state.get("revealed_ids") == [])
check("State preserves instruction", state.get("instruction") == "Add input validation to the calculator")
check("State preserves provider", state.get("provider_id") == "gemini")
check("State preserves model", state.get("model_id") == "gemini-2.5-flash")

print(f"  📊 Session files: {len(state['analysis'].get('files', []))}")
print(f"  📊 Total blocks: {sum(len(f.get('blocks', [])) for f in state['analysis']['files'])}")


# ══════════════════════════════════════════════════════════════
# TEST 10: FeedbackLoop — reject() method
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 10: FeedbackLoop — reject()")
print("=" * 60)

from track3_engine import MutationApplier

# Build a fake pending_approval state
loop10 = FeedbackLoop(client)
fake_state = loop10.start(test_files, TEST_DIR, "Test reject", "gemini", "gemini-2.5-flash")
fake_state["status"] = "pending_approval"
fake_state["pending_mutations"] = [{"id": "BLK_fake", "ops": []}]
fake_state["dry_run_result"] = {"success": True, "errors": [], "preview": {"file": "content"}}

rejected = loop10.reject(fake_state)
check("Reject → status = ready", rejected["status"] == "ready")
check("Reject → pending_mutations cleared", rejected.get("pending_mutations") is None)
check("Reject → history entry added", any(h.get("result") == "rejected" for h in rejected["history"]))

# reject on non-pending state is a no-op
non_pending = loop10.start(test_files, TEST_DIR, "x", "gemini", "gemini-2.5-flash")
non_pending["status"] = "ready"
result_no_op = loop10.reject(non_pending)
check("Reject on non-pending is no-op", result_no_op["status"] == "ready" and result_no_op["history"] == [])


# ══════════════════════════════════════════════════════════════
# TEST 11: CredentialQueue — round-robin rotation
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 11: CredentialQueue — round-robin")
print("=" * 60)

from track3_engine import CredentialQueue

tmp_queue_file = os.path.join(tempfile.gettempdir(), "track3_test_queue.json")
if os.path.exists(tmp_queue_file):
    os.remove(tmp_queue_file)

cq = CredentialQueue(state_path=tmp_queue_file)
keys = ["key_A", "key_B", "key_C"]

r1 = cq.next("pool1", keys)
r2 = cq.next("pool1", keys)
r3 = cq.next("pool1", keys)
r4 = cq.next("pool1", keys)  # wraps around

check("CQ: first pick = key_A", r1 == "key_A", f"Got: {r1}")
check("CQ: second pick = key_B", r2 == "key_B", f"Got: {r2}")
check("CQ: third pick = key_C", r3 == "key_C", f"Got: {r3}")
check("CQ: wraps around to key_A", r4 == "key_A", f"Got: {r4}")

# Single key pool — always returns same
single = cq.next("pool2", ["only_key"])
check("CQ: single key always returned", single == "only_key", f"Got: {single}")

# Empty pool → empty string
empty = cq.next("pool3", [])
check("CQ: empty pool → ''", empty == "", f"Got: {repr(empty)}")

# State persists across instances
cq2 = CredentialQueue(state_path=tmp_queue_file)
r5 = cq2.next("pool1", keys)
check("CQ: state persists (r5 = key_B after wrap)", r5 == "key_B", f"Got: {r5}")

if os.path.exists(tmp_queue_file):
    os.remove(tmp_queue_file)


# ══════════════════════════════════════════════════════════════
# TEST 12: _sanitize_state — does not mutate original state
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TEST 12: _sanitize_state — isolation")
print("=" * 60)

import sys as _sys
# Import the function from routes (not imported at top since it's Flask-based)
try:
    from track3_routes import _sanitize_state as sanitize

    loop12 = FeedbackLoop(client)
    state12 = loop12.start(test_files, TEST_DIR, "Sanitize test", "gemini", "g")
    # Inject large content into a block to trigger truncation
    first_block = state12["analysis"]["files"][0]["blocks"][0]
    first_block["content"] = "x" * 500
    original_content = first_block["content"]

    safe = sanitize(state12)

    # Original state must not be modified
    check("Sanitize: original content preserved", first_block["content"] == original_content,
          f"Content was mutated to: {first_block['content'][:50]!r}")

    # Safe state must have truncated content
    safe_block = safe["analysis"]["files"][0]["blocks"][0]
    check("Sanitize: safe copy has content_preview", "content_preview" in safe_block)
    check("Sanitize: safe copy drops full content (block not revealed)",
          "content" not in safe_block or len(safe_block.get("content", "")) <= 200)

    # dry_run_result preview stripped but errors kept
    state12["dry_run_result"] = {"success": False, "errors": ["bad syntax"], "preview": {"f": "big"}}
    safe2 = sanitize(state12)
    check("Sanitize: dry_run errors kept", safe2.get("dry_run_result", {}).get("errors") == ["bad syntax"])
    check("Sanitize: dry_run preview stripped", "preview" not in safe2.get("dry_run_result", {}))

except ImportError as e:
    print(f"  ⚠️ Skipped (Flask not available in test env): {e}")


# ══════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
total = PASS + FAIL
print(f"RESULTS: {PASS}/{total} passed, {FAIL} failed")
if FAIL == 0:
    print("🎉 ALL TESTS PASSED!")
else:
    print("⚠️  Some tests failed — review output above.")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)
