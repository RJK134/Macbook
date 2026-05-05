"""Bank of England news + statistical releases via Perplexity (the BoE
RSS endpoint returns 500 consistently; Perplexity is the reliable path).
"""

from __future__ import annotations

import json
import re
from datetime import date

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("finance.boe")

QUERIES = [
    {
        "category": "monetary-policy",
        "prompt": (
            "List news, statistical releases, and Monetary Policy Committee "
            "announcements published on bankofengland.co.uk in the last 14 "
            "days. For each return: title, summary, publication_date (ISO), "
            "url. JSON array only."
        ),
    },
    {
        "category": "financial-stability",
        "prompt": (
            "List Bank of England Financial Policy Committee, Prudential "
            "Regulation Authority, and financial stability publications from "
            "the last 30 days. JSON array of {title, summary, publication_"
            "date, url}."
        ),
    },
]


def _parse_json(answer: str) -> list[dict]:
    answer = answer.strip()
    answer = re.sub(r"^```(?:json)?\s*", "", answer)
    answer = re.sub(r"\s*```$", "", answer)
    m = re.search(r"\[.*\]", answer, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return []


def scrape() -> list[dict]:
    out: list[dict] = []
    today = date.today().isoformat()
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 3)
        except Exception as exc:
            LOGGER.warning("BoE Perplexity %s failed: %s", q["category"], exc)
            continue
        for item in _parse_json(res.get("answer", "")):
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
