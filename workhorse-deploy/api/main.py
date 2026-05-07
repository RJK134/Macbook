"""FastAPI for MyCourseMatchmaker — exposes the courses table read-only.

Bound to 0.0.0.0:8000; access from your laptop via Tailscale (or local
network) at http://192.168.1.120:8000 or http://100.65.159.28:8000.
"""

from __future__ import annotations

import os
from typing import Any

import psycopg
from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row

DB_URL = os.environ["DATABASE_URL"]

app = FastAPI(
    title="Workhorse Course API",
    description="Read-only API serving the MyCourseMatchmaker course database.",
    version="1.0.0",
)


def _conn() -> psycopg.Connection:
    return psycopg.connect(DB_URL, row_factory=dict_row)


@app.get("/health")
def health() -> dict[str, Any]:
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT count(*) AS n FROM courses WHERE active")
            n = cur.fetchone()["n"]
        return {"status": "ok", "courses": n}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/courses")
def list_courses(
    subject: str | None = Query(None, description="Subject area substring match"),
    qualification: str | None = Query(None, description="e.g. BSc, MSc, BA, PhD"),
    location: str | None = Query(None, description="City substring match"),
    provider: str | None = Query(None, description="University name substring"),
    q: str | None = Query(None, description="Free text fuzzy match on title"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    where = ["active"]
    params: list[Any] = []
    if subject:
        where.append("subject_area ILIKE %s")
        params.append(f"%{subject}%")
    if qualification:
        where.append("qualification ILIKE %s")
        params.append(f"%{qualification}%")
    if location:
        where.append("location_city ILIKE %s")
        params.append(f"%{location}%")
    if provider:
        where.append("provider ILIKE %s")
        params.append(f"%{provider}%")
    if q:
        where.append("(title %% %s OR title ILIKE %s)")
        params.extend([q, f"%{q}%"])
    sql = (
        "SELECT id, ucas_code, provider, title, qualification, subject_area, "
        "location_city, fees_uk_gbp, url, source, last_seen_at "
        f"FROM courses WHERE {' AND '.join(where)} "
        "ORDER BY provider, title LIMIT %s OFFSET %s"
    )
    params.extend([limit, offset])
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
        cur.execute(
            f"SELECT count(*) AS total FROM courses WHERE {' AND '.join(where)}",
            tuple(params[:-2]),
        )
        total = cur.fetchone()["total"]
    return {"total": total, "limit": limit, "offset": offset, "items": rows}


@app.get("/courses/{course_id}")
def get_course(course_id: str) -> dict[str, Any]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT * FROM courses WHERE id = %s", (course_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="course not found")
    return row


@app.get("/cost-of-living")
def list_col() -> dict[str, Any]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT city, country, rent_1bed_gbp, total_estimated_monthly_gbp, "
            "updated_at FROM cost_of_living ORDER BY country, city"
        )
        rows = cur.fetchall()
    return {"items": rows}


@app.get("/cost-of-living/{city}")
def get_col(city: str) -> dict[str, Any]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT * FROM cost_of_living WHERE city ILIKE %s LIMIT 1",
            (city,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="city not found")
    return row


@app.get("/providers")
def list_providers(limit: int = Query(200, ge=1, le=2000)) -> dict[str, Any]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            "SELECT provider, count(*) AS course_count FROM courses "
            "WHERE active GROUP BY provider ORDER BY course_count DESC LIMIT %s",
            (limit,),
        )
        rows = cur.fetchall()
    return {"items": rows}


@app.get("/courses/{course_id}/careers")
def course_careers(course_id: str) -> dict[str, Any]:
    """Career pathways for a specific course, based on its subject area."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT subject_area FROM courses WHERE id = %s", (course_id,))
        course = cur.fetchone()
    if not course or not course.get("subject_area"):
        raise HTTPException(status_code=404, detail="course not found or no subject area")
    return _careers_for_subject(course["subject_area"])


@app.get("/subjects")
def list_subjects() -> dict[str, Any]:
    """All subject areas with course counts and career pathway counts."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT c.subject_area, COUNT(DISTINCT c.id) AS course_count,
                   COUNT(DISTINCT cp.id) AS career_count
            FROM courses c
            LEFT JOIN course_career_pathways cp ON cp.subject_area = c.subject_area
            WHERE c.active AND c.subject_area IS NOT NULL
            GROUP BY c.subject_area
            ORDER BY course_count DESC
            """
        )
        rows = cur.fetchall()
    return {"items": rows}


@app.get("/subjects/{subject_area}/pathways")
def subject_pathways(subject_area: str) -> dict[str, Any]:
    """Full career pathways for a subject area — salary, demand, ROI, skills."""
    return _careers_for_subject(subject_area)


def _careers_for_subject(subject_area: str) -> dict[str, Any]:
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT career_title, career_sector, demand_trend, growth_pct,
                   median_salary_gbp, salary_5yr_gbp, roi_score,
                   skills_overlap, confidence, source, updated_at
            FROM course_career_pathways
            WHERE subject_area ILIKE %s
            ORDER BY median_salary_gbp DESC NULLS LAST
            """,
            (subject_area,),
        )
        pathways = cur.fetchall()
        cur.execute(
            "SELECT AVG(fees_uk_gbp) AS avg_fee, COUNT(*) AS course_count "
            "FROM courses WHERE subject_area ILIKE %s AND active AND fees_uk_gbp > 0",
            (subject_area,),
        )
        stats = cur.fetchone()
    return {
        "subject_area": subject_area,
        "course_count": stats["course_count"] if stats else 0,
        "avg_fee_gbp": float(stats["avg_fee"]) if stats and stats["avg_fee"] else None,
        "pathways": pathways,
    }


@app.get("/insights")
def list_insights(
    insight_type: str | None = Query(None, description="Filter by type: curriculum-gap, curriculum-risk, etc."),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """CoursePulse curriculum insights."""
    where = ["1=1"]
    params: list[Any] = []
    if insight_type:
        where.append("insight_type = %s")
        params.append(insight_type)
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            f"""
            SELECT insight_type, subject_area, title, summary, source, region, created_at
            FROM coursepulse_insights
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT %s
            """,
            tuple(params + [limit]),
        )
        rows = cur.fetchall()
    return {"items": rows}


@app.get("/fx")
def exchange_rates() -> dict[str, Any]:
    """Latest exchange rates and interest rates."""
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT ON (base_currency, quote_currency)
                base_currency, quote_currency, rate, rate_date, source
            FROM exchange_rates
            ORDER BY base_currency, quote_currency, rate_date DESC
            """
        )
        rows = cur.fetchall()
    return {"items": rows}
