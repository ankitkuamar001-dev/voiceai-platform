-- ============================================================
-- AI Voice Customer Support Agent — Initial Database Migration
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- 1. ORGANIZATIONS (Multi-tenant)
-- ============================================================
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(100) NOT NULL UNIQUE,
    domain          VARCHAR(255),
    plan            VARCHAR(50) NOT NULL DEFAULT 'free'
                        CHECK (plan IN ('free', 'starter', 'professional', 'enterprise')),
    settings        JSONB NOT NULL DEFAULT '{}',
    max_agents      INT NOT NULL DEFAULT 5,
    max_concurrent_calls INT NOT NULL DEFAULT 10,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_organizations_slug ON organizations(slug);

-- ============================================================
-- 2. USERS
-- ============================================================
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    email           VARCHAR(320) NOT NULL,
    password_hash   VARCHAR(255),
    full_name       VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    avatar_url      TEXT,
    user_type       VARCHAR(20) NOT NULL DEFAULT 'customer'
                        CHECK (user_type IN ('customer', 'agent', 'admin', 'superadmin')),
    status          VARCHAR(20) NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'inactive', 'suspended', 'pending_verification')),
    timezone        VARCHAR(50) DEFAULT 'UTC',
    locale          VARCHAR(10) DEFAULT 'en-US',
    last_login_at   TIMESTAMPTZ,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_users_email_org UNIQUE (org_id, email)
);

CREATE INDEX idx_users_org_id ON users(org_id);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_org_type ON users(org_id, user_type);

-- ============================================================
-- 3. ROLES & PERMISSIONS (RBAC)
-- ============================================================
CREATE TABLE roles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    is_system       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_roles_org_name UNIQUE (org_id, name)
);

CREATE TABLE permissions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource        VARCHAR(100) NOT NULL,
    action          VARCHAR(50) NOT NULL,
    description     TEXT,
    CONSTRAINT uq_permissions_resource_action UNIQUE (resource, action)
);

CREATE TABLE role_permissions (
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    permission_id   UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE user_roles (
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id         UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    assigned_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_id, org_id)
);

-- ============================================================
-- 4. SLA POLICIES (must be before tickets)
-- ============================================================
CREATE TABLE sla_policies (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name            VARCHAR(100) NOT NULL,
    description     TEXT,
    priority        SMALLINT NOT NULL CHECK (priority BETWEEN 1 AND 5),
    first_response_minutes   INT NOT NULL,
    next_response_minutes    INT NOT NULL,
    resolution_minutes       INT NOT NULL,
    business_hours_only      BOOLEAN NOT NULL DEFAULT TRUE,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    conditions      JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_sla_org_priority UNIQUE (org_id, priority)
);

-- ============================================================
-- 5. CONVERSATIONS (Voice Calls)
-- ============================================================
CREATE TABLE conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_id     UUID REFERENCES users(id),
    assigned_agent_id UUID REFERENCES users(id),
    channel         VARCHAR(30) NOT NULL DEFAULT 'voice'
                        CHECK (channel IN ('voice', 'chat', 'email', 'sms', 'whatsapp')),
    status          VARCHAR(30) NOT NULL DEFAULT 'initiated'
                        CHECK (status IN (
                            'initiated', 'ringing', 'queued', 'in_progress', 'on_hold',
                            'transferring', 'wrap_up', 'completed', 'abandoned', 'failed'
                        )),
    direction       VARCHAR(10) NOT NULL DEFAULT 'inbound'
                        CHECK (direction IN ('inbound', 'outbound')),
    priority        SMALLINT NOT NULL DEFAULT 3
                        CHECK (priority BETWEEN 1 AND 5),
    caller_number   VARCHAR(20),
    dialed_number   VARCHAR(20),
    language        VARCHAR(10) DEFAULT 'en-US',
    sentiment_score NUMERIC(4,3) CHECK (sentiment_score BETWEEN -1 AND 1),
    ai_confidence   NUMERIC(4,3) CHECK (ai_confidence BETWEEN 0 AND 1),
    is_ai_handled   BOOLEAN NOT NULL DEFAULT TRUE,
    transfer_count  SMALLINT NOT NULL DEFAULT 0,
    queue_wait_seconds INT,
    talk_duration_seconds INT,
    hold_duration_seconds INT DEFAULT 0,
    disposition     VARCHAR(100),
    summary         TEXT,
    tags            TEXT[] DEFAULT '{}',
    metadata        JSONB NOT NULL DEFAULT '{}',
    livekit_room_id VARCHAR(255),
    started_at      TIMESTAMPTZ,
    answered_at     TIMESTAMPTZ,
    ended_at        TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_conversations_org ON conversations(org_id);
