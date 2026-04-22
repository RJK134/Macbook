"""Scrape Discover Uni (gov.uk official) course search.

Discover Uni publishes a JSON-API-backed search at:
  https://discoveruni.gov.uk/search/?show=Course&query=...
The HTML page embeds JSON via __NUXT__/script blocks. We page through
the public search by subject keywords to build a wide course inventory.
"""

import json
import re
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("courses.discoveruni")

BASE = "https://discoveruni.gov.uk/search/"

# Subject area seeds — kept broad so the inventory grows over weeks.
SEEDS = [
    "computer science", "business", "psychology", "law", "engineering",
    "education", "nursing", "medicine", "biology", "mathematics",
    "history", "english literature", "economics", "art", "music",
    "physics", "chemistry", "geography", "politics", "sociology",
    "philosophy", "media", "film", "drama", "architecture",
    "criminology", "marketing", "accounting", "finance", "data science",
    "artificial intelligence", "cybersecurity", "design", "languages",
    "international relations", "social work", "physiotherapy", "dentistry",
    "veterinary", "agriculture", "environmental science", "hospitality",
    "tourism", "sports science", "journalism", "fashion", "photography",
]


def _fetch_page(query: str, page: int = 1) -> str:
    qs = urlencode({"show": "Course", "query": query, "pageNumber": page})
    url = f"{BASE}?{qs}"
    LOGGER.info("GET %s", url)
    r = http.get(url)
    return r.text


def _extract_courses(html: str) -> list[dict]:
    """Parse the embedded course list from the search results HTML."""
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []

    # Each course appears as an article/li with a link to /course/
    for a in soup.select('a[href*="/course/"]'):
        title = a.get_text(strip=True)
        href = a.get("href")
        if not title or not href or len(title) < 5:
            continue
        full_url = href if href.startswith("http") else f"https://discoveruni.gov.uk{href}"
        # Try to find the provider in surrounding context
        provider = ""
        parent = a.find_parent(["article", "li", "div"])
        if parent:
            prov = parent.find(string=re.compile(r"university|college", re.I))
            if prov:
                provider = prov.strip()
        out.append({
            "title": title,
            "url": full_url,
            "provider": provider or "Unknown",
            "source": "discoveruni",
        })
    return out


def scrape() -> list[dict]:
    """Walk through SEEDS, page once, and return de-duplicated courses."""
    seen: set[str] = set()
    all_courses: list[dict] = []
    for query in SEEDS:
        try:
            html = _fetch_page(query, page=1)
            write_raw_html("courses", f"discoveruni-{query.replace(' ', '_')}", html)
            for c in _extract_courses(html):
                key = c["url"]
                if key in seen:
                    continue
                seen.add(key)
                c["subject_area"] = query
                all_courses.append(c)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Discover Uni query %r failed: %s", query, exc)
    LOGGER.info("Discover Uni: %d unique courses", len(all_courses))
    return all_courses


if __name__ == "__main__":
    rows = scrape()
    print(f"Got {len(rows)} courses")
    for r in rows[:5]:
        print(r)
