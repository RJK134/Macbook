"""Perplexity-based discovery of education-sector tenders and procurement
opportunities relevant to Future Horizons Education and our other products.

Catches what the OCDS APIs miss — frameworks, indicative notices, devolved
nation portals, and supplier-side opportunities.
"""

from __future__ import annotations

import re
from datetime import date

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("procurement.perplexity")

QUERIES = [
    {
        "category": "education-frameworks",
        "prompt": (
            "List public sector procurement tenders, framework agreements, or "
            "Dynamic Purchasing Systems published in the UK in the last 14 "
            "days that are relevant to: education services, alternative "
            "provision, special educational needs (SEN), tutoring, online "
            "learning platforms, EdTech, careers guidance, teacher training, "
            "or curriculum development. Include DfE, ESFA, Ofsted, devolved "
            "administrations, and major local authorities. For each: title, "
            "buyer, estimated value, deadline (ISO date), and direct URL. "
            "Return JSON array only."
        ),
    },
    {
        "category": "training-providers",
        "prompt": (
            "List UK procurement opportunities published in the last 14 days "
            "where independent training providers, charities, or alternative "
            "provision settings can bid — covering Skills Bootcamps, AEB, "
            "Multiply, post-16 outreach, or apprenticeship delivery. For each "
            "include title, buyer, value, deadline (ISO date), URL. JSON only."
        ),
    },
    {
        "category": "edtech-software",
        "prompt": (
            "List UK or EU public sector tenders or framework opportunities "
            "in the last 14 days for education software, learning platforms, "
            "AI tutoring, assessment tools, or pupil-tracking systems. JSON "
            "array of {title, buyer, value, deadline, url}."
        ),
    },
]


def scrape() -> list[dict]:
    out: list[dict] = []
    today_iso = date.today().isoformat()
    for q in QUERIES:
        try:
            res = perplexity.ask(q["prompt"], model="sonar-pro")
            answer = res.get("answer", "")
            citations = res.get("citations", []) or []
        except Exception as exc:
            LOGGER.warning("Perplexity %s failed: %s", q["category"], exc)
            continue
        for item in llm_json.parse_json_array(answer):
            url = item.get("url") or (citations[0] if citations else None)
            if not url:
                continue
            value = item.get("value") or item.get("estimated_value")
            value_num: float | None = None
            if isinstance(value, (int, float)):
                value_num = float(value)
            elif isinstance(value, str):
                m = re.search(r"[\d,]+(?:\.\d+)?", value.replace(",", ""))
                if m:
                    try:
                        value_num = float(m.group(0))
                    except ValueError:
                        value_num = None
            out.append({
                "title": (item.get("title") or "")[:300] or "Untitled tender",
                "buyer": (item.get("buyer") or item.get("authority") or "")[:200],
                "buyer_type": "perplexity-discovered",
                "description": (item.get("description") or "")[:4000],
                "category": q["category"],
                "value_min": value_num,
                "value_max": value_num,
                "currency": "GBP",
                "publication_date": today_iso,
                "deadline_date": (item.get("deadline") or "")[:10] or None,
                "status": "open",
                "source": "perplexity",
                "url": url,
                "country": "UK",
                "raw_data": {"item": item, "category": q["category"]},
            })
    LOGGER.info("Perplexity procurement: %d signals", len(out))
    return out
