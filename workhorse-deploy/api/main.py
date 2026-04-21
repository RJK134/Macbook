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

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://workhorse_user:Wh0rse2026pg!@postgres:5432/workhorse",
)

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
