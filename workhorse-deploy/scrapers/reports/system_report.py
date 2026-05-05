"""Weekly system report with API cost tracking.

Sent every Sunday at 06:15, after the master digest.
Includes: full activity breakdown, token usage, estimated costs, storage status.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date, timedelta
from html import escape as html_escape

from ..common import db, email_send
from ..common.logging_setup import get_logger

LOGGER = get_logger("reports.system_report")


def _week_range() -> tuple[date, date]:
    today = date.today()
    start = today - timedelta(days=7)
    return start, today


def _disk_usage() -> list[dict]:
    try:
        result = subprocess.run(
            ["df", "-h", "--output=source,size,used,avail,pcent,target"],
            capture_output=True, text=True, timeout=10,
        )
        rows = []
        for line in result.stdout.strip().split("\n")[1:]:
            parts = line.split()
            if len(parts) >= 6 and not any(x in parts[0] for x in ["tmpfs", "loop", "snap"]):
                rows.append({
                    "source": parts[0],
                    "size": parts[1],
                    "used": parts[2],
                    "avail": parts[3],
                    "pct": parts[4],
                    "mount": " ".join(parts[5:]),
                })
        return rows
    except Exception:
        return []


def _gdrive_usage() -> str:
    try:
        result = subprocess.run(
            ["rclone", "about", "gdrive5tb:", "--json"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            used_gb = data.get("used", 0) / (1024**3)
            total_gb = data.get("total", 0) / (1024**3)
            return f"{used_gb:.1f} GB / {total_gb:.0f} GB"
    except Exception:
        pass
    return "unavailable"


def _scraper_runs(start: date) -> list[dict]:
    return db.fetch_all(
        """
        SELECT scraper_name, status, started_at, finished_at,
               items_fetched, items_inserted, items_updated, items_skipped,
               error_message
        FROM scraper_runs
        WHERE started_at >= %s
        ORDER BY started_at DESC
        """,
        (start,),
    )


def _api_usage_summary(start: date) -> list[dict]:
    return db.fetch_all(
        """
        SELECT
            service,
            model,
            COUNT(*) AS calls,
            SUM(tokens_input) AS total_input,
            SUM(tokens_output) AS total_output,
            SUM(tokens_total) AS total_tokens,
            SUM(cost_usd) AS total_cost,
            SUM(CASE WHEN cached THEN 1 ELSE 0 END) AS cached_calls
        FROM api_usage
        WHERE created_at >= %s
        GROUP BY service, model
        ORDER BY total_cost DESC
        """,
        (start,),
    )


def _api_usage_by_day(start: date) -> list[dict]:
    return db.fetch_all(
        """
        SELECT
            created_at::date AS day,
            service,
            COUNT(*) AS calls,
            SUM(tokens_total) AS tokens,
            SUM(cost_usd) AS cost
        FROM api_usage
        WHERE created_at >= %s
        GROUP BY day, service
        ORDER BY day, service
        """,
        (start,),
    )


def _esc(val: object) -> str:
    return html_escape(str(val)) if val else ""


def build_html() -> str:
    start, today = _week_range()
    api_summary = _api_usage_summary(start)
    api_daily = _api_usage_by_day(start)
    runs = _scraper_runs(start)
    disks = _disk_usage()
    gdrive = _gdrive_usage()

    total_cost = sum(float(r["total_cost"] or 0) for r in api_summary)
    total_tokens = sum(int(r["total_tokens"] or 0) for r in api_summary)
    total_calls = sum(int(r["calls"] or 0) for r in api_summary)

    html = [f'''
<html><head><meta charset="utf-8"><title>Workhorse System Report</title></head>
<body style="font-family:Arial,sans-serif;max-width:900px;margin:24px auto;color:#2c3e50;">

<div style="background:linear-gradient(135deg,#1a5276,#2471a3);color:#fff;padding:24px;border-radius:8px;margin-bottom:24px;">
  <h1 style="margin:0;font-size:28px;">Workhorse System Report</h1>
  <p style="margin:8px 0 0 0;opacity:0.85;">Week: {start.isoformat()} to {today.isoformat()}</p>
</div>

<div style="display:flex;gap:16px;margin-bottom:24px;flex-wrap:wrap;">
  <div style="flex:1;min-width:200px;background:#e8f8f5;padding:16px;border-radius:8px;text-align:center;">
    <div style="font-size:32px;font-weight:bold;color:#1abc9c;">${total_cost:.4f}</div>
    <div style="color:#666;margin-top:4px;">Total API Cost (USD)</div>
  </div>
  <div style="flex:1;min-width:200px;background:#eaf2f8;padding:16px;border-radius:8px;text-align:center;">
    <div style="font-size:32px;font-weight:bold;color:#2980b9;">{total_tokens:,}</div>
    <div style="color:#666;margin-top:4px;">Total Tokens</div>
  </div>
  <div style="flex:1;min-width:200px;background:#fef9e7;padding:16px;border-radius:8px;text-align:center;">
    <div style="font-size:32px;font-weight:bold;color:#f39c12;">{total_calls}</div>
    <div style="color:#666;margin-top:4px;">API Calls</div>
  </div>
</div>
''']

    # API cost breakdown table
    html.append('<h2 style="color:#2c3e50;">API Token &amp; Cost Breakdown</h2>')
    html.append('''
<table cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;margin-bottom:20px;">
<thead><tr style="background:#ecf0f1;">
  <th align="left">Service</th><th align="left">Model</th><th align="right">Calls</th>
  <th align="right">Input Tokens</th><th align="right">Output Tokens</th>
  <th align="right">Total Tokens</th><th align="right">Cost (USD)</th><th align="right">Cached</th>
</tr></thead><tbody>
''')
    for r in api_summary:
        html.append(
            f'<tr style="border-bottom:1px solid #ecf0f1;">'
            f'<td><strong>{r["service"]}</strong></td>'
            f'<td>{r["model"]}</td>'
            f'<td align="right">{r["calls"]}</td>'
            f'<td align="right">{int(r["total_input"] or 0):,}</td>'
            f'<td align="right">{int(r["total_output"] or 0):,}</td>'
            f'<td align="right">{int(r["total_tokens"] or 0):,}</td>'
            f'<td align="right"><strong>${float(r["total_cost"] or 0):.4f}</strong></td>'
            f'<td align="right">{r["cached_calls"]}</td>'
            f'</tr>'
        )
    html.append(
        f'<tr style="background:#ecf0f1;font-weight:bold;">'
        f'<td colspan="6">TOTAL</td>'
        f'<td align="right">${total_cost:.4f}</td>'
        f'<td></td></tr>'
    )
    html.append('</tbody></table>')

    # Daily breakdown
    if api_daily:
        html.append('<h2 style="color:#2c3e50;">Daily API Usage</h2>')
        html.append('''
<table cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;margin-bottom:20px;">
<thead><tr style="background:#ecf0f1;">
  <th align="left">Date</th><th align="left">Service</th><th align="right">Calls</th>
  <th align="right">Tokens</th><th align="right">Cost (USD)</th>
</tr></thead><tbody>
''')
        for r in api_daily:
            html.append(
                f'<tr style="border-bottom:1px solid #ecf0f1;">'
                f'<td>{r["day"]}</td><td>{r["service"]}</td>'
                f'<td align="right">{r["calls"]}</td>'
                f'<td align="right">{int(r["tokens"] or 0):,}</td>'
                f'<td align="right">${float(r["cost"] or 0):.4f}</td>'
                f'</tr>'
            )
        html.append('</tbody></table>')

    # Scraper runs
    ok_runs = [r for r in runs if r["status"] == "ok"]
    err_runs = [r for r in runs if r["status"] == "error"]
    html.append(f'<h2 style="color:#2c3e50;">Scraper Activity</h2>')
    html.append(
        f'<p>Runs this week: <strong>{len(runs)}</strong> '
        f'(<span style="color:#27ae60;">{len(ok_runs)} ok</span>, '
        f'<span style="color:#c0392b;">{len(err_runs)} errors</span>)</p>'
    )
    if err_runs:
        html.append('<h3 style="color:#c0392b;">Errors</h3><ul>')
        for r in err_runs[:10]:
            html.append(
                f'<li><strong>{r["scraper_name"]}</strong> ({r["started_at"]}): '
                f'{_esc((r.get("error_message") or "")[:200])}</li>'
            )
        html.append('</ul>')

    html.append('''
<table cellspacing="0" cellpadding="6" style="border-collapse:collapse;width:100%;margin-bottom:20px;font-size:0.9em;">
<thead><tr style="background:#ecf0f1;">
  <th align="left">Scraper</th><th align="left">Status</th><th align="right">Fetched</th>
  <th align="right">Inserted</th><th align="right">Updated</th><th align="left">When</th>
</tr></thead><tbody>
''')
    for r in runs[:30]:
        status_color = "#27ae60" if r["status"] == "ok" else "#c0392b"
        html.append(
            f'<tr style="border-bottom:1px solid #ecf0f1;">'
            f'<td>{r["scraper_name"]}</td>'
            f'<td style="color:{status_color};">{r["status"]}</td>'
            f'<td align="right">{r.get("items_fetched") or 0}</td>'
            f'<td align="right">{r.get("items_inserted") or 0}</td>'
            f'<td align="right">{r.get("items_updated") or 0}</td>'
            f'<td>{str(r["started_at"])[:16] if r.get("started_at") else ""}</td>'
            f'</tr>'
        )
    html.append('</tbody></table>')

    # Storage
    html.append('<h2 style="color:#2c3e50;">Storage Status</h2>')
    html.append('''
<table cellspacing="0" cellpadding="8" style="border-collapse:collapse;width:100%;margin-bottom:20px;">
<thead><tr style="background:#ecf0f1;">
  <th align="left">Mount</th><th align="right">Size</th><th align="right">Used</th>
  <th align="right">Free</th><th align="right">Use%</th>
</tr></thead><tbody>
''')
    for d in disks:
        pct_num = int(d["pct"].replace("%", "")) if d["pct"].replace("%", "").isdigit() else 0
        color = "#c0392b" if pct_num > 85 else "#f39c12" if pct_num > 70 else "#27ae60"
        html.append(
            f'<tr style="border-bottom:1px solid #ecf0f1;">'
            f'<td>{d["mount"]}</td>'
            f'<td align="right">{d["size"]}</td>'
            f'<td align="right">{d["used"]}</td>'
            f'<td align="right">{d["avail"]}</td>'
            f'<td align="right" style="color:{color};font-weight:bold;">{d["pct"]}</td>'
            f'</tr>'
        )
    html.append(
        f'<tr style="border-bottom:1px solid #ecf0f1;">'
        f'<td>Google Drive (gdrive5tb)</td>'
        f'<td align="right" colspan="4">{gdrive}</td></tr>'
    )
    html.append('</tbody></table>')

    html.append('''
<hr style="border:none;border-top:1px solid #eee;margin:24px 0;">
<p style="color:#7f8c8d;font-size:0.85em;">
  Workhorse System Report — generated automatically every Sunday.<br>
  API costs are estimates based on published per-token pricing.
</p>
</body></html>
''')

    return "\n".join(html)


def run(dry_run: bool = False) -> None:
    LOGGER.info("Building system report...")
    html = build_html()
    today = date.today().isoformat()
    subject = f"Workhorse System Report — {today}"

    if dry_run:
        print(subject)
        print(html[:3000])
        print("... (truncated)")
        return

    email_send.send_html(subject, html, to="richardknapp134@gmail.com")
    LOGGER.info("System report sent: %s", subject)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    try:
        run(dry_run=args.dry_run)
    except Exception as exc:
        LOGGER.exception("System report failed: %s", exc)
        sys.exit(1)
