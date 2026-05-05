"""Generate curriculum design insights from investment signals and job market data.

Uses investment trends as leading indicators: where VC money flows today
predicts where graduate jobs will be in 3-5 years. Cross-references with
current course offerings to identify gaps and opportunities.
"""

from __future__ import annotations

import json

from ..common import db, gemini, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("coursepulse.insights")

INSIGHT_QUERIES = [
    {
        "query": (
            "Based on VC and government investment trends in the last 12 months, "
            "what new university course subjects or specialisations should UK "
            "universities be developing? Consider: AI/ML applications by sector, "
            "climate tech, health tech, fintech, cyber security, space tech, "
            "creative AI. For each, give: suggested course title, target degree "
            "level, key modules, expected graduate demand in 3-5 years, "
            "relevant investment signals (company, amount, date)."
        ),
        "topic": "investment-led-courses",
        "engine": "both",
        "insight_type": "curriculum-gap",
        "region": "UK",
    },
    {
        "query": (
            "Which existing UK university courses are at risk of declining "
            "enrolment or poor graduate outcomes based on current automation "
            "trends, AI displacement, and employer demand shifts? For each "
            "at-risk subject, suggest how the curriculum could be modernised "
            "to remain relevant. Cite employment data and technology trends."
        ),
        "topic": "at-risk-courses",
        "engine": "gemini",
        "insight_type": "curriculum-risk",
        "region": "UK",
    },
    {
        "query": (
            "What interdisciplinary degree programmes are UK and Swiss "
            "universities launching that combine traditional subjects with "
            "AI, data science, or sustainability? Examples: 'Economics with "
            "Data Science', 'Law and AI', 'Sustainable Engineering'. "
            "List programmes, universities, and start dates."
        ),
        "topic": "interdisciplinary-programmes",
        "engine": "perplexity",
        "insight_type": "emerging-programme",
        "region": "UK/CH",
    },
    {
        "query": (
            "Analyse Swiss EdTech and higher education investment trends. "
            "Which sectors are receiving the most funding (Innosuisse, VC, "
            "cantonal grants)? What does this signal about future skills "
            "demand and curriculum needs in Swiss universities and "
            "Fachhochschulen? Include specific companies, amounts, and dates."
        ),
        "topic": "swiss-investment-curriculum",
        "engine": "both",
        "insight_type": "investment-signal",
        "region": "Switzerland",
    },
    {
        "query": (
            "What micro-credentials, professional certificates, and short "
            "courses are employers increasingly requiring or preferring over "
            "traditional degrees? Which universities are offering them? "
            "Focus on tech, business, healthcare, and creative sectors. "
            "Include: credential name, provider, employer adoption rate, cost."
        ),
        "topic": "micro-credentials-demand",
        "engine": "both",
        "insight_type": "credential-trend",
        "region": "UK/Global",
    },
    {
        "query": (
            "What are the top 15 fastest-growing tech job categories in the UK "
            "and Switzerland that currently have no dedicated university degree "
            "programme? For each, suggest a course structure: title, core modules, "
            "industry certifications to embed, expected salary, and demand forecast."
        ),
        "topic": "unmet-course-demand",
        "engine": "both",
        "insight_type": "curriculum-gap",
        "region": "UK/CH",
    },
]


def _store_insight(
    insight_type: str,
    topic: str,
    answer: str,
    citations: list,
    source: str,
    region: str | None,
    subject_area: str | None = None,
) -> None:
    db.execute(
        """
        INSERT INTO coursepulse_insights (
            insight_type, subject_area, title, summary, detail,
            source, region, raw_data
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            insight_type,
            subject_area,
            topic,
            answer[:500],
            answer,
            source,
            region,
            json.dumps({"citations": citations}, default=str),
        ),
    )


def run_insights() -> int:
    count = 0
    for q in INSIGHT_QUERIES:
        engine = q["engine"]

        if engine in ("perplexity", "both"):
            try:
                res = perplexity.cached_ask(
                    q["query"], topic=q["topic"], region=q.get("region"),
                    system=(
                        "You are a higher education curriculum strategist. "
                        "Provide data-driven insights for course design. "
                        "Cite sources with URLs. Be specific about trends, "
                        "dates, and figures."
                    ),
                    cache_hours=24 * 7,
                )
                if not res.get("cached"):
                    _store_insight(
                        q["insight_type"], f"{q['topic']}/perplexity",
                        res["answer"], res.get("citations", []),
                        "perplexity", q.get("region"),
                    )
                    count += 1
                LOGGER.info("Perplexity %s: %s", q["topic"], "cached" if res.get("cached") else "fresh")
            except Exception as exc:
                LOGGER.warning("Perplexity %s failed: %s", q["topic"], exc)

        if engine in ("gemini", "both"):
            try:
                res = gemini.cached_ask(
                    q["query"], topic=q["topic"], region=q.get("region"),
                    system=(
                        "You are a higher education curriculum strategist "
                        "and investment analyst. Analyse trends deeply. "
                        "Use investment data as leading indicators for "
                        "future skills demand. Be quantitative."
                    ),
                    cache_hours=24 * 7,
                )
                if not res.get("cached"):
                    _store_insight(
                        q["insight_type"], f"{q['topic']}/gemini",
                        res["answer"], res.get("citations", []),
                        "gemini", q.get("region"),
                    )
                    count += 1
                LOGGER.info("Gemini %s: %s", q["topic"], "cached" if res.get("cached") else "fresh")
            except Exception as exc:
                LOGGER.warning("Gemini %s failed: %s", q["topic"], exc)

    return count
