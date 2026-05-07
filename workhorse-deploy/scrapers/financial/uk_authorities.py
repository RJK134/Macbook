"""HMRC, FCA, and BoE official feeds — tax bulletins, regulatory updates,
monetary policy news. Stored in finance_bulletins.
"""

from __future__ import annotations

import time

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json


def _iso_date(entry) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return time.strftime("%Y-%m-%d", parsed)
        except (TypeError, ValueError):
            return None
    return None

LOGGER = get_logger("finance.uk_authorities")

FEEDS = [
    ("hmrc", "tax", "https://www.gov.uk/government/organisations/hm-revenue-customs.atom"),
    ("fca", "regulatory", "https://www.fca.org.uk/news/rss.xml"),
    ("dfe", "education-policy", "https://www.gov.uk/government/organisations/department-for-education.atom"),
    ("ons", "statistics", "https://www.gov.uk/government/organisations/office-for-national-statistics.atom"),
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for source, category, url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("%s feed failed: %s", source, exc)
            continue
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            out.append({
                "source": source,
                "category": category,
                "title": e.get("title", "")[:300],
                "url": link,
                "summary": (e.get("summary", "") or "")[:2000],
                "published_date": _iso_date(e),
                "raw_data": {"feed": url, "published": e.get("published", "")},
            })
        write_raw_json("finance_bulletins", source, [dict(e) for e in feed.entries])
    LOGGER.info("UK authorities: %d bulletins", len(out))
    return out
