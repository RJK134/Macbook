"""Scrape WhatUni course search.

WhatUni uses a search page at:
  https://www.whatuni.com/degree-courses/search?q=<subject>&pageno=<n>
Each result card has the course title, university, location, study mode.
"""

import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("courses.whatuni")

BASE = "https://www.whatuni.com/degree-courses/search"

SEEDS = [
    "computer science", "business", "engineering", "psychology", "law",
    "medicine", "education", "data science", "artificial intelligence",
    "cybersecurity", "design", "biology", "chemistry", "physics",
    "media studies", "marketing", "finance", "accounting", "history",
    "english", "mathematics", "philosophy", "sociology", "politics",
    "international relations", "criminology", "music", "drama", "art",
    "film", "fashion", "architecture", "nursing", "physiotherapy",
    "social work", "geography", "economics", "languages", "journalism",
]


def _fetch(query: str, page: int = 1) -> str:
    qs = urlencode({"q": query, "pageno": page})
    url = f"{BASE}?{qs}"
    LOGGER.info("GET %s", url)
    return http.get(url).text


def _parse(html: str, query: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for card in soup.select("article, div.crs_dis, li.search-result"):
        title_el = card.find(["h2", "h3"])
        link_el = card.find("a", href=True)
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        href = link_el["href"]
        url = href if href.startswith("http") else f"https://www.whatuni.com{href}"
        provider = ""
        prov_el = card.find(class_=re.compile("uni|provider|institution", re.I))
        if prov_el:
            provider = prov_el.get_text(strip=True)
        location = ""
        loc_el = card.find(class_=re.compile("location|address|city", re.I))
        if loc_el:
            location = loc_el.get_text(strip=True)
        if title and len(title) > 5:
            rows.append({
                "title": title,
                "url": url,
                "provider": provider or "Unknown",
                "location_city": location,
                "subject_area": query,
                "source": "whatuni",
            })
    return rows


def scrape() -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for query in SEEDS:
        try:
            html = _fetch(query)
            write_raw_html("courses", f"whatuni-{query.replace(' ', '_')}", html)
            for c in _parse(html, query):
                if c["url"] in seen:
                    continue
                seen.add(c["url"])
                out.append(c)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("WhatUni query %r failed: %s", query, exc)
    LOGGER.info("WhatUni: %d unique courses", len(out))
    return out
