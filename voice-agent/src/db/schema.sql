-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- accounts: fake customers and balances
CREATE TABLE IF NOT EXISTS accounts (
  account_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  full_name     TEXT NOT NULL,
  phone_number  TEXT UNIQUE NOT NULL,
  balance_cents BIGINT NOT NULL DEFAULT 0,
  currency      TEXT NOT NULL DEFAULT 'MYR'
);

-- cards: linked to accounts
CREATE TABLE IF NOT EXISTS cards (
  card_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID REFERENCES accounts(account_id) ON DELETE CASCADE,
  last_four  TEXT NOT NULL,
  locked     BOOLEAN NOT NULL DEFAULT false
);

-- loans: linked to accounts
CREATE TABLE IF NOT EXISTS loans (
  loan_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id        UUID REFERENCES accounts(account_id) ON DELETE CASCADE,
  loan_type         TEXT NOT NULL,
  outstanding_cents BIGINT NOT NULL,
  next_payment_date DATE NOT NULL
);

-- otp_sessions: verification state per call, outside LLM context
CREATE TABLE IF NOT EXISTS otp_sessions (
  session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id UUID REFERENCES accounts(account_id) ON DELETE CASCADE,
  otp_code   TEXT NOT NULL,
  attempts   INT NOT NULL DEFAULT 0,
  verified   BOOLEAN NOT NULL DEFAULT false,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- audit_log: every tool call and verification event
CREATE TABLE IF NOT EXISTS audit_log (
  log_id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id UUID,
  account_id UUID,
  event_type TEXT NOT NULL,
  details    JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- faq_chunks: RAG knowledge base (384-dim for all-MiniLM-L6-v2)
CREATE TABLE IF NOT EXISTS faq_chunks (
  chunk_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  content   TEXT NOT NULL,
  embedding VECTOR(384)
);
