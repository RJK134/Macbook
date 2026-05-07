"""Discover the freshest BBC Bitesize, Khan Academy, NRICH, Isaac Physics
and Seneca content for our subject set, via Perplexity. We index pointers,
not content (the platforms are CDN-served and don't need scraping).
"""

from __future__ import annotations

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("edu.curated_platforms")

PLATFORM_QUERIES = [
    {
        "platform": "bbc-bitesize",
        "prompt": (
            "List the most useful BBC Bitesize topic pages for GCSE and A-Level "
            "study, covering: English Literature, English Language, Mathematics, "
            "Combined Science, History, Geography, Religious Studies, Philosophy. "
            "For each return: subject, level (GCSE|A-Level), topic, "
            "title, url. URLs must be on bbc.co.uk/bitesize/. JSON array only."
        ),
    },
    {
        "platform": "khan-academy",
        "prompt": (
            "List the most useful Khan Academy course units for GCSE/A-Level "
            "study in: Mathematics, Biology, Chemistry, Physics, English Grammar. "
            "For each return: subject, level, topic, title, url (must be on "
            "khanacademy.org). JSON array only."
        ),
    },
    {
        "platform": "nrich",
        "prompt": (
            "List the most engaging NRICH problems and articles for GCSE and "
            "A-Level Mathematics, especially problem-solving and proof-based. "
            "For each return: subject (Mathematics), level, topic, title, url "
            "(must be on nrich.maths.org). JSON array only."
        ),
    },
    {
        "platform": "isaac-physics",
        "prompt": (
            "List the most useful Isaac Physics question collections for "
            "A-Level Physics and Mathematics. For each: subject, level, "
            "topic, title, url (must be on isaacphysics.org). JSON array only."
        ),
    },
    {
        "platform": "seneca",
        "prompt": (
            "List the most useful Seneca Learning courses for GCSE and "
            "A-Level study. For each: subject, level, topic, title, url "
            "(must be on senecalearning.com). JSON array only."
        ),
    },
]


def scrape() -> list[dict]:
    out: list[dict] = []
    for q in PLATFORM_QUERIES:
        try:
            res = perplexity.cached_ask(q["prompt"], model="sonar-pro", cache_hours=24 * 14)
        except Exception as exc:
            LOGGER.warning("Perplexity %s failed: %s", q["platform"], exc)
            continue
        for item in llm_json.parse_json_array(res.get("answer", "")):
            url = item.get("url")
            if not url or not url.startswith("http"):
                continue
            out.append({
                "exam_board": None,
                "level": (item.get("level") or "")[:30],
                "subject": (item.get("subject") or "general")[:100],
                "topic": item.get("topic"),
                "resource_type": "video" if q["platform"] == "khan-academy" else "article",
                "title": (item.get("title") or "")[:300] or f"{q['platform']} resource",
                "source": q["platform"],
                "url": url,
                "description": item.get("description"),
                "raw_data": {"platform": q["platform"], "item": item},
            })
    LOGGER.info("Curated platforms: %d resources", len(out))
    return out