CREATE INDEX idx_conversations_customer ON conversations(org_id, customer_id);
CREATE INDEX idx_conversations_status ON conversations(org_id, status);
CREATE INDEX idx_conversations_created ON conversations(org_id, created_at DESC);
CREATE INDEX idx_conversations_tags ON conversations USING GIN(tags);

-- ============================================================
-- 6. MESSAGES (Conversation Turns)
-- ============================================================
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    sender_type     VARCHAR(20) NOT NULL
                        CHECK (sender_type IN ('customer', 'agent', 'ai_bot', 'system')),
    sender_id       UUID REFERENCES users(id),
    content         TEXT NOT NULL,
    content_type    VARCHAR(30) NOT NULL DEFAULT 'text'
                        CHECK (content_type IN ('text', 'audio_transcript', 'action', 'system_event')),
    confidence      NUMERIC(4,3),
    language        VARCHAR(10),
    sentiment       VARCHAR(20),
    intent          VARCHAR(100),
    entities        JSONB DEFAULT '{}',
    is_redacted     BOOLEAN NOT NULL DEFAULT FALSE,
    token_count     INT,
    duration_ms     INT,
    sequence_num    INT NOT NULL,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_messages_conversation_seq UNIQUE (conversation_id, sequence_num)
);

CREATE INDEX idx_messages_conversation ON messages(conversation_id, sequence_num);
CREATE INDEX idx_messages_org_created ON messages(org_id, created_at DESC);

-- ============================================================
-- 7. TICKETS
-- ============================================================
CREATE TABLE tickets (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id),
    customer_id     UUID NOT NULL REFERENCES users(id),
    assigned_agent_id UUID REFERENCES users(id),
    ticket_number   BIGSERIAL,
    subject         VARCHAR(500) NOT NULL,
    description     TEXT,
    status          VARCHAR(30) NOT NULL DEFAULT 'open'
                        CHECK (status IN ('open', 'in_progress', 'waiting_on_customer',
                                          'waiting_on_agent', 'escalated', 'resolved', 'closed')),
    priority        SMALLINT NOT NULL DEFAULT 3
                        CHECK (priority BETWEEN 1 AND 5),
    category        VARCHAR(100),
    subcategory     VARCHAR(100),
    source          VARCHAR(30) NOT NULL DEFAULT 'voice'
                        CHECK (source IN ('voice', 'chat', 'email', 'web_form', 'api')),
    sla_policy_id   UUID REFERENCES sla_policies(id),
    first_response_at TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    closed_at       TIMESTAMPTZ,
    sla_breach      BOOLEAN NOT NULL DEFAULT FALSE,
    tags            TEXT[] DEFAULT '{}',
    custom_fields   JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_tickets_org_number UNIQUE (org_id, ticket_number)
);

CREATE INDEX idx_tickets_org_status ON tickets(org_id, status);
CREATE INDEX idx_tickets_customer ON tickets(org_id, customer_id);
CREATE INDEX idx_tickets_created ON tickets(org_id, created_at DESC);
CREATE INDEX idx_tickets_sla_breach ON tickets(org_id, sla_breach) WHERE sla_breach = TRUE;

