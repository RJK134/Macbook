"""gov.uk publications feed filtered for SEND / alternative provision /
exclusion / inclusion content.
"""

from __future__ import annotations

import re
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

LOGGER = get_logger("sen.govuk")

FEEDS = [
    "https://www.gov.uk/government/publications.atom?topics%5B%5D=special-educational-needs",
    "https://www.gov.uk/search/all.atom?keywords=%22alternative+provision%22+%22inclusion%22&content_purpose_supergroup%5B%5D=research_and_statistics&order=updated-newest",
    "https://www.gov.uk/search/all.atom?keywords=%22pupil+exclusion%22+%22managed+move%22&content_purpose_supergroup%5B%5D=research_and_statistics&order=updated-newest",
]

REJECT_URL_RE = re.compile(
    r"/(employment-tribunal-decisions|traffic-commissioner-regulatory-decisions|"
    r"foreign-travel-advice|government/people/|"
    r"government/organisations/[^/]+/about/|"
    r"government/news/(new-appointments-|appointment-of-|appointments-to-))",
    re.I,
)

REQUIRE_RE = re.compile(
    r"\b(send|special educational needs|ehcp|ehc plan|alternative provision|"
    r"inclusion|excluded pupil|exclusion|managed move|"
    r"speech and language|autism|adhd|dyslexia|sensory|"
    r"send code of practice|disabled children|disability|"
    r"sen support|early years|specialist provision|"
    r"pupil premium|free school meals|attainment gap|behaviour support)\b",
    re.I,
)


def _classify_category(text: str) -> str:
    t = text.lower()
    for kw, cat in [
        ("ehcp", "ehcp"), ("ehc plan", "ehcp"),
        ("alternative provision", "alt-provision"),
        ("excluded", "exclusion"), ("exclusion", "exclusion"), ("managed move", "exclusion"),
        ("autism", "autism"),
        ("dyslexia", "dyslexia"),
        ("send code of practice", "send-code"),
        ("inclusion", "inclusion"),
        ("pupil premium", "pupil-premium"),
    ]:
        if kw in t:
            return cat
    return "send-general"


def scrape() -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("SEND feed failed: %s", exc)
            continue
        for e in feed.entries:
            link = e.get("link", "")
            title = e.get("title", "")
            summary = e.get("summary", "")[:1500]
            if not link or link in seen:
                continue
            if REJECT_URL_RE.search(link):
                continue
            text = f"{title} {summary}"
            if not REQUIRE_RE.search(text):
                continue
            seen.add(link)
            out.append({
                "resource_type": "policy",
                "title": title[:300],
                "source": "govuk-send",
                "url": link,
                "category": _classify_category(text),
                "description": summary,
                "region": "UK",
                "applies_to": "all",
                "published_date": _iso_date(e),
                "raw_data": {"feed": url, "published": e.get("published", "")},
            })
        write_raw_json("sen", f"govuk-{hash(url) & 0xffff:x}", [dict(e) for e in feed.entries])
    LOGGER.info("gov.uk SEND: %d signals", len(out))
    return out
