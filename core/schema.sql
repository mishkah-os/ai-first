-- ============================================
-- QDML Platform — PostgreSQL Schema V3
-- Microservices-Ready. Code as Database Records.
--
-- Hierarchy: project → module(tier/app) → component → pillar(bulk)
-- Sync:     change_log (cursor-based, tombstones)
-- Services: service_registry
-- Auth:     platform_user + platform_session
-- ============================================

SET search_path TO qdml, public;

-- ============================================
-- CORE: Code Storage
-- ============================================

CREATE TABLE IF NOT EXISTS project (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    slug        TEXT UNIQUE NOT NULL,
    description TEXT DEFAULT '',
    db_schema   TEXT DEFAULT 'public',
    status      TEXT DEFAULT 'active' CHECK (status IN ('draft','active','archived')),
    icon        TEXT DEFAULT 'project',
    logo_url    TEXT DEFAULT '',
    base_domain TEXT,
    subdomain   TEXT,
    port        INT,
    service_name TEXT,
    service_type TEXT DEFAULT 'node',
    nginx_domain TEXT,
    test_url    TEXT,
    docs_en_md  TEXT DEFAULT '',
    docs_ar_md  TEXT DEFAULT '',
    test_credentials JSONB DEFAULT '{}',
    playwright_script TEXT,
    curl_tests  JSONB DEFAULT '[]',
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS module (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    tier        TEXT NOT NULL DEFAULT 'frontend' CHECK (tier IN ('frontend','backend','data','infra','shared')),
    app         TEXT DEFAULT 'main',
    assembler   TEXT DEFAULT 'concat',
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, slug)
);

CREATE TABLE IF NOT EXISTS component (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    module_id   UUID NOT NULL REFERENCES module(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    slug        TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'library' CHECK (kind IN ('screen','widget','service','binary','library','config')),
    target      TEXT NOT NULL DEFAULT 'mas-js' CHECK (target IN ('mas-js','node','python','cpp','sql','docker','bun')),
    meta        JSONB DEFAULT '{}',
    classification TEXT DEFAULT 'custom',
    description TEXT DEFAULT '',
    ai_category TEXT DEFAULT 'frontend',
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(module_id, slug)
);

CREATE TABLE IF NOT EXISTS pillar (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id    UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL DEFAULT 'bulk' CHECK (kind IN ('schema','logic','template','style','bulk','config','test')),
    content         TEXT NOT NULL DEFAULT '',
    lang            TEXT NOT NULL DEFAULT 'javascript',
    bulk_name       TEXT,
    bulk_order      INT DEFAULT 0,
    reveal          TEXT DEFAULT '',
    depends         TEXT DEFAULT '',
    exports         TEXT DEFAULT '',
    overflow        BOOLEAN DEFAULT false,
    description     TEXT DEFAULT '',
    human_summary   TEXT DEFAULT '',
    lines           INT GENERATED ALWAYS AS (array_length(string_to_array(content, E'\n'), 1)) STORED,
    chars           INT GENERATED ALWAYS AS (char_length(content)) STORED,
    bytes           INT GENERATED ALWAYS AS (octet_length(content)) STORED,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, bulk_name)
);

CREATE INDEX IF NOT EXISTS idx_pillar_component ON pillar(component_id, bulk_order);

-- ============================================
-- HISTORY: Code Time Machine
-- ============================================

