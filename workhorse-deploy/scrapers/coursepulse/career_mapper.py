"""Map courses to career pathways using Perplexity + Gemini.

For each subject area in the courses table, queries both engines to build
a career pathway map: which jobs this subject leads to, salary data,
demand trends, skills overlap, and ROI estimates.
"""

from __future__ import annotations

import json

from ..common import db, gemini, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("coursepulse.career_mapper")

PERPLEXITY_SYSTEM = (
    "You are a career intelligence analyst specialising in UK and Swiss higher "
    "education graduate outcomes. Return precise, current data with URLs. "
    "Format each career path as a JSON object with keys: career_title, sector, "
    "demand_trend (growing/stable/declining), growth_pct (number or null), "
    "median_salary_gbp (number), salary_5yr_gbp (number, salary after 5 years), "
    "key_skills (list of strings). Wrap all entries in a JSON array."
)

GEMINI_SYSTEM = (
    "You are a curriculum design strategist. Analyse the relationship between "
    "university subject areas and career outcomes. Consider emerging roles, "
    "automation risk, and investment trends. Be quantitative where possible. "
    "Format each career path as a JSON object with keys: career_title, sector, "
    "demand_trend, growth_pct, median_salary_gbp, salary_5yr_gbp, key_skills, "
    "emerging_roles (list of new roles not yet mainstream), curriculum_gaps "
    "(list of skills employers want but courses rarely teach). "
    "Wrap all entries in a JSON array."
)


def _parse_careers(text: str) -> list[dict]:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end <= start:
        return []
    try:
        items = json.loads(text[start : end + 1])
        return [i for i in items if isinstance(i, dict) and i.get("career_title")]
    except json.JSONDecodeError:
        return []


def _safe_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("£", "").replace("$", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def map_subject(subject_area: str, course_count: int) -> list[dict]:
    query = (
        f"What are the top 10 career paths for UK university graduates with a degree "
        f"in {subject_area}? For each career, give: job title, sector, whether demand "
        f"is growing/stable/declining, annual growth percentage, median starting salary "
        f"in GBP, salary after 5 years in GBP, and the key skills employers require. "
        f"Use Graduate Outcomes data, HESA, LinkedIn, and Prospects.ac.uk."
    )

    all_careers: dict[str, dict] = {}

    try:
        pplx = perplexity.cached_ask(
            query, topic=f"career-map-{subject_area}", region="UK",
            system=PERPLEXITY_SYSTEM, cache_hours=24 * 14,
        )
        for c in _parse_careers(pplx["answer"]):
            key = c["career_title"].lower().strip()
            all_careers[key] = {
                "career_title": c["career_title"],
                "career_sector": c.get("sector"),
                "demand_trend": c.get("demand_trend"),
                "growth_pct": _safe_float(c.get("growth_pct")),
                "median_salary_gbp": _safe_float(c.get("median_salary_gbp")),
                "salary_5yr_gbp": _safe_float(c.get("salary_5yr_gbp")),
                "skills_overlap": c.get("key_skills") or [],
                "source": "perplexity",
                "raw_data": c,
            }
        LOGGER.info("Perplexity %s: %d careers", subject_area, len(all_careers))
    except Exception as exc:
        LOGGER.warning("Perplexity career map for %s failed: %s", subject_area, exc)

    gemini_query = (
        f"Analyse career pathways for {subject_area} graduates. Include: "
        f"(1) traditional career paths with current salary and demand data, "
        f"(2) emerging roles created by AI, sustainability, and digital transformation, "
        f"(3) curriculum gaps — skills employers want that {subject_area} courses "
        f"rarely cover. Consider investment trends in related sectors as leading "
        f"indicators of future demand."
    )

    try:
        gem = gemini.cached_ask(
            gemini_query, topic=f"career-analysis-{subject_area}", region="UK",
            system=GEMINI_SYSTEM, cache_hours=24 * 14,
        )
        for c in _parse_careers(gem["answer"]):
            key = c["career_title"].lower().strip()
            if key in all_careers:
                existing = all_careers[key]
                existing["source"] = "perplexity+gemini"
                existing["confidence"] = "high"
                existing["raw_data"]["gemini"] = c
                if c.get("curriculum_gaps"):
                    existing["curriculum_gaps"] = c["curriculum_gaps"]
                if c.get("emerging_roles"):
                    existing["emerging_roles"] = c["emerging_roles"]
            else:
                all_careers[key] = {
                    "career_title": c["career_title"],
                    "career_sector": c.get("sector"),
                    "demand_trend": c.get("demand_trend"),
                    "growth_pct": _safe_float(c.get("growth_pct")),
                    "median_salary_gbp": _safe_float(c.get("median_salary_gbp")),
                    "salary_5yr_gbp": _safe_float(c.get("salary_5yr_gbp")),
                    "skills_overlap": c.get("key_skills") or [],
                    "source": "gemini",
                    "raw_data": c,
                }
        LOGGER.info("Gemini %s: total %d careers", subject_area, len(all_careers))
    except Exception as exc:
        LOGGER.warning("Gemini career map for %s failed: %s", subject_area, exc)

    fees = db.fetch_one(
        "SELECT AVG(fees_uk_gbp) AS avg_fee FROM courses WHERE subject_area = %s AND active AND fees_uk_gbp > 0",
        (subject_area,),
    )
    avg_fee = float(fees["avg_fee"]) if fees and fees["avg_fee"] else None

    rows = []
    for career in all_careers.values():
        career["subject_area"] = subject_area
        career["course_count"] = course_count

        salary = career.get("median_salary_gbp")
        if avg_fee and salary and salary > 0:
            duration_years = 3
            total_cost = avg_fee * duration_years
            career["roi_score"] = round((salary - total_cost) / total_cost * 100, 1) if total_cost > 0 else None

        rows.append(career)

    return rows


def upsert_pathways(rows: list[dict]) -> tuple[int, int]:
    inserted = updated = 0
    for r in rows:
        params = (
            r["subject_area"],
            r["career_title"][:300],
            r.get("career_sector"),
            r.get("demand_trend"),
            r.get("growth_pct"),
            r.get("median_salary_gbp"),
            r.get("salary_5yr_gbp"),
            r.get("skills_overlap") or [],
            r.get("roi_score"),
            r.get("course_count", 0),
            r.get("source", "perplexity"),
            r.get("confidence", "medium"),
            json.dumps(r.get("raw_data", {}), default=str),
        )
        result = db.fetch_one(
            """
            INSERT INTO course_career_pathways (
                subject_area, career_title, career_sector, demand_trend,
                growth_pct, median_salary_gbp, salary_5yr_gbp, skills_overlap,
                roi_score, course_count, source, confidence, raw_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (subject_area, career_title) DO UPDATE SET
                demand_trend = EXCLUDED.demand_trend,
                growth_pct = EXCLUDED.growth_pct,
                median_salary_gbp = EXCLUDED.median_salary_gbp,
                salary_5yr_gbp = EXCLUDED.salary_5yr_gbp,
                skills_overlap = EXCLUDED.skills_overlap,
                roi_score = EXCLUDED.roi_score,
                course_count = EXCLUDED.course_count,
                source = EXCLUDED.source,
                confidence = EXCLUDED.confidence,
                raw_data = course_career_pathways.raw_data || EXCLUDED.raw_data,
                updated_at = NOW()
            RETURNING (xmax = 0) AS inserted
            """,
            params,
        )
        if result and result.get("inserted"):
            inserted += 1
        else:
            updated += 1
    return inserted, updated
