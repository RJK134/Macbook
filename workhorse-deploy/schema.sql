-- gen_random_uuid() is built into PostgreSQL 13+, no extension needed
CREATE EXTENSION IF NOT EXISTS "pg_trgm" SCHEMA public;

CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  slug TEXT NOT NULL UNIQUE,
  display_name TEXT NOT NULL,
  description TEXT,
  priority SMALLINT NOT NULL DEFAULT 2,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sources (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  url TEXT NOT NULL,
  source_type TEXT NOT NULL,
  region TEXT,
  category TEXT,
  fetch_frequency TEXT NOT NULL DEFAULT 'daily',
  last_fetched_at TIMESTAMPTZ,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX sources_project_idx ON sources(project_id);
CREATE INDEX sources_type_idx ON sources(source_type);

CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  description TEXT,
  job_type TEXT NOT NULL,
  schedule TEXT,
  last_run_at TIMESTAMPTZ,
  last_status TEXT,
  last_error TEXT,
  run_count INTEGER NOT NULL DEFAULT 0,
  fail_count INTEGER NOT NULL DEFAULT 0,
  next_run_at TIMESTAMPTZ,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX jobs_project_idx ON jobs(project_id);

CREATE TABLE captures (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id UUID REFERENCES sources(id) ON DELETE SET NULL,
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  url TEXT NOT NULL,
  content_hash TEXT,
  file_path TEXT,
  mime_type TEXT,
  http_status SMALLINT,
  content_changed BOOLEAN,
  captured_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT
);
CREATE INDEX captures_source_idx ON captures(source_id);
CREATE INDEX captures_project_idx ON captures(project_id);
CREATE INDEX captures_hash_idx ON captures(content_hash);

CREATE TABLE entities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  entity_type TEXT NOT NULL,
  name TEXT NOT NULL,
  region TEXT,
  url TEXT,
  description TEXT,
  raw_data JSONB,
  status TEXT DEFAULT 'active',
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT
);
CREATE INDEX entities_type_idx ON entities(entity_type);
CREATE INDEX entities_project_idx ON entities(project_id);
CREATE INDEX entities_name_trgm ON entities USING GIN (name gin_trgm_ops);
CREATE INDEX entities_raw_gin ON entities USING GIN (raw_data);

CREATE TABLE opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  capture_id UUID REFERENCES captures(id) ON DELETE SET NULL,
  entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
  opp_type TEXT NOT NULL,
  title TEXT NOT NULL,
  funder TEXT,
  region TEXT,
  deadline DATE,
  amount_min NUMERIC,
  amount_max NUMERIC,
  currency CHAR(3) DEFAULT 'GBP',
  eligibility TEXT,
  url TEXT,
  status TEXT DEFAULT 'open',
  relevance_score SMALLINT DEFAULT 3,
  in_review_queue BOOLEAN DEFAULT FALSE,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  notes TEXT,
  raw_data JSONB
);
CREATE INDEX opps_type_idx ON opportunities(opp_type);
CREATE INDEX opps_project_idx ON opportunities(project_id);
CREATE INDEX opps_deadline_idx ON opportunities(deadline);
CREATE INDEX opps_status_idx ON opportunities(status);
CREATE INDEX opps_review_idx ON opportunities(in_review_queue) WHERE in_review_queue = TRUE;

CREATE TABLE market_signals (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  capture_id UUID REFERENCES captures(id) ON DELETE SET NULL,
  signal_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  source_url TEXT,
  region TEXT,
  relevance_score SMALLINT DEFAULT 3,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  raw_data JSONB
);
CREATE INDEX signals_type_idx ON market_signals(signal_type);
CREATE INDEX signals_project_idx ON market_signals(project_id);

CREATE TABLE notes (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  related_id UUID,
  related_type TEXT,
  note_type TEXT NOT NULL,
  content TEXT NOT NULL,
  tags TEXT[],
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX notes_project_idx ON notes(project_id);
CREATE INDEX notes_tags_gin ON notes USING GIN (tags);

CREATE TABLE alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  related_id UUID,
  related_type TEXT,
  alert_type TEXT NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  priority SMALLINT DEFAULT 2,
  sent BOOLEAN DEFAULT FALSE,
  sent_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX alerts_unsent_idx ON alerts(sent) WHERE sent = FALSE;

CREATE TABLE digests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
  digest_type TEXT NOT NULL,
  period_start DATE NOT NULL,
  period_end DATE NOT NULL,
  file_path TEXT,
  item_count INTEGER DEFAULT 0,
  generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  sent BOOLEAN DEFAULT FALSE
);

CREATE TABLE health_logs (
  id BIGSERIAL PRIMARY KEY,
  checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  disk_used_pct SMALLINT,
  ram_used_mb INTEGER,
  db_size_mb NUMERIC,
  failed_jobs_24h INTEGER,
  backup_ok BOOLEAN,
  notes TEXT
);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_projects_updated BEFORE UPDATE ON projects
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_opportunities_updated BEFORE UPDATE ON opportunities
FOR EACH ROW EXECUTE FUNCTION update_updated_at();
CREATE TRIGGER trg_notes_updated BEFORE UPDATE ON notes
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

INSERT INTO projects (slug, display_name, priority) VALUES
  ('sjms', 'SJMS 2.5 / v4 Integrated', 1),
  ('mycoursematchmaker', 'MyCourseMatchmaker', 1),
  ('shakespeare-is-boring', 'Shakespeare is Boring', 2),
  ('coursepulse', 'CoursePulse', 2),
  ('future-horizons', 'Future Horizons Education', 1),
  ('funding-watch', 'Funding Watch', 1),
  ('film-opps', 'Film & Script Opportunities', 2),
  ('career-opps', 'Career & Consultancy Opportunities', 2);

GRANT ALL ON ALL TABLES IN SCHEMA public TO workhorse_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO workhorse_user;
