# Skills — Macbook Workhorse Capabilities

## What the workhorse can do (once deployed)

### Data Collection (automated, overnight via cron)
- **Course scraping**: UCAS, Discover Uni, WhatUni, Complete University Guide
  - 47 subject seeds × 4 sources = thousands of course records
  - Cost-of-living data for 25 UK university cities (Numbeo)
- **Job trend analysis**: ONS labour market, gov.uk skills policy, WEF Future of Jobs
  - Auto-classifies growing/declining/stable sectors
  - Extracts skill tokens (AI, ML, data, cloud, cyber, etc.)
- **Funding opportunities**: Innovate UK/UKRI, EU Horizon/EIC, Swiss Innosuisse/SNSF
  - Perplexity deep search for currently-open EdTech/HE grants
  - Parses deadlines, amounts, eligibility
- **Job listings**: jobs.ac.uk (9 categories + 10 keywords), THE Unijobs, jobs.ch, swissuniversities
  - Relevance scoring by EdTech/HE management keywords
- **Film/script opportunities**: BBC Writersroom, BFI, ScreenSkills, Coverfly, Shooting People
  - Filters for genuine submission/funding/competition headings
- **Financial intelligence**: Companies House vendor watchlist, Perplexity market reports
  - EdTech market sizing, HE software vendor financials, competitor tracking
- **Gmail monitoring**: IMAP scan every 4 hours, classifies into job-app/funding/film/course/newsletter/ignore

### Research (Perplexity API)
- Global EdTech market size and forecasts
- UK HE software market: Tribal, Ellucian, Unit4, TechnologyOne market share
- Swiss EdTech investment activity
- AI spending in UK/EU higher education
- Competitor financial results (public filings)
- Active funding calls across UK/EU/Switzerland

### Reporting
- **Weekly master digest**: ONE email, Sunday 06:00, with 7 sections
- **Per-area HTML reports**: saved to USB for drill-down
- **Course CSV export**: regenerated nightly for app consumption

### API
- FastAPI on port 8000 serving the course database
- Endpoints: /courses (search), /courses/{id}, /cost-of-living, /providers
- Fuzzy title search via pg_trgm

## What it cannot do (yet)
- Real-time alerts (everything is batch/scheduled)
- LinkedIn scraping (requires authentication, not RSS-accessible)
- Perplexity web UI automation (API only; browser is manual)
- Automated PR/merge workflows (needs GitHub Actions or similar CI)
- PDF report generation (HTML only currently)
- WhatsApp message processing (runs on n8n cloud, not the Mac)

## Scraper schedule
| Time | Module | Frequency |
|---|---|---|
| 02:00 | courses | Daily |
| 03:00 | jobs | Daily |
| 03:30 | funding | Daily |
| 04:00 | film | Daily |
| 04:30 | job_trends | Daily |
| 05:00 | financial | Weekly (Saturday) |
| */4 hours | gmail | Every 4 hours |
| 05:30 | per-area reports | Daily |
| **06:00 Sunday** | **master digest email** | **Weekly** |
| 06:30 | DB backup | Daily |
