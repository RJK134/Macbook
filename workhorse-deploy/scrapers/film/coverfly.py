"""Coverfly — script competition listings via their public site.

Best-effort scraper of the contests listings page; if the structure
changes it falls back to surfacing whatever links it finds.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("film.coverfly")

PAGE = "https://writers.coverfly.com/competitions"


def scrape() -> list[dict]:
    out: list[dict] = []
    try:
        html = http.get(PAGE).text
        write_raw_html("film", "coverfly-competitions", html)
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select('a[href*="/competition"], a[href*="/contest"]'):
            title = a.get_text(strip=True)
            if not title or len(title) < 5:
                continue
            href = a.get("href")
            url = href if href.startswith("http") else f"https://writers.coverfly.com{href}"
            out.append({
                "title": title[:300],
                "organisation": "Coverfly",
                "opp_type": "competition",
                "region": "International",
                "url": url,
                "source": "coverfly",
            })
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("Coverfly failed: %s", exc)
    LOGGER.info("Coverfly: %d competitions", len(out))
    return out
