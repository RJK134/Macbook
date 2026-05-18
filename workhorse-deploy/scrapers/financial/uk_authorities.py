"""HMRC, FCA, DfE and ONS official feeds — finance bulletins relevant
to the project portfolio.

Per-source filters apply. The DfE feed is education-policy by definition
so every entry is kept. HMRC, FCA and ONS publish full firehoses (HMRC
manuals, FCA enforcement actions on banking, ONS deaths/trade/household-
costs) — those are filtered to education / HE / student-finance /
charitable-trust / academy-trust / research-funding contexts only.
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

LOGGER = get_logger("finance.uk_authorities")

FEEDS = [
    ("hmrc", "tax", "https://www.gov.uk/government/organisations/hm-revenue-customs.atom"),
    ("fca", "regulatory", "https://www.fca.org.uk/news/rss.xml"),
    ("dfe", "education-policy", "https://www.gov.uk/government/organisations/department-for-education.atom"),
    ("ons", "statistics", "https://www.gov.uk/government/organisations/office-for-national-statistics.atom"),
]

# Per-source keep regex. A row only survives if it matches its feed's
# regex. DfE feed is unfiltered (kept None) — every entry is in scope.
KEEP_RE: dict[str, re.Pattern[str] | None] = {
    "dfe": None,  # keep all
    "hmrc": re.compile(
        r"\b(academy|academies|multi[- ]academy trust|mat\b|"
        r"charity|charitable|charit(?:ies|y) tax|"
        r"gift aid|payroll giving|"
        r"student loan|student finance|"
        r"research and development tax|r&d tax|"
        r"theatre tax relief|museums and galleries tax relief|"
        r"creative industries tax|orchestra tax relief|"
        r"employer national insurance.*(academy|school)|"
        r"apprenticeship levy|apprenticeship funding|"
        r"national minimum wage.*education|"
        r"pension scheme.*(teacher|academy|school))\b",
        re.I,
    ),
    "fca": re.compile(
        r"\b(student lender|student finance|education(al)? lend|"
        r"academy trust|university endowment|"
        r"edtech|education technology|learning platform|"
        r"consumer credit.*(student|tuition)|"
        r"buy now pay later.*(course|tuition)|"
        r"fund tokenisation.*education|"
        r"impact fund|charity fund|charitable trust)\b",
        re.I,
    ),
    "ons": re.compile(
        r"\b(education|higher education|further education|"
        r"school|schools|college|university|universities|"
        r"student|pupil|enrolment|attainment|"
        r"earnings by qualification|graduate (outcomes|earnings)|"
        r"apprenticeship|skills|training|"
        r"young people not in education|neet\b|"
        r"household.*(education|tuition)|"
        r"public sector finance.*education)\b",
        re.I,
    ),
}

# Hard reject — DfE feed still emits ministerial / org-page noise.
REJECT_RE = re.compile(
    r"\b(minister of state|ministerial appointment|"
    r"cabinet reshuffle|organisation chart|"
    r"corporate report.*annual|annual accounts|"
    r"procurement at dfe|tender notice published)\b",
    re.I,
)


def _is_relevant(source: str, title: str, summary: str) -> bool:
    text = f"{title} {summary}"
    if REJECT_RE.search(text):
        return False
    keep = KEEP_RE.get(source)
    if keep is None:
        return True
    return bool(keep.search(text))


def scrape() -> list[dict]:
    out: list[dict] = []
    for source, category, url in FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:
            LOGGER.warning("%s feed failed: %s", source, exc)
            continue
        kept = 0
        total = 0
        for e in feed.entries:
            total += 1
            link = e.get("link", "")
            if not link:
                continue
            title = e.get("title", "")
            summary = (e.get("summary", "") or "")
            if not _is_relevant(source, title, summary):
                continue
            kept += 1
            out.append({
                "source": source,
                "category": category,
                "title": title[:300],
                "url": link,
                "summary": summary[:2000],
                "published_date": _iso_date(e),
                "raw_data": {"feed": url, "published": e.get("published", "")},
            })
        write_raw_json("finance_bulletins", source, [dict(e) for e in feed.entries])
        LOGGER.info("%s: %d/%d entries kept", source, kept, total)
    LOGGER.info("UK authorities: %d bulletins (post-filter)", len(out))
    return out
