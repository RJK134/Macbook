# Memory — Macbook Workhorse Project

## Owner
- Richard Knapp (richardknapp134@gmail.com)
- Based in Switzerland, with UK connections
- Skills: EdTech, Higher Education management, student management systems
- Also pursuing: screenwriting, film production

## Project portfolio (priority order)
1. **MyCourseMatchmaker** — UK course search app, needs thousands of courses in DB
2. **SJMS / HERM** — Student Journey Management System, HE reference model implementation
3. **Future Horizons Education** — funding, enterprise, education startup
4. **Funding Watch** — UK/EU/Swiss grant and funding opportunity tracker
5. **CoursePulse / Course Designer** — job-trend-aligned course recommendations
6. **Film & Script Opportunities** — screenwriting competitions, BFI/BBC funding
7. **Career & Consultancy** — personal EdTech/HE job opportunities (UK + Switzerland)
8. **Shakespeare is Boring** — creative education project

## Infrastructure
- MacBook Pro 2013, Ubuntu Desktop (GUI), wired ethernet
- Docker: Postgres 15 + n8n + FastAPI course-api
- 1TB SanDisk USB at /mnt/usb-archive (slow writes observed — may need replacement)
- Tailscale VPN: 100.65.159.28
- Claude Code installed on the Mac
- Chrome browser available for Perplexity web searches

## Key decisions made
- Moved from n8n cloud workflows → local Python scrapers + cron (n8n cloud caused 200+ duplicate spam emails from disconnected SDK nodes)
- Single weekly email digest (Sunday 06:00) replaces per-workflow email spam
- Perplexity API for deep financial/market research (7-day cache to control costs)
- Gmail IMAP for inbox classification (jobs, funding, film, courses — suppress noise)
- FastAPI on port 8000 serves MyCourseMatchmaker course database

## Accounts
- n8n cloud: rjk134.app.n8n.cloud (keep for Equismile WhatsApp webhook only)
- GitHub: RJK134
- Perplexity: Pro + Enterprise Pro (API key configured in .env)
- Gmail: richardknapp134@gmail.com

## Known issues
- SanDisk USB exhibited 8.6 kB/s write speed (dd test) — may be failing
- n8n cloud workflows must be manually deactivated (7 workflows in Macbook Workhorse project)
- Postgres password contains `!` — must be URL-encoded in connection URIs
