"""Master Injector: One script to build the entire AI-First Platform."""
import asyncio, sys, os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine
from core.compiler import Compiler

# Import all plans
from core.fill_cpp import PILLARS as CPP_PILLARS
from core.fill_python import PILLARS as PY_PILLARS
from core.fill_node import PILLARS as NODE_PILLARS
from core.fill_mas import PILLARS as MAS_PILLARS
from core.fill_ui import PILLARS as UI_PILLARS
from core.fill_hawaa_ui import PILLARS as HAWAA_UI_PILLARS

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

async def inject_layer(e, pillars, target_lang):
    print(f"\n--- Injecting {target_lang} Layer ---")
    async with e.pool.acquire() as conn:
        for slug, content_map in pillars.items():
            cid = await conn.fetchval("SELECT id FROM component WHERE slug=$1", slug)
            if not cid:
                print(f"  [Error] Component {slug} not found in tree")
                continue
            for kind, content in content_map.items():
                await e.set_pillar(cid, kind, content, lang=target_lang)
                print(f"  + {slug}.{kind} ({len(content)} bytes)")

async def main():
    e = CoreEngine(DSN)
    try:
        await e.connect()
    except Exception as err:
        print(f"\n[CRITICAL] Could not connect to PostgreSQL: {err}")
        print("Please ensure Docker PG is running on port 5433.")
        return

    print("Step 1: Running Bootstrap (Init Tree)...")
    import core.bootstrap as bootstrap
    import core.fill_app_hawaa as hawaa_tree
    
    bootstrap.DSN = DSN
    await bootstrap.main()
    
    hawaa_tree.DSN = DSN
    await hawaa_tree.main()

    print("\nStep 2: Injecting All Component Logic...")
    await inject_layer(e, CPP_PILLARS, "cpp")
    await inject_layer(e, PY_PILLARS, "python")
    await inject_layer(e, NODE_PILLARS, "node")
    await inject_layer(e, MAS_PILLARS, "mas-js")
    await inject_layer(e, UI_PILLARS, "mas-js")
    await inject_layer(e, HAWAA_UI_PILLARS, "mas-js")

    print("\nStep 3: Compiling All Bundles...")
    out_dir = str(Path(__file__).parent.parent / "_build")
    if os.path.exists(out_dir):
        import shutil
        shutil.rmtree(out_dir)
    
    compiler = Compiler(e)
    files = await compiler.compile(out_dir, strategy="single-bundle")
    
    print(f"\n{'='*50}")
    print("SUCCESS: AI-FIRST PLATFORM BUILT FROM DATABASE")
    print(f"{'='*50}")
    print(f"Generated {len(files)} files in {out_dir}:")
    for f in files:
        print(f"  - {os.path.basename(f)} ({os.path.getsize(f)} bytes)")
    
    print("\nCommands to run your ecosystem:")
    print("  1. C++ ORM: ./_build/bundle-cpp.cpp (Compile with g++)")
    print("  2. Python API: python ./_build/bundle-python.py")
    print("  3. Node.js WS: node ./_build/bundle-node.js")
    
    await e.close()

if __name__ == "__main__":
    asyncio.run(main())
