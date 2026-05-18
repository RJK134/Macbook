"""Bank of England news + statistical releases via Perplexity (the BoE
RSS endpoint returns 500 consistently; Perplexity is the reliable path).
"""

from __future__ import annotations

from datetime import date

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("finance.boe")

QUERIES = [
    {
        "category": "monetary-policy",
        "prompt": (
            "List ONLY the headline Monetary Policy Committee decisions, "
            "Monetary Policy Reports, and rate-change announcements "
            "published on bankofengland.co.uk in the last 14 days. EXCLUDE "
            "weekly statistical releases, market-operations Q-reports, "
            "and minutes of working groups — those are operational noise "
            "for our consultancy context. For each kept item return: "
            "title, summary, publication_date (ISO), url. JSON array only."
        ),
    },
]


def scrape() -> list[dict]:
    out: list[dict] = []
    today = date.today().isoformat()
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 3)
        except Exception as exc:
            LOGGER.warning("BoE Perplexity %s failed: %s", q["category"], exc)
            continue
        for item in llm_json.parse_json_array(res.get("answer", "")):
            url = item.get("url")
            if not url or "bankofengland.co.uk" not in url:
                continue
            out.append({
                "source": "boe",
                "category": q["category"],
                "title": (item.get("title") or "")[:300],
                "url": url,
                "summary": (item.get("summary") or "")[:2000],
                "published_date": (item.get("publication_date") or today)[:10],
                "raw_data": {"category": q["category"], "item": item},
            })
    LOGGER.info("BoE: %d bulletins", len(out))
    return out
