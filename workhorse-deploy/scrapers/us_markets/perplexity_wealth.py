"""Perplexity-driven US wealth advisory research.

Weekly deep queries focused on US financial markets, asset allocation,
and wealth management trends for high-net-worth advisory support.
"""

from __future__ import annotations

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("us_markets.perplexity_wealth")

SYSTEM_PROMPT = (
    "You are a senior wealth management research analyst. Provide precise, "
    "data-backed analysis with source citations. Focus on actionable insights "
    "for a US-focused high-net-worth wealth advisory practice. Include specific "
    "numbers, dates, and source URLs."
)

QUERIES = [
    {
        "topic": "us-market-outlook",
        "region": "US",
        "query": (
            "What is the current US equity market outlook for the next 6 months? "
            "Cover: S&P 500 consensus targets, Fed rate path expectations, "
            "earnings growth estimates, key risks (geopolitical, inflation, "
            "recession probability). Cite major bank research (Goldman, JPMorgan, "
            "Morgan Stanley, BofA) published in the last 30 days."
        ),
    },
    {
        "topic": "us-fixed-income",
        "region": "US",
        "query": (
            "Current state of US fixed income markets: Treasury yield curve "
            "(2Y, 10Y, 30Y), corporate bond spreads (IG and HY), municipal bond "
            "yields. What are the consensus views on duration positioning for "
            "HNW portfolios? Any notable new issuance or credit events in the "
            "last 14 days?"
        ),
    },
    {
        "topic": "us-alternative-investments",
        "region": "US",
        "query": (
            "Latest developments in US alternative investments accessible to "
            "accredited investors: private credit funds, real estate (BREIT, "
            "Starwood, KKR RE), private equity secondaries, hedge fund "
            "performance. Any new SEC regulatory changes affecting alts access? "
            "Cite fund performance data from the last quarter."
        ),
    },
    {
        "topic": "us-tax-planning",
        "region": "US",
        "query": (
            "What are the key US tax planning strategies for HNW individuals "
            "in 2026? Cover: capital gains harvesting, Roth conversion windows, "
            "estate/gift tax exemption status, SALT deduction changes, "
            "qualified opportunity zones. Any proposed legislation that could "
            "affect 2026-2027 planning? Cite IRS guidance and CPA firm "
            "publications from the last 60 days."
        ),
    },
    {
        "topic": "us-sector-rotation",
        "region": "US",
        "query": (
            "Which US equity sectors are showing the strongest momentum and "
            "which are lagging over the last 30 and 90 days? Cover: Technology, "
            "Healthcare, Financials, Energy, Consumer Discretionary, Industrials, "
            "Utilities. Include specific ETF performance (XLK, XLV, XLF, XLE, "
            "XLY, XLI, XLU). What are strategists recommending for sector "
            "allocation shifts?"
        ),
    },
]


def run_all() -> list[dict]:
    out: list[dict] = []
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(
                q["query"],
                topic=q["topic"],
                region=q["region"],
                system=SYSTEM_PROMPT,
                cache_hours=24 * 7,
            )
            out.append({
                "topic": q["topic"],
                "region": q["region"],
                "answer": res["answer"],
                "citations": res["citations"],
                "cached": res.get("cached", False),
            })
            LOGGER.info("Topic %s: %s", q["topic"], "cached" if res.get("cached") else "fresh")
        except Exception as exc:
            LOGGER.exception("Topic %s failed: %s", q["topic"], exc)
    return out
