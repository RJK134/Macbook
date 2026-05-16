"""Discover exam-board resources (specs, past papers, mark schemes) via
Perplexity research. Targets AQA, OCR, Pearson Edexcel, WJEC for GCSE
and A-Level core subjects relevant to Maieus / Maieus2.

Past-paper rows additionally carry the paper-code / paper-name /
duration / total-marks / licence / official-PDF / aggregator-URL fields
required by the Maieus datalake importer (ExamPaperRefSchema). The
Perplexity prompt explicitly forbids extracting question text, answer
text, or mark-scheme text — only metadata about the paper. The Maieus
side re-checks this at the CSV header level and refuses any import
that smuggles a body column through.
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
        f"boards (AQA, OCR, Pearson Edexcel, WJEC, CCEA, SQA). For each return "
        f"these fields as JSON keys: title, resource_type "
        f"(specification|past-paper|mark-scheme|examiners-report|sample-paper), "
        f"exam_board, year, direct_url, paper_code (e.g. 8462/1H), paper_name "
        f"(e.g. 'Biology Paper 1 (Higher)'), duration_minutes (integer), "
        f"total_marks (integer), licence (e.g. 'metadata-only', 'out-of-copyright', "
        f"'cc-by-4.0'), official_pdf_url, aggregator_urls (array of strings). "
        f"Only include URLs that point to the official exam-board domain for "
        f"direct_url and official_pdf_url. METADATA ONLY — do not include any "
        f"question text, answer text, mark-scheme text, solution text, or "
        f"body / questionBody / markScheme / answer / solution fields. "
        f"Return JSON array only."
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
        aggregator = item.get("aggregator_urls") or []
        if isinstance(aggregator, str):
            aggregator = [aggregator]
        aggregator = [u for u in aggregator if isinstance(u, str) and u.startswith("http")]
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
            "year": _safe_int(item.get("year")),
            "difficulty": item.get("difficulty"),
            "paper_code": _safe_str(item.get("paper_code"), 50),
            "paper_name": _safe_str(item.get("paper_name"), 300),
            "duration_minutes": _safe_int(item.get("duration_minutes")),
            "total_marks": _safe_int(item.get("total_marks")),
            "licence": _safe_str(item.get("licence"), 100),
            "official_pdf_url": _safe_url(item.get("official_pdf_url")),
            "aggregator_urls": aggregator,
            "raw_data": item,
        })
    return rows


def _safe_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _safe_str(value, limit: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:limit]


def _safe_url(value) -> str | None:
    if not value or not isinstance(value, str):
        return None
    return value if value.startswith("http") else None


def scrape() -> list[dict]:
    out: list[dict] = []
    for subject, level in SUBJECT_PLAN:
        out.extend(_query_subject(subject, level))
    LOGGER.info("Exam boards: %d resources discovered", len(out))
    return out
