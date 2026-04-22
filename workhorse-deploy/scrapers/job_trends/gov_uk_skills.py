"""Pull skills & jobs intelligence from gov.uk Atom feeds."""

from __future__ import annotations

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("trends.gov_uk")

FEEDS = [
    "https://www.gov.uk/search/all.atom?keywords=skills+shortage+labour+market&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=future+jobs+emerging+skills&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=apprenticeship+technical+education&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=AI+automation+workforce&order=updated-newest",
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
                    "sector": "skills-policy",
                    "trend": "growing",
                    "source": "gov.uk",
                    "source_url": e.get("link", ""),
                    "raw_data": {
                        "summary": e.get("summary", "")[:1000],
                        "published": e.get("published", ""),
                    },
                })
            write_raw_json("job_trends", f"gov-uk-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Gov.uk feed failed: %s", exc)
    LOGGER.info("Gov.uk skills: %d signals", len(out))
    return out
