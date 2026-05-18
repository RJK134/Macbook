"""Perplexity-driven film and screenwriting opportunity discovery.

The site-scraping siblings (BBC Writersroom, ScreenSkills, Coverfly,
Shooting People) all degraded:
  - BBC Writersroom SPA'd its opportunities page; HTML is 128 bytes.
  - ScreenSkills serves Cloudflare 403 to non-browser UAs.
  - Shooting People's RSS feed returns 404.
  - Coverfly's `writers.` subdomain is unreachable.

This module replaces them with three scoped Perplexity prompts that
target current UK / EU script comps, screenwriting bursaries, and
short-film commissions. BFI's HTML page is still scrapable so we keep
the dedicated bfi.py module alongside this one.
"""

from __future__ import annotations

from datetime import date

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("film.perplexity")

QUERIES = [
    {
        "category": "scriptcomp",
        "opp_type": "competition",
        "prompt": (
            "List UK screenwriting and short-film competitions whose "
            "submission deadline falls in the next 90 days. Include "
            "BBC Writersroom open calls, Channel 4 4Screenwriting, "
            "BIFA Discovery, BlueCat Screenplay UK, Page International, "
            "Scriptapalooza UK heat, Red Planet Prize. Return a JSON "
            "array with these exact keys: title, organisation, deadline "
            "(ISO YYYY-MM-DD), entry_fee_gbp (integer or null), "
            "prize_gbp (integer or null), url, summary. JSON ONLY."
        ),
    },
    {
        "category": "bursary",
        "opp_type": "funding",
        "prompt": (
            "List currently-open UK and Ireland screenwriting bursaries, "
            "talent-development schemes, and short-film production funds. "
            "Include BFI NETWORK, Film London, Northern Ireland Screen, "
            "Ffilm Cymru, Screen Scotland, BBC Writers Access Group, "
            "ScreenSkills bursaries. For each: title, organisation, "
            "deadline (ISO YYYY-MM-DD or null), prize_gbp (integer or "
            "null), url, summary. JSON ONLY."
        ),
    },
    {
        "category": "commission",
        "opp_type": "submission",
        "prompt": (
            "List UK and EU broadcaster / streamer open calls for short "
            "films, half-hour scripts, or animation pitches currently "
            "accepting submissions. Include BBC iPlayer commissioning "
            "windows, Channel 4 Random Acts, Sky Arts, Film4, Random "
            "Film Festival, festival call-outs. For each: title, "
            "organisation, deadline (ISO YYYY-MM-DD or null), url, "
            "summary. JSON ONLY."
        ),
    },
]


def _safe_int(val) -> int | None:
    if val is None:
        return None
    try:
        return int(float(str(val).replace(",", "").replace("£", "").strip()))
    except (ValueError, TypeError):
        return None


def _safe_date(val) -> str | None:
    if not val:
        return None
    s = str(val).strip()[:10]
    return s if len(s) == 10 and s[4] == "-" and s[7] == "-" else None


def scrape() -> list[dict]:
    out: list[dict] = []
    today = date.today().isoformat()
    for q in QUERIES:
        try:
            res = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 7)
        except Exception as exc:
            LOGGER.warning("Perplexity %s failed: %s", q["category"], exc)
            continue
        items = llm_json.parse_json_array(res.get("answer", ""))
        for item in items:
            url = item.get("url")
            if not url or not str(url).startswith("http"):
                continue
            title = (item.get("title") or "")[:300]
            if not title:
                continue
            out.append({
                "title": title,
                "organisation": (item.get("organisation") or "")[:200] or "Unknown",
                "opp_type": q["opp_type"],
                "region": "UK",
                "fee_gbp": _safe_int(item.get("entry_fee_gbp")),
                "prize_gbp": _safe_int(item.get("prize_gbp")),
                "submission_deadline": _safe_date(item.get("deadline")),
                "description": (item.get("summary") or "")[:4000],
                "url": url,
                "source": "perplexity",
                "status": "open",
                "relevance_score": 3,
                "raw_data": {"category": q["category"], "discovered": today, "item": item},
            })
    LOGGER.info("Perplexity film: %d signals", len(out))
    return out
