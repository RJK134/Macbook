"""Pull UK Companies House filings for a watchlist of EdTech / HE management vendors.

Requires COMPANIES_HOUSE_API_KEY in .env (free at developer.company-information.service.gov.uk).
If not configured the module returns an empty list with a warning.
"""

from __future__ import annotations

import httpx

from ..common.config import COMPANIES_HOUSE_API_KEY
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("financial.companies_house")

API_BASE = "https://api.company-information.service.gov.uk"

# Watchlist of UK-registered HE/EdTech vendors and adjacent firms.
WATCHLIST = [
    "Tribal Group",
    "Ellucian UK",
    "Unit4 Business Software",
    "TechnologyOne UK",
    "Aptem",
    "Studee",
    "Hubken",
    "FutureLearn",
    "SAGE Publishing",
    "BridgeU",
    "UCAS Media",
]


def _search(name: str) -> dict | None:
    if not COMPANIES_HOUSE_API_KEY:
        return None
    with httpx.Client(auth=(COMPANIES_HOUSE_API_KEY, ""), timeout=30.0) as c:
        r = c.get(
            f"{API_BASE}/search/companies",
            params={"q": name, "items_per_page": 1},
        )
        r.raise_for_status()
        return r.json()


def _filing_history(company_number: str) -> dict | None:
    if not COMPANIES_HOUSE_API_KEY:
        return None
    with httpx.Client(auth=(COMPANIES_HOUSE_API_KEY, ""), timeout=30.0) as c:
        r = c.get(
            f"{API_BASE}/company/{company_number}/filing-history",
            params={"items_per_page": 25},
        )
        r.raise_for_status()
        return r.json()


def scrape() -> list[dict]:
    if not COMPANIES_HOUSE_API_KEY:
        LOGGER.warning("COMPANIES_HOUSE_API_KEY not set — skipping Companies House")
        return []

    out: list[dict] = []
    for name in WATCHLIST:
        try:
            search = _search(name)
            if not search or not search.get("items"):
                continue
            company = search["items"][0]
            number = company.get("company_number")
            if not number:
                continue
            history = _filing_history(number)
            write_raw_json(
                "financial",
                f"ch-{name.replace(' ', '_')}",
                {"search": company, "history": history},
            )
            for filing in (history or {}).get("items", [])[:10]:
                out.append({
                    "query": f"{name} filing: {filing.get('description', '')}",
                    "topic": f"vendor-filing:{name}",
                    "answer": filing.get("description", ""),
                    "citations": [
                        f"https://find-and-update.company-information.service.gov.uk"
                        f"/company/{number}"
                    ],
                    "region": "UK",
                    "raw_data": {"company": company, "filing": filing},
                })
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Companies House %s failed: %s", name, exc)
    LOGGER.info("Companies House: %d filings", len(out))
    return out
