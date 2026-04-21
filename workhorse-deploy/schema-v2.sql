-- Workhorse v2 Schema Migration
-- Additive only — does not modify or drop existing tables.
-- Apply with:
--   docker cp schema-v2.sql workhorse-postgres:/tmp/schema-v2.sql
--   docker exec -e PGPASSWORD=$DB_PASSWORD workhorse-postgres \
--     psql -U workhorse_user -d workhorse -f /tmp/schema-v2.sql

-- gen_random_uuid() and pg_trgm already present from schema.sql

------------------------------------------------------------
-- Courses (target: thousands of records for MyCourseMatchmaker)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ucas_code TEXT,
  provider TEXT NOT NULL,
  title TEXT NOT NULL,
  qualification TEXT,
  subject_area TEXT,
  duration_months INTEGER,
  study_mode TEXT,
  location_city TEXT,
  location_country TEXT DEFAULT 'UK',
  fees_uk_gbp NUMERIC,
  fees_intl_gbp NUMERIC,
  entry_requirements TEXT,
  url TEXT,
  source TEXT,
  description TEXT,
  raw_data JSONB,
  first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  active BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT courses_provider_title_qual_unique UNIQUE NULLS NOT DISTINCT (provider, title, qualification)
);
CREATE INDEX IF NOT EXISTS courses_provider_idx ON courses(provider);
CREATE INDEX IF NOT EXISTS courses_subject_idx ON courses(subject_area);
CREATE INDEX IF NOT EXISTS courses_qualification_idx ON courses(qualification);
CREATE INDEX IF NOT EXISTS courses_location_idx ON courses(location_city);
CREATE INDEX IF NOT EXISTS courses_title_trgm ON courses USING GIN (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS courses_provider_trgm ON courses USING GIN (provider gin_trgm_ops);
CREATE INDEX IF NOT EXISTS courses_raw_gin ON courses USING GIN (raw_data);

------------------------------------------------------------
-- Cost of living per university city
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cost_of_living (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  city TEXT NOT NULL,
  country TEXT NOT NULL DEFAULT 'UK',
  rent_1bed_gbp NUMERIC,
  rent_shared_gbp NUMERIC,
  groceries_monthly_gbp NUMERIC,
  transport_monthly_gbp NUMERIC,
  utilities_monthly_gbp NUMERIC,
  total_estimated_monthly_gbp NUMERIC,
  source TEXT,
  source_url TEXT,
  raw_data JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT cost_of_living_city_country_unique UNIQUE (city, country)
);
CREATE INDEX IF NOT EXISTS cost_of_living_country_idx ON cost_of_living(country);
DROP TRIGGER IF EXISTS trg_cost_of_living_updated ON cost_of_living;
CREATE TRIGGER trg_cost_of_living_updated
  BEFORE UPDATE ON cost_of_living
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

------------------------------------------------------------
-- Job trends (emerging skills, future jobs, sector growth)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_trends (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  occupation TEXT NOT NULL,
  sector TEXT,
  trend TEXT,
  growth_pct NUMERIC,
  median_salary_gbp NUMERIC,
  skills_required TEXT[],
  region TEXT,
  source TEXT NOT NULL,
  source_url TEXT,
  reported_at DATE,
  raw_data JSONB,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS job_trends_occupation_idx ON job_trends(occupation);
CREATE INDEX IF NOT EXISTS job_trends_sector_idx ON job_trends(sector);
CREATE INDEX IF NOT EXISTS job_trends_trend_idx ON job_trends(trend);
CREATE INDEX IF NOT EXISTS job_trends_skills_gin ON job_trends USING GIN (skills_required);
CREATE INDEX IF NOT EXISTS job_trends_reported_idx ON job_trends(reported_at);

------------------------------------------------------------
-- Financial research records (Perplexity-backed)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS financial_research (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  query TEXT NOT NULL,
  topic TEXT,
  answer TEXT,
  citations JSONB,
  region TEXT,
  source TEXT NOT NULL DEFAULT 'perplexity',
  cached_until TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS financial_research_topic_idx ON financial_research(topic);
CREATE INDEX IF NOT EXISTS financial_research_created_idx ON financial_research(created_at DESC);

------------------------------------------------------------
-- Live job listings (EdTech / HE Management focus)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS job_listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  employer TEXT,
  location TEXT,
  country TEXT,
  salary_min NUMERIC,
  salary_max NUMERIC,
  currency CHAR(3),
  url TEXT UNIQUE,
  closing_date DATE,
  posted_date DATE,
  description TEXT,
  source TEXT NOT NULL,
  category TEXT,
  relevance_score SMALLINT NOT NULL DEFAULT 3,
  raw_data JSONB,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS job_listings_country_idx ON job_listings(country);
CREATE INDEX IF NOT EXISTS job_listings_category_idx ON job_listings(category);
CREATE INDEX IF NOT EXISTS job_listings_closing_idx ON job_listings(closing_date);
CREATE INDEX IF NOT EXISTS job_listings_relevance_idx ON job_listings(relevance_score DESC);

------------------------------------------------------------
-- Gmail items (parsed from inbox)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS gmail_items (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  message_id TEXT UNIQUE,
  thread_id TEXT,
  from_email TEXT,
  from_name TEXT,
  subject TEXT,
  received_at TIMESTAMPTZ,
  category TEXT,
  extracted JSONB,
  body_excerpt TEXT,
  labels TEXT[],
  classified_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS gmail_category_idx ON gmail_items(category);
CREATE INDEX IF NOT EXISTS gmail_received_idx ON gmail_items(received_at DESC);
CREATE INDEX IF NOT EXISTS gmail_from_idx ON gmail_items(from_email);

------------------------------------------------------------
-- Weekly digest log
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS weekly_digests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  digest_area TEXT NOT NULL,
  week_start DATE NOT NULL,
  week_end DATE NOT NULL,
  item_count INTEGER NOT NULL DEFAULT 0,
  file_path TEXT,
  email_sent_at TIMESTAMPTZ,
  recipient TEXT,
  notes TEXT,
  CONSTRAINT weekly_digest_area_week_unique UNIQUE (digest_area, week_start)
);
CREATE INDEX IF NOT EXISTS weekly_digests_week_idx ON weekly_digests(week_start DESC);

------------------------------------------------------------
-- Funding opportunities (UK / EU / Switzerland)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS funding_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  funder TEXT,
  programme TEXT,
  region TEXT,
  country TEXT,
  amount_min NUMERIC,
  amount_max NUMERIC,
  currency CHAR(3) DEFAULT 'GBP',
  deadline DATE,
  eligibility TEXT,
  description TEXT,
  url TEXT UNIQUE,
  source TEXT NOT NULL,
  category TEXT,
  status TEXT DEFAULT 'open',
  relevance_score SMALLINT DEFAULT 3,
  raw_data JSONB,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS funding_country_idx ON funding_opportunities(country);
CREATE INDEX IF NOT EXISTS funding_deadline_idx ON funding_opportunities(deadline);
CREATE INDEX IF NOT EXISTS funding_status_idx ON funding_opportunities(status);
CREATE INDEX IF NOT EXISTS funding_category_idx ON funding_opportunities(category);

------------------------------------------------------------
-- Film/script opportunities (publication, promotion, funding, submissions)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS film_opportunities (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  organisation TEXT,
  opp_type TEXT,
  region TEXT,
  fee_gbp NUMERIC,
  prize_gbp NUMERIC,
  submission_deadline DATE,
  description TEXT,
  url TEXT UNIQUE,
  source TEXT NOT NULL,
  status TEXT DEFAULT 'open',
  relevance_score SMALLINT DEFAULT 3,
  raw_data JSONB,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS film_opp_type_idx ON film_opportunities(opp_type);
CREATE INDEX IF NOT EXISTS film_opp_deadline_idx ON film_opportunities(submission_deadline);
CREATE INDEX IF NOT EXISTS film_opp_status_idx ON film_opportunities(status);

------------------------------------------------------------
-- Scraper run log (for monitoring & idempotency)
------------------------------------------------------------
CREATE TABLE IF NOT EXISTS scraper_runs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  scraper_name TEXT NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ,
  status TEXT,
  items_fetched INTEGER DEFAULT 0,
  items_inserted INTEGER DEFAULT 0,
  items_updated INTEGER DEFAULT 0,
  items_skipped INTEGER DEFAULT 0,
  error_message TEXT,
  raw_log_path TEXT
);
CREATE INDEX IF NOT EXISTS scraper_runs_name_idx ON scraper_runs(scraper_name);
CREATE INDEX IF NOT EXISTS scraper_runs_started_idx ON scraper_runs(started_at DESC);

------------------------------------------------------------
-- Trigger: keep courses.last_seen_at fresh on update
------------------------------------------------------------
CREATE OR REPLACE FUNCTION update_course_last_seen()
RETURNS TRIGGER AS $$
BEGIN
  NEW.last_seen_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_courses_last_seen ON courses;
CREATE TRIGGER trg_courses_last_seen
  BEFORE UPDATE ON courses
  FOR EACH ROW EXECUTE FUNCTION update_course_last_seen();

------------------------------------------------------------
-- Grants
------------------------------------------------------------
GRANT ALL ON ALL TABLES IN SCHEMA public TO workhorse_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO workhorse_user;
