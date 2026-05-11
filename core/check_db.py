import asyncio
import asyncpg

async def check():
    for port in [5432, 5433]:
        try:
            conn = await asyncpg.connect(f'postgresql://aifirst:aifirst_password@localhost:{port}/ai_first_platform')
            print(f"CONNECTED TO {port}")
            await conn.close()
            return
        except Exception as e:
            print(f"FAILED {port}: {e}")

if __name__ == "__main__":
    asyncio.run(check())
