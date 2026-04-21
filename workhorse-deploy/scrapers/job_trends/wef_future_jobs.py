"""Future of Jobs / WEF feeds and reports.

WEF publishes the Future of Jobs Report annually plus ongoing articles.
We poll their RSS for relevant content and attribute as 'wef'.
"""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("trends.wef")

FEEDS = [
    "https://www.weforum.org/agenda/topics/future-of-work.rss",
    "https://www.weforum.org/agenda/topics/jobs-and-the-future-of-work.rss",
    "https://www.weforum.org/agenda/topics/skills-training.rss",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                out.append({
                    "occupation": e.get("title", "")[:200],
                    "sector": "future-of-work",
                    "trend": "growing",
                    "source": "wef",
                    "source_url": e.get("link", ""),
                    "raw_data": {
                        "summary": e.get("summary", "")[:1000],
                        "published": e.get("published", ""),
                    },
                })
            write_raw_json("job_trends", f"wef-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("WEF feed failed: %s", exc)
    LOGGER.info("WEF: %d signals", len(out))
    return out
