"""Research orchestrator — runs all dual-engine queries and syncs to Google Drive."""

from __future__ import annotations

import argparse
import subprocess
import sys

from ..common import db
from ..common.logging_setup import get_logger
from . import engine, queries

LOGGER = get_logger("research.orchestrator")

GDRIVE_REMOTE = "gdrive5tb:workhorse-archive"
LOCAL_ARCHIVE = "/mnt/usb-archive"


def _sync_to_gdrive() -> None:
    try:
        subprocess.run(
            ["rclone", "sync", f"{LOCAL_ARCHIVE}/raw/", f"{GDRIVE_REMOTE}/raw/", "--quiet"],
            timeout=300,
            check=False,
        )
        LOGGER.info("Google Drive sync complete")
    except FileNotFoundError:
        LOGGER.warning("rclone not found — skipping cloud sync")
    except Exception as exc:
        LOGGER.warning("Google Drive sync failed: %s", exc)


def run(dry_run: bool = False, area: str | None = None) -> None:
    run_id = db.start_scraper_run("research.orchestrator")
    LOGGER.info("Research orchestrator run %s", run_id)

    try:
        if area:
            query_list = [q for q in queries.ALL_QUERIES if q.get("area") == area]
            LOGGER.info("Filtered to area=%s: %d queries", area, len(query_list))
        else:
            query_list = queries.ALL_QUERIES
            LOGGER.info("Running all %d research queries", len(query_list))

        if dry_run:
            for q in query_list:
                print(f"  [{q['engine']}] {q['area']}/{q['topic']} ({q.get('region')})")
            print(f"\n{len(query_list)} queries (dry run — no API calls)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(query_list))
            return

        results = engine.run_queries(query_list)

        fresh = [r for r in results if not r.get("cached")]
        cached = [r for r in results if r.get("cached")]
        LOGGER.info("Results: %d fresh, %d cached", len(fresh), len(cached))

        _sync_to_gdrive()

        db.finish_scraper_run(
            run_id,
            "ok",
            fetched=len(query_list),
            inserted=len(fresh),
            skipped=len(cached),
        )
    except Exception as exc:
        LOGGER.exception("Research orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--area", choices=["courses", "jobs", "funding", "film", "job_trends", "financial"])
    args = parser.parse_args()
    run(dry_run=args.dry_run, area=args.area)
