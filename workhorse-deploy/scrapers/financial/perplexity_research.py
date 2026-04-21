"""Deep financial research questions for Future Horizons + the EdTech app.

Runs a curated set of Perplexity Sonar Pro queries weekly. Caches answers
for 7 days in financial_research so the master digest can include them
without re-paying for the same query.
"""

from __future__ import annotations

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("financial.perplexity")

SYSTEM_PROMPT = (
    "You are a financial intelligence analyst for an EdTech founder based "
    "in Switzerland with operations in the UK and EU. Be precise. "
    "Cite sources with URLs. Provide quantitative figures where available. "
    "Format responses with clear sections, bullet points, and source citations."
)

QUERIES = [
    {
        "topic": "edtech-market-size",
        "region": "Global",
        "query": (
            "What is the latest global EdTech market size estimate, growth "
            "rate, and 5-year forecast? Break down by segment (K-12, HE, "
            "corporate L&D, language learning) and by region (UK, EU, CH, US, APAC). "
            "Cite report names and publication dates."
        ),
    },
    {
        "topic": "he-software-market-uk",
        "region": "UK",
        "query": (
            "Size and trends of the UK higher-education software market: "
            "student information systems, learning management, academic "
            "management, and admissions software. Vendor market share for "
            "Tribal, Ellucian, Unit4, TechnologyOne. Recent contracts and "
            "wins/losses in the last 12 months."
        ),
    },
    {
        "topic": "swiss-edtech-funding",
        "region": "Switzerland",
        "query": (
            "Swiss EdTech investment activity in the last 12 months: "
            "VC rounds, public funding, M&A, accelerator cohorts. "
            "Names, amounts in CHF, dates, investors."
        ),
    },
    {
        "topic": "ai-in-he-spending",
        "region": "UK/EU",
        "query": (
            "How much are UK and EU universities spending on AI tools, "
            "automated marking, and AI-powered student support in 2025-2026? "
            "Notable procurement frameworks, pilot programmes, and budget "
            "lines. Cite sector reports and university press releases."
        ),
    },
    {
        "topic": "competitor-financials",
        "region": "Global",
        "query": (
            "Latest published financial results for: Tribal Group plc, "
            "Ellucian, Unit4, TechnologyOne, Anthology, Coursera, 2U, "
            "Chegg, Duolingo. Revenue, growth, profitability, and recent "
            "strategic announcements."
        ),
    },
]


def run_all() -> list[dict]:
    """Execute every research query and return list of cached/fresh results."""
    out: list[dict] = []
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(
                q["query"],
                topic=q["topic"],
                region=q["region"],
                system=SYSTEM_PROMPT,
                cache_hours=24 * 7,
            )
            out.append({
                "topic": q["topic"],
                "region": q["region"],
                "answer": res["answer"],
                "citations": res["citations"],
                "cached": res.get("cached", False),
            })
            LOGGER.info("Topic %s: %s", q["topic"], "cached" if res.get("cached") else "fresh")
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Topic %s failed: %s", q["topic"], exc)
    return out
