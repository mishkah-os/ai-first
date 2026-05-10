-- ============================================
-- AI-First Core Engine — Component Model Schema V2
-- Code as structured data. QDML Protocol.
--
-- Hierarchy: project → module(tier/app) → component → pillar(bulk)
-- History:   bulk_history (full content snapshots)
-- Feedback:  syntax_error (compile → AI loop)
-- ============================================

-- Project: top-level container for mega-projects
CREATE TABLE IF NOT EXISTS project (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Module: grouped by project, tier, and app/service
CREATE TABLE IF NOT EXISTS module (
    id          SERIAL PRIMARY KEY,
    project_id  INT REFERENCES project(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    tier        TEXT DEFAULT 'frontend',   -- frontend | backend | data | infra
    app         TEXT DEFAULT 'main',       -- admin | portal | api_gateway | auth_service | ...
    sort_order  INT DEFAULT 0,
    assembler   TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, slug)
);

-- Component: a unit of code that compiles to output
CREATE TABLE IF NOT EXISTS component (
    id          SERIAL PRIMARY KEY,
    module_id   INT NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    kind        TEXT DEFAULT 'screen',   -- screen | widget | service | binary | script | library
    target      TEXT DEFAULT 'mas-js',   -- mas-js | cpp | python | node
    meta        JSONB DEFAULT '{}',      -- {persist:[], fetchUrl:'', persistEnv:[]}
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(module_id, slug)
);

-- Pillar: code unit — classic (schema/logic/template/style) or bulk (m-bulk)
CREATE TABLE IF NOT EXISTS pillar (
    id              SERIAL PRIMARY KEY,
    component_id    INT NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,             -- schema | template | logic | style | bulk
    content         TEXT DEFAULT '',
    lang            TEXT DEFAULT 'javascript',
    bulk_name       TEXT,                      -- e.g. 'render_engine', 'constants'
    bulk_order      INT DEFAULT 0,             -- sort order for assembly
    reveal          TEXT DEFAULT '',            -- '0:2,8:9,24:25' — important lines for mini-code
    depends         TEXT DEFAULT '',            -- 'B02:constants,B08:head_manager'
    exports         TEXT DEFAULT '',            -- 'render,setProps'
    overflow        BOOLEAN DEFAULT false,      -- true = consciously exceeds 100-line limit
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, kind, bulk_name)
);

-- Bulk History: full snapshot before every mutation (code time-machine)
CREATE TABLE IF NOT EXISTS bulk_history (
    id          BIGSERIAL PRIMARY KEY,
    pillar_id   INT NOT NULL REFERENCES pillar(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,                 -- the OLD content before mutation
    changed_by  TEXT DEFAULT 'ai',             -- 'ai' | 'human' | 'system'
    reason      TEXT DEFAULT '',               -- why this change was made
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_bulk_history_pillar ON bulk_history(pillar_id, ts DESC);

-- Syntax Errors: compile feedback → AI correction loop
CREATE TABLE IF NOT EXISTS syntax_error (
    id          BIGSERIAL PRIMARY KEY,
    pillar_id   INT REFERENCES pillar(id) ON DELETE SET NULL,
    component_id INT REFERENCES component(id) ON DELETE CASCADE,
    error_type  TEXT NOT NULL,                 -- 'syntax' | 'reference' | 'type' | 'lint'
    message     TEXT NOT NULL,
    line        INT,                           -- line number within the bulk
    col         INT,                           -- column number
    severity    TEXT DEFAULT 'error',          -- 'error' | 'warning' | 'info'
    resolved    BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_syntax_error_unresolved ON syntax_error(component_id) WHERE resolved = false;

-- Shared functions: global utilities visible to AI context and all components
CREATE TABLE IF NOT EXISTS shared_function (
    id          SERIAL PRIMARY KEY,
    name        TEXT UNIQUE NOT NULL,
    content     TEXT DEFAULT '',
    lang        TEXT DEFAULT 'javascript',
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Global variables: app-wide or scoped constants
CREATE TABLE IF NOT EXISTS global_var (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    value       TEXT DEFAULT '',
    scope       TEXT DEFAULT 'app',
    scope_ref   TEXT,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Design tokens: CSS custom properties stored as data
CREATE TABLE IF NOT EXISTS design_token (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    value       TEXT NOT NULL,
    category    TEXT DEFAULT 'color',
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- i18n: key-first internationalization
CREATE TABLE IF NOT EXISTS i18n_key (
    id          SERIAL PRIMARY KEY,
    key         TEXT UNIQUE NOT NULL,
    ns          TEXT DEFAULT 'common',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS i18n_value (
    id          SERIAL PRIMARY KEY,
    key_id      INT NOT NULL REFERENCES i18n_key(id) ON DELETE CASCADE,
    lang        TEXT NOT NULL DEFAULT 'en',
    value       TEXT NOT NULL,
    UNIQUE(key_id, lang)
);

-- ============================================
-- Project Artifacts: EVERY file that isn't code
-- .env, requirements.txt, Dockerfile, .gitignore,
-- package.json, nginx.conf, systemd service files...
-- ALL stored here, ALL compiled to disk with the project.
-- ============================================
CREATE TABLE IF NOT EXISTS project_artifact (
    id          SERIAL PRIMARY KEY,
    filename    TEXT NOT NULL,             -- e.g. '.env', 'Dockerfile', '.gitignore'
    path        TEXT DEFAULT './',         -- relative output path
    content     TEXT DEFAULT '',
    category    TEXT DEFAULT 'config',     -- config | build | env | docker | ignore | readme | service
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(path, filename)
);

-- ============================================
-- Change log: every mutation recorded.
-- Tombstone = true means a DELETE (for sync propagation).
-- ============================================
CREATE TABLE IF NOT EXISTS change_log (
    id          BIGSERIAL PRIMARY KEY,
    table_name  TEXT NOT NULL,
    row_id      INT NOT NULL,
    operation   TEXT NOT NULL CHECK (operation IN ('INSERT', 'UPDATE', 'DELETE')),
    payload     JSONB,
    tombstone   BOOLEAN DEFAULT false,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_changelog_ts ON change_log(ts);
CREATE INDEX IF NOT EXISTS idx_changelog_table ON change_log(table_name, row_id);

-- Real-time Notification Function
CREATE OR REPLACE FUNCTION notify_change() RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
BEGIN
    payload = jsonb_build_object(
        'table', TG_TABLE_NAME,
        'id', (CASE WHEN TG_OP = 'DELETE' THEN OLD.id ELSE NEW.id END),
        'op', TG_OP
    );
    
    INSERT INTO change_log (table_name, row_id, operation, payload, tombstone)
    VALUES (TG_TABLE_NAME, (payload->>'id')::int, TG_OP, (CASE WHEN TG_OP = 'DELETE' THEN NULL ELSE row_to_json(NEW)::jsonb END), (TG_OP = 'DELETE'));
    
    PERFORM pg_notify('change_log_event', payload::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;
