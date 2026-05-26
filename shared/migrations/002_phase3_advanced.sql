-- ============================================================
-- Phase 3 Advanced Features - Database Migration
-- ============================================================

-- 1. WHATSAPP & INTENT SUPPORT (Conversations)
-- Add fields for WhatsApp sessions and AI intent tracking
ALTER TABLE conversations
    ADD COLUMN whatsapp_session_id VARCHAR(255),
    ADD COLUMN whatsapp_phone VARCHAR(50),
    ADD COLUMN intent_history TEXT[] DEFAULT '{}';

CREATE INDEX idx_conversations_whatsapp ON conversations(whatsapp_phone);

-- 2. HANDOFF QUEUE
-- Table to manage the queue of customers waiting for human agents
CREATE TABLE handoff_requests (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id          UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    escalation_id   UUID REFERENCES escalations(id) ON DELETE CASCADE,
    customer_id     UUID REFERENCES users(id),
    status          VARCHAR(30) NOT NULL DEFAULT 'queued'
                        CHECK (status IN ('queued', 'routing', 'assigned', 'abandoned', 'resolved')),
    assigned_to     UUID REFERENCES users(id),
    priority        SMALLINT NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    wait_time_sec   INT DEFAULT 0,
    requested_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    assigned_at     TIMESTAMPTZ,
    resolved_at     TIMESTAMPTZ,
    CONSTRAINT uq_handoff_conversation UNIQUE (conversation_id)
);

CREATE INDEX idx_handoff_org_status ON handoff_requests(org_id, status);
CREATE INDEX idx_handoff_priority ON handoff_requests(org_id, priority, requested_at ASC);

-- 3. ESCALATION ENGINE SIGNALS
-- Add JSONB field to track which signals triggered the escalation
ALTER TABLE escalations
    ADD COLUMN escalation_signals JSONB NOT NULL DEFAULT '[]';

-- 4. CALL RECORDING PLAYBACK
-- Add field for cached playback URL
ALTER TABLE call_recordings
    ADD COLUMN recording_url VARCHAR(2048);

-- Update timestamp trigger for new table
CREATE TRIGGER trg_handoff_requests_updated
    BEFORE UPDATE ON handoff_requests
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
