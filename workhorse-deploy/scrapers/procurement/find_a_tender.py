"""UK Find a Tender Service via OCDS public API (high-value tenders > £139k).

Uses the same project-scope classifier as contracts_finder so non-education
sectors (NHS, social care, defence, etc.) don't leak through.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json
from .contracts_finder import _classify

LOGGER = get_logger("procurement.find_a_tender")

API_URL = "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"


def _ocds_to_row(release: dict) -> dict | None:
    tender = release.get("tender") or {}
    title = tender.get("title") or ""
    description = tender.get("description") or ""
    buyer = (release.get("buyer") or {}).get("name", "")
    category, score = _classify(f"{title} {description} {buyer}")
    if score < 3:
        return None
    period = tender.get("tenderPeriod") or {}
    value = tender.get("value") or {}
    notice_id = release.get("ocid") or ""
    return {
        "notice_id": notice_id,
        "title": title[:300],
        "buyer": buyer[:200],
        "buyer_type": "uk-public-sector",
        "description": description[:4000],
        "category": category,
        "value_min": value.get("amount"),
        "value_max": value.get("amount"),
        "currency": (value.get("currency") or "GBP")[:3],
        "publication_date": (release.get("date") or "")[:10] or None,
        "deadline_date": (period.get("endDate") or "")[:10] or None,
        "status": "open",
        "source": "find-a-tender",
        "url": f"https://www.find-tender.service.gov.uk/Notice/{notice_id.split('-')[-1]}",
        "country": "UK",
        "relevance_score": score,
        "raw_data": release,
    }


def scrape() -> list[dict]:
    out: list[dict] = []
    since = (date.today() - timedelta(days=14)).isoformat()
    params = {"updatedFrom": f"{since}T00:00:00"}
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(API_URL, params=params, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        LOGGER.warning("Find a Tender fetch failed: %s", exc)
        return out
    releases = data.get("releases") or []
    if not releases:
        for pkg in data.get("releasePackages", []) or []:
            releases.extend(pkg.get("releases", []))
    for rel in releases:
        try:
            row = _ocds_to_row(rel)
            if row:
                out.append(row)
        except Exception as exc:
            LOGGER.debug("skip release: %s", exc)
    write_raw_json("procurement", "find-a-tender", releases[:200])
    LOGGER.info("Find a Tender: %d/%d notices kept", len(out), len(releases))
    return out
