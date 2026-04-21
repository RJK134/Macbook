"""Scrape jobs.ac.uk — primary HE/EdTech job board in the UK.

Uses search RSS feeds keyed on job categories relevant to EdTech/HE management.
"""

from __future__ import annotations

from urllib.parse import urlencode

import feedparser

from ..common.logging_setup import get_logger

LOGGER = get_logger("jobs.jobs_ac_uk")

CATEGORIES = [
    "education-management",
    "academic-management",
    "it-management",
    "academic-administration",
    "student-services",
    "academic-services",
    "registry",
    "quality-assurance",
    "learning-and-teaching",
]

KEYWORDS = [
    "edtech", "student management", "academic management",
    "higher education", "head of digital", "director of digital",
    "head of education technology", "learning technology",
    "academic director", "head of student services",
]


def _feed_url_for_category(cat: str) -> str:
    return f"https://www.jobs.ac.uk/search/?categories={cat}&feed=rss"


def _feed_url_for_keyword(kw: str) -> str:
    qs = urlencode({"keywords": kw, "feed": "rss"})
    return f"https://www.jobs.ac.uk/search/?{qs}"


def scrape() -> list[dict]:
    out: list[dict] = []
    feeds = [_feed_url_for_category(c) for c in CATEGORIES] + [_feed_url_for_keyword(k) for k in KEYWORDS]
    for url in feeds:
        try:
            LOGGER.info("RSS %s", url)
            feed = feedparser.parse(url)
            for e in feed.entries:
                out.append({
                    "title": e.get("title", "")[:300],
                    "employer": e.get("author", "Unknown"),
                    "location": e.get("category", ""),
                    "country": "UK",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": (e.get("summary", "") or "")[:2000],
                    "source": "jobs.ac.uk",
                    "category": "he-management",
                    "raw_data": {"published": e.get("published", "")},
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("jobs.ac.uk feed %s failed: %s", url, exc)
    LOGGER.info("jobs.ac.uk: %d listings", len(out))
    return out
