"""CoursePulse orchestrator — career mapping + curriculum insights + data lake export."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from ..common import db
from ..common.logging_setup import get_logger
from ..common.usb import databases_dir
from . import career_mapper, curriculum_insights

LOGGER = get_logger("coursepulse.orchestrator")

GDRIVE_REMOTE = "gdrive5tb:workhorse-archive"
DATALAKE_GDRIVE = "gdrive5tb:workhorse-datalake"


def _get_subject_areas() -> list[dict]:
    return db.fetch_all(
        """
        SELECT subject_area, COUNT(*) AS course_count
        FROM courses
        WHERE active AND subject_area IS NOT NULL
        GROUP BY subject_area
        ORDER BY course_count DESC
        """
    )


def _export_career_pathways_csv() -> str:
    rows = db.fetch_all(
        """
        SELECT cp.subject_area, cp.career_title, cp.career_sector,
               cp.demand_trend, cp.growth_pct, cp.median_salary_gbp,
               cp.salary_5yr_gbp, cp.roi_score, cp.course_count,
               cp.skills_overlap, cp.confidence, cp.source, cp.updated_at
        FROM course_career_pathways cp
        ORDER BY cp.subject_area, cp.median_salary_gbp DESC NULLS LAST
        """
    )
    if not rows:
        return ""
    path = databases_dir() / "career_pathways.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "subject_area", "career_title", "career_sector", "demand_trend",
            "growth_pct", "median_salary_gbp", "salary_5yr_gbp", "roi_score",
            "course_count", "skills_overlap", "confidence", "source", "updated_at",
        ])
        writer.writeheader()
        for r in rows:
            r["skills_overlap"] = ", ".join(r["skills_overlap"] or [])
            writer.writerow(r)
    LOGGER.info("Exported %d career pathways to %s", len(rows), path)
    return str(path)


def _export_datalake() -> None:
    """Export denormalised datasets to Google Drive as the CoursePulse data lake."""
    db_dir = databases_dir()

    # 1. Enriched courses (courses + cost of living + career pathways)
    rows = db.fetch_all(
        """
        SELECT
            c.provider, c.title, c.qualification, c.subject_area,
            c.duration_months, c.study_mode, c.location_city, c.location_country,
            c.fees_uk_gbp, c.fees_intl_gbp, c.url, c.source,
            c.first_seen_at, c.last_seen_at,
            col.rent_1bed_gbp, col.rent_shared_gbp,
            col.groceries_monthly_gbp, col.transport_monthly_gbp,
            col.total_estimated_monthly_gbp
        FROM courses c
        LEFT JOIN cost_of_living col ON LOWER(c.location_city) = LOWER(col.city)
        WHERE c.active
        ORDER BY c.provider, c.title
        """
    )
    if rows:
        path = db_dir / "datalake_courses_enriched.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        LOGGER.info("Data lake: %d enriched courses", len(rows))

    # 2. Career pathways
    _export_career_pathways_csv()

    # 3. Full funding opportunities
    rows = db.fetch_all(
        """
        SELECT title, funder, region, country, amount_max, currency,
               deadline, url, source, category, status, discovered_at
        FROM funding_opportunities
        WHERE status = 'open'
        ORDER BY deadline NULLS LAST
        """
    )
    if rows:
        path = db_dir / "datalake_funding.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        LOGGER.info("Data lake: %d funding opportunities", len(rows))

    # 4. CoursePulse insights
    rows = db.fetch_all(
        """
        SELECT insight_type, subject_area, title, summary, source, region, created_at
        FROM coursepulse_insights
        ORDER BY created_at DESC
        LIMIT 200
        """
    )
    if rows:
        path = db_dir / "datalake_coursepulse_insights.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        LOGGER.info("Data lake: %d CoursePulse insights", len(rows))

    # 5. Job trends
    rows = db.fetch_all(
        """
        SELECT occupation, sector, trend, growth_pct, median_salary_gbp,
               skills_required, region, source, discovered_at
        FROM job_trends
        ORDER BY discovered_at DESC
        """
    )
    if rows:
        path = db_dir / "datalake_job_trends.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            for r in rows:
                r["skills_required"] = ", ".join(r["skills_required"] or [])
                writer.writerow(r)
        LOGGER.info("Data lake: %d job trends", len(rows))

    # Sync to Google Drive
    try:
        subprocess.run(
            ["rclone", "sync", str(db_dir) + "/", f"{DATALAKE_GDRIVE}/", "--quiet"],
            timeout=300, check=False,
        )
        LOGGER.info("Data lake synced to Google Drive")
    except FileNotFoundError:
        LOGGER.warning("rclone not found — skipping data lake sync")
    except Exception as exc:
        LOGGER.warning("Data lake sync failed: %s", exc)


def run(dry_run: bool = False, area: str | None = None) -> None:
    run_id = db.start_scraper_run("coursepulse.orchestrator")
    LOGGER.info("CoursePulse orchestrator run %s", run_id)

    try:
        subjects = _get_subject_areas()
        LOGGER.info("Found %d subject areas in courses table", len(subjects))

        if area:
            subjects = [s for s in subjects if s["subject_area"].lower() == area.lower()]

        if dry_run:
            print(f"Subject areas ({len(subjects)}):")
            for s in subjects:
                print(f"  {s['subject_area']:30s} ({s['course_count']} courses)")
            print(f"\nInsight queries: {len(curriculum_insights.INSIGHT_QUERIES)}")
            print("(dry run — no API calls)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(subjects))
            return

        # Phase 1: Career mapping for each subject area
        total_pathways = 0
        total_inserted = 0
        total_updated = 0
        for s in subjects:
            LOGGER.info("Mapping careers for: %s (%d courses)", s["subject_area"], s["course_count"])
            rows = career_mapper.map_subject(s["subject_area"], s["course_count"])
            ins, upd = career_mapper.upsert_pathways(rows)
            total_pathways += len(rows)
            total_inserted += ins
            total_updated += upd
            LOGGER.info("  %s: %d pathways (%d new, %d updated)", s["subject_area"], len(rows), ins, upd)

        # Phase 2: Curriculum insights from investment + job market signals
        insights_count = curriculum_insights.run_insights()
        LOGGER.info("Curriculum insights: %d new", insights_count)

        # Phase 3: Export data lake to Google Drive
        _export_datalake()

        db.finish_scraper_run(
            run_id, "ok",
            fetched=len(subjects),
            inserted=total_inserted + insights_count,
            updated=total_updated,
        )
        LOGGER.info(
            "CoursePulse complete: %d pathways (%d new), %d insights, data lake exported",
            total_pathways, total_inserted, insights_count,
        )
    except Exception as exc:
        LOGGER.exception("CoursePulse orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--area", help="Only process a single subject area")
    args = parser.parse_args()
    run(dry_run=args.dry_run, area=args.area)
