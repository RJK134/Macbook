"""Per-area weekly report generator.

Writes individual HTML reports to /mnt/usb-archive/reports/<ISO-week>/
so the user can drill into a single area on demand without spawning
a separate email per area.
"""

from __future__ import annotations

from datetime import date

from ..common import db
from ..common.logging_setup import get_logger
from ..common.usb import reports_dir
from . import sections

LOGGER = get_logger("reports.per_area")

AREA_FUNCS = {
    "courses": sections.courses_section,
    "job_trends": sections.job_trends_section,
    "financial": sections.financial_section,
    "funding": sections.funding_section,
    "jobs": sections.jobs_section,
    "film": sections.film_section,
    "coursepulse": sections.coursepulse_section,
    "research": sections.research_section,
    "procurement": sections.procurement_section,
    "education_resources": sections.education_resources_section,
    "sen": sections.sen_section,
    "shakespeare": sections.shakespeare_section,
    "finance_bulletins": sections.finance_bulletins_section,
    "gmail": sections.gmail_section,
}


def _wrap(area_title: str, body_html: str) -> str:
    today = date.today().isoformat()
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f'<title>{area_title} Report — {today}</title></head>'
        '<body style="font-family:Arial,sans-serif;max-width:800px;margin:24px auto;">'
        f'<h1>{area_title} Report</h1>'
        f'<p style="color:#666;">Week ending {today}</p>'
        f'{body_html}'
        '</body></html>'
    )


def _log_digest(area: str, count: int, file_path: str) -> None:
    week_start = date.today().toordinal()
    from datetime import date as dt
    from datetime import timedelta as td
    today = dt.today()
    monday = today - td(days=today.weekday())
    sunday = monday + td(days=6)
    db.execute(
        """
        INSERT INTO weekly_digests (digest_area, week_start, week_end, item_count, file_path)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (digest_area, week_start) DO UPDATE
          SET item_count = EXCLUDED.item_count,
              file_path = EXCLUDED.file_path
        """,
        (area, monday, sunday, count, file_path),
    )


def generate(area: str) -> str:
    """Generate one area report and return its file path."""
    fn = AREA_FUNCS[area]
    section = fn()
    html = _wrap(section["title"], section["html"])
    out = reports_dir() / f"{area}-report.html"
    out.write_text(html, encoding="utf-8")
    _log_digest(area, section["count"], str(out))
    LOGGER.info("Wrote %s (%d items) to %s", area, section["count"], out)
    return str(out)


def generate_all() -> dict[str, str]:
    return {area: generate(area) for area in AREA_FUNCS}


if __name__ == "__main__":
    paths = generate_all()
    for area, p in paths.items():
        print(f"{area}: {p}")
