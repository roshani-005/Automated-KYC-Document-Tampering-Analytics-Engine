CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    onboarding_cohort DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS merchants (
    merchant_id VARCHAR(64) PRIMARY KEY,
    merchant_name VARCHAR(120),
    merchant_segment VARCHAR(64) NOT NULL DEFAULT 'SMB',
    city VARCHAR(80),
    state VARCHAR(80),
    onboarding_cohort DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(64) NOT NULL REFERENCES users(user_id),
    merchant_id VARCHAR(64) NOT NULL REFERENCES merchants(merchant_id),
    document_type VARCHAR(16) NOT NULL CHECK (document_type IN ('PAN', 'AADHAAR', 'GSTIN')),
    tamper_score NUMERIC(5,2) NOT NULL CHECK (tamper_score BETWEEN 0 AND 100),
    authentic_confidence NUMERIC(5,2) NOT NULL CHECK (authentic_confidence BETWEEN 0 AND 100),
    flagged_status VARCHAR(16) NOT NULL CHECK (flagged_status IN ('Authentic', 'Suspicious')),
    risk_tier VARCHAR(16) NOT NULL CHECK (risk_tier IN ('Low', 'Medium', 'High')),
    intervention VARCHAR(32) NOT NULL CHECK (intervention IN ('AUTO_APPROVE', 'MANUAL_REVIEW', 'BLOCK_AND_ESCALATE')),
    processing_time_ms INTEGER NOT NULL CHECK (processing_time_ms >= 0),
    "timestamp" TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address INET
);

CREATE TABLE IF NOT EXISTS fraud_escalations (
    escalation_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    verification_id UUID NOT NULL UNIQUE REFERENCES verifications(verification_id) ON DELETE CASCADE,
    reason VARCHAR(255) NOT NULL,
    status VARCHAR(24) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_REVIEW', 'CLOSED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_verifications_timestamp ON verifications ("timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_verifications_merchant_timestamp ON verifications (merchant_id, "timestamp" DESC);
CREATE INDEX IF NOT EXISTS idx_verifications_status ON verifications (flagged_status);
CREATE INDEX IF NOT EXISTS idx_verifications_document_type ON verifications (document_type);
CREATE INDEX IF NOT EXISTS idx_verifications_risk_tier ON verifications (risk_tier);
CREATE INDEX IF NOT EXISTS idx_merchants_segment_city ON merchants (merchant_segment, city);
