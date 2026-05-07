"""TED-Ed lessons RSS — short animated educational videos useful for
Socratic prompts in Maieus / Maieus2.
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

LOGGER = get_logger("edu.ted_ed")

FEEDS = [
    "https://www.ted.com/feeds/talks.rss",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("TED-Ed feed failed: %s", exc)
            continue
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            title = e.get("title", "")[:300]
            summary = e.get("summary", "")[:1000]
            out.append({
                "exam_board": None,
                "level": "ks3-ks4-a-level",
                "subject": "general",
                "topic": title,
                "resource_type": "video",
                "title": title,
                "source": "ted-ed",
                "url": link,
                "description": summary,
                "raw_data": {"published": e.get("published", "")},
            })
        write_raw_json("education_resources", "ted-ed", [dict(e) for e in feed.entries])
    LOGGER.info("TED-Ed: %d videos", len(out))
    return out
