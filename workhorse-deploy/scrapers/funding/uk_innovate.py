"""UK Innovate / UKRI funding opportunities.

The two gov.uk Atom feeds that used to live here returned the whole
"innovate UK grant funding competition" / "startup grant" search
firehose, which leaks DVSA notices, foreign-policy press releases,
driving-instructor articles, etc. into the funding section. They are
removed: this module now reads only the actual UKRI opportunity feeds
and post-filters on edu-relevant keywords so the funding section stays
focused on grants the operator can actually apply to.
"""

from __future__ import annotations

import re

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.uk_innovate")

FEEDS = [
    "https://www.ukri.org/opportunity/feed/",
    "https://www.ukri.org/feed/",
]

# Anything written about education, learning, EdTech, HE/FE, SEN,
# Innovate UK grants for digital / creative / curriculum, or
# competition-style open calls.
KEEP_RE = re.compile(
    r"\b(education|edtech|e-learning|online learning|"
    r"curriculum|higher education|further education|"
    r"learning platform|student|teacher|school|college|university|"
    r"send|sen support|alternative provision|"
    r"skills bootcamp|t levels?|"
    r"innovate uk.*(competition|grant|funding|call)|"
    r"open call|competition open|"
    r"creative industries|cultural sector|"
    r"research and innovation|knowledge exchange)\b",
    re.I,
)
# Hard reject — gov.uk feed items that mention "funding" / "grant" in
# unrelated contexts (transport, defence, foreign policy, etc.).
REJECT_RE = re.compile(
    r"\b(travel advice|sanctions|cyber defen[cs]e|counter uas|"
    r"driving (instructor|test|licence)|dvsa|hgv|"
    r"emissions trading|carbon trading|"
    r"national minimum wage|employment law|"
    r"flood (defence|warning)|highway|"
    r"defence procurement|royal navy|raf\b|army\b|"
    r"prison|hmp|probation|"
    r"refugee|asylum|home office|"
    r"minister of state|ministerial appointment|"
    r"procurement at dfe|dfe procurement|"
    r"organisation chart|cabinet reshuffle)\b",
    re.I,
)


def _is_relevant(title: str, summary: str) -> bool:
    text = f"{title} {summary}"
    if REJECT_RE.search(text):
        return False
    return bool(KEEP_RE.search(text))


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        LOGGER.info("RSS %s", url)
        try:
            feed = feedparser.parse(url)
            for e in feed.entries:
                title = e.get("title", "")
                summary = (e.get("summary", "") or e.get("description", ""))
                if not _is_relevant(title, summary):
                    continue
                out.append({
                    "title": title[:300],
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
    LOGGER.info("UK Innovate: %d edu-relevant opportunities", len(out))
    return out
