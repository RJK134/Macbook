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

# --- ignore-first patterns (run before any category match) -----------

# Promotional digest / sender spam — keep classified as 'ignore' so they
# never surface in the weekly digest even when their bodies mention
# "course", "job", "funding" etc.
IGNORE_SENDER_RE = re.compile(
    r"(info@jobs\.ch|candidat@jobup\.ch|jobalerts-noreply@linkedin\.com|"
    r"recommender@my\.jobscout24\.ch|"
    r"noreply@filmfreeway\.com|no-reply@e\.udemymail\.com|"
    r"hello@instructors\.udemy\.com|coursera@m\.learn\.coursera\.org|"
    r"no-reply@t\.mail\.coursera\.org|email@nofilmschool\.com|"
    r"deals@|offers@|promo@|marketing@|newsletter@|"
    r"failed-payments\+|billing@|payments@|receipts@|invoice@|"
    r"contact@mail\.scrapes\.ai|"
    r"hi@cursor\.com|notification@slack\.com|"
    r"hsbcuk@|hello@notify\.railway\.app|stripe\.com|"
    r"@mail\.michaelpage\.ch|noreply_careers@elca\.ch|"
    r"@privaterelay\.appleid\.com|"
    r"account-security-noreply@accountpro)",
    re.I,
)
IGNORE_SUBJECT_RE = re.compile(
    r"(job recommendations for you|festival spotlight|"
    r"this week on filmfreeway|"
    r"\bsale\b.*\$\d|\d+% off|discount|coupon|\bdeal\b|"
    r"payment was unsuccessful|payment failed|invoice #|receipt for|"
    r"re: query regarding billing|re: .* charges|"
    r"news about your companies|weekly job opportunities|"
    r"recommended:|join us for|may sale|"
    r"your task is complete|scan failed|build failed|"
    r"no api access|automation blocked|standup brief|"
    r"automation script provided|script for issue and pr|"
    r"new app\(s\) connected to your)",
    re.I,
)

# Self-emails the user sends himself as notes
SELF_EMAIL = "richardknapp134@gmail.com"

JOB_BOARDS = re.compile(
    r"\b(jobs\.ac\.uk|timeshighereducation|jobs\.ch|linkedin.*(?:job|hiring|posted)|"
    r"indeed|glassdoor|reed\.co|cv-library|monster|jobup|jobscout24|"
    r"michaelpage|academicpositions|elca\.ch|hays|adzuna)\b",
    re.I,
)
# Tighter — needs application-process specific phrasing, not just
# "unfortunately" or "next steps" which match marketing copy.
JOB_APP_RE = re.compile(
    r"\b(application (received|update|status|reference)|"
    r"interview invitation|interview scheduled|"
    r"thank you for applying|we have reviewed your application|"
    r"unfortunately.*your application|regarding your application|"
    r"job offer:|offer of employment|conditional offer)\b",
    re.I,
)
FUNDING_RE = re.compile(
    r"\b(grant call|innovate uk|ukri|horizon europe|snsf|call for proposals?|"
    r"bursary|scheme open|research council|funding opportunity|"
    r"award open for applications)\b",
    re.I,
)
INVESTMENT_RE = re.compile(
    r"\b(seed round|series [a-c]|venture capital|angel invest\w*|"
    r"pitch deadline|accelerator|incubat\w*|innosuisse|f6s|swisspreneur|fongit|"
    r"edtech fund|venture builder|pre-seed)\b",
    re.I,
)
FILM_RE = re.compile(
    r"\b(bfi|bbc writersroom|screenskills|coverfly|shooting people|"
    r"script (competition|comp)|screenplay|film fund|writers? room|"
    r"finaldraft|final draft|"
    r"script.?to.?screen|screenwriting|"
    r"short film|feature film commission)\b",
    re.I,
)
COURSE_RE = re.compile(
    r"\b(ucas|discoveruni|whatuni|complete university guide|"
    r"prospectus|enrol|admission|"
    r"findamasters|findaphd|open university)\b",
    re.I,
)
# 'Learning' = signals about dev tools the user actually develops with.
# Tightened so generic mentions of "cursor" (as in "move cursor") or
# transactional Stripe/Cursor billing emails no longer match.
LEARNING_RE = re.compile(
    r"\b(claude code|cursor (release|update|tip)|copilot release|"
    r"merge conflict|build failed|mcp server|n8n release|"
    r"anthropic blog|openai api update|agents? sdk)\b",
    re.I,
)
NEWSLETTER_RE = re.compile(
    r"\b(wonkhe|hepi|jisc|times higher|university business|herm|edtech weekly|"
    r"iamexpat|swisscore|belearn)\b",
    re.I,
)


def classify(*, from_email: str, subject: str, body: str,
             label_hint: str | None = None) -> str:
    sender = (from_email or "").lower()
    text = f"{sender} {subject} {body[:2000]}".lower()

    # Self-emails are notes-to-self, never go into the digest
    if SELF_EMAIL in sender:
        return "ignore"

    # Promotional / billing / sender spam — short-circuit to ignore
    if IGNORE_SENDER_RE.search(sender) or IGNORE_SUBJECT_RE.search(subject or ""):
        return "ignore"

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
        m = re.search(r"(?:CHF|Fr\.|[£€$])\s?(\d{1,3}(?:[,\d]{0,10}))(k|m|M)?", body, re.I)
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
