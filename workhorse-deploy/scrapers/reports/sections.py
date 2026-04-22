"""Reusable HTML section builders shared by per-area and master reports.

All section functions return:
  {"title": str, "html": str, "count": int, "items": list[dict]}

`items` is also returned so the master digest can compose summaries
without re-querying the database.
"""

from __future__ import annotations

from datetime import date, timedelta
from html import escape as _esc

from ..common import db


def esc(val: object) -> str:
    """HTML-escape any value for safe embedding in report HTML."""
    return _esc(str(val)) if val else ""


def _week_window() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=7)
    return start, today


def courses_section(limit: int = 20) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT provider, title, qualification, subject_area, location_city, url
        FROM courses
        WHERE first_seen_at >= %s AND active
        ORDER BY first_seen_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    total = db.fetch_one("SELECT count(*) AS c FROM courses WHERE active")
    new_count = db.fetch_one(
        "SELECT count(*) AS c FROM courses WHERE first_seen_at >= %s",
        (start,),
    )
    html = ['<h2 style="color:#2c3e50;">Courses (MyCourseMatchmaker)</h2>']
    html.append(
        f'<p style="color:#666;">Total in DB: <strong>{total["c"]:,}</strong> | '
        f'New this week: <strong>{new_count["c"]:,}</strong></p>'
    )
    if not rows:
        html.append('<p><em>No new courses indexed this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            line = f'<strong>{esc(r["title"])}</strong> &mdash; {esc(r["provider"])}'
            if r.get("location_city"):
                line += f' &middot; {esc(r["location_city"])}'
            if r.get("url"):
                line = f'<a href="{esc(r["url"])}">{line}</a>'
            html.append(f'<li>{line}</li>')
        html.append('</ul>')
    return {"title": "Courses", "html": "\n".join(html), "count": new_count["c"], "items": rows}


def job_trends_section(limit: int = 15) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT occupation, sector, trend, source, source_url, skills_required
        FROM job_trends
        WHERE discovered_at >= %s
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Job Trends (CoursePulse / Course Designer)</h2>']
    if not rows:
        html.append('<p><em>No new trend signals this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            trend_color = {"growing": "#27ae60", "declining": "#c0392b"}.get(r.get("trend") or "", "#7f8c8d")
            line = (
                f'<strong>{esc(r["occupation"])}</strong> '
                f'<span style="color:{trend_color};">[{r.get("trend") or "stable"}]</span>'
            )
            if r.get("skills_required"):
                line += f' <em>skills:</em> {", ".join(r["skills_required"][:6])}'
            if r.get("source_url"):
                line = f'<a href="{r["source_url"]}">{line}</a>'
            html.append(f'<li>{line}</li>')
        html.append('</ul>')
    return {"title": "Job Trends", "html": "\n".join(html), "count": len(rows), "items": rows}


def financial_section(limit: int = 6) -> dict:
    rows = db.fetch_all(
        """
        SELECT topic, region, answer, citations, created_at
        FROM financial_research
        WHERE source = 'perplexity'
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (limit,),
    )
    html = ['<h2 style="color:#2c3e50;">Financial Research (Perplexity)</h2>']
    if not rows:
        html.append('<p><em>No fresh research yet — run the financial orchestrator.</em></p>')
    else:
        for r in rows:
            html.append(
                f'<h3 style="color:#34495e;margin-bottom:4px;">{r["topic"]} '
                f'<span style="color:#7f8c8d;font-weight:normal;">({r.get("region") or ""})</span></h3>'
            )
            answer = (r["answer"] or "")[:1200]
            answer = answer.replace("\n", "<br>")
            html.append(f'<div style="margin-bottom:12px;">{answer}{"&hellip;" if len(r["answer"] or "") > 1200 else ""}</div>')
            cits = r.get("citations") or []
            if cits:
                links = " &middot; ".join(
                    f'<a href="{c}">[{i + 1}]</a>' for i, c in enumerate(cits[:8])
                )
                html.append(f'<p style="color:#7f8c8d;font-size:0.9em;">Sources: {links}</p>')
    return {"title": "Financial", "html": "\n".join(html), "count": len(rows), "items": rows}


def funding_section(limit: int = 20) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT title, funder, country, currency, amount_max, deadline, url, description
        FROM funding_opportunities
        WHERE discovered_at >= %s
          AND (deadline IS NULL OR deadline >= CURRENT_DATE)
          AND status = 'open'
        ORDER BY relevance_score, deadline NULLS LAST
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Funding & Grants (UK / EU / Switzerland)</h2>']
    if not rows:
        html.append('<p><em>No new funding calls this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            amount = ""
            if r.get("amount_max"):
                amount = f' &middot; {r.get("currency") or "GBP"} {r["amount_max"]:,.0f}'
            deadline = ""
            if r.get("deadline"):
                deadline = f' &middot; deadline <strong>{r["deadline"]}</strong>'
            line = (
                f'<strong>{esc(r["title"])}</strong> ({esc(r.get("country"))})'
                f'{amount}{deadline}'
            )
            if r.get("url"):
                line = f'<a href="{r["url"]}">{line}</a>'
            html.append(f'<li>{line}</li>')
        html.append('</ul>')
    return {"title": "Funding", "html": "\n".join(html), "count": len(rows), "items": rows}


def jobs_section(limit: int = 20) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT title, employer, country, category, url, closing_date
        FROM job_listings
        WHERE discovered_at >= %s
          AND (closing_date IS NULL OR closing_date >= CURRENT_DATE)
        ORDER BY relevance_score, discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Job Listings (EdTech / HE Management)</h2>']
    if not rows:
        html.append('<p><em>No new jobs this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            closing = ""
            if r.get("closing_date"):
                closing = f' &middot; closes <strong>{r["closing_date"]}</strong>'
            line = (
                f'<strong>{esc(r["title"])}</strong> &mdash; {esc(r.get("employer") or "Unknown")} '
                f'({r.get("country") or ""}){closing}'
            )
            if r.get("url"):
                line = f'<a href="{r["url"]}">{line}</a>'
            html.append(f'<li>{line}</li>')
        html.append('</ul>')
    return {"title": "Jobs", "html": "\n".join(html), "count": len(rows), "items": rows}


def film_section(limit: int = 20) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT title, organisation, opp_type, submission_deadline, url
        FROM film_opportunities
        WHERE discovered_at >= %s
          AND (submission_deadline IS NULL OR submission_deadline >= CURRENT_DATE)
          AND status = 'open'
        ORDER BY relevance_score, submission_deadline NULLS LAST
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Film & Script Opportunities</h2>']
    if not rows:
        html.append('<p><em>No new film/script opps this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            deadline = ""
            if r.get("submission_deadline"):
                deadline = f' &middot; deadline <strong>{r["submission_deadline"]}</strong>'
            line = (
                f'<strong>{esc(r["title"])}</strong> &mdash; {esc(r.get("organisation"))} '
                f'<em>({r.get("opp_type") or "opportunity"})</em>{deadline}'
            )
            if r.get("url"):
                line = f'<a href="{r["url"]}">{line}</a>'
            html.append(f'<li>{line}</li>')
        html.append('</ul>')
    return {"title": "Film", "html": "\n".join(html), "count": len(rows), "items": rows}


def gmail_section(limit: int = 25) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT from_email, from_name, subject, category, received_at, body_excerpt
        FROM gmail_items
        WHERE classified_at >= %s
          AND category != 'ignore'
        ORDER BY received_at DESC NULLS LAST
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Inbox Highlights (Gmail)</h2>']
    if not rows:
        html.append('<p><em>No relevant inbox items this week.</em></p>')
    else:
        html.append('<ul style="padding-left:18px;">')
        for r in rows:
            badge = (
                f'<span style="background:#ecf0f1;color:#34495e;'
                f'padding:1px 6px;border-radius:3px;font-size:0.8em;'
                f'margin-right:6px;">{esc(r["category"])}</span>'
            )
            sender = r.get("from_name") or r.get("from_email") or "Unknown"
            html.append(
                f'<li>{badge}<strong>{esc(r["subject"])}</strong> &mdash; {esc(sender)}</li>'
            )
        html.append('</ul>')
    return {"title": "Gmail", "html": "\n".join(html), "count": len(rows), "items": rows}
