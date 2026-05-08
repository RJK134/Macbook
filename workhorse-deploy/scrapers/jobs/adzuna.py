"""Adzuna API — UK/CH/EU job aggregation with salary data.

Free tier: 2,500 calls/month. Requires APP_ID + APP_KEY.
Register at https://developer.adzuna.com
"""

from __future__ import annotations

from ..common.config import ADZUNA_APP_ID, ADZUNA_APP_KEY
from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("jobs.adzuna")

API_BASE = "https://api.adzuna.com/v1/api/jobs"

SEARCHES = [
    {"country": "gb", "what": "EdTech higher education manager", "category": "education-jobs"},
    {"country": "gb", "what": "learning technology director", "category": "education-jobs"},
    {"country": "gb", "what": "student management system", "category": "it-jobs"},
    {"country": "ch", "what": "education technology"},
    {"country": "ch", "what": "university digital manager"},
]


def scrape() -> list[dict]:
    if not ADZUNA_APP_ID or not ADZUNA_APP_KEY:
        LOGGER.warning("ADZUNA_APP_ID/ADZUNA_APP_KEY not configured — skipping")
        return []
    out: list[dict] = []
    for search in SEARCHES:
        try:
            country = search["country"]
            params = {
                "app_id": ADZUNA_APP_ID,
                "app_key": ADZUNA_APP_KEY,
                "what": search["what"],
                "results_per_page": 50,
            }
            if search.get("category"):
                params["category"] = search["category"]
            url = f"{API_BASE}/{country}/search/1"
            LOGGER.info("Adzuna %s: %s", country.upper(), search["what"])
            r = http.get(url, params=params, timeout=30.0)
            data = r.json()
            for job in data.get("results", []):
                out.append({
                    "title": (job.get("title") or "")[:300],
                    "employer": job.get("company", {}).get("display_name", "Unknown"),
                    "location": job.get("location", {}).get("display_name", ""),
                    "country": country.upper(),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "currency": "CHF" if country == "ch" else "GBP",
                    "url": job.get("redirect_url", ""),
                    "description": (job.get("description") or "")[:2000],
                    "source": "adzuna",
                    "category": search.get("category", "edtech"),
                    "relevance_score": 2,
                    "raw_data": {"adzuna_id": job.get("id"), "created": job.get("created")},
                })
            LOGGER.info("Adzuna %s '%s': %d results", country.upper(), search["what"], len(data.get("results", [])))
        except Exception as exc:
            LOGGER.warning("Adzuna search failed: %s", exc)
    write_raw_json("jobs", "adzuna-summary", {"total": len(out)})
    LOGGER.info("Adzuna total: %d listings", len(out))
    return out
