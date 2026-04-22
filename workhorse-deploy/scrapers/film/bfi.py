"""British Film Institute funding & talent development pages."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("film.bfi")

PAGES = [
    "https://www.bfi.org.uk/get-funding-support",
    "https://www.bfi.org.uk/get-funding-support/funding-development-distribution",
    "https://www.bfi.org.uk/get-funding-support/talent-development-skills",
]


def _parse(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for h in soup.select("h2, h3, h4"):
        text = h.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if not re.search(r"\b(fund|grant|scheme|develop|talent|opportun|award)\b", text, re.I):
            continue
        link = h.find_parent("a", href=True) or h.find("a", href=True)
        url = source_url
        if link and link.get("href"):
            href = link["href"]
            url = href if href.startswith("http") else f"https://www.bfi.org.uk{href}"
        out.append({
            "title": text[:300],
            "organisation": "BFI",
            "opp_type": "funding",
            "region": "UK",
            "url": url,
            "source": "bfi",
        })
    return out


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in PAGES:
        try:
            html = http.get(url).text
            write_raw_html("film", "bfi-" + url.rsplit("/", 1)[-1], html)
            out.extend(_parse(html, url))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("BFI %s failed: %s", url, exc)
    LOGGER.info("BFI: %d items", len(out))
    return out
