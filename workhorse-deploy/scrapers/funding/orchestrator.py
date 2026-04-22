"""Funding orchestrator — runs all source scrapers and upserts results."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime

from ..common import db
from ..common.logging_setup import get_logger
from . import eu_horizon, perplexity_funding, swiss_innosuisse, uk_innovate

LOGGER = get_logger("funding.orchestrator")

SCRAPERS = [
    ("uk_innovate", uk_innovate.scrape),
    ("eu_horizon", eu_horizon.scrape),
    ("swiss", swiss_innosuisse.scrape),
    ("perplexity", perplexity_funding.scrape),
]


def _parse_date(s) -> datetime | None:
    if not s:
        return None
    if hasattr(s, "isoformat"):
        return s
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = r.get("url") or ""
        if not url:
            continue
        deadline = _parse_date(r.get("deadline"))
        params = (
            r["title"][:300],
            r.get("funder"),
            r.get("programme"),
            r.get("region"),
            r.get("country"),
            r.get("amount_min"),
            r.get("amount_max"),
            (r.get("currency") or "GBP")[:3],
            deadline.date() if deadline else None,
            r.get("eligibility"),
            (r.get("description") or "")[:4000],
            url,
            r.get("source", "rss"),
            r.get("category"),
            r.get("status", "open"),
            r.get("relevance_score", 3),
            json.dumps(r.get("raw_data", {}), default=str),
        )
        existing = db.fetch_one(
            "SELECT id FROM funding_opportunities WHERE url = %s",
            (url,),
        )
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO funding_opportunities (
              title, funder, programme, region, country,
              amount_min, amount_max, currency, deadline, eligibility,
              description, url, source, category, status, relevance_score, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            params,
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("funding.orchestrator")
    LOGGER.info("Funding orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("%s failed: %s", name, exc)
        if dry_run:
            for r in all_rows[:10]:
                print(r)
            print(f"... ({len(all_rows)} total)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows))
            return
        ins, upd = _upsert(all_rows)
        LOGGER.info("Funding: %d inserted, %d skipped", ins, upd)
        db.finish_scraper_run(run_id, "ok", fetched=len(all_rows), inserted=ins, skipped=upd)
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
