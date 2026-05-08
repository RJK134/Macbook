"""HESA Open Data (CC-BY) CSV downloads from data.gov.uk.

Provides official UK HE statistics: student numbers, outcomes,
demographics per institution. CC-BY licensed — commercially usable
with attribution.
"""

from __future__ import annotations

import csv
import io

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("courses.hesa")

HESA_STUDENT_URL = (
    "https://www.hesa.ac.uk/data-and-analysis/students/table-1.csv"
)


def scrape() -> list[dict]:
    """Download HESA student enrolment data and return institution-level records."""
    out: list[dict] = []
    try:
        LOGGER.info("Downloading HESA student data CSV")
        r = http.get(HESA_STUDENT_URL, timeout=60.0)
        reader = csv.DictReader(io.StringIO(r.text))
        for row in reader:
            provider = row.get("HE provider") or row.get("Provider") or ""
            if not provider or len(provider) < 3:
                continue
            out.append({
                "provider": provider.strip(),
                "title": f"HESA enrolment stats: {provider.strip()}",
                "source": "hesa",
                "raw_data": dict(row),
            })
        write_raw_json("courses", "hesa-students", {"rows": len(out)})
        LOGGER.info("HESA: %d institution records", len(out))
    except Exception as exc:
        LOGGER.warning("HESA download failed: %s", exc)
    return out
