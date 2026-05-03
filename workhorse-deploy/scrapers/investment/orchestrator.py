"""Investment signals orchestrator — Perplexity discovery + future email parsing."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import perplexity_discovery

LOGGER = get_logger("investment.orchestrator")

SCRAPERS = [
    ("perplexity_discovery", perplexity_discovery.scrape),
]


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    for r in rows:
        url = r.get("url") or ""
        title = r.get("title", "")
        if not title:
            continue
        if url:
            existing = db.fetch_one(
                "SELECT id FROM investment_signals WHERE url = %s", (url,)
            )
            if existing:
                skipped += 1
                continue
        params = (
            r.get("signal_type", "news"),
            title[:300],
            r.get("company"),
            r.get("funder"),
            r.get("amount"),
            (r.get("currency") or "CHF")[:3],
            r.get("stage"),
            r.get("region"),
            r.get("country"),
            r.get("sector"),
            url or None,
            r.get("source", "perplexity"),
            r.get("source_ref"),
            (r.get("description") or "")[:4000],
            json.dumps(r.get("raw_data", {}), default=str),
        )
        rowcount = db.execute(
            """
            INSERT INTO investment_signals (
              signal_type, title, company, funder, amount, currency,
              stage, region, country, sector, url, source, source_ref,
              description, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            params,
        )
        if rowcount:
            inserted += 1
        else:
            skipped += 1
    return inserted, skipped


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("investment.orchestrator")
    LOGGER.info("Investment orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)
        if dry_run:
            for r in all_rows[:10]:
                print(r)
            print(f"... ({len(all_rows)} total)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows))
            return
        ins, skip = _upsert(all_rows)
        LOGGER.info("Investment: %d inserted, %d skipped", ins, skip)
        db.finish_scraper_run(run_id, "ok", fetched=len(all_rows), inserted=ins, skipped=skip)
    except Exception as exc:
        LOGGER.exception("Investment orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