CREATE TABLE IF NOT EXISTS bulk_history (
    id          BIGSERIAL PRIMARY KEY,
    pillar_id   UUID NOT NULL REFERENCES pillar(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    changed_by  TEXT DEFAULT 'system',
    reason      TEXT DEFAULT '',
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_history_pillar ON bulk_history(pillar_id, ts DESC);

-- ============================================
-- OPERATIONS: Metrics & Logging
-- ============================================

CREATE TABLE IF NOT EXISTS operation_log (
    id          BIGSERIAL PRIMARY KEY,
    project_id  UUID REFERENCES project(id),
    operation   TEXT NOT NULL,
    service     TEXT DEFAULT 'qdml',
    actor       TEXT DEFAULT 'system',
    success     BOOLEAN DEFAULT true,
    duration_ms INT,
    details     JSONB DEFAULT '{}',
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oplog_project ON operation_log(project_id, ts DESC);

-- ============================================
-- FEEDBACK: Syntax errors → AI correction loop
-- ============================================

CREATE TABLE IF NOT EXISTS syntax_error (
    id          BIGSERIAL PRIMARY KEY,
    pillar_id   UUID REFERENCES pillar(id) ON DELETE SET NULL,
    component_id UUID REFERENCES component(id) ON DELETE CASCADE,
    error_type  TEXT NOT NULL,
    message     TEXT NOT NULL,
    line        INT,
    col         INT,
    severity    TEXT DEFAULT 'error' CHECK (severity IN ('error','warning','info')),
    resolved    BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_syntax_unresolved ON syntax_error(component_id) WHERE resolved = false;

-- ============================================
-- SHARED: Functions, Variables, Tokens, i18n
-- ============================================

CREATE TABLE IF NOT EXISTS shared_function (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES project(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    signature   TEXT DEFAULT '',
    content     TEXT DEFAULT '',
    lang        TEXT DEFAULT 'javascript',
    category    TEXT DEFAULT 'util',
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, name)
);

CREATE TABLE IF NOT EXISTS global_var (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES project(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT DEFAULT '',
    value_type  TEXT DEFAULT 'string',
    scope       TEXT DEFAULT 'project',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, key)
);

CREATE TABLE IF NOT EXISTS design_token (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES project(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    category    TEXT DEFAULT 'color',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, key)
);

CREATE TABLE IF NOT EXISTS i18n_key (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES project(id) ON DELETE CASCADE,
    key         TEXT NOT NULL,
    ns          TEXT DEFAULT 'common',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, key)
);

CREATE TABLE IF NOT EXISTS i18n_value (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id      UUID NOT NULL REFERENCES i18n_key(id) ON DELETE CASCADE,
    lang        TEXT NOT NULL DEFAULT 'en',
    value       TEXT NOT NULL,
    UNIQUE(key_id, lang)
);

-- ============================================
-- ARTIFACTS: Non-code files (Dockerfile, .env, etc.)
-- ============================================

CREATE TABLE IF NOT EXISTS project_artifact (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES project(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    path        TEXT DEFAULT './',
    content     TEXT DEFAULT '',
    category    TEXT DEFAULT 'config',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, path, filename)
);

-- ============================================
-- MICROSERVICES: Service Registry
-- ============================================

CREATE TABLE IF NOT EXISTS service_registry (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID REFERENCES project(id) ON DELETE SET NULL,
    name        TEXT NOT NULL,
    url         TEXT NOT NULL,
    port        INT NOT NULL,
    protocol    TEXT DEFAULT 'http' CHECK (protocol IN ('http','ws','stdio','grpc')),
    health_url  TEXT,
    status      TEXT DEFAULT 'active' CHECK (status IN ('active','inactive','starting','error')),
    meta        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(name, port)
);

CREATE TABLE IF NOT EXISTS component_endpoint (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    endpoint_type TEXT NOT NULL DEFAULT 'preview',
    subdomain  TEXT,
    path        TEXT NOT NULL DEFAULT '/',
    port        INT,
    url         TEXT NOT NULL,
    health_url  TEXT,
    is_primary  BOOLEAN DEFAULT false,
    meta        JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(component_id, endpoint_type, path)
);

CREATE TABLE IF NOT EXISTS service_config (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    port        INT,
    env_vars    JSONB DEFAULT '{}',
    health_check TEXT,
    startup_cmd TEXT,
    test_routes JSONB DEFAULT '[]',
    UNIQUE(component_id)
);

CREATE TABLE IF NOT EXISTS test_suite (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    component_id UUID NOT NULL REFERENCES component(id) ON DELETE CASCADE,
    test_name   TEXT NOT NULL,
    test_type   TEXT NOT NULL,
    test_code   TEXT,
    curl_config JSONB,
    assertions  JSONB,
    last_run    TIMESTAMPTZ,
    last_result JSONB,
    UNIQUE(component_id, test_name)
);

-- ============================================
-- SYNC: Change Log (cursor-based, tombstones)
-- ============================================

CREATE SEQUENCE IF NOT EXISTS change_log_cursor_seq;

CREATE TABLE IF NOT EXISTS change_log (
    id          BIGSERIAL PRIMARY KEY,
    project_id  UUID NOT NULL REFERENCES project(id),
    table_name  TEXT NOT NULL,
    record_id   TEXT NOT NULL,
    action      TEXT NOT NULL CHECK (action IN ('insert','update','delete')),
    delta       JSONB,
    cursor_seq  BIGINT NOT NULL DEFAULT nextval('change_log_cursor_seq'),
    tombstone   BOOLEAN DEFAULT false,
    actor_id    UUID,
    ts          TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_changelog_cursor ON change_log(project_id, cursor_seq);
CREATE INDEX IF NOT EXISTS idx_changelog_table ON change_log(project_id, table_name, cursor_seq);

-- ============================================
-- SCHEMA REGISTRY: Schema-Driven Development
-- ============================================

CREATE TABLE IF NOT EXISTS schema_registry (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id  UUID NOT NULL REFERENCES project(id),
    table_name  TEXT NOT NULL,
    schema_doc  JSONB NOT NULL,
    version     INT DEFAULT 1,
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, table_name, version)
);

-- ============================================
-- AUTH: Platform Users & Sessions
-- ============================================

CREATE TABLE IF NOT EXISTS platform_user (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username    TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role        TEXT DEFAULT 'developer' CHECK (role IN ('superadmin','admin','developer','viewer')),
    is_active   BOOLEAN DEFAULT true,
    created_at  TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS platform_session (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES platform_user(id) ON DELETE CASCADE,
    token       TEXT UNIQUE NOT NULL,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_session_token ON platform_session(token);
CREATE INDEX IF NOT EXISTS idx_session_expires ON platform_session(expires_at);

-- ============================================
-- NOTIFY: Real-time change propagation
-- ============================================

CREATE OR REPLACE FUNCTION qdml_notify_change() RETURNS TRIGGER AS $$
DECLARE
    payload JSONB;
    rec_id TEXT;
    proj_id UUID;
BEGIN
    rec_id := CASE WHEN TG_OP = 'DELETE' THEN OLD.id::text ELSE NEW.id::text END;

    -- Try to get project_id from the row
    IF TG_OP = 'DELETE' THEN
        proj_id := NULL;
    ELSE
        BEGIN
            proj_id := (row_to_json(NEW)::jsonb)->>'project_id';
        EXCEPTION WHEN OTHERS THEN
            proj_id := NULL;
        END;
    END IF;

    payload := jsonb_build_object(
        'table', TG_TABLE_NAME,
        'id', rec_id,
        'op', lower(TG_OP),
        'project_id', proj_id
    );

    PERFORM pg_notify('qdml_changes', payload::text);
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to pillar table (most important for code changes)
DROP TRIGGER IF EXISTS trg_pillar_notify ON pillar;
CREATE TRIGGER trg_pillar_notify
    AFTER INSERT OR UPDATE OR DELETE ON pillar
    FOR EACH ROW EXECUTE FUNCTION qdml_notify_change();

-- ============================================
-- SEED: Default admin user (password: admin)
-- ============================================

INSERT INTO platform_user (username, password_hash, display_name, role)
VALUES ('admin', encode(sha256('admin'::bytea), 'hex'), 'Administrator', 'superadmin')
ON CONFLICT (username) DO NOTHING;
