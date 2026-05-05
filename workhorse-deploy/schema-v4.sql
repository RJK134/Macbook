-- Schema v4: tables for procurement, education resources, SEN, Shakespeare,
-- and finance bulletins. Idempotent — safe to re-apply.

-- ============================================================
-- Procurement opportunities (Contracts Finder, Find a Tender, TED)
-- Drives Future Horizons Education tender discovery + current builds
-- ============================================================
CREATE TABLE IF NOT EXISTS procurement_opportunities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  notice_id text,
  title text NOT NULL,
  buyer text,
  buyer_type text,
  description text,
  category text,
  cpv_codes text[],
  value_min numeric,
  value_max numeric,
  currency text DEFAULT 'GBP',
  publication_date date,
  deadline_date date,
  status text DEFAULT 'open',
  source text NOT NULL,
  url text UNIQUE NOT NULL,
  region text,
  country text DEFAULT 'UK',
  relevance_score int DEFAULT 3,
  raw_data jsonb,
  discovered_at timestamptz NOT NULL DEFAULT NOW(),
  updated_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_procurement_status ON procurement_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_procurement_deadline ON procurement_opportunities(deadline_date);
CREATE INDEX IF NOT EXISTS idx_procurement_buyer ON procurement_opportunities(buyer);
CREATE INDEX IF NOT EXISTS idx_procurement_category ON procurement_opportunities(category);

-- ============================================================
-- Education resources for Maieus / Maieus2 Socratic teaching tools
-- (GCSE + A-Level past papers, specs, BBC Bitesize, Khan Academy, NRICH, etc.)
-- ============================================================
CREATE TABLE IF NOT EXISTS education_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  exam_board text,
  level text,
  subject text NOT NULL,
  topic text,
  resource_type text NOT NULL,
  title text NOT NULL,
  source text NOT NULL,
  url text UNIQUE NOT NULL,
  description text,
  year int,
  difficulty text,
  raw_data jsonb,
  discovered_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_education_subject ON education_resources(subject);
CREATE INDEX IF NOT EXISTS idx_education_level ON education_resources(level);
CREATE INDEX IF NOT EXISTS idx_education_resource_type ON education_resources(resource_type);

-- ============================================================
-- SEN / Inclusion / Excluded learners resources
-- ============================================================
CREATE TABLE IF NOT EXISTS sen_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resource_type text NOT NULL,
  title text NOT NULL,
  source text NOT NULL,
  url text UNIQUE NOT NULL,
  category text,
  description text,
  region text,
  applies_to text,
  published_date date,
  raw_data jsonb,
  discovered_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_sen_resource_type ON sen_resources(resource_type);
CREATE INDEX IF NOT EXISTS idx_sen_category ON sen_resources(category);

-- ============================================================
-- Shakespeare engagement resources for "Shakespeare is Boring" app
-- ============================================================
CREATE TABLE IF NOT EXISTS shakespeare_resources (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  resource_type text NOT NULL,
  title text NOT NULL,
  source text NOT NULL,
  url text UNIQUE NOT NULL,
  play text,
  format text,
  audience text,
  description text,
  engagement_score int,
  published_date date,
  raw_data jsonb,
  discovered_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_shakespeare_play ON shakespeare_resources(play);
CREATE INDEX IF NOT EXISTS idx_shakespeare_format ON shakespeare_resources(format);

-- ============================================================
-- Finance bulletins (HMRC, FCA, BoE, ONS, yfinance market data)
-- Extends financial_research — bulletins capture official feed items.
-- ============================================================
CREATE TABLE IF NOT EXISTS finance_bulletins (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL,
  category text,
  title text NOT NULL,
  url text UNIQUE NOT NULL,
  summary text,
  published_date date,
  ticker text,
  metric_value numeric,
  metric_unit text,
  raw_data jsonb,
  discovered_at timestamptz NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_finance_source ON finance_bulletins(source);
CREATE INDEX IF NOT EXISTS idx_finance_published ON finance_bulletins(published_date);
CREATE INDEX IF NOT EXISTS idx_finance_ticker ON finance_bulletins(ticker);
