"""Shakespeare resources orchestrator."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import feeds, perplexity_discovery

LOGGER = get_logger("shakespeare.orchestrator")

SCRAPERS = [
    ("feeds", feeds.scrape),
    ("perplexity", perplexity_discovery.scrape),
]


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        existing = db.fetch_one(
            "SELECT id FROM shakespeare_resources WHERE url = %s",
            (url,),
        )
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO shakespeare_resources (
              resource_type, title, source, url, play, format, audience,
              description, engagement_score, published_date, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                r.get("resource_type", "article"),
                r.get("title", "")[:300],
                r.get("source"),
                url,
                r.get("play"),
                r.get("format"),
                r.get("audience"),
                r.get("description"),
                r.get("engagement_score", 3),
                r.get("published_date"),
                json.dumps(r.get("raw_data", {}), default=str),
            ),
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("shakespeare.orchestrator")
    LOGGER.info("Shakespeare orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)
        if dry_run:
            for r in all_rows[:8]:
                print(f"  {r['source']}: [{r.get('play') or '-'}] {r['title'][:80]}")
            print(f"... ({len(all_rows)} total)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows))
            return
        ins, upd = _upsert(all_rows)
        LOGGER.info("Shakespeare: %d inserted, %d skipped", ins, upd)
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
