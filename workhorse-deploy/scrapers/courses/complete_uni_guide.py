"""Scrape The Complete University Guide subject league tables.

CUG publishes ranking pages per subject at:
  https://www.thecompleteuniversityguide.co.uk/league-tables/rankings/<subject>
Each page lists universities offering courses in that subject with links.
"""

from urllib.parse import urlencode

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("courses.cug")

BASE = "https://www.thecompleteuniversityguide.co.uk/league-tables/rankings"

SUBJECTS = [
    "computer-science", "business-management-studies", "law", "psychology",
    "education", "engineering", "medicine", "biological-sciences",
    "mathematics", "physics", "chemistry", "history", "english",
    "economics", "politics", "sociology", "philosophy", "media-studies",
    "drama-dance-cinematics", "art-design", "architecture",
    "nursing", "physiotherapy", "criminology", "marketing",
    "accounting-finance", "geography", "social-work",
]


def _fetch(subject: str) -> str:
    url = f"{BASE}/{subject}"
    LOGGER.info("GET %s", url)
    return http.get(url).text


def _parse(html: str, subject: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    rows: list[dict] = []
    for tr in soup.select("table tr"):
        cells = tr.find_all(["td", "th"])
        if len(cells) < 2:
            continue
        link = tr.find("a", href=True)
        if not link:
            continue
        provider = link.get_text(strip=True)
        if not provider or len(provider) < 3:
            continue
        href = link["href"]
        url = href if href.startswith("http") else f"https://www.thecompleteuniversityguide.co.uk{href}"
        rows.append({
            "title": f"{subject.replace('-', ' ').title()} at {provider}",
            "provider": provider,
            "subject_area": subject.replace("-", " "),
            "url": url,
            "source": "cug",
        })
    return rows


def scrape() -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for subject in SUBJECTS:
        try:
            html = _fetch(subject)
            write_raw_html("courses", f"cug-{subject}", html)
            for c in _parse(html, subject):
                key = (c["provider"], c["subject_area"])
                if key in seen:
                    continue
                seen.add(key)
                out.append(c)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("CUG subject %r failed: %s", subject, exc)
    LOGGER.info("CUG: %d university-subject pairs", len(out))
    return out
