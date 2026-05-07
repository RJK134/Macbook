"""SEC EDGAR API — US company filings (10-K, 10-Q, 8-K).

Free, no auth required. Rate limit: 10 req/sec with User-Agent header.
Covers all SEC-registered companies.

https://www.sec.gov/search#/dateRange=custom&startdt=2024-01-01&enddt=2024-12-31
https://efts.sec.gov/LATEST/search-index?q=...
"""

from __future__ import annotations

from datetime import datetime, timedelta

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("us_markets.sec_edgar")

EFTS_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_FULL_TEXT = "https://efts.sec.gov/LATEST/search-index"

# Watchlist: companies relevant to EdTech/wealth advisory
SEARCHES = [
    {"q": '"education technology"', "forms": "10-K,10-Q,8-K"},
    {"q": '"student management"', "forms": "10-K,10-Q,8-K"},
    {"q": 'Coursera OR Duolingo OR "2U Inc" OR Chegg OR Instructure', "forms": "10-K,10-Q,8-K"},
    {"q": '"wealth management" AND technology', "forms": "10-K,10-Q"},
    {"q": '"financial advisory" AND "artificial intelligence"', "forms": "10-K,8-K"},
]

SEC_SEARCH = "https://efts.sec.gov/LATEST/search-index"


def scrape() -> list[dict]:
    out: list[dict] = []
    since = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")
    for search in SEARCHES:
        try:
            params = {
                "q": search["q"],
                "dateRange": "custom",
                "startdt": since,
                "forms": search["forms"],
            }
            LOGGER.info("SEC EDGAR: %s", search["q"][:60])
            r = http.get(
                "https://efts.sec.gov/LATEST/search-index",
                params=params,
                timeout=30.0,
            )
            data = r.json()
            hits = data.get("hits", {}).get("hits", [])
            for hit in hits[:20]:
                source = hit.get("_source", {})
                title = source.get("display_names", [""])[0] if source.get("display_names") else ""
                form = source.get("form_type", "")
                filed = source.get("file_date", "")
                entity = source.get("entity_name", "")
                url = f"https://www.sec.gov/Archives/edgar/data/{source.get('file_num', '')}"
                out.append({
                    "signal_type": "sec-filing",
                    "title": f"{entity}: {form} - {title}"[:300],
                    "company": entity,
                    "source": "sec_edgar",
                    "url": url,
                    "region": "US",
                    "country": "US",
                    "description": f"Form {form} filed {filed}",
                    "raw_data": source,
                })
            LOGGER.info("SEC EDGAR '%s': %d hits", search["q"][:40], len(hits))
        except Exception as exc:
            LOGGER.warning("SEC EDGAR search failed: %s", exc)
    write_raw_json("us_markets", "sec-edgar", {"total": len(out)})
    LOGGER.info("SEC EDGAR total: %d filings", len(out))
    return out
