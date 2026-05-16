"""Weekly data-lake export — denormalised CSVs of every domain table,
synced to gdrive5tb:workhorse-datalake/ for downstream products.

Each table dumps to its own CSV under a date-stamped directory so we
preserve historical snapshots in the cloud.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from datetime import date
from pathlib import Path

from ..common import db
from ..common.logging_setup import get_logger
from ..common.usb import databases_dir

LOGGER = get_logger("reports.datalake_export")

DATALAKE_GDRIVE = "gdrive5tb:workhorse-datalake"

# (csv_filename, sql) — one entry per table we want in the lake
EXPORTS: list[tuple[str, str]] = [
    ("courses.csv",
     "SELECT id, ucas_code, provider, title, qualification, subject_area, "
     "location_city, fees_uk_gbp, fees_intl_gbp, url, source, last_seen_at "
     "FROM courses WHERE active"),
    ("cost_of_living.csv",
     "SELECT city, country, rent_1bed_gbp, total_estimated_monthly_gbp, "
     "updated_at FROM cost_of_living"),
    ("course_career_pathways.csv",
     "SELECT subject_area, career_title, career_sector, demand_trend, "
     "growth_pct, median_salary_gbp, salary_5yr_gbp, roi_score, "
     "skills_overlap, confidence, source, updated_at "
     "FROM course_career_pathways"),
    ("coursepulse_insights.csv",
     "SELECT insight_type, subject_area, title, summary, source, region, created_at "
     "FROM coursepulse_insights"),
    ("funding_opportunities.csv",
     "SELECT title, funder, programme, region, country, amount_min, amount_max, "
     "currency, deadline, status, url, category, discovered_at "
     "FROM funding_opportunities"),
    ("job_listings.csv",
     "SELECT title, employer, location, salary_min, salary_max, currency, "
     "closing_date, posted_date, url, source, category, discovered_at "
     "FROM job_listings"),
    ("job_trends.csv",
     "SELECT occupation, sector, trend, growth_pct, median_salary_gbp, "
     "skills_required, region, source, source_url, reported_at, discovered_at "
     "FROM job_trends"),
    ("film_opportunities.csv",
     "SELECT title, opp_type, organisation, submission_deadline, fee_gbp, prize_gbp, "
     "url, region, source, status, discovered_at "
     "FROM film_opportunities"),
    ("investment_signals.csv",
     "SELECT title, company, sector, signal_type, amount, currency, funder, "
     "stage, region, country, source, url, discovered_at "
     "FROM investment_signals"),
    ("exchange_rates.csv",
     "SELECT base_currency, quote_currency, rate, rate_date, source "
     "FROM exchange_rates"),
    ("procurement_opportunities.csv",
     "SELECT notice_id, title, buyer, buyer_type, category, value_min, value_max, "
     "currency, publication_date, deadline_date, status, source, url, country "
     "FROM procurement_opportunities"),
    ("education_resources.csv",
     "SELECT exam_board, level, subject, topic, resource_type, title, source, "
     "url, year, difficulty, discovered_at "
     "FROM education_resources"),
    # past_paper_refs.csv — Maieus ExamPaperRef consumer (RJK134/Maieus2 PR #94).
    # METADATA ONLY. Filtered to past papers + specimens. board_id, subject_id,
    # and level are normalised to Maieus's catalogue ids so the importer's Zod
    # validation accepts them without further mapping.
    ("past_paper_refs.csv",
     "SELECT "
     "  CASE "
     "    WHEN UPPER(exam_board) = 'AQA' THEN 'aqa' "
     "    WHEN UPPER(exam_board) LIKE '%EDEXCEL%' "
     "      OR UPPER(exam_board) LIKE '%PEARSON%' THEN 'edexcel' "
     "    WHEN UPPER(exam_board) = 'OCR' THEN 'ocr' "
     "    WHEN UPPER(exam_board) LIKE '%WJEC%' "
     "      OR UPPER(exam_board) LIKE '%EDUQAS%' THEN 'wjec-eduqas' "
     "    WHEN UPPER(exam_board) = 'CCEA' THEN 'ccea' "
     "    WHEN UPPER(exam_board) = 'SQA' THEN 'sqa' "
     "  END AS board_id, "
     "  year, paper_code, paper_name, duration_minutes, total_marks, "
     "  CASE "
     "    WHEN LOWER(subject) = 'mathematics' THEN 'mathematics' "
     "    WHEN LOWER(subject) = 'biology' THEN 'biology' "
     "    WHEN LOWER(subject) = 'chemistry' THEN 'chemistry' "
     "    WHEN LOWER(subject) = 'physics' THEN 'physics' "
     "    WHEN LOWER(subject) = 'english literature' THEN 'english-literature' "
     "    WHEN LOWER(subject) = 'history' THEN 'history' "
     "    WHEN LOWER(subject) = 'geography' THEN 'geography' "
     "    WHEN LOWER(subject) = 'computer science' THEN 'computer-science' "
     "  END AS subject_id, "
     "  CASE "
     "    WHEN UPPER(level) = 'GCSE' THEN 'gcse' "
     "    WHEN UPPER(level) IN ('A-LEVEL','A LEVEL','ALEVEL') THEN 'a-level' "
     "  END AS level, "
     "  official_pdf_url, "
     "  ('[' || array_to_string("
     "    array(SELECT '\"' || u || '\"' FROM unnest(aggregator_urls) AS u), ',') "
     "    || ']') AS aggregator_urls, "
     "  licence "
     "FROM education_resources "
     "WHERE resource_type IN ('past-paper', 'sample-paper', 'specimen') "
     "  AND paper_code IS NOT NULL "
     "  AND year IS NOT NULL "
     "  AND duration_minutes IS NOT NULL "
     "  AND total_marks IS NOT NULL "
     "  AND CASE "
     "    WHEN UPPER(exam_board) = 'AQA' THEN 'aqa' "
     "    WHEN UPPER(exam_board) LIKE '%EDEXCEL%' "
     "      OR UPPER(exam_board) LIKE '%PEARSON%' THEN 'edexcel' "
     "    WHEN UPPER(exam_board) = 'OCR' THEN 'ocr' "
     "    WHEN UPPER(exam_board) LIKE '%WJEC%' "
     "      OR UPPER(exam_board) LIKE '%EDUQAS%' THEN 'wjec-eduqas' "
     "    WHEN UPPER(exam_board) = 'CCEA' THEN 'ccea' "
     "    WHEN UPPER(exam_board) = 'SQA' THEN 'sqa' "
     "  END IS NOT NULL"),
    ("sen_resources.csv",
     "SELECT resource_type, title, source, url, category, region, applies_to, "
     "published_date, discovered_at "
     "FROM sen_resources"),
    ("shakespeare_resources.csv",
     "SELECT resource_type, title, source, url, play, format, audience, "
     "engagement_score, published_date, discovered_at "
     "FROM shakespeare_resources"),
    ("finance_bulletins.csv",
     "SELECT source, category, title, url, summary, published_date, "
     "ticker, metric_value, metric_unit, discovered_at "
     "FROM finance_bulletins"),
    ("financial_research.csv",
     "SELECT topic, region, source, query, answer, citations, created_at "
     "FROM financial_research WHERE created_at > NOW() - INTERVAL '90 days'"),
]


def _export_table(filename: str, sql: str, out_dir: Path) -> int:
    try:
        rows = db.fetch_all(sql)
    except Exception as exc:
        LOGGER.warning("Skipping %s: %s", filename, exc)
        return 0
    if not rows:
        return 0
    path = out_dir / filename
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow({k: ("" if v is None else str(v)) for k, v in r.items()})
    return len(rows)


def _sync_to_gdrive(local_dir: Path, snapshot: str) -> None:
    if not _has_rclone():
        LOGGER.warning("rclone not found — skipping data lake sync")
        return
    target = f"{DATALAKE_GDRIVE}/{snapshot}/"
    LOGGER.info("rclone sync %s -> %s", local_dir, target)
    subprocess.run(
        ["rclone", "sync", str(local_dir) + "/", target, "--quiet"],
        check=False,
    )
    # Also keep a 'latest' pointer
    subprocess.run(
        ["rclone", "sync", str(local_dir) + "/", f"{DATALAKE_GDRIVE}/latest/", "--quiet"],
        check=False,
    )


def _has_rclone() -> bool:
    try:
        subprocess.run(["rclone", "version"], check=True, capture_output=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("reports.datalake_export")
    LOGGER.info("Data lake export run %s", run_id)
    today = date.today().isoformat()
    out_dir = databases_dir() / "datalake" / today
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    try:
        for filename, sql in EXPORTS:
            n = _export_table(filename, sql, out_dir)
            total += n
            if n:
                LOGGER.info("  %s: %d rows", filename, n)
        if dry_run:
            print(f"Would sync {out_dir} ({total} rows) to {DATALAKE_GDRIVE}/{today}/")
            db.finish_scraper_run(run_id, "dry_run", fetched=total)
            return
        _sync_to_gdrive(out_dir, today)
        db.finish_scraper_run(run_id, "ok", fetched=total, inserted=total)
        LOGGER.info("Data lake export complete: %d total rows", total)
    except Exception as exc:
        LOGGER.exception("Data lake export failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
