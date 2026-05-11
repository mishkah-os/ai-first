"""Register Mostamal Hawaa App Module into the Kernel Tree."""
import asyncio, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from core.engine import CoreEngine

DSN = "postgresql://aifirst:aifirst_password@localhost:5433/ai_first_platform"

HAWAA_TREE = [
    ("Hawaa Core Logic",    "hawaa-logic",      "library", "mas-js"),
    ("Hawaa Theme",         "hawaa-theme",      "library", "mas-js"),
    ("Feed Component",      "hawaa-feed",       "widget",  "mas-js"),
    ("Post Editor",         "hawaa-editor",     "widget",  "mas-js"),
    ("Auth Controller",     "hawaa-auth",       "library", "mas-js"),
    ("Admin Dashboard",     "hawaa-admin-db",   "screen",  "mas-js"),
    ("Hawaa API Wrapper",   "hawaa-api",        "library", "python"),
]

async def main():
    e = CoreEngine(DSN)
    # We wait for DB connection
    try:
        await e.connect()
    except:
        print("Plan: Register Mostamal Hawaa App Tree")
        for name, slug, kind, target in HAWAA_TREE:
            print(f"  + {name} [{target}]")
        return

    mid = await e.create_module("Mostamal Hawaa", "mostamal-hawaa", sort_order=100)
    print(f"Module Created: Mostamal Hawaa (id={mid})")
    
    for name, slug, kind, target in HAWAA_TREE:
        cid = await e.create_component("mostamal-hawaa", name, slug, kind=kind, target=target)
        print(f"  Component Registered: {name} (id={cid})")

    await e.close()

if __name__ == "__main__":
    asyncio.run(main())
