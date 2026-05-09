-- ============================================
-- AI-First Core Engine — Component Model Schema
-- The heart of the system: code as structured data.
--
-- Rules:
--   1. Every piece of code lives here as a row
--   2. Every config file lives here as a project_artifact
--   3. Every mutation is logged in change_log
--   4. Nothing exists on disk except the core engine itself
-- ============================================

-- Module: top-level grouping (e.g. "auth", "dashboard", "accounting")
CREATE TABLE IF NOT EXISTS module (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now()
);

-- Component: a unit of code that compiles to output
CREATE TABLE IF NOT EXISTS component (
    id          SERIAL PRIMARY KEY,
    module_id   INT NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    kind        TEXT DEFAULT 'screen',   -- screen | widget | service | binary | script | library
    target      TEXT DEFAULT 'mas-js',   -- mas-js | cpp | python | node
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(module_id, slug)
);

-- Pillar: one of the 4 code pillars per component
CREATE TABLE IF NOT EXISTS pillar (
    id              SERIAL PRIMARY KEY,
    component_id    INT NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL CHECK (kind IN ('schema', 'template', 'logic', 'style')),
    content         TEXT DEFAULT '',
    lang            TEXT DEFAULT 'javascript',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, kind)
);

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
