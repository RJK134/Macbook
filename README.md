# Macbook Workhorse

Automated research, scraping, and reporting platform running on a MacBook Pro 2013 under Ubuntu Linux. Collects intelligence across education, funding, jobs, film, and financial markets — delivering a single consolidated weekly digest email.

## What it does

| Area | Sources | Output |
|---|---|---|
| **MyCourseMatchmaker** | UCAS, Discover Uni, WhatUni, Complete Uni Guide, Numbeo | Course database (thousands) + cost-of-living per city |
| **Job Trends** | ONS, gov.uk skills, WEF Future of Jobs | Growing/declining sectors, skill gap analysis |
| **Funding (UK/EU/CH)** | UKRI, EU Horizon, Innosuisse + Perplexity deep search | Open grants with deadlines and amounts |
| **Jobs (EdTech/HE)** | jobs.ac.uk, THE Unijobs, jobs.ch, swissuniversities | Relevance-scored listings for HE management roles |
| **Film & Script** | BBC Writersroom, BFI, ScreenSkills, Coverfly, Shooting People | Competitions, funding, submissions |
| **Financial Intel** | Companies House, Perplexity Sonar Pro | EdTech market sizing, vendor financials, competitor tracking |
| **Gmail Monitor** | IMAP (every 4 hours) | Classified inbox: jobs, funding, film, courses |

## Architecture

- **Python 3.11** scrapers with BeautifulSoup + httpx
- **PostgreSQL 15** (Docker) with 20+ tables
- **FastAPI** course server on port 8000
- **Perplexity API** for deep financial/market research (7-day cache)
- **Cron** scheduling — scrapers run overnight 02:00–05:00
- **1TB USB** at `/mnt/usb-archive` for raw data, reports, backups
- **Single weekly email** (Sunday 06:00 Europe/Zurich)

## Quick start

```bash
git clone https://github.com/RJK134/Macbook.git ~/macbook-deploy
cd ~/macbook-deploy
bash workhorse-deploy/deploy/install_v2.sh
nano /srv/scrapers/.env   # set PERPLEXITY_API_KEY, GMAIL_APP_PASSWORD
```

## Repo structure

```
├── CLAUDE.md              # Claude Code project instructions
├── Memory.md              # Project context and decisions
├── skills.md              # Capability matrix and schedule
└── workhorse-deploy/
    ├── docker-compose.yml  # Postgres + n8n + course-api
    ├── schema.sql          # v1 base tables
    ├── schema-v2.sql       # v2 additions (courses, funding, jobs, etc.)
    ├── api/                # FastAPI course server
    ├── scrapers/           # Python scraping + reporting
    │   ├── common/         # db, http, perplexity, usb, email, config
    │   ├── courses/        # UCAS, Discover Uni, WhatUni, CUG, Numbeo
    │   ├── job_trends/     # ONS, gov.uk, WEF
    │   ├── funding/        # UKRI, EU Horizon, Innosuisse, Perplexity
    │   ├── jobs/           # jobs.ac.uk, THE, jobs.ch, swissuniversities
    │   ├── film/           # BBC, BFI, ScreenSkills, Coverfly
    │   ├── financial/      # Companies House, Perplexity research
    │   ├── gmail/          # IMAP monitor + classifier
    │   └── reports/        # sections, per_area, master_digest
    └── deploy/             # install_v2.sh, crontab, cloud disable guide
```

See [CLAUDE.md](CLAUDE.md) for conventions and [skills.md](skills.md) for the full capability matrix.
