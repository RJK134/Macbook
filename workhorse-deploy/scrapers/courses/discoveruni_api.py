"""Discover Uni / Unistats API client.

The Discover Uni dataset provides ~21,500 UK HE programmes with NSS
satisfaction scores, graduate outcome data, entry qualifications,
continuation rates, and subject codes. Licensed under HESA 'With Rights'
which explicitly permits commercial exploitation.

Bulk XML download:
  https://discoveruni.gov.uk/wp-content/themes/discoveruni/data/dataset.xml

We download the XML bulk file (refreshed weekly by OfS) and parse it
into structured course records.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from ..common import http
from ..common.logging_setup import get_logger
from ..common.usb import write_raw_json

LOGGER = get_logger("courses.discoveruni_api")

DATASET_URL = "https://discoveruni.gov.uk/wp-content/themes/discoveruni/data/dataset.xml"


def _parse_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out: list[dict] = []
    for inst in root.iter("INSTITUTION"):
        ukprn = (inst.findtext("UKPRN") or "").strip()
        provider = (inst.findtext("PUBUKPRN_NAME") or inst.findtext("LEGAL_NAME") or "").strip()
        for course in inst.iter("KISCOURSE"):
            title = (course.findtext("TITLE") or "").strip()
            if not title:
                continue
            kiscourseid = (course.findtext("KISCOURSEID") or "").strip()
            ucas_code = (course.findtext("UCASPROGID") or "").strip()
            qual = (course.findtext("KISTYPE") or "").strip()
            mode = (course.findtext("KISMODE") or "").strip()
            study_mode = {"1": "full-time", "2": "part-time", "3": "both"}.get(mode, mode)
            location = (course.findtext("LOCNAME") or "").strip()
            subject = (course.findtext("SBJ") or course.findtext("SUBJLABEL") or "").strip()
            # NSS satisfaction
            nss_el = course.find(".//NSS")
            nss_q27 = None
            if nss_el is not None:
                nss_q27 = nss_el.findtext("Q27")
            # Salary data
            salary_el = course.find(".//SALARY")
            median_salary = None
            if salary_el is not None:
                median_salary = salary_el.findtext("MED")
            # Entry tariff
            entry_el = course.find(".//ENTRY")
            entry_tariff = None
            if entry_el is not None:
                entry_tariff = entry_el.findtext("TARIFF")

            out.append({
                "ucas_code": ucas_code or None,
                "provider": provider or "Unknown",
                "title": title,
                "qualification": qual or None,
                "subject_area": subject or None,
                "study_mode": study_mode or None,
                "location_city": location or None,
                "location_country": "UK",
                "url": f"https://discoveruni.gov.uk/course-details/{ukprn}/{kiscourseid}/" if ukprn and kiscourseid else None,
                "source": "discoveruni-api",
                "raw_data": {
                    "ukprn": ukprn,
                    "kiscourseid": kiscourseid,
                    "nss_overall_satisfaction": nss_q27,
                    "median_salary_6mo": median_salary,
                    "entry_tariff": entry_tariff,
                },
            })
    return out


def scrape() -> list[dict]:
    LOGGER.info("Downloading Discover Uni bulk XML dataset")
    try:
        r = http.get(DATASET_URL, timeout=120.0)
        xml_text = r.text
        LOGGER.info("Downloaded %d bytes", len(xml_text))
        courses = _parse_xml(xml_text)
        LOGGER.info("Parsed %d courses from Discover Uni XML", len(courses))
        write_raw_json("courses", "discoveruni-api-summary", {"count": len(courses)})
        return courses
    except Exception as exc:
        LOGGER.exception("Discover Uni API download failed: %s", exc)
        return []
