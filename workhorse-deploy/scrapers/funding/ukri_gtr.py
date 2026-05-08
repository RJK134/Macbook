"""UKRI Gateway to Research REST API.

170k+ funded UK research projects since 2006 including Innovate UK
EdTech grants. Free, no authentication, OGL licensed.

API docs: https://gtr.ukri.org/resources/gtrapi.html
"""

from __future__ import annotations

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("funding.ukri_gtr")

API_BASE = "https://gtr.ukri.org/gtr/api"

SEARCHES = [
    {"term": "education technology", "funder": "Innovate UK"},
    {"term": "learning technology", "funder": "Innovate UK"},
    {"term": "student management", "funder": "Innovate UK"},
    {"term": "EdTech", "funder": "Innovate UK"},
    {"term": "higher education digital", "funder": "ESRC"},
    {"term": "course platform", "funder": "Innovate UK"},
]


def _search_projects(term: str, page: int = 1, page_size: int = 100) -> list[dict]:
    params = {
        "q": term,
        "p": page,
        "s": page_size,
        "f": "pro.gr",
    }
    url = f"{API_BASE}/projects"
    LOGGER.info("GtR search: %s (page %d)", term, page)
    r = http.get(url, params=params, timeout=30.0)
    try:
        data = r.json()
    except Exception:
        return []
    projects = data.get("project", [])
    if isinstance(projects, dict):
        projects = [projects]
    return projects


def scrape() -> list[dict]:
    out: list[dict] = []
    seen_ids: set[str] = set()
    for search in SEARCHES:
        try:
            projects = _search_projects(search["term"])
            for p in projects:
                pid = p.get("id", "")
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                title = (p.get("title") or "").strip()
                if not title:
                    continue
                abstract = (p.get("abstractText") or "")[:2000]
                fund = p.get("fund", {})
                actual_funder = (
                    fund.get("funder", {}).get("name")
                    or search.get("funder", "UKRI")
                )
                amount = fund.get("valuePounds", {}).get("amount")
                start = fund.get("start")
                end = fund.get("end")
                url = f"https://gtr.ukri.org/projects?ref={pid}" if pid else None
                out.append({
                    "title": title[:300],
                    "funder": actual_funder,
                    "country": "UK",
                    "region": "UK",
                    "currency": "GBP",
                    "amount_max": float(amount) if amount else None,
                    "url": url,
                    "description": abstract,
                    "source": "ukri_gtr",
                    "category": "innovation-grant",
                    "raw_data": {
                        "project_id": pid,
                        "start": start,
                        "end": end,
                        "search_term": search["term"],
                    },
                })
            LOGGER.info("GtR '%s': %d projects", search["term"], len(projects))
        except Exception as exc:
            LOGGER.warning("GtR search '%s' failed: %s", search["term"], exc)
    write_raw_json("funding", "ukri-gtr-summary", {"total": len(out)})
    LOGGER.info("UKRI GtR total: %d unique projects", len(out))
    return out
