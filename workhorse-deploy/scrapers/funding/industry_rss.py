"""EdTech industry RSS feeds — EdSurge, EU-Startups, Sifted, TechCrunch.

These are news feeds, not grant calls. We tag rows category='industry-news'
so the funding section can exclude them. They surface as supporting
context in the AI Research / investment views instead.

Strict EdTech filter: a row only survives if the title or summary
contains an explicit education / learning-platform / curriculum signal.
Generic biotech / quantum / cyber funding rounds are dropped.
"""

from __future__ import annotations

import re

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

# Must reference education explicitly. Plain "funding"/"raises"/"series A"
# matched too much biotech / SaaS / quantum / cyber news.
EDU_REQUIRED_RE = re.compile(
    r"\b(edtech|edu-?tech|education technology|"
    r"k-?12|higher education|university|college|"
    r"learning platform|online learning|e-learning|"
    r"curriculum|tutoring|tutor app|"
    r"student|teacher|school|"
    r"instructional design|learning experience|"
    r"micro-credential|skills bootcamp|apprenticeship platform)\b",
    re.I,
)


def scrape() -> list[dict]:
    out: list[dict] = []
    for url, source_name in FEEDS:
        try:
            LOGGER.info("RSS %s", url)
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                summary = e.get("summary", "") or ""
                if not EDU_REQUIRED_RE.search(f"{title} {summary}"):
                    continue
                out.append({
                    "title": title[:300],
                    "funder": "Various",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": summary[:2000],
                    "source": source_name,
                    "category": "industry-news",
                    "relevance_score": 4,
                    "raw_data": {"published": e.get("published", "")},
                })
            write_raw_json("funding", f"rss-{source_name}", {"items": len(feed.entries)})
        except Exception as exc:
            LOGGER.warning("RSS %s failed: %s", source_name, exc)
    LOGGER.info("Industry RSS: %d EdTech-relevant items", len(out))
    return out
