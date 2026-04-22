# Workhorse Deploy

Headless research and reporting platform running on a MacBook Pro 2013
under Ubuntu, backed by PostgreSQL, a 1 TB USB drive, and a small
collection of Python scrapers + a FastAPI course server.

## Layout

```
workhorse-deploy/
├── docker-compose.yml          # Postgres 15 + n8n + course-api
├── schema.sql                  # v1 base schema (8 projects, opportunities, etc.)
├── schema-v2.sql               # v2 additive: courses, cost_of_living, job_trends,
│                                 financial_research, job_listings, gmail_items,
│                                 funding_opportunities, film_opportunities, scraper_runs
├── api/                        # FastAPI course server (port 8000)
├── scrapers/                   # Python scraping + reporting codebase
│   ├── common/                 # db, http, perplexity, usb, email_send, logging
│   ├── courses/                # MyCourseMatchmaker — UCAS, Discover Uni, WhatUni, CUG, Numbeo
│   ├── job_trends/             # ONS, gov.uk skills, WEF future of jobs
│   ├── funding/                # UKRI, EU Horizon, Innosuisse, Perplexity
│   ├── jobs/                   # jobs.ac.uk, THE Unijobs, jobs.ch, swissuniversities
│   ├── film/                   # BBC Writersroom, BFI, ScreenSkills, Coverfly, Shooting People
│   ├── financial/              # Companies House + Perplexity deep research
│   ├── gmail/                  # IMAP monitor + rule-based classifier
│   └── reports/                # Per-area HTML reports + master weekly digest
├── deploy/
│   ├── install_v2.sh           # idempotent installer
│   ├── crontab.txt             # full schedule
│   └── disable_cloud_workflows.md
├── workflows/                  # legacy n8n cloud workflow JSONs (deprecated, kept for reference)
└── deploy.sh, local-deploy.sh  # v1 install scripts
```

## Quick start

```bash
# On the MacBook
cd ~/macbook-deploy && git pull
bash workhorse-deploy/deploy/install_v2.sh

# Edit secrets
nano /srv/scrapers/.env   # set PERPLEXITY_API_KEY, GMAIL_APP_PASSWORD

# Smoke test
/srv/scrapers/.venv/bin/python -m scrapers.courses.orchestrator --dry-run
/srv/scrapers/.venv/bin/python -m scrapers.reports.master_digest --dry-run

# Course API
curl http://localhost:8000/health
```

## Schedule

| When | Module |
|---|---|
| 02:00 daily | courses |
| 03:00 daily | jobs |
| 03:30 daily | funding |
| 04:00 daily | film |
| 04:30 daily | job_trends |
| 05:00 Saturday | financial (weekly Perplexity refresh) |
| every 4 h | gmail |
| 05:30 daily | per-area HTML reports → USB |
| **06:00 Sunday** | **master digest email — the only recurring email** |
| 06:30 daily | DB backup (existing) |

## Storage

- **Postgres** (Docker): structured records — `courses`, `funding_opportunities`,
  `job_trends`, `financial_research`, `job_listings`, `film_opportunities`,
  `gmail_items`, `scraper_runs`.
- **/mnt/usb-archive/raw/<area>/<YYYY-MM>/**: raw scraped HTML + JSON.
- **/mnt/usb-archive/databases/**: nightly CSV exports for app loading.
- **/mnt/usb-archive/reports/<ISO-week>/**: per-area HTML reports.
- **/mnt/usb-archive/logs/**: scraper + report logs.

## API endpoints (port 8000)

- `GET /health`
- `GET /courses?subject=&qualification=&location=&provider=&q=&limit=&offset=`
- `GET /courses/{id}`
- `GET /cost-of-living[/{city}]`
- `GET /providers`

## Verification

```bash
# Postgres counts
docker exec -e PGPASSWORD="$DB_PASSWORD" workhorse-postgres \
  psql -U workhorse_user -d workhorse \
  -c "SELECT 'courses' AS t, count(*) FROM courses
      UNION ALL SELECT 'funding', count(*) FROM funding_opportunities
      UNION ALL SELECT 'jobs', count(*) FROM job_listings
      UNION ALL SELECT 'film', count(*) FROM film_opportunities
      UNION ALL SELECT 'gmail', count(*) FROM gmail_items
      UNION ALL SELECT 'trends', count(*) FROM job_trends;"

# Recent scraper runs
docker exec -e PGPASSWORD="$DB_PASSWORD" workhorse-postgres \
  psql -U workhorse_user -d workhorse \
  -c "SELECT scraper_name, status, items_inserted, started_at
      FROM scraper_runs ORDER BY started_at DESC LIMIT 20;"

# Today's logs
ls -la /mnt/usb-archive/logs/scrapers/
```
