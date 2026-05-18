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


_LOOKBACK_DAYS = 7


def set_lookback_days(days: int) -> None:
    """Allow callers to set the lookback window (e.g. 3 for mid-week summaries)."""
    global _LOOKBACK_DAYS
    _LOOKBACK_DAYS = max(1, int(days))


def _week_window() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=_LOOKBACK_DAYS)
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
    # 'industry-news' rows are press articles, not grants the operator
    # can apply to — surfaced separately. relevance_score in this table
    # uses 1 (top) → 5 (noise); 3 is the open-grant default.
    rows = db.fetch_all(
        """
        SELECT title, funder, country, currency, amount_max, deadline, url, description
        FROM funding_opportunities
        WHERE discovered_at >= %s
          AND (deadline IS NULL OR deadline >= CURRENT_DATE)
          AND status = 'open'
          AND COALESCE(category, '') <> 'industry-news'
          AND COALESCE(relevance_score, 3) <= 3
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
    # job_listings.relevance_score: 1 = high (EdTech/HE-specific titles),
    # 3 = medium (mentions university/college/student), 5 = noise (no
    # edu signal). The default sort by score still works, but we now
    # drop the noise tier so generic remote SWE jobs don't surface.
    rows = db.fetch_all(
        """
        SELECT title, employer, country, category, url, closing_date
        FROM job_listings
        WHERE discovered_at >= %s
          AND (closing_date IS NULL OR closing_date >= CURRENT_DATE)
          AND COALESCE(relevance_score, 5) <= 3
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


def coursepulse_section(limit: int = 20) -> dict:
    start, _ = _week_window()
    pathways = db.fetch_all(
        """
        SELECT subject_area, career_title, demand_trend, median_salary_gbp,
               salary_5yr_gbp, roi_score, skills_overlap, confidence
        FROM course_career_pathways
        WHERE updated_at >= %s
        ORDER BY roi_score DESC NULLS LAST
        LIMIT %s
        """,
        (start, limit),
    )
    insights = db.fetch_all(
        """
        SELECT insight_type, title, summary, source, region
        FROM coursepulse_insights
        WHERE created_at >= %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">CoursePulse (Curriculum Intelligence)</h2>']

    if pathways:
        html.append('<h3 style="color:#34495e;">Career Pathways (updated this week)</h3>')
        html.append(
            '<table cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;font-size:0.9em;">'
            '<thead><tr style="background:#ecf0f1;">'
            '<th align="left">Subject</th><th align="left">Career</th>'
            '<th align="left">Trend</th><th align="right">Salary</th>'
            '<th align="right">5yr Salary</th><th align="right">ROI%</th>'
            '</tr></thead><tbody>'
        )
        for p in pathways:
            trend_color = {"growing": "#27ae60", "declining": "#c0392b"}.get(p.get("demand_trend") or "", "#7f8c8d")
            salary = f"£{p['median_salary_gbp']:,.0f}" if p.get("median_salary_gbp") else "-"
            salary5 = f"£{p['salary_5yr_gbp']:,.0f}" if p.get("salary_5yr_gbp") else "-"
            roi = f"{p['roi_score']:.0f}%" if p.get("roi_score") is not None else "-"
            html.append(
                f'<tr style="border-bottom:1px solid #ecf0f1;">'
                f'<td>{esc(p["subject_area"])}</td>'
                f'<td><strong>{esc(p["career_title"])}</strong></td>'
                f'<td style="color:{trend_color};">{p.get("demand_trend") or "?"}</td>'
                f'<td align="right">{salary}</td>'
                f'<td align="right">{salary5}</td>'
                f'<td align="right">{roi}</td></tr>'
            )
        html.append('</tbody></table>')

    if insights:
        html.append('<h3 style="color:#34495e;">Curriculum Insights</h3><ul>')
        type_labels = {
            "curriculum-gap": "GAP", "curriculum-risk": "RISK",
            "emerging-programme": "NEW", "investment-signal": "INVEST",
            "credential-trend": "CREDENTIAL",
        }
        for i in insights:
            badge_text = type_labels.get(i["insight_type"], i["insight_type"])
            badge_color = {"GAP": "#e74c3c", "RISK": "#e67e22", "NEW": "#27ae60", "INVEST": "#3498db"}.get(badge_text, "#7f8c8d")
            html.append(
                f'<li><span style="background:{badge_color};color:#fff;padding:2px 6px;'
                f'border-radius:3px;font-size:0.75em;">{badge_text}</span> '
                f'<strong>{esc(i["title"])}</strong> ({esc(i["source"])} / {esc(i.get("region") or "")})'
                f'<br><span style="color:#666;font-size:0.9em;">{esc((i["summary"] or "")[:200])}</span></li>'
            )
        html.append('</ul>')

    if not pathways and not insights:
        html.append('<p><em>No CoursePulse data this week — run the orchestrator.</em></p>')

    count = len(pathways) + len(insights)
    return {"title": "CoursePulse", "html": "\n".join(html), "count": count, "items": pathways + insights}


def research_section(limit: int = 15) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT topic, region, source, answer, citations, created_at
        FROM financial_research
        WHERE created_at >= %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">AI Research (Perplexity + Gemini)</h2>']
    if not rows:
        html.append('<p><em>No research queries ran this week.</em></p>')
    else:
        for r in rows:
            source_badge = (
                f'<span style="background:{"#3498db" if r["source"] == "perplexity" else "#e67e22"};'
                f'color:#fff;padding:2px 8px;border-radius:3px;font-size:0.75em;">'
                f'{esc(r["source"])}</span>'
            )
            html.append(
                f'<h3 style="margin-bottom:4px;">{source_badge} {esc(r["topic"])} '
                f'<span style="color:#7f8c8d;font-weight:normal;">({esc(r.get("region") or "")})</span></h3>'
            )
            raw_answer = r["answer"] or ""
            answer_html = esc(raw_answer[:800]).replace("\n", "<br>")
            html.append(
                f'<div style="margin-bottom:8px;">{answer_html}'
                f'{"&hellip;" if len(raw_answer) > 800 else ""}</div>'
            )
            cits = r.get("citations") or []
            if cits:
                links = " &middot; ".join(
                    f'<a href="{c}">[{i + 1}]</a>' for i, c in enumerate(cits[:6])
                )
                html.append(f'<p style="color:#7f8c8d;font-size:0.85em;">Sources: {links}</p>')
    return {"title": "AI Research", "html": "\n".join(html), "count": len(rows), "items": rows}


def gmail_section(limit: int = 25) -> dict:
    start, _ = _week_window()
    # 'learning' is dev-tools chatter the user doesn't need in a weekly
    # business digest. Self-emails are notes-to-self.
    rows = db.fetch_all(
        """
        SELECT from_email, from_name, subject, category, received_at, body_excerpt
        FROM gmail_items
        WHERE classified_at >= %s
          AND category NOT IN ('ignore', 'learning')
          AND lower(COALESCE(from_email, '')) <> 'richardknapp134@gmail.com'
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


def procurement_section(limit: int = 15) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT title, buyer, value_max, currency, deadline_date, source, url, category
        FROM procurement_opportunities
        WHERE discovered_at >= %s
          AND relevance_score >= 3
          AND category <> 'rejected'
          AND (deadline_date IS NULL OR deadline_date >= CURRENT_DATE)
        ORDER BY relevance_score DESC,
                 (deadline_date IS NULL), deadline_date ASC,
                 value_max DESC NULLS LAST
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Procurement (Future Horizons + builds)</h2>']
    if not rows:
        html.append('<p><em>No procurement opportunities discovered this week.</em></p>')
    else:
        html.append('<ul style="padding-left:20px;">')
        for r in rows:
            value = ""
            if r.get("value_max"):
                value = f"{r['currency']} {r['value_max']:,.0f}"
            deadline = f" — closes {r['deadline_date']}" if r.get("deadline_date") else ""
            buyer = f" ({esc(r['buyer'])})" if r.get("buyer") else ""
            html.append(
                f'<li><strong><a href="{esc(r["url"])}">{esc(r["title"])}</a></strong>'
                f'{buyer}<br>'
                f'<span style="color:#666;font-size:0.9em;">{esc(r.get("source"))} '
                f'· {esc(r.get("category") or "")} · {value}{deadline}</span></li>'
            )
        html.append('</ul>')
    return {"title": "Procurement", "html": "\n".join(html), "count": len(rows), "items": rows}


def education_resources_section(limit: int = 15) -> dict:
    start, _ = _week_window()
    # Drop rows that fell through the scraper-side classifier without a
    # real subject (legacy ted-ed imports, perplexity rows with empty
    # subject, etc.) — they were the main source of irrelevant noise.
    rows = db.fetch_all(
        """
        SELECT subject, level, exam_board, resource_type, title, source, url
        FROM education_resources
        WHERE discovered_at >= %s
          AND subject IS NOT NULL
          AND subject <> ''
          AND lower(subject) <> 'general'
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Education Resources (Maieus / Maieus2)</h2>']
    if not rows:
        html.append('<p><em>No new education resources this week.</em></p>')
    else:
        html.append('<ul style="padding-left:20px;">')
        for r in rows:
            tag = f"[{r['level'] or '-'} {r.get('exam_board') or ''}]".strip()
            html.append(
                f'<li><strong><a href="{esc(r["url"])}">{esc(r["title"])}</a></strong>'
                f' <span style="color:#888;font-size:0.85em;">{esc(tag)}</span><br>'
                f'<span style="color:#666;font-size:0.9em;">{esc(r["subject"])} · '
                f'{esc(r["resource_type"])} · {esc(r["source"])}</span></li>'
            )
        html.append('</ul>')
    return {"title": "Education Resources", "html": "\n".join(html), "count": len(rows), "items": rows}


def sen_section(limit: int = 12) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT category, title, source, url, applies_to, published_date, description
        FROM sen_resources
        WHERE discovered_at >= %s
        ORDER BY discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">SEN &amp; Excluded Learners</h2>']
    if not rows:
        html.append('<p><em>No new SEN resources this week.</em></p>')
    else:
        html.append('<ul style="padding-left:20px;">')
        for r in rows:
            badge = (
                f'<span style="background:#9b59b6;color:#fff;padding:2px 6px;'
                f'border-radius:3px;font-size:0.75em;">{esc(r["category"] or "send")}</span>'
            )
            html.append(
                f'<li>{badge} <strong><a href="{esc(r["url"])}">{esc(r["title"])}</a></strong>'
                f' <span style="color:#888;font-size:0.85em;">{esc(r.get("applies_to") or "")}</span><br>'
                f'<span style="color:#666;font-size:0.9em;">{esc((r.get("description") or "")[:200])}</span></li>'
            )
        html.append('</ul>')
    return {"title": "SEN", "html": "\n".join(html), "count": len(rows), "items": rows}


def shakespeare_section(limit: int = 12) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT play, format, audience, resource_type, title, source, url, engagement_score
        FROM shakespeare_resources
        WHERE discovered_at >= %s
        ORDER BY engagement_score DESC NULLS LAST, discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Shakespeare Engagement</h2>']
    if not rows:
        html.append('<p><em>No new Shakespeare content discovered this week.</em></p>')
    else:
        html.append('<ul style="padding-left:20px;">')
        for r in rows:
            play = f' <em>({esc(r["play"])})</em>' if r.get("play") else ""
            html.append(
                f'<li><strong><a href="{esc(r["url"])}">{esc(r["title"])}</a></strong>{play}<br>'
                f'<span style="color:#666;font-size:0.9em;">{esc(r["resource_type"])} · '
                f'{esc(r.get("format") or "")} · {esc(r.get("audience") or "")} · {esc(r["source"])}</span></li>'
            )
        html.append('</ul>')
    return {"title": "Shakespeare", "html": "\n".join(html), "count": len(rows), "items": rows}


def finance_bulletins_section(limit: int = 12) -> dict:
    start, _ = _week_window()
    rows = db.fetch_all(
        """
        SELECT source, category, title, url, summary, published_date
        FROM finance_bulletins
        WHERE discovered_at >= %s
        ORDER BY published_date DESC NULLS LAST, discovered_at DESC
        LIMIT %s
        """,
        (start, limit),
    )
    html = ['<h2 style="color:#2c3e50;">Finance Bulletins (HMRC / FCA / BoE / DfE / ONS)</h2>']
    if not rows:
        html.append('<p><em>No new finance bulletins this week.</em></p>')
    else:
        html.append('<ul style="padding-left:20px;">')
        for r in rows:
            badge_color = {"hmrc": "#e74c3c", "fca": "#3498db", "boe": "#27ae60",
                           "dfe": "#f39c12", "ons": "#7f8c8d"}.get(r["source"], "#95a5a6")
            badge = (
                f'<span style="background:{badge_color};color:#fff;padding:2px 6px;'
                f'border-radius:3px;font-size:0.75em;">{esc(r["source"].upper())}</span>'
            )
            html.append(
                f'<li>{badge} <strong><a href="{esc(r["url"])}">{esc(r["title"])}</a></strong>'
                f' <span style="color:#888;font-size:0.85em;">{esc(r["category"] or "")}</span><br>'
                f'<span style="color:#666;font-size:0.9em;">{esc((r.get("summary") or "")[:180])}</span></li>'
            )
        html.append('</ul>')
    return {"title": "Finance Bulletins", "html": "\n".join(html), "count": len(rows), "items": rows}
