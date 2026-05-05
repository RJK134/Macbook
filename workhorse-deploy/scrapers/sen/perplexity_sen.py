"""Perplexity-driven discovery of current SEN best practice, alt-provision
news, EHCP guidance, and inclusive teaching resources for excluded learners.
"""

from __future__ import annotations

import json
import re

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("sen.perplexity")

QUERIES = [
    {
        "category": "best-practice",
        "prompt": (
            "List the most useful UK resources published or updated in the "
            "last 90 days on inclusive teaching practice for SEND students "
            "and excluded learners, especially online delivery models. "
            "Include NASEN, Council for Disabled Children, Autism Education "
            "Trust, IPSEA, Whole School SEND. For each: title, organisation, "
            "summary, url, applies_to (early-years|primary|secondary|post-16). "
            "JSON array only."
        ),
    },
    {
        "category": "alt-provision",
        "prompt": (
            "List recent UK reports, datasets, and best-practice guides on "
            "alternative provision and pupils excluded from mainstream school. "
            "Include DfE statistics releases, IntegratED, Centre for Social "
            "Justice, Difference Coalition. JSON array of {title, organisation, "
            "summary, url}."
        ),
    },
    {
        "category": "ehcp-tribunal",
        "prompt": (
            "List recent UK decisions, guidance, and tools relevant to EHCP "
            "applications and SEND tribunal practice in the last 90 days. "
            "JSON array of {title, organisation, summary, url}."
        ),
    },
    {
        "category": "online-tools",
        "prompt": (
            "List currently-active free or low-cost online learning platforms "
            "specifically designed for or strongly used by students with SEND "
            "or those out of mainstream education (home-educated, school-"
            "refusers, hospital schools). For each: name, target audience, "
            "subjects covered, url, cost-model. JSON array only."
        ),
    },
]


def _parse_json(answer: str) -> list[dict]:
    answer = answer.strip()
    answer = re.sub(r"^```(?:json)?\s*", "", answer)
    answer = re.sub(r"\s*```$", "", answer)
    m = re.search(r"\[.*\]", answer, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return []
    return []


def scrape() -> list[dict]:
    out: list[dict] = []
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 7)
        except Exception as exc:
            LOGGER.warning("Perplexity %s failed: %s", q["category"], exc)
            continue
        for item in _parse_json(res.get("answer", "")):
            url = item.get("url")
            if not url or not url.startswith("http"):
                continue
            out.append({
                "resource_type": "guidance" if q["category"] != "online-tools" else "tool",
                "title": (item.get("title") or item.get("name") or "")[:300],
                "source": "perplexity",
                "url": url,
                "category": q["category"],
                "description": (item.get("summary") or item.get("description") or "")[:4000],
                "region": "UK",
                "applies_to": item.get("applies_to") or item.get("target_audience"),
                "published_date": None,
                "raw_data": {"category": q["category"], "item": item},
            })
    LOGGER.info("Perplexity SEN: %d signals", len(out))
    return out
