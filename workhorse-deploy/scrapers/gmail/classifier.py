"""Lightweight rule-based classifier for incoming emails.

Categorises into:
  - job-app          (job application updates / responses)
  - job-listing      (vacancy alerts from job boards)
  - funding          (grant/funding announcements + applications)
  - film             (script comp / film opportunity)
  - course           (HE / EdTech sector course-related correspondence)
  - newsletter       (sector newsletters worth keeping in scope)
  - ignore           (everything else — no further processing)

The intent is to suppress noise: only categorised non-ignore items end
up in the weekly master digest.
"""

from __future__ import annotations

import re

# Senders we trust as job listing sources.
JOB_BOARDS = re.compile(
    r"\b(jobs\.ac\.uk|timeshighereducation|jobs\.ch|linkedin|indeed|"
    r"glassdoor|reed|cv-library|monster)\b",
    re.I,
)
JOB_APP_RE = re.compile(
    r"\b(application (received|update|status)|interview|offer|next steps?|"
    r"unfortunately|we regret|thank you for applying|your application)\b",
    re.I,
)
FUNDING_RE = re.compile(
    r"\b(grant|funding|innovate uk|ukri|horizon|innosuisse|snsf|call for|"
    r"award|bursary|scheme open)\b",
    re.I,
)
FILM_RE = re.compile(
    r"\b(bfi|bbc writersroom|screenskills|coverfly|shooting people|"
    r"script (competition|comp)|screenplay|film fund|writers? room)\b",
    re.I,
)
COURSE_RE = re.compile(
    r"\b(ucas|discoveruni|whatuni|complete university guide|course (info|catalog)|"
    r"prospectus|enrol|admission)\b",
    re.I,
)
NEWSLETTER_RE = re.compile(
    r"\b(wonkhe|hepi|jisc|times higher|university business|herm|edtech weekly)\b",
    re.I,
)


def classify(*, from_email: str, subject: str, body: str) -> str:
    text = f"{from_email} {subject} {body[:2000]}".lower()
    if JOB_APP_RE.search(text):
        return "job-app"
    if JOB_BOARDS.search(text):
        return "job-listing"
    if FUNDING_RE.search(text):
        return "funding"
    if FILM_RE.search(text):
        return "film"
    if COURSE_RE.search(text):
        return "course"
    if NEWSLETTER_RE.search(text):
        return "newsletter"
    return "ignore"


def extract_fields(*, subject: str, body: str, category: str) -> dict:
    """Pull a small set of structured fields per category."""
    snippet = body[:500].strip()
    out = {"snippet": snippet}
    if category == "job-app":
        m = re.search(r"(application|application id|reference)[:\s]+([A-Z0-9-]{4,})", subject + " " + body, re.I)
        if m:
            out["reference"] = m.group(2)
    if category in ("funding", "film"):
        m = re.search(r"deadline[:\s]+([A-Za-z0-9 ,/-]{4,40})", body, re.I)
        if m:
            out["deadline"] = m.group(1).strip()
        m = re.search(r"[££](\d{1,3}(?:[,\d]{0,3}))(k|m)?", body, re.I)
        if m:
            out["amount"] = m.group(0)
    return out
