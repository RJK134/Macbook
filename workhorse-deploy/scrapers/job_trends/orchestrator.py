"""Run job_trends scrapers and persist to job_trends table."""

from __future__ import annotations

import argparse
import json
import re
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import gov_uk_skills, ons_labour_market, wef_future_jobs

LOGGER = get_logger("trends.orchestrator")

SCRAPERS = [
    ("ons", ons_labour_market.scrape),
    ("gov.uk", gov_uk_skills.scrape),
    ("wef", wef_future_jobs.scrape),
]

# Keywords that indicate "growing" vs "declining" sectors.
GROWING_HINTS = re.compile(
    r"\b(grow|growing|emerging|increasing|in demand|shortage|hiring boom|expand)\b",
    re.I,
)
DECLINING_HINTS = re.compile(
    r"\b(declin|shrinking|automated away|displac|fall|decreas|loss of)\b",
    re.I,
)
SKILL_TOKENS = re.compile(
    r"\b(AI|machine learning|data|cloud|cyber|software|coding|programming|"
    r"analytics|automation|leadership|communication|maths?|engineering|"
    r"design|UX|product|finance|sustainability|green skills?|digital)\b",
    re.I,
)


def _classify(row: dict) -> dict:
    text = (row.get("occupation", "") + " " + json.dumps(row.get("raw_data", {}))).lower()
    if DECLINING_HINTS.search(text):
        row["trend"] = "declining"
    elif GROWING_HINTS.search(text):
        row["trend"] = "growing"
    skills = sorted({m.group(0).lower() for m in SKILL_TOKENS.finditer(text)})
    row["skills_required"] = skills[:20]
    return row


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        r = _classify(r)
        params = (
            r["occupation"][:300],
            r.get("sector"),
            r.get("trend"),
            r.get("growth_pct"),
            r.get("median_salary_gbp"),
            r.get("skills_required") or [],
            r.get("region"),
            r["source"],
            r.get("source_url"),
            r.get("reported_at"),
            json.dumps(r.get("raw_data", {}), default=str),
        )
        # Dedupe by (source_url, occupation) within last 30 days
        existing = db.fetch_one(
            "SELECT id FROM job_trends "
            "WHERE source_url = %s AND occupation = %s "
            "AND discovered_at > NOW() - INTERVAL '30 days'",
            (r.get("source_url"), r["occupation"][:300]),
        )
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO job_trends (
              occupation, sector, trend, growth_pct, median_salary_gbp,
              skills_required, region, source, source_url, reported_at, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            params,
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("job_trends.orchestrator")
    LOGGER.info("Job trends orchestrator run %s", run_id)
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
        LOGGER.info("Trends: %d inserted, %d skipped (dup)", ins, upd)
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
