"""Weekly Perplexity-driven investment/funding signal discovery."""

from __future__ import annotations

import re

from ..common.logging_setup import get_logger
from ..common import perplexity

LOGGER = get_logger("investment.perplexity")

QUERIES = [
    {
        "query": (
            "List Swiss EdTech and education technology startup funding rounds "
            "announced in the last 14 days. For each, give: company name, amount, "
            "currency, stage (seed/series-A/etc), investor names, and a URL. "
            "Include Innosuisse grants if any were announced."
        ),
        "sector": "edtech",
        "region": "Switzerland",
        "country": "CH",
    },
    {
        "query": (
            "List UK and EU EdTech startup funding rounds and grants announced "
            "in the last 14 days. Include UKRI Innovate UK awards. "
            "For each: company, amount, currency, stage, URL."
        ),
        "sector": "edtech",
        "region": "UK/EU",
        "country": "UK",
    },
    {
        "query": (
            "List Swiss accelerator and incubator programmes accepting applications "
            "right now. Include Venture Kick, MassChallenge Switzerland, Kickstart, "
            "Climate-KIC, and any university-affiliated programmes. "
            "For each: name, deadline, focus area, URL."
        ),
        "sector": "general",
        "region": "Switzerland",
        "country": "CH",
    },
]

AMOUNT_RE = re.compile(
    r"(?:CHF|EUR|USD|GBP|£|€|\$)\s?([\d,.]+)\s?(million|m|k|billion|b)?",
    re.I,
)


def _parse_amount(text: str) -> tuple[float | None, str]:
    m = AMOUNT_RE.search(text)
    if not m:
        return None, "CHF"
    raw = m.group(1).replace(",", "")
    try:
        val = float(raw)
    except ValueError:
        return None, "CHF"
    suffix = (m.group(2) or "").lower()
    if suffix in ("m", "million"):
        val *= 1_000_000
    elif suffix in ("k",):
        val *= 1_000
    elif suffix in ("b", "billion"):
        val *= 1_000_000_000
    currency = "CHF"
    prefix = text[m.start():m.start()+3]
    if "EUR" in prefix or "€" in prefix:
        currency = "EUR"
    elif "USD" in prefix or "$" in prefix:
        currency = "USD"
    elif "GBP" in prefix or "£" in prefix:
        currency = "GBP"
    return val, currency


def scrape() -> list[dict]:
    out: list[dict] = []
    for q in QUERIES:
        try:
            resp = perplexity.ask(q["query"], model="sonar-pro")
            answer = resp.get("answer", "")
            citations = resp.get("citations", [])
            lines = [l.strip() for l in answer.split("\n") if l.strip() and len(l.strip()) > 20]
            for line in lines:
                amount, currency = _parse_amount(line)
                out.append({
                    "signal_type": "funding-round",
                    "title": line[:300],
                    "company": None,
                    "funder": None,
                    "amount": amount,
                    "currency": currency,
                    "stage": None,
                    "region": q["region"],
                    "country": q["country"],
                    "sector": q["sector"],
                    "url": citations[0] if citations else None,
                    "source": "perplexity",
                    "description": answer[:2000],
                    "raw_data": {"query": q["query"], "citations": citations},
                })
            LOGGER.info("Perplexity %s/%s: %d lines", q["sector"], q["region"], len(lines))
        except Exception as exc:
            LOGGER.warning("Perplexity query failed: %s", exc)
    LOGGER.info("Perplexity investment discovery: %d signals", len(out))
    return out
