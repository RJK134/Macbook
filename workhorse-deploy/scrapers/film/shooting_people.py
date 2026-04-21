"""Shooting People — UK independent film community RSS."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger

LOGGER = get_logger("film.shooting_people")

# Shooting People publishes daily bulletins; this is the public news feed.
FEEDS = [
    "https://shootingpeople.org/blog/feed",
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
                    "organisation": "Shooting People",
                    "opp_type": "community",
                    "region": "UK",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": (e.get("summary", "") or "")[:2000],
                    "source": "shooting_people",
                    "raw_data": {"published": e.get("published", "")},
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Shooting People feed failed: %s", exc)
    LOGGER.info("Shooting People: %d items", len(out))
    return out
