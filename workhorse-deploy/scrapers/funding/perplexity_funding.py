"""Use Perplexity Sonar to deep-search current funding opportunities.

Adds value beyond RSS by searching the wider web for active calls,
deadlines, and amounts that are not in the standard feeds.
"""

from __future__ import annotations

import json

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("funding.perplexity")

QUERIES = [
    {
        "query": (
            "List the top 10 currently open UK government and Innovate UK "
            "funding opportunities for EdTech, education technology, or "
            "higher-education management software. For each, give: title, "
            "funder, deadline (DD-MM-YYYY), amount in GBP, eligibility, URL."
        ),
        "topic": "uk-edtech-funding",
        "region": "UK",
    },
    {
        "query": (
            "List the top 10 open EU Horizon Europe and EIC funding calls "
            "relevant to digital education, AI in higher education, or "
            "academic management platforms. For each: title, funder, deadline, "
            "amount in EUR, eligibility, URL."
        ),
        "topic": "eu-horizon-edtech",
        "region": "EU",
    },
    {
        "query": (
            "List the top 10 currently open Swiss funding opportunities "
            "(Innosuisse, SNSF, cantonal innovation funds) for EdTech, "
            "academic software, or higher-education enterprise tools. "
            "For each: title, funder, deadline, amount in CHF, eligibility, URL."
        ),
        "topic": "swiss-edtech-funding",
        "region": "Switzerland",
    },
    {
        "query": (
            "What new business support programmes, grants, or accelerators "
            "have launched in the last 30 days for UK, EU, or Swiss founders "
            "in the EdTech, AI-in-education, or academic-management space? "
            "Give: name, funder, deadline, amount, URL."
        ),
        "topic": "new-funding-30d",
        "region": "UK/EU/CH",
    },
]


SYSTEM_PROMPT = (
    "You are a funding intelligence analyst. Be precise. "
    "Only list real, currently-open opportunities with verifiable URLs. "
    "Format each entry as a JSON object with keys: title, funder, deadline, "
    "amount, currency, eligibility, url, description. "
    "Wrap the list in a JSON array. Do not invent URLs."
)


def _to_funding_rows(answer: str, citations: list[str], topic: str) -> list[dict]:
    """Try to extract structured rows from the Perplexity answer."""
    rows: list[dict] = []
    # Find a JSON array in the response if present.
    text = answer.strip()
    start = text.find("[")
    end = text.rfind("]")
    items: list[dict] = []
    if start != -1 and end != -1 and end > start:
        try:
            items = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            items = []
    if not items:
        # Fallback: store the whole answer as a single record per citation.
        for url in citations[:10]:
            rows.append({
                "title": f"Perplexity research: {topic}",
                "funder": "Various",
                "url": url,
                "description": text[:1500],
                "source": "perplexity",
                "category": topic,
                "currency": "GBP",
                "raw_data": {"answer": text, "citations": citations},
            })
        return rows
    for it in items:
        if not isinstance(it, dict):
            continue
        rows.append({
            "title": (it.get("title") or "Unnamed opportunity")[:300],
            "funder": it.get("funder"),
            "country": None,
            "region": it.get("region") or topic.split("-")[0].upper(),
            "amount_min": it.get("amount_min"),
            "amount_max": it.get("amount_max") or it.get("amount"),
            "currency": (it.get("currency") or "GBP")[:3],
            "deadline": it.get("deadline"),
            "eligibility": it.get("eligibility"),
            "description": it.get("description"),
            "url": it.get("url"),
            "source": "perplexity",
            "category": topic,
            "raw_data": it,
        })
    return rows


def scrape() -> list[dict]:
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
            rows = _to_funding_rows(res["answer"], res["citations"], q["topic"])
            LOGGER.info("Perplexity %s -> %d rows (cached=%s)", q["topic"], len(rows), res.get("cached"))
            out.extend(rows)
        except Exception as exc:  # noqa: BLE001
            LOGGER.exception("Perplexity query %s failed: %s", q["topic"], exc)
    return out
