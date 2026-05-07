"""Education resources orchestrator — runs source scrapers and upserts."""

from __future__ import annotations

import argparse
import json
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import curated_platforms, exam_boards, ted_ed

LOGGER = get_logger("edu.orchestrator")

SCRAPERS = [
    ("ted_ed", ted_ed.scrape),
    ("exam_boards", exam_boards.scrape),
    ("curated_platforms", curated_platforms.scrape),
]


def _upsert(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            continue
        existing = db.fetch_one(
            "SELECT id FROM education_resources WHERE url = %s",
            (url,),
        )
        if existing:
            updated += 1
            continue
        db.execute(
            """
            INSERT INTO education_resources (
              exam_board, level, subject, topic, resource_type,
              title, source, url, description, year, difficulty, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (url) DO NOTHING
            """,
            (
                r.get("exam_board"),
                r.get("level"),
                r.get("subject", "general")[:100],
                r.get("topic"),
                r.get("resource_type", "article"),
                r.get("title", "")[:300],
                r.get("source"),
                url,
                r.get("description"),
                r.get("year"),
                r.get("difficulty"),
                json.dumps(r.get("raw_data", {}), default=str),
            ),
        )
        inserted += 1
    return inserted, updated


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("edu.orchestrator")
    LOGGER.info("Education resources orchestrator run %s", run_id)
    try:
        all_rows: list[dict] = []
        for name, fn in SCRAPERS:
            try:
                all_rows.extend(fn())
            except Exception as exc:
                LOGGER.exception("%s failed: %s", name, exc)
        if dry_run:
            for r in all_rows[:8]:
                print(f"  {r['source']}: [{r.get('level') or '-'}] {r['subject']} — {r['title'][:70]}")
            print(f"... ({len(all_rows)} total)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rows))
            return
        ins, upd = _upsert(all_rows)
        LOGGER.info("Education: %d inserted, %d skipped", ins, upd)
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
