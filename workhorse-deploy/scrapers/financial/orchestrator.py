"""Financial orchestrator — runs Perplexity research + Companies House."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import boe_news, companies_house, perplexity_research, uk_authorities

LOGGER = get_logger("financial.orchestrator")


def _store_bulletins(rows: list[dict]) -> int:
    inserted = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        existing = db.fetch_one(
            "SELECT id FROM finance_bulletins WHERE url = %s",
            (url,),
        )
        if existing:
            continue
        db.execute(
            """
            INSERT INTO finance_bulletins (
              source, category, title, url, summary, published_date,
              ticker, metric_value, metric_unit, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                r["source"],
                r.get("category"),
                r["title"][:300],
                url,
                r.get("summary"),
                r.get("published_date"),
                r.get("ticker"),
                r.get("metric_value"),
                r.get("metric_unit"),
                json.dumps(r.get("raw_data", {}), default=str),
            ),
        )
        inserted += 1
    return inserted


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
        bulletins: list[dict] = []
        for name, fn in [("uk_authorities", uk_authorities.scrape), ("boe_news", boe_news.scrape)]:
            try:
                bulletins.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)

        if dry_run:
            print(f"Perplexity topics: {len(results)}")
            print(f"Companies House filings: {len(ch_rows)}")
            print(f"Finance bulletins: {len(bulletins)}")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(results) + len(ch_rows) + len(bulletins))
            return

        ch_inserted = _store_filings(ch_rows)
        bull_inserted = _store_bulletins(bulletins)
        LOGGER.info("Companies House: %d filings stored, bulletins: %d", ch_inserted, bull_inserted)

        db.finish_scraper_run(
            run_id,
            "ok",
            fetched=len(results) + len(ch_rows) + len(bulletins),
            inserted=len([r for r in results if not r.get("cached")]) + ch_inserted + bull_inserted,
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