-- ============================================================
-- 8. ESCALATIONS
-- ============================================================
CREATE TABLE escalations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id),
    ticket_id       UUID REFERENCES tickets(id),
    escalated_from  UUID REFERENCES users(id),
    escalated_to    UUID REFERENCES users(id),
    escalation_type VARCHAR(30) NOT NULL
                        CHECK (escalation_type IN (
                            'ai_to_agent', 'agent_to_supervisor', 'agent_to_specialist',
                            'sla_breach', 'customer_request', 'sentiment_threshold'
                        )),
    reason          TEXT NOT NULL,
    priority        SMALLINT NOT NULL DEFAULT 3,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'accepted', 'rejected', 'resolved', 'expired')),
    ai_confidence_at_escalation NUMERIC(4,3),
    sentiment_at_escalation     NUMERIC(4,3),
    metadata        JSONB NOT NULL DEFAULT '{}',
    escalated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at     TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_escalations_org ON escalations(org_id);
CREATE INDEX idx_escalations_conversation ON escalations(conversation_id);
CREATE INDEX idx_escalations_status ON escalations(org_id, status);

-- ============================================================
-- 9. KNOWLEDGE BASE
-- ============================================================
CREATE TABLE kb_categories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    parent_id       UUID REFERENCES kb_categories(id),
    name            VARCHAR(200) NOT NULL,
    slug            VARCHAR(200) NOT NULL,
    description     TEXT,
    sort_order      INT NOT NULL DEFAULT 0,
    is_published    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kb_cat_org_slug UNIQUE (org_id, slug)
);

CREATE TABLE kb_articles (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    category_id     UUID REFERENCES kb_categories(id),
    author_id       UUID NOT NULL REFERENCES users(id),
    title           VARCHAR(500) NOT NULL,
    slug            VARCHAR(500) NOT NULL,
    content         TEXT NOT NULL,
    content_format  VARCHAR(20) NOT NULL DEFAULT 'markdown',
    excerpt         VARCHAR(1000),
    status          VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'review', 'published', 'archived')),
    visibility      VARCHAR(20) NOT NULL DEFAULT 'public'
                        CHECK (visibility IN ('public', 'internal', 'agents_only')),
    language        VARCHAR(10) NOT NULL DEFAULT 'en',
    version         INT NOT NULL DEFAULT 1,
    tags            TEXT[] DEFAULT '{}',
    embedding_id    VARCHAR(255),
    view_count      INT NOT NULL DEFAULT 0,
    helpful_count   INT NOT NULL DEFAULT 0,
    last_indexed_at TIMESTAMPTZ,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_kb_articles_org_slug UNIQUE (org_id, slug)
);

CREATE INDEX idx_kb_articles_org_status ON kb_articles(org_id, status);
CREATE INDEX idx_kb_articles_tags ON kb_articles USING GIN(tags);

-- ============================================================
-- 10. CALL RECORDINGS
-- ============================================================
CREATE TABLE call_recordings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    storage_provider VARCHAR(20) NOT NULL DEFAULT 's3',
    storage_bucket  VARCHAR(255) NOT NULL,
    storage_key     VARCHAR(1000) NOT NULL,
    file_format     VARCHAR(10) NOT NULL DEFAULT 'wav',
    file_size_bytes BIGINT NOT NULL,
    duration_seconds INT NOT NULL,
    sample_rate     INT DEFAULT 16000,
    channels        SMALLINT DEFAULT 1,
    transcription_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                        CHECK (transcription_status IN ('pending', 'processing', 'completed', 'failed')),
    is_redacted     BOOLEAN NOT NULL DEFAULT FALSE,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_recordings_conversation ON call_recordings(conversation_id);
CREATE INDEX idx_recordings_org ON call_recordings(org_id, created_at DESC);

-- ============================================================
-- 11. ANALYTICS EVENTS
-- ============================================================
CREATE TABLE analytics_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    event_type      VARCHAR(100) NOT NULL,
    event_category  VARCHAR(50) NOT NULL
                        CHECK (event_category IN ('call', 'ai', 'agent', 'ticket', 'kb', 'system', 'user')),
    actor_type      VARCHAR(20)
                        CHECK (actor_type IN ('customer', 'agent', 'ai_bot', 'system')),
    actor_id        UUID,
    conversation_id UUID REFERENCES conversations(id),
    ticket_id       UUID REFERENCES tickets(id),
    properties      JSONB NOT NULL DEFAULT '{}',
    numeric_value   NUMERIC(12,4),
    occurred_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_analytics_org_type ON analytics_events(org_id, event_type, occurred_at DESC);
