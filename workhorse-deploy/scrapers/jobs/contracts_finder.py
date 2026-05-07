"""UK Contracts Finder OCDS JSON API.

Free, no authentication for public search. Returns Open Contracting
Data Standard (OCDS) JSON. Covers UK public sector tenders >£12k.

Filtered for education + technology CPV codes.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("jobs.contracts_finder")

API_BASE = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

KEYWORDS = [
    "education technology",
    "EdTech",
    "student management system",
    "learning management",
    "higher education IT",
    "digital learning",
    "course management",
]


def scrape() -> list[dict]:
    out: list[dict] = []
    since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    seen_urls: set[str] = set()
    for kw in KEYWORDS:
        try:
            params = {
                "publishedFrom": since,
                "stages": "tender",
                "limit": 50,
            }
            url = f"{API_BASE}?publishedFrom={since}&stages=tender&limit=50"
            LOGGER.info("Contracts Finder: %s", kw)
            r = http.get(url, timeout=30.0)
            data = r.json()
            releases = data.get("releases", [])
            for release in releases:
                tender = release.get("tender", {})
                title = tender.get("title", "")
                description = tender.get("description", "")
                text = (title + " " + description).lower()
                if kw.lower() not in text:
                    continue
                tender_url = release.get("id", "")
                if tender_url in seen_urls:
                    continue
                seen_urls.add(tender_url)
                buyer = release.get("buyer", {})
                value = tender.get("value", {})
                deadline = tender.get("tenderPeriod", {}).get("endDate")
                closing_date = None
                if deadline:
                    try:
                        closing_date = datetime.fromisoformat(deadline.replace("Z", "+00:00")).date()
                    except ValueError:
                        pass
                out.append({
                    "title": title[:300],
                    "employer": buyer.get("name", "UK Public Sector"),
                    "location": "UK",
                    "country": "UK",
                    "salary_min": value.get("amount"),
                    "currency": (value.get("currency") or "GBP")[:3],
                    "url": f"https://www.contractsfinder.service.gov.uk/Notice/{release.get('id', '')}",
                    "closing_date": closing_date,
                    "description": description[:4000],
                    "source": "contracts_finder",
                    "category": "public-tender",
                    "relevance_score": 1,
                    "raw_data": {"keyword": kw, "ocds_id": release.get("id")},
                })
            LOGGER.info("Contracts Finder '%s': %d matching", kw, len(releases))
        except Exception as exc:
            LOGGER.warning("Contracts Finder '%s' failed: %s", kw, exc)
    write_raw_json("jobs", "contracts-finder", {"total": len(out)})
    LOGGER.info("Contracts Finder total: %d tenders", len(out))
    return out
