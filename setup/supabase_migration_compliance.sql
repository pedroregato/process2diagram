-- setup/supabase_migration_compliance.sql
-- PC81 — LGPD Compliance Layer
-- Sprint 1: compliance_consent + compliance_audit tables
-- Run once on the Supabase project via the SQL Editor or psycopg2.

-- ── Tabela de consentimento LGPD por reunião ─────────────────────────────────

CREATE TABLE IF NOT EXISTS compliance_consent (
    id               UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    meeting_id       UUID REFERENCES meetings(id)  ON DELETE CASCADE,
    project_id       UUID REFERENCES contexts(id)  ON DELETE SET NULL,
    granted_by       TEXT NOT NULL,
    legal_basis      TEXT NOT NULL
                         CHECK (legal_basis IN (
                             'legitimo_interesse',
                             'consentimento',
                             'contrato',
                             'obrigacao_legal'
                         )),
    participant_type TEXT DEFAULT 'interno'
                         CHECK (participant_type IN ('interno', 'externo', 'misto')),
    retention_days   INTEGER DEFAULT 60 CHECK (retention_days > 0),
    pii_detected     JSONB DEFAULT '{}',
    expires_at       TIMESTAMPTZ,
    notes            TEXT DEFAULT '',
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS compliance_consent_meeting_idx  ON compliance_consent(meeting_id);
CREATE INDEX IF NOT EXISTS compliance_consent_project_idx  ON compliance_consent(project_id);
CREATE INDEX IF NOT EXISTS compliance_consent_expires_idx  ON compliance_consent(expires_at);

COMMENT ON TABLE  compliance_consent IS 'LGPD consent records per meeting (Art. 7°)';
COMMENT ON COLUMN compliance_consent.legal_basis     IS 'LGPD Art. 7 legal basis for data processing';
COMMENT ON COLUMN compliance_consent.retention_days  IS 'Data retention period in days from creation';
COMMENT ON COLUMN compliance_consent.expires_at      IS 'Computed: created_at + retention_days interval';
COMMENT ON COLUMN compliance_consent.pii_detected    IS 'PIIDetectionResult.summary JSON from detector.py';


-- ── Tabela de trilha de auditoria LGPD ───────────────────────────────────────

CREATE TABLE IF NOT EXISTS compliance_audit (
    id          UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    meeting_id  UUID,           -- nullable: pré-reunião events have no meeting yet
    project_id  UUID,
    event_type  TEXT NOT NULL,  -- pipeline_run | consent_granted | data_accessed
                                -- | data_deleted | pii_detected
    user_login  TEXT,
    details     JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS compliance_audit_meeting_idx ON compliance_audit(meeting_id);
CREATE INDEX IF NOT EXISTS compliance_audit_project_idx ON compliance_audit(project_id);
CREATE INDEX IF NOT EXISTS compliance_audit_created_idx ON compliance_audit(created_at DESC);
CREATE INDEX IF NOT EXISTS compliance_audit_event_idx   ON compliance_audit(event_type);

COMMENT ON TABLE compliance_audit IS 'LGPD audit trail — retained 365 days (longer than meeting data TTL)';
