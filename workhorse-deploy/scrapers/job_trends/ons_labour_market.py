"""Pull labour market overview signals from the ONS RSS/Atom feeds.

ONS publishes monthly labour market statistics. We pull recent releases
and extract any occupation/sector mentions for trend tracking.
"""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("trends.ons")

FEEDS = [
    "https://www.ons.gov.uk/employmentandlabourmarket/peopleinwork/rss",
    "https://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/rss",
    "https://www.ons.gov.uk/businessindustryandtrade/changestobusiness/rss",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
            entries = [
                {
                    "title": e.get("title", ""),
                    "summary": e.get("summary", "")[:1000],
                    "link": e.get("link", ""),
                    "published": e.get("published", ""),
                }
                for e in feed.entries
            ]
            write_raw_json("job_trends", f"ons-{url.split('/')[-2]}", entries)
            for e in entries:
                out.append({
                    "occupation": e["title"][:200],
                    "sector": "labour-market",
                    "trend": "stable",
                    "source": "ons",
                    "source_url": e["link"],
                    "raw_data": e,
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("ONS feed %s failed: %s", url, exc)
    LOGGER.info("ONS: %d trend signals", len(out))
    return out
