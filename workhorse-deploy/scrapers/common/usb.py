"""Helpers for writing scraped data to the 1TB USB at /mnt/usb-archive."""

import json
from datetime import date, datetime
from pathlib import Path

from .config import USB_ROOT


def _ym() -> str:
    return datetime.utcnow().strftime("%Y-%m")


def _iso_week() -> str:
    today = date.today()
    iso = today.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def raw_dir(area: str) -> Path:
    """e.g. /mnt/usb-archive/raw/courses/2026-04/ — created on demand."""
    p = USB_ROOT / "raw" / area / _ym()
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_raw_html(area: str, slug: str, html: str) -> Path:
    """Save raw scraped HTML for audit/replay."""
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    path = raw_dir(area) / f"{ts}-{slug}.html"
    path.write_text(html, encoding="utf-8", errors="ignore")
    return path


def write_raw_json(area: str, slug: str, payload: dict | list) -> Path:
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    path = raw_dir(area) / f"{ts}-{slug}.json"
    path.write_text(
        json.dumps(payload, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    return path


def reports_dir() -> Path:
    p = USB_ROOT / "reports" / _iso_week()
    p.mkdir(parents=True, exist_ok=True)
    return p


def databases_dir() -> Path:
    p = USB_ROOT / "databases"
    p.mkdir(parents=True, exist_ok=True)
    return p


def logs_dir(kind: str = "scrapers") -> Path:
    p = USB_ROOT / "logs" / kind
    p.mkdir(parents=True, exist_ok=True)
    return p
