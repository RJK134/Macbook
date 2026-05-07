"""Ofqual Register of Regulated Qualifications API.

Free REST API, no authentication required. Covers 44,787+ regulated
qualifications (A-levels, BTECs, GCSEs, apprenticeships). OGL licensed.

Useful for mapping entry requirements to regulated qualification details.
"""

from __future__ import annotations

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("courses.ofqual")

API_BASE = "https://register-api.ofqual.gov.uk/api"

SEARCHES = [
    {"title": "computer science", "qualificationLevels": "Level 3"},
    {"title": "business", "qualificationLevels": "Level 3"},
    {"title": "engineering", "qualificationLevels": "Level 3"},
    {"title": "data science", "qualificationLevels": "Level 4"},
    {"title": "education", "qualificationLevels": "Level 4"},
    {"title": "health", "qualificationLevels": "Level 3"},
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for params in SEARCHES:
        try:
            LOGGER.info("Ofqual search: %s", params)
            r = http.get(f"{API_BASE}/qualifications", params=params)
            data = r.json()
            results = data if isinstance(data, list) else data.get("results", [])
            for q in results[:50]:
                out.append({
                    "title": q.get("title", "")[:300],
                    "provider": q.get("organisationName", "Unknown"),
                    "qualification": q.get("type", ""),
                    "source": "ofqual",
                    "url": f"{API_BASE}/Qualifications/{q.get('qualificationNumber', '')}",
                    "raw_data": q,
                })
            LOGGER.info("Ofqual %s: %d results", params["title"], len(results))
        except Exception as exc:
            LOGGER.warning("Ofqual search %s failed: %s", params, exc)
    write_raw_json("courses", "ofqual-summary", {"total": len(out)})
    LOGGER.info("Ofqual total: %d qualifications", len(out))
    return out
