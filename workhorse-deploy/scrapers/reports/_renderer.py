"""Helpers for rendering Perplexity / Gemini research output in weekly reports.

The raw text from these sources is markdown — headings, tables, lists,
bold, links. Without rendering it lands in the HTML as a wall of
``###`` and ``|``-pipes that the reader has to mentally parse. With
rendering, the table is a table and the heading is bold.

Three jobs:

1. **Detect "no useful signal" responses.** Perplexity often returns a
   long answer whose entire payload is "Based on the search results
   provided, I can offer these data-driven insights, though I must
   note significant limitations…" — i.e. the model says "no data".
   Showing this verbatim is noise; we surface a one-line "no signal"
   placeholder instead so the section header is still informative.
2. **Render markdown to HTML.** Use ``markdown-it-py`` (CommonMark +
   GFM tables, strikethrough). Already in the venv via transitive
   deps.
3. **Truncate at a sentence boundary.** The previous implementation
   sliced at a fixed char count and appended ``…`` — almost always
   mid-word, almost always before the first table or list. New
   policy: cap at ~1500 chars but extend to the next sentence end so
   the reader gets a clean paragraph.

Public surface: :func:`render_research_answer(raw)` returns either
``(None, "<no-signal placeholder html>")`` when the answer is empty
of signal, or ``(tldr, body_html)`` otherwise.
"""

from __future__ import annotations

import re

from markdown_it import MarkdownIt


_md = MarkdownIt("commonmark", {"breaks": True, "linkify": True}).enable("table").enable("strikethrough")

# Boilerplate phrases that mark a "no useful signal" answer. Treated
# case-insensitively. A row is considered no-signal if more than one
# phrase matches OR the answer is dominated by them.
_NO_SIGNAL_MARKERS: tuple[str, ...] = (
    "significant limitations in the available sources",
    "no specific.*identified",
    "i must note",
    "the sources don't provide",
    "the sources do not provide",
    "no data available",
    "no relevant data",
    "no university-specific",
    "no.*were identified",
    "no public.*data",
    "limited data available",
)

_TRUNCATION_TARGET_CHARS = 1500
_TRUNCATION_HARD_CAP_CHARS = 2200


def render_research_answer(raw: str | None) -> tuple[str | None, str]:
    """Return ``(tldr, body_html)`` for a Perplexity / Gemini answer.

    ``tldr`` is ``None`` when the answer is judged to contain no
    actionable signal; in that case ``body_html`` is a short
    placeholder. Otherwise:

    * ``tldr`` is a single-sentence summary lifted from the first
      paragraph (sentence-boundary cut at ~180 chars).
    * ``body_html`` is the markdown-rendered, sentence-boundary
      truncated HTML.
    """
    text = (raw or "").strip()
    if not text:
        return None, '<em style="color:#7f8c8d;">No answer recorded.</em>'

    if _is_no_signal(text):
        return None, (
            '<em style="color:#7f8c8d;">No new signal this week '
            '(model reported the search did not surface usable data).</em>'
        )

    truncated = _truncate_at_sentence(text, _TRUNCATION_TARGET_CHARS, _TRUNCATION_HARD_CAP_CHARS)
    body_html = _md.render(truncated)
    tldr = _extract_tldr(text)
    return tldr, body_html


def _is_no_signal(text: str) -> bool:
    """Return True when the answer is dominated by 'no useful data' boilerplate."""
    body_lower = text.lower()
    matches = sum(1 for pat in _NO_SIGNAL_MARKERS if re.search(pat, body_lower))
    # Two or more boilerplate phrases → clearly no-signal. One phrase in
    # a short answer (<800 chars) also qualifies; the response is mostly
    # the disclaimer.
    if matches >= 2:
        return True
    if matches >= 1 and len(text) < 800:
        return True
    return False


def _extract_tldr(text: str) -> str | None:
    """Pull the first sentence of the first content paragraph, ≤180 chars."""
    # Skip markdown leading characters (#, *, -, |, table separators).
    candidates: list[str] = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Skip table separators and pure-marker lines.
        if re.fullmatch(r"[#*\-|=`>+\s_]+", line):
            continue
        # Strip leading markdown markers.
        cleaned = re.sub(r"^[#*\->\s]+", "", line).strip()
        if cleaned:
            candidates.append(cleaned)
            break
    if not candidates:
        return None
    first = candidates[0]
    sentence_end = re.search(r"[.!?](?:\s|$)", first)
    if sentence_end:
        candidate = first[: sentence_end.start() + 1].strip()
    else:
        candidate = first
    if len(candidate) > 180:
        cut = candidate[:177].rsplit(" ", 1)[0]
        return cut + "…"
    return candidate or None


def _truncate_at_sentence(text: str, target: int, hard_cap: int) -> str:
    """If text > target chars, extend to the next sentence end up to hard_cap.

    Falls back to a hard cut + ellipsis when no sentence boundary is found
    inside the [target, hard_cap] window — but breaks at a word boundary
    so we never cut mid-word.
    """
    if len(text) <= target:
        return text
    window_end = min(len(text), hard_cap)
    boundary = re.search(r"[.!?](?:\s|$)", text[target:window_end])
    if boundary:
        return text[: target + boundary.end()].rstrip() + "\n\n_…(truncated for digest; full answer in DB)_"
    # No sentence break — cut on word boundary at target.
    cut = text[:target].rsplit(" ", 1)[0]
    return cut + " …(truncated)"


__all__ = ["render_research_answer"]
