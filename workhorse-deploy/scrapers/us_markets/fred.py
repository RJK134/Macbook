"""FRED API — Federal Reserve Economic Data.

Free API key required (register at https://fred.stlouisfed.org/docs/api/api_key.html).
US economic indicators, interest rates, yield curves, employment data.
"""

from __future__ import annotations

import os

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("us_markets.fred")

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
API_BASE = "https://api.stlouisfed.org/fred"

# Key series for wealth advisory context
SERIES = [
    ("DFF", "Federal Funds Rate"),
    ("DGS10", "10-Year Treasury Yield"),
    ("DGS2", "2-Year Treasury Yield"),
    ("SP500", "S&P 500"),
    ("UNRATE", "Unemployment Rate"),
    ("CPIAUCSL", "Consumer Price Index"),
    ("GDP", "Gross Domestic Product"),
    ("VIXCLS", "CBOE Volatility Index (VIX)"),
    ("DCOILWTICO", "Crude Oil WTI"),
    ("GOLDAMGBD228NLBM", "Gold Price (London)"),
]


def scrape() -> list[dict]:
    if not FRED_API_KEY:
        LOGGER.warning("FRED_API_KEY not set — skipping FRED")
        return []
    out: list[dict] = []
    for series_id, label in SERIES:
        try:
            params = {
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "sort_order": "desc",
                "limit": 5,
            }
            LOGGER.info("FRED: %s (%s)", series_id, label)
            r = http.get(f"{API_BASE}/series/observations", params=params, timeout=20.0)
            data = r.json()
            observations = data.get("observations", [])
            if observations:
                latest = observations[0]
                out.append({
                    "signal_type": "economic-indicator",
                    "title": f"{label}: {latest.get('value', 'N/A')} ({latest.get('date', '')})",
                    "company": None,
                    "source": "fred",
                    "url": f"https://fred.stlouisfed.org/series/{series_id}",
                    "region": "US",
                    "country": "US",
                    "description": f"{label} as of {latest.get('date', '')}: {latest.get('value', '')}",
                    "raw_data": {
                        "series_id": series_id,
                        "label": label,
                        "observations": observations[:5],
                    },
                })
        except Exception as exc:
            LOGGER.warning("FRED %s failed: %s", series_id, exc)
    write_raw_json("us_markets", "fred-indicators", {"total": len(out)})
    LOGGER.info("FRED total: %d indicators", len(out))
    return out
