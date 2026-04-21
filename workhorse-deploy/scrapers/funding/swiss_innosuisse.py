"""Swiss innovation funding (Innosuisse, SNSF, Switzerland Global Enterprise)."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.swiss")

FEEDS = [
    "https://www.innosuisse.ch/inno/en/home.rss.xml",
    "https://www.snf.ch/en/news.rss",
    # Switzerland Global Enterprise news:
    "https://www.s-ge.com/en/global-news.rss",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                summary = (e.get("summary", "") or e.get("description", ""))
                out.append({
                    "title": e.get("title", "")[:300],
                    "funder": "Swiss Confederation",
                    "country": "CH",
                    "region": "Switzerland",
                    "currency": "CHF",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": summary[:2000],
                    "source": "swiss",
                    "category": "innovation-grant",
                    "raw_data": {"published": e.get("published", "")},
                })
            write_raw_json("funding", f"ch-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Swiss feed failed: %s", exc)
    LOGGER.info("Swiss: %d opportunities", len(out))
    return out
