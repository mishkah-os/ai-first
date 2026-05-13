#!/usr/bin/env python3
"""Add task system, agent traces, and WS event notifications"""
import asyncio
import asyncpg
from config import DATABASE_URL, QDML_SCHEMA

async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    s = QDML_SCHEMA

    # Tasks table
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {s}.tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            project_id UUID REFERENCES {s}.project(id),
            title TEXT NOT NULL,
            task_type TEXT NOT NULL,
            classification TEXT,
            target_component TEXT,
            status TEXT DEFAULT 'pending',
            user_prompt TEXT NOT NULL,
            plan JSONB,
            result_summary TEXT,
            created_by TEXT DEFAULT 'user',
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ,
            archived BOOLEAN DEFAULT false
        )
    """)
    print("  ✅ tasks")

    # Agent executions
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {s}.agent_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            task_id UUID REFERENCES {s}.tasks(id) ON DELETE CASCADE,
            agent_role TEXT NOT NULL,
            classification TEXT,
            target_component TEXT,
            status TEXT DEFAULT 'running',
            system_prompt_used TEXT,
            user_message TEXT,
            ai_response TEXT,
            tokens_used INT DEFAULT 0,
            duration_ms INT DEFAULT 0,
            error TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            completed_at TIMESTAMPTZ
        )
    """)
    print("  ✅ agent_executions")

    # Task events (WS-broadcastable)
    await conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {s}.task_events (
            id BIGSERIAL PRIMARY KEY,
            task_id UUID REFERENCES {s}.tasks(id) ON DELETE CASCADE,
            agent_execution_id UUID REFERENCES {s}.agent_executions(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            payload JSONB DEFAULT '{{}}',
            created_at TIMESTAMPTZ DEFAULT now()
        )
    """)
    print("  ✅ task_events")

    # Classification improvements
    cols = [
        ("classification_registry", "ai_instructions_md", "TEXT DEFAULT ''"),
        ("classification_registry", "human_docs_ar", "TEXT DEFAULT ''"),
        ("classification_registry", "human_docs_en", "TEXT DEFAULT ''"),
        ("classification_registry", "is_system", "BOOLEAN DEFAULT false"),
        ("classification_registry", "allow_create", "BOOLEAN DEFAULT true"),
        ("classification_registry", "allow_update", "BOOLEAN DEFAULT true"),
    ]
    for table, col, dtype in cols:
        try:
            await conn.execute(f"ALTER TABLE {s}.{table} ADD COLUMN IF NOT EXISTS {col} {dtype}")
        except:
            pass
    print("  ✅ classification_registry extended")

    # Indexes
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_tasks_project ON {s}.tasks(project_id, status)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_tasks_status ON {s}.tasks(status, created_at DESC)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_agent_task ON {s}.agent_executions(task_id, created_at)")
    await conn.execute(f"CREATE INDEX IF NOT EXISTS idx_events_task ON {s}.task_events(task_id, created_at)")
    print("  ✅ indexes")

    # WS notification trigger
    await conn.execute(f"""
        CREATE OR REPLACE FUNCTION {s}.notify_task_event() RETURNS trigger AS $fn$
        BEGIN
            PERFORM pg_notify('task_events', json_build_object(
                'task_id', NEW.task_id,
                'event_type', NEW.event_type,
                'payload', NEW.payload
            )::text);
            RETURN NEW;
        END;
        $fn$ LANGUAGE plpgsql
    """)

    try:
        await conn.execute(f"""
            CREATE TRIGGER trg_task_event_notify
            AFTER INSERT ON {s}.task_events
            FOR EACH ROW EXECUTE FUNCTION {s}.notify_task_event()
        """)
    except:
        pass
    print("  ✅ WS notify trigger")

    await conn.close()
    print("\n✅ Task system complete")

if __name__ == "__main__":
    asyncio.run(main())
