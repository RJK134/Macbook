"""Pull skills & jobs intelligence from gov.uk Atom feeds.

Filters out non-employment content (property listings, planning applications)
that the generic gov.uk search returns.
"""

from __future__ import annotations

import re

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("trends.gov_uk")

FEEDS = [
    "https://www.gov.uk/government/publications.atom?topics%5B%5D=employment&topics%5B%5D=further-education-skills",
    "https://www.gov.uk/search/all.atom?keywords=%22skills+shortage%22+%22labour+market%22&content_purpose_supergroup%5B%5D=research_and_statistics&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=%22future+skills%22+%22workforce%22&content_purpose_supergroup%5B%5D=research_and_statistics&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=%22apprenticeship%22+%22technical+education%22&content_purpose_supergroup%5B%5D=policy_and_engagement&order=updated-newest",
]

REJECT_RE = re.compile(
    r"(planning\s+application|listed\s+building|licence|premises|"
    r"Flat \d|property|insolvency|Court |Street |Road |Lane |Avenue |"
    r"House,|MAN/\d|certificate of)",
    re.I,
)

REQUIRE_RE = re.compile(
    r"(skill|employ|labour|workforce|apprentice|occupation|job|career|"
    r"qualification|training|education|wage|salary|hiring|recruitment|"
    r"graduate|STEM|digital|AI|automation|sector)",
    re.I,
)


def scrape() -> list[dict]:
    out: list[dict] = []
    seen_urls: set[str] = set()
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                link = e.get("link", "")
                summary = e.get("summary", "")[:1000]
                text = f"{title} {summary}"

                if REJECT_RE.search(text):
                    continue
                if not REQUIRE_RE.search(text):
                    continue
                if link in seen_urls:
                    continue
                seen_urls.add(link)

                out.append({
                    "occupation": title[:200],
                    "sector": "skills-policy",
                    "trend": "growing",
                    "source": "gov.uk",
                    "source_url": link,
                    "raw_data": {
                        "summary": summary,
                        "published": e.get("published", ""),
                    },
                })
            write_raw_json("job_trends", f"gov-uk-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Gov.uk feed failed: %s", exc)
    LOGGER.info("Gov.uk skills: %d signals (filtered)", len(out))
    return out
