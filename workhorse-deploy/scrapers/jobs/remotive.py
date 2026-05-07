"""Remotive API — remote EdTech/tech jobs. Free, no auth.

Rate limit: ~4 calls/day recommended.
"""

from __future__ import annotations

from ..common import http
from ..common.logging_setup import get_logger

LOGGER = get_logger("jobs.remotive")

API_URL = "https://remotive.com/api/remote-jobs"

SEARCHES = [
    {"category": "education", "search": ""},
    {"category": "product-management", "search": "education"},
    {"category": "", "search": "EdTech"},
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for search in SEARCHES:
        try:
            params = {}
            if search["category"]:
                params["category"] = search["category"]
            if search["search"]:
                params["search"] = search["search"]
            LOGGER.info("Remotive: %s", params)
            r = http.get(API_URL, params=params, timeout=30.0)
            data = r.json()
            for job in data.get("jobs", []):
                out.append({
                    "title": (job.get("title") or "")[:300],
                    "employer": job.get("company_name", "Unknown"),
                    "location": job.get("candidate_required_location", "Remote"),
                    "country": "Remote",
                    "url": job.get("url", ""),
                    "description": (job.get("description") or "")[:2000],
                    "source": "remotive",
                    "category": job.get("category", "education"),
                    "relevance_score": 3,
                    "raw_data": {"remotive_id": job.get("id"), "job_type": job.get("job_type")},
                })
        except Exception as exc:
            LOGGER.warning("Remotive failed: %s", exc)
    LOGGER.info("Remotive total: %d listings", len(out))
    return out
