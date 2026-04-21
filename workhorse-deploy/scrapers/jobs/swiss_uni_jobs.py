"""Swiss university and EdTech job feeds (jobs.ch, swissuniversities)."""

from __future__ import annotations

from urllib.parse import urlencode

import feedparser

from ..common.logging_setup import get_logger

LOGGER = get_logger("jobs.swiss")

# jobs.ch supports RSS via the "/feed" endpoint per query.
def _jobs_ch(query: str) -> str:
    qs = urlencode({"query": query, "publication_date": "5"})  # last 5 days
    return f"https://www.jobs.ch/en/vacancies/feed/?{qs}"


SWISSUNI_FEED = "https://www.swissuniversities.ch/en/news/feed.xml"

QUERIES = [
    "EdTech", "education technology", "higher education", "academic management",
    "university administration", "student services", "learning technology",
    "head of digital education",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for q in QUERIES:
        url = _jobs_ch(q)
        try:
            LOGGER.info("RSS %s", url)
            feed = feedparser.parse(url)
            for e in feed.entries:
                out.append({
                    "title": e.get("title", "")[:300],
                    "employer": e.get("author", "Unknown"),
                    "country": "CH",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": (e.get("summary", "") or "")[:2000],
                    "source": "jobs.ch",
                    "category": "edtech",
                    "raw_data": {"query": q, "published": e.get("published", "")},
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("jobs.ch query %r failed: %s", q, exc)

    try:
        feed = feedparser.parse(SWISSUNI_FEED)
        for e in feed.entries:
            out.append({
                "title": e.get("title", "")[:300],
                "employer": "Swiss Universities",
                "country": "CH",
                "url": e.get("link", "") or e.get("guid", ""),
                "description": (e.get("summary", "") or "")[:2000],
                "source": "swissuniversities",
                "category": "he-management",
                "raw_data": {"published": e.get("published", "")},
            })
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("swissuniversities failed: %s", exc)

    LOGGER.info("Swiss jobs: %d listings", len(out))
    return out
