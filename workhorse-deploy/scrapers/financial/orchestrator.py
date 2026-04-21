"""Financial orchestrator — runs Perplexity research + Companies House."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import companies_house, perplexity_research

LOGGER = get_logger("financial.orchestrator")


def _store_filings(rows: list[dict]) -> int:
    """Companies House results land in financial_research too (one record each)."""
    inserted = 0
    for r in rows:
        existing = db.fetch_one(
            "SELECT id FROM financial_research WHERE query = %s ORDER BY created_at DESC LIMIT 1",
            (r["query"],),
        )
        if existing:
            continue
        db.execute(
            """
            INSERT INTO financial_research (query, topic, answer, citations, region, source)
            VALUES (%s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                r["query"],
                r["topic"],
                r["answer"],
                json.dumps(r.get("citations", [])),
                r.get("region"),
                "companies_house",
            ),
        )
        inserted += 1
    return inserted


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("financial.orchestrator")
    LOGGER.info("Financial orchestrator run %s", run_id)
    try:
        # Perplexity research is self-persisting via cached_ask
        results = perplexity_research.run_all()
        LOGGER.info("Perplexity: %d topics processed", len(results))

        ch_rows = companies_house.scrape()
        if dry_run:
            print(f"Perplexity topics: {len(results)}")
            print(f"Companies House filings: {len(ch_rows)}")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(results) + len(ch_rows))
            return

        ch_inserted = _store_filings(ch_rows)
        LOGGER.info("Companies House: %d filings stored", ch_inserted)

        db.finish_scraper_run(
            run_id,
            "ok",
            fetched=len(results) + len(ch_rows),
            inserted=len([r for r in results if not r.get("cached")]) + ch_inserted,
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
