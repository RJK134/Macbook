"""UK Contracts Finder via the OCDS public API.

Filters notices by education / training / SEN / EdTech / curriculum keywords
relevant to Future Horizons Education and the wider product portfolio.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("procurement.contracts_finder")

API_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

KEEP_RE = re.compile(
    r"\b(education|training|curriculum|edtech|e-learning|online learning|"
    r"school|college|university|further education|higher education|"
    r"special educational needs|sen\b|ehcp|alternative provision|"
    r"excluded pupils|inclusion|sen support|"
    r"careers|apprenticeship|skills|t levels?|"
    r"shakespeare|literacy|numeracy|gcse|a.level|key stage|"
    r"socratic|tutor|tutoring|learning platform|"
    r"safeguarding|youth|young people|adult learning|"
    r"workforce development|teacher training|cpd)\b",
    re.I,
)


def _ocds_to_row(release: dict) -> dict | None:
    tender = release.get("tender") or {}
    title = tender.get("title") or release.get("title") or ""
    description = tender.get("description") or ""
    text = f"{title} {description}"
    if not KEEP_RE.search(text):
        return None
    buyer = (release.get("buyer") or {}).get("name", "")
    period = tender.get("tenderPeriod") or {}
    publication = release.get("date")
    deadline = period.get("endDate")
    value = tender.get("value") or {}
    amount = value.get("amount")
    currency = (value.get("currency") or "GBP")[:3]
    items = tender.get("items") or []
    cpv_codes = []
    for it in items:
        cls = it.get("classification") or {}
        if cls.get("scheme", "").upper().startswith("CPV"):
            code = cls.get("id")
            if code:
                cpv_codes.append(code)
    notice_id = release.get("ocid") or release.get("id") or ""
    documents = tender.get("documents") or []
    url = ""
    for d in documents:
        if d.get("documentType") in ("tenderNotice", "biddingDocuments") and d.get("url"):
            url = d["url"]
            break
    if not url:
        url = f"https://www.contractsfinder.service.gov.uk/Notice/{notice_id}"
    return {
        "notice_id": notice_id,
        "title": title[:300],
        "buyer": buyer[:200],
        "buyer_type": "uk-public-sector",
        "description": description[:4000],
        "category": "education-services",
        "cpv_codes": cpv_codes or None,
        "value_min": amount,
        "value_max": amount,
        "currency": currency,
        "publication_date": (publication or "")[:10] or None,
        "deadline_date": (deadline or "")[:10] or None,
        "status": "open",
        "source": "contracts-finder",
        "url": url,
        "country": "UK",
        "raw_data": release,
    }


def scrape() -> list[dict]:
    out: list[dict] = []
    since = (date.today() - timedelta(days=14)).isoformat()
    params = {
        "publishedFrom": f"{since}T00:00:00",
    }
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            r = client.get(API_URL, params=params, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        LOGGER.warning("Contracts Finder fetch failed: %s", exc)
        return out
    releases = data.get("releases") or data.get("results") or []
    for rel in releases:
        try:
            row = _ocds_to_row(rel)
            if row:
                out.append(row)
        except Exception as exc:
            LOGGER.debug("skip release: %s", exc)
            continue
    write_raw_json("procurement", "contracts-finder", releases)
    LOGGER.info("Contracts Finder: %d/%d notices kept", len(out), len(releases))
    return out
