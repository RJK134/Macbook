"""US markets orchestrator — SEC filings + FRED indicators + market data + wealth research."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import fred, perplexity_wealth, sec_edgar, yahoo_finance

LOGGER = get_logger("us_markets.orchestrator")

SCRAPERS = [
    ("sec_edgar", sec_edgar.scrape),
    ("fred", fred.scrape),
    ("yahoo_finance", yahoo_finance.scrape),
]


def _upsert_signals(rows: list[dict]) -> tuple[int, int]:
    inserted = skipped = 0
    for r in rows:
        url = r.get("url") or ""
        title = r.get("title", "")[:300]
        if not title:
            continue
        # Dedupe by (source, title) within last 7 days
        existing = db.fetch_one(
            "SELECT id FROM market_signals "
            "WHERE source_url = %s AND title = %s "
            "AND discovered_at > NOW() - INTERVAL '7 days'",
            (url, title),
        )
        if existing:
            skipped += 1
            continue
        db.execute(
            """
            INSERT INTO market_signals (
              project_id, signal_type, title, summary, source_url,
              region, relevance_score, raw_data
            ) SELECT p.id, %s, %s, %s, %s, %s, %s, %s::jsonb
            FROM projects p WHERE p.slug = 'sjms'
            """,
            (
                r.get("signal_type", "market-data"),
                title,
                (r.get("description") or "")[:2000],
                url,
                r.get("region", "US"),
                r.get("relevance_score", 3),
                json.dumps(r.get("raw_data", {}), default=str),
            ),
        )
        inserted += 1
    return inserted, skipped


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("us_markets.orchestrator")
    LOGGER.info("US markets orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)

        # Perplexity wealth research (self-persisting via cached_ask)
        wealth_results = perplexity_wealth.run_all()
        LOGGER.info("Perplexity wealth: %d topics", len(wealth_results))

        if dry_run:
            print(f"Market signals: {len(all_rows)}")
            print(f"Wealth research topics: {len(wealth_results)}")
            for r in all_rows[:5]:
                print(f"  {r.get('title', '')[:80]}")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows) + len(wealth_results))
            return

        ins, skip = _upsert_signals(all_rows)
        LOGGER.info("US market signals: %d inserted, %d skipped", ins, skip)
        db.finish_scraper_run(
            run_id,
            "ok",
            fetched=len(all_rows) + len(wealth_results),
            inserted=ins + len([r for r in wealth_results if not r.get("cached")]),
            skipped=skip,
        )
    except Exception as exc:
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
