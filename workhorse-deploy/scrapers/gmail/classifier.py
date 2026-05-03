"""Lightweight rule-based classifier for incoming emails.

Categorises into:
  - job-app          (job application updates / responses)
  - job-listing      (vacancy alerts from job boards)
  - funding          (grant/funding announcements + applications)
  - investment       (startup rounds, VC, accelerators, EdTech funding signals)
  - film             (script comp / film opportunity)
  - course           (HE / EdTech sector course-related correspondence)
  - learning         (Claude, Cursor, coding, MCP, GitHub — dev-learning signal)
  - newsletter       (sector newsletters worth keeping in scope)
  - ignore           (everything else — no further processing)

The intent is to suppress noise: only categorised non-ignore items end
up in the weekly master digest.
"""

from __future__ import annotations

import re

JOB_BOARDS = re.compile(
    r"\b(jobs\.ac\.uk|timeshighereducation|jobs\.ch|linkedin.*(?:job|hiring|posted)|"
    r"indeed|glassdoor|reed\.co|cv-library|monster|jobup|jobscout24|"
    r"michaelpage|academicpositions|elca\.ch|hays|adzuna)\b",
    re.I,
)
JOB_APP_RE = re.compile(
    r"\b(application (received|update|status)|interview|offer|next steps?|"
    r"unfortunately|we regret|thank you for applying|your application)\b",
    re.I,
)
FUNDING_RE = re.compile(
    r"\b(grant|innovate uk|ukri|horizon europe|snsf|call for proposals?|"
    r"award|bursary|scheme open|research council)\b",
    re.I,
)
INVESTMENT_RE = re.compile(
    r"\b(startup|seed round|series [a-c]|venture capital|angel invest\w*|fundrais\w*|"
    r"pitch deadline|accelerator|incubat\w*|innosuisse|f6s|swisspreneur|fongit|"
    r"edtech fund|eu-startups|silicon canals|fresh rounds|funding round|"
    r"venture builder|pre-seed)\b",
    re.I,
)
FILM_RE = re.compile(
    r"\b(bfi|bbc writersroom|screenskills|coverfly|shooting people|"
    r"script (competition|comp)|screenplay|film fund|writers? room|"
    r"filmfreeway|nofilmschool|cinefile|finaldraft|final draft|"
    r"festival spotlight|script.?to.?screen|screenwriting|"
    r"short film|feature film|film festival)\b",
    re.I,
)
COURSE_RE = re.compile(
    r"\b(ucas|discoveruni|whatuni|complete university guide|course (info|catalog)|"
    r"prospectus|enrol|admission|coursera|edx|futurelearn|class central|"
    r"findamasters|findaphd|open university|udemy)\b",
    re.I,
)
LEARNING_RE = re.compile(
    r"\b(claude code|cursor |copilot|github actions?|pull request|"
    r"merge conflict|build fail\w*|mcp server|n8n |code review|"
    r"anthropic|openai api|claude shortcut|agents? go|"
    r"scrapes\.ai|skool\.com)\b",
    re.I,
)
NEWSLETTER_RE = re.compile(
    r"\b(wonkhe|hepi|jisc|times higher|university business|herm|edtech weekly|"
    r"perplexity|iamexpat|swisscore|belearn)\b",
    re.I,
)


def classify(*, from_email: str, subject: str, body: str,
             label_hint: str | None = None) -> str:
    text = f"{from_email} {subject} {body[:2000]}".lower()

    if JOB_APP_RE.search(text):
        return "job-app"
    if FILM_RE.search(text):
        return "film"
    if INVESTMENT_RE.search(text):
        return "investment"
    if FUNDING_RE.search(text):
        return "funding"
    if JOB_BOARDS.search(text):
        return "job-listing"
    if LEARNING_RE.search(text):
        return "learning"
    if COURSE_RE.search(text):
        return "course"
    if NEWSLETTER_RE.search(text):
        return "newsletter"
    if label_hint:
        return label_hint
    return "ignore"


def extract_fields(*, subject: str, body: str, category: str) -> dict:
    """Pull a small set of structured fields per category."""
    snippet = body[:500].strip()
    out = {"snippet": snippet}
    if category == "job-app":
        m = re.search(r"(application|application id|reference)[:\s]+([A-Z0-9-]{4,})", subject + " " + body, re.I)
        if m:
            out["reference"] = m.group(2)
    if category in ("funding", "film", "investment"):
        m = re.search(r"deadline[:\s]+([A-Za-z0-9 ,/-]{4,40})", body, re.I)
        if m:
            out["deadline"] = m.group(1).strip()
        m = re.search(r"[£€$][\s]?(\d{1,3}(?:[,\d]{0,10}))(k|m|M)?", body, re.I)
        if m:
            out["amount"] = m.group(0)
    if category == "investment":
        m = re.search(r"\b(pre-seed|seed|series [a-c]|growth|ipo)\b", body, re.I)
        if m:
            out["stage"] = m.group(0).lower()
    if category == "job-listing":
        m = re.search(r"(?:CHF|EUR|GBP|£|€)\s?[\d,]+(?:[kK])?\s?(?:-|to|–)\s?(?:CHF|EUR|GBP|£|€)?\s?[\d,]+(?:[kK])?", body)
        if m:
            out["salary_range"] = m.group(0)
    return out
