"""Discover exam-board resources (specs, past papers, mark schemes) via
Perplexity research. Targets AQA, OCR, Pearson Edexcel, WJEC for GCSE
and A-Level core subjects relevant to Maieus / Maieus2.
"""

from __future__ import annotations

from ..common import llm_json, perplexity
from ..common.logging_setup import get_logger

LOGGER = get_logger("edu.exam_boards")

# Subjects most relevant to Socratic teaching (humanities + sciences)
SUBJECT_PLAN = [
    ("English Literature", "GCSE"),
    ("English Language", "GCSE"),
    ("Mathematics", "GCSE"),
    ("Combined Science", "GCSE"),
    ("History", "GCSE"),
    ("Religious Studies", "GCSE"),
    ("Geography", "GCSE"),
    ("English Literature", "A-Level"),
    ("Mathematics", "A-Level"),
    ("Biology", "A-Level"),
    ("Chemistry", "A-Level"),
    ("Physics", "A-Level"),
    ("History", "A-Level"),
    ("Philosophy", "A-Level"),
    ("Religious Studies", "A-Level"),
    ("Politics", "A-Level"),
]


def _query_subject(subject: str, level: str) -> list[dict]:
    prompt = (
        f"List the most useful currently-available {level} {subject} resources "
        f"published or updated in the last 6 months from the major UK exam "
        f"boards (AQA, OCR, Pearson Edexcel, WJEC). For each return: title, "
        f"resource_type (specification|past-paper|mark-scheme|examiners-report|"
        f"sample-paper), exam_board, year, direct_url. Only include URLs that "
        f"point to the official exam-board domain. Return JSON array only."
    )
    try:
        res = perplexity.cached_ask(prompt, model="sonar-pro", cache_hours=24 * 14)
    except Exception as exc:
        LOGGER.warning("Perplexity %s/%s failed: %s", level, subject, exc)
        return []
    items = llm_json.parse_json_array(res.get("answer", ""))
    rows: list[dict] = []
    for item in items:
        url = item.get("direct_url") or item.get("url")
        if not url or not url.startswith("http"):
            continue
        rows.append({
            "exam_board": (item.get("exam_board") or "").upper()[:50],
            "level": level,
            "subject": subject,
            "topic": item.get("topic"),
            "resource_type": (item.get("resource_type") or "specification").lower(),
            "title": (item.get("title") or "")[:300] or f"{subject} {level} resource",
            "source": (item.get("exam_board") or "exam-board").lower(),
            "url": url,
            "description": item.get("description"),
            "year": item.get("year"),
            "difficulty": item.get("difficulty"),
            "raw_data": item,
        })
    return rows


def scrape() -> list[dict]:
    out: list[dict] = []
    for subject, level in SUBJECT_PLAN:
        out.extend(_query_subject(subject, level))
    LOGGER.info("Exam boards: %d resources discovered", len(out))
    return out
