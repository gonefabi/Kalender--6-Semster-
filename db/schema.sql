CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL,
    earliest_start TIMESTAMPTZ NOT NULL,
    "due" TIMESTAMPTZ NOT NULL,
    priority INTEGER NOT NULL DEFAULT 1,
    preferred_windows JSONB,
    metadata_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    external_id VARCHAR(255),
    source VARCHAR(64),
    metadata_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_meetings_external_id ON meetings(external_id);

CREATE TABLE IF NOT EXISTS plan_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    module VARCHAR(32) NOT NULL,
    label VARCHAR(255),
    metrics JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS task_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    plan_snapshot_id UUID NOT NULL REFERENCES plan_snapshots(id) ON DELETE CASCADE,
    task_id UUID NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    scheduled_start TIMESTAMPTZ NOT NULL,
    scheduled_end TIMESTAMPTZ NOT NULL,
    deviation_minutes INTEGER NOT NULL DEFAULT 0,
    tardiness_minutes INTEGER NOT NULL DEFAULT 0,
    cost_components JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_assignments_plan ON task_assignments(plan_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_task_assignments_task ON task_assignments(task_id);

CREATE TABLE IF NOT EXISTS integration_credentials (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    provider VARCHAR(64) NOT NULL,
    account_email VARCHAR(255),
    calendar_id VARCHAR(255),
    access_token TEXT,
    refresh_token TEXT,
    token_expiry TIMESTAMPTZ,
    scopes JSON,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_integration_credentials_provider ON integration_credentials(provider);
