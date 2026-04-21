"""EU Horizon Europe and Funding & Tenders opportunities."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.eu_horizon")

FEEDS = [
    # EU Funding & Tenders Portal does not have a great RSS, but the news
    # section publishes call updates here:
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/opportunities/competitive-calls-cs.atom",
    # Horizon news from CORDIS:
    "https://cordis.europa.eu/news/rcn/news.atom?language=en",
    # European Innovation Council:
    "https://eic.ec.europa.eu/news.xml",
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
                    "funder": "European Commission",
                    "country": "EU",
                    "region": "EU",
                    "currency": "EUR",
                    "url": e.get("link", "") or e.get("guid", ""),
                    "description": summary[:2000],
                    "source": "eu",
                    "category": "horizon",
                    "raw_data": {"published": e.get("published", "")},
                })
            write_raw_json("funding", f"eu-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("EU feed failed: %s", exc)
    LOGGER.info("EU Horizon: %d opportunities", len(out))
    return out
