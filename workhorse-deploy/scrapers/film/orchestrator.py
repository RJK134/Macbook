"""Film & screenwriting orchestrator — dedupe, classify, upsert."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import bbc_writersroom, bfi, coverfly, perplexity_film, screenskills, shooting_people

LOGGER = get_logger("film.orchestrator")

# bfi.py still scrapes successfully and perplexity_film.py covers the
# four sources that have degraded (BBC SPA, ScreenSkills 403, Shooting
# People 404, Coverfly unreachable). The dead site-scrapers stay in the
# list so they auto-recover if any source restores HTML, but they no
# longer block the orchestrator from producing results.
SCRAPERS = [
    ("perplexity", perplexity_film.scrape),
    ("bfi", bfi.scrape),
    ("bbc", bbc_writersroom.scrape),
    ("screenskills", screenskills.scrape),
    ("shooting_people", shooting_people.scrape),
    ("coverfly", coverfly.scrape),
]


def _dedupe(rows: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for r in rows:
        key = (r.get("url") or "") + "|" + (r.get("title") or "").lower()
        if not key.strip("|") or key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = r.get("url")
        if not url:
            continue
        existing = db.fetch_one("SELECT id FROM film_opportunities WHERE url = %s", (url,))
        if existing:
            updated += 1
            continue
        params = (
            r["title"][:300],
            r.get("organisation"),
            r.get("opp_type"),
            r.get("region"),
            r.get("fee_gbp"),
            r.get("prize_gbp"),
            r.get("submission_deadline"),
            (r.get("description") or "")[:4000],
            url,
            r.get("source"),
            r.get("status", "open"),
            r.get("relevance_score", 3),
            json.dumps(r.get("raw_data", {}), default=str),
        )
        db.execute(
            """
            INSERT INTO film_opportunities (
              title, organisation, opp_type, region, fee_gbp, prize_gbp,
              submission_deadline, description, url, source, status,
              relevance_score, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            params,
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("film.orchestrator")
    LOGGER.info("Film orchestrator run %s", run_id)
    try:
        rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                rows.extend(fn())
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("%s failed: %s", name, exc)
        deduped = _dedupe(rows)
        if dry_run:
            for r in deduped[:10]:
                print(r)
            print(f"... ({len(deduped)} unique of {len(rows)})")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(rows))
            return
        ins, upd = _upsert(deduped)
        LOGGER.info("Film opps: %d inserted, %d skipped", ins, upd)
        db.finish_scraper_run(run_id, "ok", fetched=len(rows), inserted=ins, skipped=upd)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
