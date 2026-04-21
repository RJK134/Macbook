# Disabling the legacy n8n cloud workflows

The cloud workflows on `rjk134.app.n8n.cloud` (the Macbook Workhorse
project) caused 200+ duplicate emails over 3 days because the SDK
created disconnected nodes that were re-wired in the UI in ways that
spawned 4× sends per trigger.

Workhorse v2 replaces all of them with local Python scrapers + a
single Sunday 06:00 master digest. Once v2 is live, deactivate the
cloud workflows.

## Workflows to deactivate

| Workflow | ID | Replaced by |
|---|---|---|
| Funding & Opportunities Scanner | `5y8RjshxxPvM7R44` | `scrapers/funding/` |
| Film & Screenwriting Opportunities | `nbHZmrSKFtEl92WX` | `scrapers/film/` |
| Course Data Scraper - MyCourseMatchmaker | `lfY7JFSJaxTRMheb` | `scrapers/courses/` |
| AI Enterprise & EdTech Market Scanner | `bJNMGndJ2zWQ0JOA` | `scrapers/financial/` (Perplexity research) |
| Future Horizons - Funding & Enterprise Opps | `bljep8OqK0dudZG5` | `scrapers/funding/` + `scrapers/financial/` |
| HMGCC SPA - Research & Document Library Builder | `qYzfPr5aT3ZeuPnw` | (Future scraper module — see backlog) |
| HERM & HE Academic Management Landscape Scanner | `PPQ4iOkBn4JpvqNP` | `scrapers/financial/perplexity_research.py` (HE software market) |

## Steps

1. Open https://rjk134.app.n8n.cloud in your laptop browser
2. Navigate to the Macbook Workhorse project
3. For each workflow above:
   - Click the workflow
   - Toggle the "Active" switch OFF (top-right)
   - Confirm
4. Optional: archive each one (three-dot menu → Archive)
5. Verify no further emails arrive after 24 hours

## Keep n8n cloud running

Do **not** cancel the n8n cloud subscription — the Equismile WhatsApp
webhook (`equismile-whatsapp`) is on this instance and is the entry
point for production WhatsApp messages from Meta.

## Local n8n remains for future use

The local n8n on the MacBook (`http://192.168.1.120:5678`) is still
running — kept for any future workflow that needs a webhook trigger
inside the local network.
