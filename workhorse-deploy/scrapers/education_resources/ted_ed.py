"""TED-Ed YouTube channel feed — short animated lessons useful for
Socratic prompts in Maieus / Maieus2.

The legacy implementation pulled ted.com/feeds/talks.rss, which is the
*main* TED Talks feed (politics, business, etc.) and was leaking
off-topic talks into the education report. This module now reads
TED-Ed's actual YouTube channel feed and filters to items whose title
or summary plausibly relates to a school subject.
"""

from __future__ import annotations

import re
import time

import feedparser

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("edu.ted_ed")

# TED-Ed's YouTube channel (UCsooa4yRKGN_zEE8iknghZA)
FEEDS = [
    "https://www.youtube.com/feeds/videos.xml?channel_id=UCsooa4yRKGN_zEE8iknghZA",
]

# Heuristic subject classifier — keep this conservative; "general" is
# what gets dropped at report time.
SUBJECT_MAP: list[tuple[str, re.Pattern[str]]] = [
    ("Mathematics", re.compile(r"\b(math|maths|algebra|geometry|probability|calculus|equation|prime|number theory)\b", re.I)),
    ("Physics",     re.compile(r"\b(physics|gravity|quantum|relativity|particle|atom|electromagnet|thermodynamic|velocity)\b", re.I)),
    ("Chemistry",   re.compile(r"\b(chemistry|molecule|reaction|periodic|acid|alkali|isotope|chemical bond)\b", re.I)),
    ("Biology",     re.compile(r"\b(biology|cell|dna|gene|evolution|species|ecosystem|microb|virus|bacteri|neuron|organism|enzyme)\b", re.I)),
    ("History",     re.compile(r"\b(history|empire|ancient|medieval|revolution|war|dynasty|civili[sz]ation|archaeolog)\b", re.I)),
    ("English Literature", re.compile(r"\b(shakespeare|poem|poetry|sonnet|novel|literature|metaphor|narrative|prose)\b", re.I)),
    ("Geography",   re.compile(r"\b(geography|tectonic|volcano|climate|river|continent|ocean|earthquake|biome)\b", re.I)),
    ("Philosophy",  re.compile(r"\b(philosoph|ethics|metaphysic|consciousness|logic puzzle|moral dilemma|stoic|existential)\b", re.I)),
    ("Religious Studies", re.compile(r"\b(religion|buddhis|hindu|islam|christian|judais|theolog|sacred text)\b", re.I)),
    ("Politics",    re.compile(r"\b(democracy|election|parliament|constitution|government structure|geopolitic)\b", re.I)),
]

EXCLUDE_RE = re.compile(
    r"\b(tedx talk|tedx event|live event recap|sponsored|trailer|"
    r"behind the scenes|q&a session)\b",
    re.I,
)


def _classify_subject(text: str) -> str | None:
    for subject, pattern in SUBJECT_MAP:
        if pattern.search(text):
            return subject
    return None


def _iso_date(entry) -> str | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return time.strftime("%Y-%m-%d", parsed)
        except (TypeError, ValueError):
            return None
    return None


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("TED-Ed feed failed: %s", exc)
            continue
        for e in feed.entries:
            link = e.get("link", "")
            if not link:
                continue
            title = e.get("title", "")[:300]
            summary = e.get("summary", "")[:1000]
            text = f"{title} {summary}"
            if EXCLUDE_RE.search(text):
                continue
            subject = _classify_subject(text)
            if not subject:
                # If we can't tie it to a school subject, don't report it.
                continue
            out.append({
                "exam_board": None,
                "level": "ks3-ks4-a-level",
                "subject": subject,
                "topic": title,
                "resource_type": "video",
                "title": title,
                "source": "ted-ed",
                "url": link,
                "description": summary,
                "raw_data": {"published": e.get("published", "")},
            })
        write_raw_json("education_resources", "ted-ed", [dict(e) for e in feed.entries])
    LOGGER.info("TED-Ed: %d videos kept", len(out))
    return out
