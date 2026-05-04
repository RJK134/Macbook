# Macbook Workhorse

## What this is
Research, scraping, and reporting platform running on a MacBook Pro 2013
under Ubuntu Linux (desktop GUI, wired ethernet, SSH accessible). Backed
by PostgreSQL 15, a 1TB SanDisk USB drive, and Python scrapers scheduled
via cron. Outputs a single consolidated weekly digest email.

## Key conventions
- Python 3.12, psycopg 3, httpx, BeautifulSoup. No Flask, no Django.
- FastAPI for the read-only course API (port 8000).
- Docker Compose for the course-api container (connects to external Postgres).
- Postgres + n8n run as separate Docker containers on the `core_default` network.
- All scrapers live under `workhorse-deploy/scrapers/` with a common
  infrastructure layer at `scrapers/common/`.
- Secrets in `/srv/scrapers/.env` (never committed — `.gitignore`d).
- Raw scraped data goes to `/mnt/usb-archive/raw/<area>/<YYYY-MM>/`.
- Weekly HTML reports go to `/mnt/usb-archive/reports/<ISO-week>/`.
- ONE email per week (Sunday 06:00 Europe/Zurich) via SMTP.
- Cron entries tagged `#workhorse-v2` for idempotent reinstall.
- All HTML output must use `html.escape()` on scraped content (XSS prevention).
- Database passwords URL-encoded via `urllib.parse.quote_plus()`.
- `ON CONFLICT` upserts default NULL-prone columns to `''` to avoid
  Postgres NULL != NULL unique constraint bypass.

## Project structure
```
workhorse-deploy/
├── docker-compose.yml          (course-api only; Postgres/n8n separate)
├── schema.sql, schema-v2.sql, schema-v3.sql
├── api/                  (FastAPI course server)
├── scrapers/
│   ├── common/           (db, http, perplexity, usb, email, logging, config)
│   ├── courses/          (UCAS, Discover Uni, WhatUni, CUG, cost-of-living)
│   ├── job_trends/       (ONS, gov.uk, WEF)
│   ├── funding/          (UKRI, EU Horizon, Innosuisse, Perplexity)
│   ├── jobs/             (jobs.ac.uk, THE, jobs.ch, swissuniversities)
│   ├── film/             (BBC Writersroom, BFI, ScreenSkills, Coverfly, Shooting People)
│   ├── financial/        (Companies House, Perplexity deep research)
│   ├── investment/       (Perplexity investment signal discovery)
│   ├── gmail/            (IMAP monitor + classifier)
│   └── reports/          (sections, per_area, master_digest)
├── deploy/               (install_v2.sh, crontab.txt, disable_cloud_workflows.md)
└── workflows/            (legacy n8n JSON — deprecated, kept for reference)
```

## Mac details
- User: `richard-knapp` (home: `/home/richard-knapp`)
- Hostname: `richard-knapp-MacBookPro11-1`
- Postgres: Docker container `workhorse-postgres` on port 5433
- n8n local: port 5678 (kept for webhooks)
- Course API: port 8000
- USB: `/mnt/usb-archive` (1TB SanDisk, check health before heavy writes)
- Tailscale IP: `100.65.159.28`
- Local IP: `192.168.1.120` (may change on DHCP)

## How to deploy
```bash
cd ~/macbook-deploy && git pull origin main
bash workhorse-deploy/deploy/install_v2.sh
nano /srv/scrapers/.env   # set PERPLEXITY_API_KEY and GMAIL_APP_PASSWORD
```

## How to test
```bash
/srv/scrapers/.venv/bin/python -m scrapers.courses.orchestrator --dry-run
/srv/scrapers/.venv/bin/python -m scrapers.reports.master_digest --dry-run
curl http://localhost:8000/health
```
