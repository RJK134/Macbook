"""Scrape cost-of-living estimates for UK university cities.

Uses Numbeo's public per-city pages.
  https://www.numbeo.com/cost-of-living/in/<city>
"""

import re

from bs4 import BeautifulSoup

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_html

LOGGER = get_logger("courses.cost_of_living")

# Major UK university cities; expand over time.
CITIES = [
    ("London", "UK"),
    ("Manchester", "UK"),
    ("Birmingham", "UK"),
    ("Leeds", "UK"),
    ("Glasgow", "UK"),
    ("Edinburgh", "UK"),
    ("Liverpool", "UK"),
    ("Bristol", "UK"),
    ("Sheffield", "UK"),
    ("Newcastle-upon-Tyne", "UK"),
    ("Nottingham", "UK"),
    ("Cardiff", "UK"),
    ("Belfast", "UK"),
    ("Coventry", "UK"),
    ("Oxford", "UK"),
    ("Cambridge", "UK"),
    ("York", "UK"),
    ("Bath", "UK"),
    ("Exeter", "UK"),
    ("Southampton", "UK"),
    ("Durham", "UK"),
    ("Reading", "UK"),
    ("Brighton", "UK"),
    ("Aberdeen", "UK"),
    ("St-Andrews", "UK"),
]

GBP_PATTERN = re.compile(r"[££]\s*([\d,]+(?:\.\d+)?)")


def _fetch(city: str) -> str:
    slug = city.replace(" ", "-")
    url = f"https://www.numbeo.com/cost-of-living/in/{slug}"
    LOGGER.info("GET %s", url)
    return http.get(url).text


def _parse_amount(text: str) -> float | None:
    m = GBP_PATTERN.search(text or "")
    if not m:
        return None
    return float(m.group(1).replace(",", ""))


def _parse(html: str, city: str, country: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    rows: dict[str, float | None] = {
        "rent_1bed_gbp": None,
        "rent_shared_gbp": None,
        "groceries_monthly_gbp": None,
        "transport_monthly_gbp": None,
        "utilities_monthly_gbp": None,
    }
    # Numbeo's cost-of-living table: row label + price column
    for tr in soup.select("table.data_wide_table tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).lower()
        amount = _parse_amount(cells[1].get_text())
        if not amount:
            continue
        if "apartment (1 bedroom) outside" in label:
            rows["rent_1bed_gbp"] = amount
        elif "milk" in label or "bread" in label:
            # Approximate groceries via item proxies (improved later)
            rows["groceries_monthly_gbp"] = (rows["groceries_monthly_gbp"] or 0) + amount * 30
        elif "monthly pass" in label and "transport" in label:
            rows["transport_monthly_gbp"] = amount
        elif "utilities" in label:
            rows["utilities_monthly_gbp"] = amount

    total = sum(v or 0 for v in rows.values())
    return {
        "city": city,
        "country": country,
        "source": "numbeo",
        "source_url": f"https://www.numbeo.com/cost-of-living/in/{city.replace(' ', '-')}",
        "total_estimated_monthly_gbp": total or None,
        **rows,
    }


def scrape() -> list[dict]:
    out: list[dict] = []
    for city, country in CITIES:
        try:
            html = _fetch(city)
            write_raw_html("courses", f"col-{city.lower()}", html)
            out.append(_parse(html, city, country))
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning("Cost of living for %s failed: %s", city, exc)
    LOGGER.info("Cost of living: %d city records", len(out))
    return out
