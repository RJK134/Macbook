"""Scrape Times Higher Education Unijobs board for HE management posts."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger

LOGGER = get_logger("jobs.the")

FEEDS = [
    "https://www.timeshighereducation.com/unijobs/en-gb/listings/rss/?discipline=administrative",
    "https://www.timeshighereducation.com/unijobs/en-gb/listings/rss/?discipline=it-computing",
    "https://www.timeshighereducation.com/unijobs/en-gb/listings/rss/?discipline=education",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        try:
            LOGGER.info("RSS %s", url)
            feed = feedparser.parse(url)
            for e in feed.entries:
                out.append({
                    "title": e.get("title", "")[:300],
                    "employer": e.get("author", "Unknown"),
                    "country": "UK",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": (e.get("summary", "") or "")[:2000],
                    "source": "times_higher_ed",
                    "category": "he-management",
                    "raw_data": {"published": e.get("published", "")},
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("THE feed failed: %s", exc)
    LOGGER.info("Times Higher Ed: %d listings", len(out))
    return out
