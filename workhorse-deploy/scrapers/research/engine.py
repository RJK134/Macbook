"""Dual-engine research runner.

Sends queries to Perplexity (web search) and/or Gemini (deep analysis)
based on each query's engine setting, then stores results in Postgres.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from ..common import db, gemini, perplexity
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("research.engine")

PERPLEXITY_SYSTEM = (
    "You are a research analyst. Return precise, current information with "
    "verifiable URLs. Use bullet points. Cite sources. If data is unavailable "
    "or uncertain, say so rather than guessing."
)

GEMINI_SYSTEM = (
    "You are a strategic research analyst. Provide deep analysis with "
    "structured sections, quantitative data where available, and actionable "
    "insights. Compare sources when possible. Be precise about dates and figures."
)

CACHE_HOURS = 24 * 7


def _run_perplexity(query: dict) -> dict | None:
    try:
        res = perplexity.cached_ask(
            query["query"],
            topic=query["topic"],
            region=query.get("region"),
            system=PERPLEXITY_SYSTEM,
            cache_hours=CACHE_HOURS,
        )
        return {
            "source": "perplexity",
            "topic": query["topic"],
            "region": query.get("region"),
            "area": query.get("area"),
            "answer": res["answer"],
            "citations": res.get("citations", []),
            "cached": res.get("cached", False),
        }
    except Exception as exc:
        LOGGER.warning("Perplexity failed for %s: %s", query["topic"], exc)
        return None


def _run_gemini(query: dict) -> dict | None:
    try:
        res = gemini.cached_ask(
            query["query"],
            topic=query["topic"],
            region=query.get("region"),
            system=GEMINI_SYSTEM,
            cache_hours=CACHE_HOURS,
        )
        return {
            "source": "gemini",
            "topic": query["topic"],
            "region": query.get("region"),
            "area": query.get("area"),
            "answer": res["answer"],
            "citations": res.get("citations", []),
            "cached": res.get("cached", False),
        }
    except Exception as exc:
        LOGGER.warning("Gemini failed for %s: %s", query["topic"], exc)
        return None


def run_query(query: dict) -> list[dict]:
    engine = query.get("engine", "perplexity")
    results = []

    if engine in ("perplexity", "both"):
        res = _run_perplexity(query)
        if res:
            results.append(res)

    if engine in ("gemini", "both"):
        res = _run_gemini(query)
        if res:
            results.append(res)

    for r in results:
        if not r.get("cached"):
            write_raw_json(
                r.get("area") or "research",
                f"research-{r['source']}-{r['topic']}",
                r,
            )

    return results


def run_queries(queries: list[dict]) -> list[dict]:
    all_results = []
    for q in queries:
        results = run_query(q)
        for r in results:
            status = "cached" if r.get("cached") else "fresh"
            LOGGER.info("%s/%s [%s]: %s", r["source"], r["topic"], r["area"], status)
        all_results.extend(results)
    return all_results
