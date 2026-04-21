"""Thin wrapper around the Perplexity Sonar API.

Docs: https://docs.perplexity.ai/

We use the chat completions endpoint with citations enabled to capture
the source URLs alongside each answer.
"""

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from . import db
from .config import PERPLEXITY_API_KEY

API_URL = "https://api.perplexity.ai/chat/completions"

DEFAULT_MODEL = "sonar-pro"
DEEP_MODEL = "sonar-reasoning-pro"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def ask(
    query: str,
    *,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Query Perplexity. Returns dict with 'answer' (str) and 'citations' (list[str])."""
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not configured in .env")

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": query})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "return_citations": True,
    }

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }

    with httpx.Client(timeout=120.0) as client:
        r = client.post(API_URL, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    answer = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    return {"answer": answer, "citations": citations, "raw": data}


def cached_ask(
    query: str,
    *,
    topic: str | None = None,
    region: str | None = None,
    model: str = DEFAULT_MODEL,
    cache_hours: int = 24 * 7,
    system: str | None = None,
) -> dict[str, Any]:
    """Look up cached answer in financial_research; fall back to live API."""
    cached = db.fetch_one(
        """
        SELECT id, query, answer, citations, created_at, cached_until
        FROM financial_research
        WHERE query = %s
          AND (cached_until IS NULL OR cached_until > NOW())
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (query,),
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
        VALUES (%s, %s, %s, %s::jsonb, %s, 'perplexity', %s)
        """,
        (query, topic, fresh["answer"], json.dumps(fresh["citations"]), region, cached_until),
    )
    fresh["cached"] = False
    return fresh
