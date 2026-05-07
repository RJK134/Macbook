"""Direct RSS feeds for Shakespeare content (Globe, Folger, etc.)."""

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

LOGGER = get_logger("shakespeare.feeds")

FEEDS = [
    ("globe", "https://www.shakespearesglobe.com/feed/"),
    ("folger-blog", "https://www.folger.edu/blogs/shakespeare-and-beyond/feed/"),
]

PLAY_RE = re.compile(
    r"\b(Hamlet|Macbeth|Othello|King Lear|Romeo and Juliet|"
    r"Midsummer Night|Much Ado|Twelfth Night|As You Like It|"
    r"Tempest|Julius Caesar|Henry [IVX]+|Richard [IVX]+|"
    r"Merchant of Venice|Taming of the Shrew|Coriolanus|"
    r"Antony and Cleopatra|Winter's Tale|Measure for Measure|"
    r"Cymbeline|Pericles|Troilus and Cressida|Timon)\b",
    re.I,
)


def _detect_play(text: str) -> str | None:
    m = PLAY_RE.search(text)
    return m.group(1).title() if m else None


def scrape() -> list[dict]:
    out: list[dict] = []
    for source, url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("%s feed failed: %s", source, exc)
            continue
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            title = e.get("title", "")[:300]
            summary = e.get("summary", "")[:1500]
            text = f"{title} {summary}"
            out.append({
                "resource_type": "production" if source == "globe" else "article",
                "title": title,
                "source": source,
                "url": link,
                "play": _detect_play(text),
                "format": "traditional" if source == "globe" else "educational",
                "audience": "general",
                "description": summary,
                "engagement_score": 3,
                "published_date": _iso_date(e),
                "raw_data": {"source": source, "published": e.get("published", "")},
            })
        write_raw_json("shakespeare", source, [dict(e) for e in feed.entries])
    LOGGER.info("Shakespeare feeds: %d items", len(out))
    return out
