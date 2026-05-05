"""Perplexity-driven discovery of Shakespeare content trending in modern
media — TikTok, YouTube, podcasts — for the 'Shakespeare is Boring' app
which targets students who find traditional teaching dull.
"""

from __future__ import annotations

import json
import re

from ..common import perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("shakespeare.perplexity")

QUERIES = [
    {
        "category": "tiktok-trending",
        "format": "modern-adaptation",
        "audience": "ks3-ks4",
        "engagement": 5,
        "prompt": (
            "List Shakespeare-related TikTok creators, hashtags, and viral "
            "videos that have gained traction in the last 60 days, especially "
            "ones that make Shakespeare accessible or funny for teenagers. "
            "For each: creator/handle, content_summary, play (if specific), "
            "url, why_engaging. JSON array only."
        ),
    },
    {
        "category": "youtube-channels",
        "format": "educational",
        "audience": "ks3-ks4-a-level",
        "engagement": 5,
        "prompt": (
            "List YouTube channels and recent videos that explain Shakespeare "
            "in modern, engaging ways for KS3, KS4, and A-Level English "
            "Literature students. Avoid traditional academic lectures. "
            "Return: channel/video_title, play, summary, url, audience. "
            "JSON array only."
        ),
    },
    {
        "category": "podcasts",
        "format": "podcast",
        "audience": "general",
        "engagement": 4,
        "prompt": (
            "List active Shakespeare podcasts publishing new episodes in 2025 "
            "or 2026 that focus on practical understanding, performance, or "
            "modern relevance. For each: podcast_name, episode_count, latest_"
            "episode_topic, url. JSON array only."
        ),
    },
    {
        "category": "modern-adaptations",
        "format": "modern-adaptation",
        "audience": "general",
        "engagement": 4,
        "prompt": (
            "List recent (2024-2026) modern adaptations of Shakespeare plays — "
            "films, web series, TV, novels, graphic novels, streaming. For each: "
            "title, play, year, format, where_to_watch_or_buy, summary. JSON only."
        ),
    },
    {
        "category": "performance-resources",
        "format": "educational",
        "audience": "ks3-ks4-a-level",
        "engagement": 4,
        "prompt": (
            "List free or low-cost online resources from RSC, Globe, Folger, "
            "Bell Shakespeare, Stratford Festival, Royal Shakespeare Company, "
            "or other professional companies that teach practical performance "
            "or active interpretation of Shakespeare. For each: resource_title, "
            "play, organisation, url, summary. JSON array only."
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
            title = (
                item.get("title") or item.get("video_title") or
                item.get("creator") or item.get("podcast_name") or
                item.get("resource_title") or item.get("channel") or
                "Shakespeare resource"
            )
            description = (
                item.get("summary") or item.get("content_summary") or
                item.get("why_engaging") or item.get("description") or ""
            )
            out.append({
                "resource_type": q["category"],
                "title": str(title)[:300],
                "source": q["category"],
                "url": url,
                "play": item.get("play"),
                "format": q["format"],
                "audience": q["audience"],
                "description": str(description)[:4000],
                "engagement_score": q["engagement"],
                "published_date": None,
                "raw_data": {"category": q["category"], "item": item},
            })
    LOGGER.info("Perplexity Shakespeare: %d signals", len(out))
    return out
