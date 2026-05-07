"""Daily FX + interest rate tracker with dramatic-change alerts.

Sources (all free, no API key):
  - ECB: EUR-based rates (GBP, CHF, USD)
  - BoE: UK base rate (Bank Rate)
  - SNB: Swiss policy rate

Alerts when:
  - Any FX rate moves > 1% day-on-day
  - Any interest rate changes at all (they move in 0.25% steps, so any change is news)
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta

import httpx

from ..common import db
from ..common.email_send import send_html
from ..common.logging_setup import get_logger

LOGGER = get_logger("fx.orchestrator")

ECB_URL = "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP+CHF+USD.EUR.SP00.A?lastNObservations=5&format=jsondata"
BOE_URL = "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp?Travel=NIxAZxSUx&FromSeries=1&ToSeries=50&DAT=RNG&FD=1&FM=Jan&FY=2024&TD=31&TM=Dec&TY=2027&FNY=Y&CSVF=CN&html.x=66&html.y=26&SeriesCodes=IUDBEDR&UsingCodes=Y"

FX_ALERT_THRESHOLD = 1.0
INTEREST_RATE_ALERT_THRESHOLD = 0.0

ALERT_RECIPIENT = "richardknapp134@gmail.com"


def _fetch_ecb_rates() -> list[dict]:
    """Fetch latest ECB exchange rates (EUR base)."""
    rows = []
    try:
        with httpx.Client(timeout=30.0) as client:
            r = client.get(ECB_URL)
            r.raise_for_status()
            data = r.json()

        datasets = data.get("dataSets", [{}])[0]
        series = datasets.get("series", {})
        dimensions = data.get("structure", {}).get("dimensions", {}).get("series", [])
        obs_dims = data.get("structure", {}).get("dimensions", {}).get("observation", [])

        currency_dim_idx = 0
        currency_values = []
        for i, d in enumerate(dimensions):
            if d.get("id") == "CURRENCY":
                currency_dim_idx = i
                currency_values = d.get("values", [])
                break

        obs_dates = []
        for d in obs_dims:
            if d.get("id") == "TIME_PERIOD":
                obs_dates = [v["id"] for v in d.get("values", [])]

        for series_key, series_data in series.items():
            key_parts = series_key.split(":")
            cidx = int(key_parts[currency_dim_idx]) if len(key_parts) > currency_dim_idx else 0
            currency = currency_values[cidx]["id"] if cidx < len(currency_values) else "UNK"

            observations = series_data.get("observations", {})
            for obs_idx, obs_val in observations.items():
                rate_val = obs_val[0] if obs_val else None
                if rate_val is None:
                    continue
                obs_date = obs_dates[int(obs_idx)] if int(obs_idx) < len(obs_dates) else None
                if obs_date:
                    rows.append({
                        "base_currency": "EUR",
                        "quote_currency": currency,
                        "rate": float(rate_val),
                        "rate_date": obs_date,
                        "source": "ecb",
                    })

        # Derive GBP/CHF cross rate
        latest_gbp = next((r for r in sorted(rows, key=lambda x: x["rate_date"], reverse=True) if r["quote_currency"] == "GBP"), None)
        latest_chf = next((r for r in sorted(rows, key=lambda x: x["rate_date"], reverse=True) if r["quote_currency"] == "CHF"), None)
        if latest_gbp and latest_chf:
            rows.append({
                "base_currency": "GBP",
                "quote_currency": "CHF",
                "rate": round(latest_chf["rate"] / latest_gbp["rate"], 6),
                "rate_date": latest_gbp["rate_date"],
                "source": "ecb-derived",
            })

    except Exception as exc:
        LOGGER.warning("ECB fetch failed: %s", exc)
    return rows


def _fetch_boe_rate() -> list[dict]:
    """Fetch UK Bank Rate from BoE."""
    rows = []
    try:
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            r = client.get(BOE_URL)
            r.raise_for_status()
            text = r.text

        lines = text.strip().split("\n")
        for line in lines[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 2:
                date_str = parts[0].strip().strip('"')
                rate_str = parts[1].strip().strip('"')
                try:
                    rate = float(rate_str)
                    rows.append({
                        "base_currency": "GBP",
                        "quote_currency": "INTEREST",
                        "rate": rate,
                        "rate_date": date_str,
                        "source": "boe-bank-rate",
                    })
                except ValueError:
                    continue
    except Exception as exc:
        LOGGER.warning("BoE fetch failed: %s", exc)

    if not rows:
        LOGGER.info("BoE CSV empty, using Perplexity fallback")
        try:
            from ..common import perplexity
            res = perplexity.ask(
                "What is the current UK Bank of England base interest rate as of today? "
                "Also what is the current Swiss National Bank policy rate? "
                "Return ONLY two numbers, one per line: UK rate then Swiss rate.",
                model="sonar",
            )
            answer = res["answer"]
            import re
            numbers = re.findall(r"(\d+\.?\d*)\s*%", answer)
            today = date.today().isoformat()
            if len(numbers) >= 1:
                rows.append({"base_currency": "GBP", "quote_currency": "INTEREST",
                             "rate": float(numbers[0]), "rate_date": today, "source": "boe-via-perplexity"})
            if len(numbers) >= 2:
                rows.append({"base_currency": "CHF", "quote_currency": "INTEREST",
                             "rate": float(numbers[1]), "rate_date": today, "source": "snb-via-perplexity"})
        except Exception as exc:
            LOGGER.warning("Perplexity interest rate fallback failed: %s", exc)

    return rows


def _store_rates(rates: list[dict]) -> int:
    inserted = 0
    for r in rates:
        try:
            db.execute(
                """
                INSERT INTO exchange_rates (base_currency, quote_currency, rate, rate_date, source)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (base_currency, quote_currency, rate_date, source) DO NOTHING
                """,
                (r["base_currency"], r["quote_currency"], r["rate"], r["rate_date"], r["source"]),
            )
            inserted += 1
        except Exception:
            pass
    return inserted


def _check_alerts(rates: list[dict]) -> list[dict]:
    """Compare today's rates with yesterday's. Return alerts for big moves."""
    alerts = []
    for r in rates:
        prev = db.fetch_one(
            """
            SELECT rate, rate_date FROM exchange_rates
            WHERE base_currency = %s AND quote_currency = %s
              AND rate_date < %s
            ORDER BY rate_date DESC LIMIT 1
            """,
            (r["base_currency"], r["quote_currency"], r["rate_date"]),
        )
        if not prev:
            continue

        prev_rate = float(prev["rate"])
        curr_rate = float(r["rate"])
        if prev_rate == 0:
            continue

        change_pct = ((curr_rate - prev_rate) / prev_rate) * 100
        is_interest = r["quote_currency"] == "INTEREST"
        threshold = INTEREST_RATE_ALERT_THRESHOLD if is_interest else FX_ALERT_THRESHOLD

        if abs(change_pct) > threshold:
            pair = f"{r['base_currency']}/{r['quote_currency']}"
            direction = "UP" if change_pct > 0 else "DOWN"

            if is_interest:
                msg = (
                    f"INTEREST RATE CHANGE: {r['base_currency']} rate moved {direction} "
                    f"from {prev_rate}% to {curr_rate}% ({change_pct:+.2f}pp)"
                )
            else:
                msg = (
                    f"FX ALERT: {pair} moved {direction} {abs(change_pct):.2f}% "
                    f"({prev_rate:.4f} -> {curr_rate:.4f})"
                )

            alerts.append({
                "alert_type": "interest-rate" if is_interest else "fx-rate",
                "pair": pair,
                "current_rate": curr_rate,
                "previous_rate": prev_rate,
                "change_pct": round(change_pct, 4),
                "message": msg,
            })
    return alerts


def _send_alerts(alerts: list[dict]) -> None:
    if not alerts:
        return

    html = [
        '<div style="background:#e74c3c;color:#fff;padding:16px;border-radius:8px;margin-bottom:16px;">',
        '<h2 style="margin:0;">Workhorse Rate Alert</h2></div>',
    ]
    for a in alerts:
        color = "#27ae60" if a["change_pct"] > 0 else "#c0392b"
        html.append(
            f'<div style="border-left:4px solid {color};padding:12px;margin:8px 0;">'
            f'<strong>{a["message"]}</strong></div>'
        )
    html.append(
        '<p style="color:#7f8c8d;font-size:0.85em;">Automated alert from Workhorse FX tracker.</p>'
    )

    subject = f"RATE ALERT: {', '.join(a['pair'] for a in alerts)} — {date.today().isoformat()}"
    send_html(subject, "\n".join(html), to=ALERT_RECIPIENT)

    for a in alerts:
        db.execute(
            """
            INSERT INTO rate_alerts (alert_type, pair, current_rate, previous_rate, change_pct, message, sent)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            """,
            (a["alert_type"], a["pair"], a["current_rate"], a["previous_rate"], a["change_pct"], a["message"]),
        )

    LOGGER.info("Sent %d rate alerts", len(alerts))


def run(dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("fx.orchestrator")
    LOGGER.info("FX orchestrator run %s", run_id)

    try:
        ecb_rates = _fetch_ecb_rates()
        interest_rates = _fetch_boe_rate()
        all_rates = ecb_rates + interest_rates

        LOGGER.info("Fetched %d ECB rates, %d interest rates", len(ecb_rates), len(interest_rates))

        if dry_run:
            for r in all_rates:
                print(f"  {r['base_currency']}/{r['quote_currency']} = {r['rate']} ({r['rate_date']}, {r['source']})")
            print(f"\n{len(all_rates)} rates (dry run)")
            db.finish_scraper_run(run_id, "dry_run", fetched=len(all_rates))
            return

        inserted = _store_rates(all_rates)
        LOGGER.info("Stored %d rates", inserted)

        alerts = _check_alerts(all_rates)
        if alerts:
            LOGGER.info("ALERTS: %s", [a["message"] for a in alerts])
            _send_alerts(alerts)
        else:
            LOGGER.info("No rate alerts triggered")

        db.finish_scraper_run(run_id, "ok", fetched=len(all_rates), inserted=inserted)

    except Exception as exc:
        LOGGER.exception("FX orchestrator failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc))
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
