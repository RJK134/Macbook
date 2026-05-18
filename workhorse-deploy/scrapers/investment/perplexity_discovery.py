"""Weekly Perplexity-driven investment / funding signal discovery.

The previous implementation split the Perplexity answer on newlines and
stored every line as a signal — every paragraph, table header and
disclaimer ended up as a row. This version asks Perplexity for a
strict JSON array and walks the parsed array instead.
"""

from __future__ import annotations

import hashlib
import re

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("investment.perplexity")

QUERIES = [
    {
        "prompt": (
            "List Swiss EdTech and education-technology startup funding "
            "rounds announced in the last 14 days. Include Innosuisse "
            "grants if any were announced in the same window. Return a "
            "JSON array of objects with these exact keys: company, amount "
            "(integer in stated currency), currency (CHF|EUR|USD|GBP), "
            "stage (pre-seed|seed|series-a|series-b|series-c|growth|grant), "
            "investors (array of strings), title, url, announced_date "
            "(ISO YYYY-MM-DD). Empty array if none. JSON ONLY — no prose."
        ),
        "sector": "edtech",
        "region": "Switzerland",
        "country": "CH",
    },
    {
        "prompt": (
            "List UK and EU EdTech startup funding rounds and Innovate UK "
            "EdTech-specific grant awards announced in the last 14 days. "
            "Return a JSON array with the same shape: company, amount, "
            "currency, stage, investors, title, url, announced_date. "
            "Empty array if none. JSON ONLY."
        ),
        "sector": "edtech",
        "region": "UK/EU",
        "country": "UK",
    },
    {
        "prompt": (
            "List Swiss accelerator and incubator programmes that are "
            "currently accepting applications (deadline in the future). "
            "Cover Venture Kick, MassChallenge Switzerland, Kickstart, "
            "Climate-KIC, and any university-affiliated programmes. "
            "Return a JSON array of objects with keys: company (the "
            "programme name), stage='accelerator', title (the cohort or "
            "track name), url, deadline (ISO YYYY-MM-DD), focus (string). "
            "Empty array if none. JSON ONLY."
        ),
        "sector": "general",
        "region": "Switzerland",
        "country": "CH",
    },
]

# Stage values we accept; anything else is normalised to None so the
# downstream filter can flag malformed entries.
ALLOWED_STAGES = {
    "pre-seed", "seed", "series-a", "series-b", "series-c",
    "growth", "grant", "accelerator",
}


def _normalise_amount(raw) -> tuple[float | None, str]:
    """Coerce Perplexity's amount field (often a string with suffix)."""
    if raw is None:
        return None, "CHF"
    if isinstance(raw, (int, float)):
        return float(raw), "CHF"
    s = str(raw).strip()
    # Currency hint from the string itself
    currency = "CHF"
    for code, token in (("EUR", "EUR"), ("EUR", "€"),
                        ("USD", "USD"), ("USD", "$"),
                        ("GBP", "GBP"), ("GBP", "£")):
        if token in s.upper() if token.isalpha() else token in s:
            currency = code
            break
    m = re.search(r"([\d.,]+)\s*(million|m|k|billion|b)?", s, re.I)
    if not m:
        return None, currency
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None, currency
    suffix = (m.group(2) or "").lower()
    if suffix in ("m", "million"):
        val *= 1_000_000
    elif suffix in ("k",):
        val *= 1_000
    elif suffix in ("b", "billion"):
        val *= 1_000_000_000
    return val, currency


def _normalise_stage(raw) -> str | None:
    if not raw:
        return None
    s = str(raw).strip().lower().replace(" ", "-")
    return s if s in ALLOWED_STAGES else None


def _source_ref(query_idx: int, item: dict) -> str:
    """Deterministic dedup key — prefer URL, fall back to company+date."""
    key = item.get("url") or f"{item.get('company','')}|{item.get('announced_date','')}"
    return hashlib.sha256(f"{query_idx}:{key}".encode()).hexdigest()[:16]


def scrape() -> list[dict]:
    out: list[dict] = []
    for idx, q in enumerate(QUERIES):
        try:
            resp = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 3)
        except Exception as exc:
            LOGGER.warning("Perplexity %s/%s failed: %s", q["sector"], q["region"], exc)
            continue
        items = llm_json.parse_json_array(resp.get("answer", ""))
        for item in items:
            url = item.get("url")
            if not url or not str(url).startswith("http"):
                continue
            title = (item.get("title") or item.get("company") or "")[:300]
            if not title:
                continue
            amount, parsed_currency = _normalise_amount(item.get("amount"))
            currency = (item.get("currency") or parsed_currency or "CHF")[:3]
            stage = _normalise_stage(item.get("stage"))
            investors = item.get("investors") or []
            if isinstance(investors, str):
                investors = [investors]
            investors_text = ", ".join(str(i) for i in investors[:10] if i)
            description_parts = [
                item.get("company", ""),
                f"stage={stage}" if stage else "",
                f"investors: {investors_text}" if investors_text else "",
                item.get("focus", ""),
            ]
            description = " · ".join(p for p in description_parts if p)
            out.append({
                "signal_type": "funding-round" if stage != "accelerator" else "accelerator-call",
                "title": title,
                "company": (item.get("company") or "")[:200],
                "funder": investors_text[:300] or None,
                "amount": amount,
                "currency": currency,
                "stage": stage,
                "region": q["region"],
                "country": q["country"],
                "sector": q["sector"],
                "url": url,
                "source": "perplexity",
                "source_ref": _source_ref(idx, item),
                "description": description[:2000],
                "raw_data": {"query_idx": idx, "item": item},
            })
        LOGGER.info("Perplexity %s/%s: %d items kept (was %d returned)",
                    q["sector"], q["region"], sum(1 for o in out if o["raw_data"]["query_idx"] == idx),
                    len(items))
    LOGGER.info("Investment discovery: %d signals", len(out))
    return out
