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

# URL paths that publish content matching our keywords but are NOT
# labour-market intelligence (tribunal cases, staff bios, traffic
# decisions, travel advice, generic guidance, board appointments).
REJECT_URL_RE = re.compile(
    r"/(employment-tribunal-decisions|traffic-commissioner-regulatory-decisions|"
    r"foreign-travel-advice|research-for-development-outputs|"
    r"cma-cases|drug-device-alerts|food-alert)/|"
    r"/government/people/|"
    r"/government/organisations/[^/]+/about/|"
    r"/government/news/(new-appointments-|appointment-of-|appointments-to-)",
    re.I,
)

REJECT_RE = re.compile(
    r"^(Mr|Mrs|Ms|Miss|Dr)\s+\w+(\s+\w+)?\s+v\s+|"
    r"\bv\s+\w[^:]*Ltd:?\s*\d{3,}/\d{4}|"
    r"(planning\s+application|listed\s+building|premises|certificate of|"
    r"travel advice|country policy|river conditions|veterinary|"
    r"appointments?\s+(to|made to)|our governance|procurement at|"
    r"\bUKSIA\b|bird gathering|insolvency service board|"
    r"DBS regional|jet fuel|trade mission|holiday(s)? from disruption)",
    re.I,
)

# Title or summary must contain at least one strong labour-market signal.
REQUIRE_RE = re.compile(
    r"\b(skill\s*(shortage|gap|need|projection|priority|white paper|policy|strategy)|"
    r"labour\s+market|workforce|apprentice|occupation|career path|jobs?\s+plan|"
    r"future skills|priority skills|education and skills|post-?16|"
    r"employment\s+(rate|trend|statistics|patterns|outcomes|data|projection)|"
    r"low pay|t\s*levels?|"
    r"vocational|further education|jobcentre|technical education|"
    r"sector skills|industry analysis|economic activity|"
    r"hiring|recruitment trend|wage growth|salary survey|"
    r"qualification framework|graduate outcomes|"
    r"AI labour|AI skills|cyber security skills)\b",
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

                if REJECT_URL_RE.search(link):
                    continue
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
