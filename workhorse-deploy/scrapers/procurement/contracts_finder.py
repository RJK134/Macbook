"""UK Contracts Finder via the OCDS public API.

Filters notices to project-relevant scope: schools / HE / FE / SEND /
EdTech / curriculum / Shakespeare / film. Broad terms like
"safeguarding" or "workforce development" are excluded unless paired
with an educational modifier — they leak NHS, social-care, and council
HR tenders that aren't in scope.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx

from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("procurement.contracts_finder")

API_URL = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"

# Strong, unambiguously-educational terms. A match here is enough on its own
# (REJECT_RE still runs first, so "NHS education" / "armed forces education"
# don't slip through).
STRONG_RE = re.compile(
    r"\b(education|edtech|e-learning|online learning|learning platform|"
    r"curriculum|further education|higher education|"
    r"school|schools|college|university|sixth form|academy trust|"
    r"special educational needs|send|ehcp|alternative provision|"
    r"excluded pupil|sen support|pupil referral unit|pru|"
    r"t levels?|gcse|a.level|key stage|ks[1-5]\b|"
    r"shakespeare|literacy|numeracy|"
    r"tutor|tutoring|tuition|socratic|"
    r"teacher training|teaching assistant|cpd for teachers?|"
    r"course provision|examination|exam board|qualification framework|"
    r"jisc)\b",
    re.I,
)

# Weak terms that need to pair with an educational modifier to count.
WEAK_RE = re.compile(
    r"\b(careers|apprenticeship|skills bootcamp|skills training|"
    r"safeguarding|inclusion|youth|young people|workforce development|"
    r"adult learning|education and training|training provider)\b",
    re.I,
)
EDU_MODIFIER_RE = re.compile(
    r"\b(school|college|university|pupil|student|learner|"
    r"education|curriculum|teacher|gcse|a.level|sen|send|ehcp|"
    r"alternative provision|further education|higher education|"
    r"key stage|t levels?)\b",
    re.I,
)

# Hard rejects — sectors that surface against the weak terms but are
# never in scope for the project portfolio.
REJECT_RE = re.compile(
    r"\b(nhs|hospital|hospice|gp practice|primary care|mental health trust|"
    r"social care|adult social care|residential care|care home|"
    r"highway|road maintenance|gritting|street lighting|"
    r"refuse collection|waste management|recycling contract|"
    r"defence|ministry of defence|royal navy|raf\b|army\b|"
    r"prison|hmp|probation|youth justice|"
    r"housing repair|fire and rescue)\b",
    re.I,
)

# School / college-adjacent operational contracts — they match "school"
# or "college" via STRONG_RE but are facilities / transport / marketing
# work, not curriculum, EdTech, or SEN-delivery scope.
FACILITIES_RE = re.compile(
    r"\b(passenger assistant|school transport|home to school transport|"
    r"education transport|transport routes|"
    r"taxi service|minibus|coach hire|"
    r"fire safety|fire alarm|fire door|sprinkler|"
    r"refurbishment|extension works|capital works|building works|"
    r"sixth form block|school capacity|"
    r"led lighting|lighting installation|"
    r"paint and decorating|painting and decorating|decorating supplies|"
    r"roof replacement|window replacement|cladding|demolition|"
    r"catering services|kitchen refurb|grounds maintenance|"
    r"cleaning services|janitorial|caretaking|"
    r"marketing and advertising|advertising services|"
    r"insurance services|legal services|audit services|"
    r"energy supply|electricity supply|gas supply|water supply|"
    r"dark fibre|fibre installation|broadband supply|telecoms infra|"
    r"bikeability|cycling proficiency|"
    r"boiler replacement|boiler installation|"
    r"bus services|coach services|"
    r"arp adaptations|building adaptations|access adaptations)\b",
    re.I,
)
# Strong "delivery" signal — if present, the row stays even if it also
# mentions facilities-style words (e.g. "EdTech platform refurbishment
# for SEN classrooms" is still in scope).
DELIVERY_RE = re.compile(
    r"\b(edtech|e-learning|learning platform|curriculum|"
    r"tutor|tutoring|tuition|teaching|cpd for teachers?|"
    r"send|ehcp|alternative provision|sen support|"
    r"gcse|a.level|key stage|exam board|"
    r"socratic|shakespeare|literacy programme|numeracy programme)\b",
    re.I,
)


def _classify(text: str) -> tuple[str, int]:
    """Return (category, relevance_score 1-5). Score 1 = drop."""
    t = text.lower()
    if REJECT_RE.search(t):
        return ("rejected", 1)
    if FACILITIES_RE.search(t) and not DELIVERY_RE.search(t):
        return ("rejected", 1)
    if STRONG_RE.search(t):
        if re.search(r"\b(send|sen support|ehcp|alternative provision|"
                     r"excluded pupil|pupil referral)\b", t):
            return ("send-alt-provision", 5)
        if re.search(r"\bedtech|learning platform|online learning|e-learning\b", t):
            return ("edtech-platform", 5)
        if re.search(r"\b(curriculum|gcse|a.level|key stage|exam board)\b", t):
            return ("curriculum-assessment", 4)
        if re.search(r"\b(tutor|tutoring|socratic|teacher training)\b", t):
            return ("teaching-services", 4)
        if re.search(r"\b(shakespeare|literacy|numeracy)\b", t):
            return ("subject-specific", 4)
        return ("education-services", 3)
    if WEAK_RE.search(t) and EDU_MODIFIER_RE.search(t):
        return ("training-adjacent", 3)
    return ("rejected", 1)


def _ocds_to_row(release: dict) -> dict | None:
    tender = release.get("tender") or {}
    title = tender.get("title") or release.get("title") or ""
    description = tender.get("description") or ""
    buyer = (release.get("buyer") or {}).get("name", "")
    text = f"{title} {description} {buyer}"
    category, score = _classify(text)
    if score < 3:
        return None
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
        "category": category,
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
        "relevance_score": score,
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
