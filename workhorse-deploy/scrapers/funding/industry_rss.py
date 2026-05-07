"""EdTech industry RSS feeds — EdSurge, EU-Startups, Sifted.

Three free RSS feeds providing EdTech funding news that the broad
gov.uk Atom feeds miss.
"""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.industry_rss")

FEEDS = [
    ("https://www.edsurge.com/articles_rss", "edsurge"),
    ("https://www.eu-startups.com/feed", "eu-startups"),
    ("https://sifted.eu/feed", "sifted"),
    ("https://techcrunch.com/tag/funding/feed", "techcrunch"),
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url, source_name in FEEDS:
        try:
            LOGGER.info("RSS %s", url)
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                text = (title + " " + (e.get("summary", "") or "")).lower()
                if not any(kw in text for kw in (
                    "edtech", "education", "learning", "university",
                    "funding", "raise", "series", "seed", "grant",
                    "accelerator", "incubat", "student",
                )):
                    continue
                out.append({
                    "title": title[:300],
                    "funder": "Various",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": (e.get("summary", "") or "")[:2000],
                    "source": source_name,
                    "category": "industry-news",
                    "raw_data": {"published": e.get("published", "")},
                })
            write_raw_json("funding", f"rss-{source_name}", {"items": len(feed.entries)})
        except Exception as exc:
            LOGGER.warning("RSS %s failed: %s", source_name, exc)
    LOGGER.info("Industry RSS: %d EdTech-relevant items", len(out))
    return out
