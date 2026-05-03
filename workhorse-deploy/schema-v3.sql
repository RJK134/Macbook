-- Workhorse v3 Schema Addition — investment_signals
-- Additive only. Apply after schema-v2.sql.

CREATE TABLE IF NOT EXISTS investment_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  signal_type TEXT NOT NULL,
  title TEXT NOT NULL,
  company TEXT,
  funder TEXT,
  amount NUMERIC,
  currency CHAR(3) DEFAULT 'CHF',
  stage TEXT,
  region TEXT,
  country TEXT,
  sector TEXT,
  url TEXT,
  source TEXT NOT NULL,
  source_ref TEXT,
  description TEXT,
  raw_data JSONB,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT investment_url_unique UNIQUE (url)
);
CREATE INDEX IF NOT EXISTS investment_type_idx ON investment_signals(signal_type);
CREATE INDEX IF NOT EXISTS investment_sector_idx ON investment_signals(sector);
CREATE INDEX IF NOT EXISTS investment_country_idx ON investment_signals(country);
CREATE INDEX IF NOT EXISTS investment_discovered_idx ON investment_signals(discovered_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS investment_source_ref_idx ON investment_signals(source, source_ref);

GRANT ALL ON ALL TABLES IN SCHEMA public TO workhorse_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO workhorse_user;
