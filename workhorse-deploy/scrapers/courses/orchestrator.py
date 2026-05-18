"""Orchestrate all course scrapers, dedupe, and upsert to Postgres."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from typing import Iterable

from ..common import db
from ..common.logging_setup import get_logger
from ..common.usb import databases_dir
from . import complete_uni_guide, cost_of_living, discoveruni_api, hesa, ofqual, whatuni

LOGGER = get_logger("courses.orchestrator")

# Title-based qualification inference. Discover Uni / WhatUni / CUG often
# emit the qualification embedded in the title ("BA (Hons) Drama",
# "Drama - MA", "PhD in Sociology") but don't populate the `qualification`
# column itself. Patterns are checked in order; first match wins. Order
# matters: doctoral before masters, integrated-masters before plain
# bachelors, otherwise an MEng matches "BEng" first.
_QUAL_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(PhD|DPhil|EdD|DBA|MD\b|MPhil)\b", re.I), "Doctorate"),
    (re.compile(r"\bMA(?:\s|\(|$)", re.I), "MA"),
    (re.compile(r"\bMSc(?:\s|\(|$)", re.I), "MSc"),
    (re.compile(r"\bMBA(?:\s|\(|$)", re.I), "MBA"),
    (re.compile(r"\bLLM(?:\s|\(|$)", re.I), "LLM"),
    (re.compile(r"\bMRes(?:\s|\(|$)", re.I), "MRes"),
    (re.compile(r"\bMEng(?:\s|\(|$)", re.I), "MEng (Integrated Masters)"),
    (re.compile(r"\bMSci(?:\s|\(|$)", re.I), "MSci (Integrated Masters)"),
    (re.compile(r"\bMPharm(?:\s|\(|$)", re.I), "MPharm"),
    (re.compile(r"\bMArch(?:\s|\(|$)", re.I), "MArch"),
    (re.compile(r"\bBA(?:\s|\(|$)", re.I), "BA (Hons)"),
    (re.compile(r"\bBSc(?:\s|\(|$)", re.I), "BSc (Hons)"),
    (re.compile(r"\bBEng(?:\s|\(|$)", re.I), "BEng (Hons)"),
    (re.compile(r"\bLLB(?:\s|\(|$)", re.I), "LLB (Hons)"),
    (re.compile(r"\bMB\s*ChB|\bMBBS\b", re.I), "MB ChB"),
    (re.compile(r"\b(Foundation Degree|FdA|FdSc)\b", re.I), "Foundation Degree"),
    (re.compile(r"\b(HND|Higher National Diploma)\b", re.I), "HND"),
    (re.compile(r"\b(HNC|Higher National Certificate)\b", re.I), "HNC"),
    (re.compile(r"\bDiploma\b", re.I), "Diploma"),
    (re.compile(r"\bCertificate\b", re.I), "Certificate"),
    (re.compile(r"\bA[- ]?Level\b", re.I), "GCE A Level"),
    (re.compile(r"\bGCSE\b", re.I), "GCSE"),
]


def _infer_qualification(title: str) -> str:
    """Best-effort qualification extraction from a course title."""
    if not title:
        return ""
    for pat, label in _QUAL_PATTERNS:
        if pat.search(title):
            return label
    return ""

# NOTE: UCAS scraper removed — UCAS ToS explicitly prohibit commercial use.
# Discover Uni API replaces it with richer, licensed data (21,500 programmes).
SCRAPERS = [
    ("discoveruni-api", discoveruni_api.scrape),
    ("whatuni", whatuni.scrape),
    ("cug", complete_uni_guide.scrape),
    ("hesa", hesa.scrape),
    ("ofqual", ofqual.scrape),
]


def _dedupe(courses: Iterable[dict]) -> list[dict]:
    seen: set[tuple[str, str, str]] = set()
    out: list[dict] = []
    for c in courses:
        title = (c.get("title") or "").strip()
        qual = (c.get("qualification") or _infer_qualification(title)).strip()
        key = (
            (c.get("provider") or "").lower().strip(),
            title.lower(),
            qual.lower(),
        )
        if not key[0] or not key[1]:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def _upsert_courses(courses: list[dict]) -> tuple[int, int]:
    if not courses:
        return 0, 0
    inserted = 0
    updated = 0
    for c in courses:
        qual = c.get("qualification") or _infer_qualification(c.get("title") or "")
        params = (
            c.get("ucas_code"),
            c.get("provider") or "Unknown",
            c.get("title") or "Untitled",
            qual,
            c.get("subject_area"),
            c.get("duration_months"),
            c.get("study_mode"),
            c.get("location_city"),
            c.get("location_country", "UK"),
            c.get("fees_uk_gbp"),
            c.get("fees_intl_gbp"),
            c.get("entry_requirements"),
            c.get("url"),
            c.get("source"),
            c.get("description"),
            json.dumps(c, default=str),
        )
        result = db.fetch_one(
            """
            INSERT INTO courses (
              ucas_code, provider, title, qualification, subject_area,
              duration_months, study_mode, location_city, location_country,
              fees_uk_gbp, fees_intl_gbp, entry_requirements, url, source,
              description, raw_data
            ) VALUES (
              %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb
            )
            ON CONFLICT (provider, title, qualification) DO UPDATE
              SET last_seen_at = NOW(),
                  url = COALESCE(EXCLUDED.url, courses.url),
                  fees_uk_gbp = COALESCE(EXCLUDED.fees_uk_gbp, courses.fees_uk_gbp),
                  fees_intl_gbp = COALESCE(EXCLUDED.fees_intl_gbp, courses.fees_intl_gbp),
                  entry_requirements = COALESCE(EXCLUDED.entry_requirements, courses.entry_requirements),
                  duration_months = COALESCE(EXCLUDED.duration_months, courses.duration_months),
                  study_mode = COALESCE(EXCLUDED.study_mode, courses.study_mode),
                  description = COALESCE(EXCLUDED.description, courses.description),
                  raw_data = courses.raw_data || EXCLUDED.raw_data
            RETURNING (xmax = 0) AS inserted
            """,
            params,
        )
        if result and result.get("inserted"):
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def _upsert_cost_of_living(rows: list[dict]) -> tuple[int, int]:
    if not rows:
        return 0, 0
    inserted = updated = 0
    for r in rows:
        params = (
            r["city"],
            r.get("country", "UK"),
            r.get("rent_1bed_gbp"),
            r.get("rent_shared_gbp"),
            r.get("groceries_monthly_gbp"),
            r.get("transport_monthly_gbp"),
            r.get("utilities_monthly_gbp"),
            r.get("total_estimated_monthly_gbp"),
            r.get("source"),
            r.get("source_url"),
            json.dumps(r, default=str),
        )
        res = db.fetch_one(
            """
            INSERT INTO cost_of_living (
              city, country, rent_1bed_gbp, rent_shared_gbp,
              groceries_monthly_gbp, transport_monthly_gbp,
              utilities_monthly_gbp, total_estimated_monthly_gbp,
              source, source_url, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (city, country) DO UPDATE
              SET rent_1bed_gbp = EXCLUDED.rent_1bed_gbp,
                  rent_shared_gbp = EXCLUDED.rent_shared_gbp,
                  groceries_monthly_gbp = EXCLUDED.groceries_monthly_gbp,
                  transport_monthly_gbp = EXCLUDED.transport_monthly_gbp,
                  utilities_monthly_gbp = EXCLUDED.utilities_monthly_gbp,
                  total_estimated_monthly_gbp = EXCLUDED.total_estimated_monthly_gbp,
                  raw_data = cost_of_living.raw_data || EXCLUDED.raw_data,
                  updated_at = NOW()
            RETURNING (xmax = 0) AS inserted
            """,
            params,
        )
        if res and res.get("inserted"):
            inserted += 1
        else:
            updated += 1
    return inserted, updated


def _export_csv() -> None:
    rows = db.fetch_all(
        "SELECT provider, title, qualification, subject_area, "
        "location_city, fees_uk_gbp, url, source, last_seen_at "
        "FROM courses WHERE active ORDER BY provider, title"
    )
    if not rows:
        return
    path = databases_dir() / "courses_export.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    LOGGER.info("Wrote %d courses to %s", len(rows), path)


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("courses.orchestrator")
    LOGGER.info("Course orchestrator run %s", run_id)
    try:
        all_courses: list[dict] = []
        for name, fn in SCRAPERS:
            LOGGER.info("Running scraper: %s", name)
            try:
                all_courses.extend(fn())
            except Exception as exc:
                LOGGER.exception("Scraper %s failed: %s", name, exc)

        deduped = _dedupe(all_courses)
        LOGGER.info("Total %d, after dedupe: %d", len(all_courses), len(deduped))

        if dry_run:
            for c in deduped[:10]:
                print(c)
            print(f"... ({len(deduped)} total, dry run — no DB writes)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_courses))
            return

        c_inserted, c_updated = _upsert_courses(deduped)
        LOGGER.info("Courses: %d inserted, %d updated", c_inserted, c_updated)

        col_rows = cost_of_living.scrape()
        col_inserted, col_updated = _upsert_cost_of_living(col_rows)
        LOGGER.info("Cost of living: %d inserted, %d updated", col_inserted, col_updated)

        _export_csv()

        db.finish_scraper_run(
            run_id,
            "ok",
            fetched=len(all_courses) + len(col_rows),
            inserted=c_inserted + col_inserted,
            updated=c_updated + col_updated,
        )
    except Exception as exc:
        LOGGER.exception("Orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
