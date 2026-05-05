"""Procurement orchestrator — runs all source scrapers and upserts results."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import contracts_finder, find_a_tender, perplexity_procurement

LOGGER = get_logger("procurement.orchestrator")

SCRAPERS = [
    ("contracts_finder", contracts_finder.scrape),
    ("find_a_tender", find_a_tender.scrape),
    ("perplexity", perplexity_procurement.scrape),
]


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        existing = db.fetch_one(
            "SELECT id FROM procurement_opportunities WHERE url = %s",
            (url,),
        )
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO procurement_opportunities (
              notice_id, title, buyer, buyer_type, description, category,
              cpv_codes, value_min, value_max, currency,
              publication_date, deadline_date, status, source, url, country,
              relevance_score, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                r.get("notice_id"),
                r["title"][:300],
                r.get("buyer"),
                r.get("buyer_type"),
                r.get("description"),
                r.get("category"),
                r.get("cpv_codes"),
                r.get("value_min"),
                r.get("value_max"),
                r.get("currency", "GBP"),
                r.get("publication_date"),
                r.get("deadline_date"),
                r.get("status", "open"),
                r["source"],
                url,
                r.get("country", "UK"),
                r.get("relevance_score", 3),
                json.dumps(r.get("raw_data", {}), default=str),
            ),
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("procurement.orchestrator")
    LOGGER.info("Procurement orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)
        if dry_run:
            for r in all_rows[:5]:
                print(f"  {r['source']}: {r['title'][:80]}  -> {r['url'][:80]}")
            print(f"... ({len(all_rows)} total)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows))
            return
        ins, upd = _upsert(all_rows)
        LOGGER.info("Procurement: %d inserted, %d skipped", ins, upd)
        db.finish_scraper_run(run_id, "ok", fetched=len(all_rows), inserted=ins, skipped=upd)
    except Exception as exc:
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
