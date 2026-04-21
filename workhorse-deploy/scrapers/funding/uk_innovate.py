"""UK Innovate / UKRI funding opportunities."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.uk_innovate")

FEEDS = [
    "https://www.ukri.org/opportunity/feed/",
    "https://www.ukri.org/feed/",
    "https://www.gov.uk/search/all.atom?keywords=innovate+UK+grant+funding+competition&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=startup+grant+small+business+funding&order=updated-newest",
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
                    "funder": "UK Government / UKRI",
                    "country": "UK",
                    "region": "UK",
                    "currency": "GBP",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": summary[:2000],
                    "source": "ukri",
                    "category": "innovation-grant",
                    "raw_data": {"published": e.get("published", "")},
                })
            write_raw_json("funding", f"ukri-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("UKRI feed failed: %s", exc)
    LOGGER.info("UK Innovate: %d opportunities", len(out))
    return out
