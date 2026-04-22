"""BBC Writersroom — opportunities, calls for scripts, schemes."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("film.bbc")

PAGES = [
    "https://www.bbc.co.uk/writersroom/opportunities",
    "https://www.bbc.co.uk/writersroom/news",
]


def _parse(html: str, source_url: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    out: list[dict] = []
    for h in soup.select("h2, h3, h4"):
        text = h.get_text(strip=True)
        if not text or len(text) < 5:
            continue
        if not re.search(r"\b(submit|opportun|call|scheme|comp|writer|script|fund|talent)\b", text, re.I):
            continue
        link = h.find("a", href=True) or h.find_parent("a", href=True)
        url = source_url
        if link and link.get("href"):
            href = link["href"]
            url = href if href.startswith("http") else f"https://www.bbc.co.uk{href}"
        out.append({
            "title": text[:300],
            "organisation": "BBC Writersroom",
            "opp_type": "submission",
            "region": "UK",
            "url": url,
            "source": "bbc_writersroom",
            "raw_data": {"page": source_url},
        })
    return out


def scrape() -> list[dict]:
    out: list[dict] = []
    for url in PAGES:
        try:
            html = http.get(url).text
            write_raw_html("film", "bbc-" + url.rsplit("/", 1)[-1], html)
            out.extend(_parse(html, url))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("BBC Writersroom %s failed: %s", url, exc)
    LOGGER.info("BBC Writersroom: %d items", len(out))
    return out
