"""Remotive API — remote EdTech/tech jobs. Free, no auth.

Rate limit: ~4 calls/day recommended.

Remotive does not have an actual 'education' category and its `search`
keyword is a loose substring match, so we post-filter every row against
a strict EdTech / HE / learning-platform keyword set. Rows without a
real edu signal are discarded rather than stored with a low score.
"""

from __future__ import annotations

import re

from ..common import http
from ..common.logging_setup import get_logger

LOGGER = get_logger("jobs.remotive")

API_URL = "https://remotive.com/api/remote-jobs"

SEARCHES = [
    {"category": "education", "search": ""},
    {"category": "product-management", "search": "education"},
    {"category": "", "search": "EdTech"},
]

# Must hit one of these in title or description to be kept. Generic
# software / customer-support / marketing roles that mention "education"
# only in a benefits blurb don't count.
EDU_KEEP_RE = re.compile(
    r"\b(edtech|education technology|learning platform|"
    r"online learning|e-learning|online education|"
    r"k-?12|higher education|university|college|"
    r"curriculum|instructional design|learning experience|"
    r"learning designer|learning engineer|education product|"
    r"learning content|edu tech|edu-?tech|lms|"
    r"tutoring|tutor (platform|product)|student success)\b",
    re.I,
)


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
                title = (job.get("title") or "")[:300]
                description = (job.get("description") or "")[:2000]
                if not EDU_KEEP_RE.search(f"{title} {description}"):
                    continue
                out.append({
                    "title": title,
                    "employer": job.get("company_name", "Unknown"),
                    "location": job.get("candidate_required_location", "Remote"),
                    "country": "Remote",
                    "url": job.get("url", ""),
                    "description": description,
                    "source": "remotive",
                    "category": job.get("category", "education"),
                    "relevance_score": 3,
                    "raw_data": {"remotive_id": job.get("id"), "job_type": job.get("job_type")},
                })
        except Exception as exc:
            LOGGER.warning("Remotive failed: %s", exc)
    LOGGER.info("Remotive: %d EdTech-relevant listings", len(out))
    return out
