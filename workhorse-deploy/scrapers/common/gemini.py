"""Thin wrapper around the Google Gemini API (google-genai SDK)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from google import genai

from . import db
from .config import GEMINI_API_KEY

DEFAULT_MODEL = "gemini-2.5-flash"
DEEP_MODEL = "gemini-2.5-pro"

COST_PER_MILLION = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
}


def _estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    rates = COST_PER_MILLION.get(model, COST_PER_MILLION["gemini-2.5-flash"])
    return (tokens_in * rates["input"] + tokens_out * rates["output"]) / 1_000_000

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY not configured in .env")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def ask(
    query: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    client = _get_client()
    config = genai.types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system,
    )
    response = client.models.generate_content(
        model=model,
        contents=query,
        config=config,
    )
    answer = response.text or ""

    usage = getattr(response, "usage_metadata", None)
    tokens_in = getattr(usage, "prompt_token_count", 0) or 0
    tokens_out = getattr(usage, "candidates_token_count", 0) or 0
    cost = _estimate_cost(model, tokens_in, tokens_out)
    db.execute(
        """
        INSERT INTO api_usage (service, model, endpoint, tokens_input, tokens_output, tokens_total, cost_usd, cached)
        VALUES ('gemini', %s, 'generateContent', %s, %s, %s, %s, FALSE)
        """,
        (model, tokens_in, tokens_out, tokens_in + tokens_out, cost),
    )

    return {"answer": answer, "model": model, "raw": str(response)}


def cached_ask(
    query: str,
    *,
    topic: str | None = None,
    region: str | None = None,
    model: str = DEFAULT_MODEL,
    cache_hours: int = 24 * 7,
    system: str | None = None,
) -> dict[str, Any]:
    cache_key = f"gemini:{query}"
    cached = db.fetch_one(
        """
        SELECT id, query, answer, citations, created_at, cached_until
        FROM financial_research
        WHERE query = %s
          AND source = 'gemini'
          AND (cached_until IS NULL OR cached_until > NOW())
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (cache_key,),
    )
    if cached:
        return {
            "answer": cached["answer"],
            "citations": cached["citations"] or [],
            "cached": True,
        }

    fresh = ask(query, model=model, system=system)
    cached_until = datetime.now(timezone.utc) + timedelta(hours=cache_hours)
    db.execute(
        """
        INSERT INTO financial_research (query, topic, answer, citations, region, source, cached_until)
        VALUES (%s, %s, %s, %s::jsonb, %s, 'gemini', %s)
        """,
        (cache_key, topic, fresh["answer"], json.dumps([]), region, cached_until),
    )
    fresh["cached"] = False
    fresh["citations"] = []
    return fresh
