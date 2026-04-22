"""Scrape UCAS course search.

UCAS uses a JSON API at:
  https://digital.ucas.com/coursedisplay/courses/search?searchTerm=...
But it's behind anti-bot measures. Falls back to the public search HTML at:
  https://www.ucas.com/explore/search/courses?query=<term>
"""

import json
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("courses.ucas")

BASE = "https://www.ucas.com/explore/search/courses"

SEEDS = [
    "computer science", "business management", "law", "psychology",
    "engineering", "education", "nursing", "medicine", "biology",
    "data science", "artificial intelligence", "cyber security",
    "mathematics", "physics", "chemistry", "history", "english",
    "economics", "marketing", "accounting", "criminology",
    "international relations", "film studies", "design",
]


def _fetch(query: str) -> str:
    qs = urlencode({"query": query})
    url = f"{BASE}?{qs}"
    LOGGER.info("GET %s", url)
    return http.get(url).text


def _parse(html: str, query: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for a in soup.select('a[href*="/course"], a[href*="/courses/"]'):
        title = a.get_text(strip=True)
        href = a.get("href")
        if not title or len(title) < 5 or not href:
            continue
        url = href if href.startswith("http") else f"https://www.ucas.com{href}"
        provider = ""
        parent = a.find_parent(["article", "li", "div"])
        if parent:
            prov_el = parent.find(class_=lambda c: c and ("provider" in c.lower() or "uni" in c.lower()))
            if prov_el:
                provider = prov_el.get_text(strip=True)
        rows.append({
            "title": title,
            "url": url,
            "provider": provider or "Unknown",
            "subject_area": query,
            "source": "ucas",
        })
    return rows


def scrape() -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for query in SEEDS:
        try:
            html = _fetch(query)
            write_raw_html("courses", f"ucas-{query.replace(' ', '_')}", html)
            for c in _parse(html, query):
                if c["url"] in seen:
                    continue
                seen.add(c["url"])
                out.append(c)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("UCAS query %r failed: %s", query, exc)
    LOGGER.info("UCAS: %d unique courses", len(out))
    return out
