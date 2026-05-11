"""Nucleus CLI — The Command Center for AI-First Unified Platform."""
import asyncio, sys, os
from pathlib import Path
from core.engine import CoreEngine
from core.compiler import Compiler

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

async def show_status():
    e = CoreEngine(DSN)
    try:
        await e.connect()
        counts = await e.count()
        tree = await e.describe()
        print("\n--- Nucleus Status ---")
        print(f"Database: CONNECTED")
        print(f"Modules: {counts['modules']}")
        print(f"Components: {counts['components']}")
        print(f"Pillars: {counts['pillars']}")
        print(f"Project Artifacts: {counts['artifacts']}")
        print(f"Recent Changes: {counts['changes']}")
        print("\n--- Active Tree ---")
        for mod in tree:
            print(f"📦 {mod['module']} ({mod['slug']})")
            for c in mod['components']:
                print(f"  └─ {c['name']} [{c['target']}]")
        await e.close()
    except Exception as err:
        print(f"Database: OFFLINE ({err})")

async def build_platform():
    print("\n🚀 Launching Master Injector...")
    import core.master_injector as master
    await master.main()

async def compile_only():
    print("\n⚙️ Compiling Database State to Files...")
    e = CoreEngine(DSN)
    await e.connect()
    c = Compiler(e)
    out = str(Path(__file__).parent / "_build")
    files = await c.compile(out, strategy="single-bundle")
    print(f"Done. Generated {len(files)} bundles in {out}")
    await e.close()

def print_help():
    print("""
AI-First Nucleus CLI
Usage: python nucleus.py [command]

Commands:
  status   - Show current database state and component tree
  build    - Full bootstrap, injection, and compilation
  compile  - Generate physical files from current DB state
  help     - Show this help
    """)

async def main():
    if len(sys.argv) < 2:
        print_help()
        return

    cmd = sys.argv[1].lower()
    if cmd == "status":
        await show_status()
    elif cmd == "build":
        await build_platform()
    elif cmd == "compile":
        await compile_only()
    else:
        print_help()

if __name__ == "__main__":
    asyncio.run(main())