CREATE INDEX idx_analytics_org_category ON analytics_events(org_id, event_category, occurred_at DESC);

-- ============================================================
-- 12. AUDIT LOG
-- ============================================================
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    resource_type   VARCHAR(100) NOT NULL,
    resource_id     UUID,
    old_value       JSONB,
    new_value       JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_org ON audit_log(org_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit_log(user_id, created_at DESC);

-- ============================================================
-- 13. UPDATED_AT TRIGGERS
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_organizations_updated BEFORE UPDATE ON organizations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_conversations_updated BEFORE UPDATE ON conversations FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_tickets_updated BEFORE UPDATE ON tickets FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_kb_articles_updated BEFORE UPDATE ON kb_articles FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_call_recordings_updated BEFORE UPDATE ON call_recordings FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER trg_sla_policies_updated BEFORE UPDATE ON sla_policies FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 14. SEED DATA
-- ============================================================

-- Default permissions
INSERT INTO permissions (resource, action, description) VALUES
    ('conversations', 'read', 'View conversations'),
    ('conversations', 'write', 'Create/update conversations'),
    ('conversations', 'delete', 'Delete conversations'),
    ('tickets', 'read', 'View tickets'),
    ('tickets', 'write', 'Create/update tickets'),
    ('tickets', 'delete', 'Delete tickets'),
    ('tickets', 'escalate', 'Escalate tickets'),
    ('knowledge_base', 'read', 'View knowledge base'),
    ('knowledge_base', 'write', 'Edit knowledge base'),
    ('knowledge_base', 'delete', 'Delete KB articles'),
    ('analytics', 'read', 'View analytics'),
    ('analytics', 'export', 'Export analytics data'),
    ('users', 'read', 'View users'),
    ('users', 'write', 'Manage users'),
    ('users', 'delete', 'Delete users'),
    ('settings', 'read', 'View settings'),
    ('settings', 'write', 'Modify settings'),
    ('recordings', 'read', 'Listen to recordings'),
    ('recordings', 'delete', 'Delete recordings');

-- Default organization
INSERT INTO organizations (id, name, slug, plan) VALUES
    ('00000000-0000-0000-0000-000000000001', 'VoiceAI Demo', 'voiceai-demo', 'enterprise');

-- Default admin user (password: admin123 — change in production!)
INSERT INTO users (id, org_id, email, password_hash, full_name, user_type, status) VALUES
    ('00000000-0000-0000-0000-000000000002',
     '00000000-0000-0000-0000-000000000001',
     'admin@voiceai.demo',
     '$2b$12$LQv3c1yqBo9SkvXS7QTJJeJx.z7UdE7z4xNxG2Q.h0HZsD6m5z8ee',
     'Admin User',
     'admin',
     'active');

-- Default roles
INSERT INTO roles (org_id, name, description, is_system) VALUES
    ('00000000-0000-0000-0000-000000000001', 'admin', 'Full system access', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'supervisor', 'Team management and escalation handling', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'agent', 'Handle customer interactions', TRUE),
    ('00000000-0000-0000-0000-000000000001', 'customer', 'Customer self-service access', TRUE);

-- Default SLA policies
INSERT INTO sla_policies (org_id, name, priority, first_response_minutes, next_response_minutes, resolution_minutes) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Critical', 1, 5, 15, 60),
    ('00000000-0000-0000-0000-000000000001', 'High', 2, 15, 30, 240),
    ('00000000-0000-0000-0000-000000000001', 'Medium', 3, 60, 120, 480),
    ('00000000-0000-0000-0000-000000000001', 'Low', 4, 240, 480, 1440),
    ('00000000-0000-0000-0000-000000000001', 'Minimal', 5, 480, 1440, 2880);
