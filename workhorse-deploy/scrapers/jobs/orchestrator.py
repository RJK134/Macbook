"""Jobs orchestrator — dedupe by URL, score relevance, upsert."""

from __future__ import annotations

import argparse
import json
import re
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import jobs_ac_uk, swiss_uni_jobs, times_higher_ed

LOGGER = get_logger("jobs.orchestrator")

SCRAPERS = [
    ("jobs_ac_uk", jobs_ac_uk.scrape),
    ("times_higher_ed", times_higher_ed.scrape),
    ("swiss_uni_jobs", swiss_uni_jobs.scrape),
]

HIGH_RELEVANCE = re.compile(
    r"\b(edtech|education technology|higher education|academic management|"
    r"student management|learning technology|head of digital|director of digital|"
    r"head of student|registrar|quality assurance)\b",
    re.I,
)
MEDIUM_RELEVANCE = re.compile(
    r"\b(university|college|education|academic|student|registry|admissions)\b",
    re.I,
)


def _score(row: dict) -> int:
    text = f"{row.get('title', '')} {row.get('description', '')}"
    if HIGH_RELEVANCE.search(text):
        return 1  # higher = more relevant; we'll sort ASC
    if MEDIUM_RELEVANCE.search(text):
        return 3
    return 5


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = r.get("url") or ""
        if not url:
            continue
        score = _score(r)
        params = (
            r["title"][:300],
            r.get("employer"),
            r.get("location"),
            r.get("country"),
            r.get("salary_min"),
            r.get("salary_max"),
            (r.get("currency") or ("CHF" if r.get("country") == "CH" else "GBP"))[:3],
            url,
            r.get("closing_date"),
            r.get("posted_date"),
            (r.get("description") or "")[:4000],
            r.get("source", "rss"),
            r.get("category"),
            score,
            json.dumps(r.get("raw_data", {}), default=str),
        )
        existing = db.fetch_one("SELECT id FROM job_listings WHERE url = %s", (url,))
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO job_listings (
              title, employer, location, country, salary_min, salary_max,
              currency, url, closing_date, posted_date, description,
              source, category, relevance_score, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            params,
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("jobs.orchestrator")
    LOGGER.info("Jobs orchestrator run %s", run_id)
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
        LOGGER.info("Jobs: %d inserted, %d skipped", ins, upd)
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
