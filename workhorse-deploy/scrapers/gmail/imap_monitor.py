"""Multi-label IMAP monitor for Gmail.

Connects via IMAPS to imap.gmail.com using a Google App Password.
Scans INBOX plus configured labels, classifies each message, and
upserts to the gmail_items table.

Idempotent — uses the Message-ID header as the unique key.
"""

from __future__ import annotations

import argparse
import email
import email.utils
import imaplib
import json
import sys
from datetime import datetime, timedelta, timezone
from email.header import decode_header

from ..common import db
from ..common.config import GMAIL_ADDRESS, GMAIL_APP_PASSWORD
from ..common.logging_setup import get_logger
from . import classifier

LOGGER = get_logger("gmail.imap")

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
LOOKBACK_DAYS = 7

SCAN_LABELS: list[tuple[str, str | None]] = [
    ("INBOX", None),
    ("JAs &- Linkedin", "job-listing"),
    ("Personal, Writing etc/Screenwriting and Final Draft", "film"),
    ("Future Horizons/Funding &- UKRI/Swiss and Europe Startup and Funding News", "investment"),
    ("Future Horizons/Funding &- UKRI/Swiss and Europe Startup and Funding News/Innosuisse &- Company Startup", "investment"),
    ("Future Horizons/Funding &- UKRI/Swiss and Europe Startup and Funding News/Swiss Startup News and Info", "investment"),
    ("INBOX/Perplexity Alerts and Reports", "newsletter"),
    ("INBOX/Product Development/Claude, Cursor, Gitbot and Coding", "learning"),
    ("INBOX/Git Hub And Cursor Fixes", "learning"),
    ("Future Horizons/AI and Business Research", "newsletter"),
    ("Future Horizons/Employment and Skills", "job-listing"),
    ("Future Horizons/Course Creation", "course"),
    ("Future Horizons/HEPI, WonkHE, HE &- Ed Sector", "newsletter"),
    ("Personal, Writing etc/Swiss Education and Employment Opportunities", "job-listing"),
]


def _decode(header_value: str) -> str:
    if not header_value:
        return ""
    parts = decode_header(header_value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            try:
                out.append(text.decode(enc or "utf-8", errors="replace"))
            except LookupError:
                out.append(text.decode("utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_body(msg: email.message.Message) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    payload = msg.get_payload(decode=True)
    if isinstance(payload, bytes):
        return payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return payload or ""


def _connect() -> imaplib.IMAP4_SSL:
    if not GMAIL_ADDRESS or not GMAIL_APP_PASSWORD:
        raise RuntimeError("GMAIL_ADDRESS and GMAIL_APP_PASSWORD must be set in .env")
    LOGGER.info("Connecting IMAP %s as %s", IMAP_HOST, GMAIL_ADDRESS)
    M = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    M.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    return M


def _quote_label(label: str) -> str:
    return '"' + label.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _fetch_from_label(M: imaplib.IMAP4_SSL, label: str, since: str) -> list[bytes]:
    try:
        typ, data = M.select(_quote_label(label), readonly=True)
        if typ != "OK":
            LOGGER.warning("Could not select %r: %s", label, data)
            return []
    except imaplib.IMAP4.error as exc:
        LOGGER.warning("Label %r error: %s", label, exc)
        return []
    typ, data = M.search(None, f'(SINCE "{since}")')
    if typ != "OK" or not data or not data[0]:
        return []
    return data[0].split()


def _process_uid(M: imaplib.IMAP4_SSL, uid: bytes, *,
                 label: str, label_hint: str | None) -> bool:
    status, data = M.fetch(uid, "(RFC822)")
    if status != "OK" or not data or not data[0]:
        return False
    raw = data[0][1]
    msg = email.message_from_bytes(raw)
    message_id = (msg.get("Message-ID") or "").strip().strip("<>")
    if not message_id:
        return False

    existing = db.fetch_one(
        "SELECT id FROM gmail_items WHERE message_id = %s", (message_id,)
    )
    if existing:
        return False

    from_full = _decode(msg.get("From", ""))
    from_name = ""
    from_addr = from_full
    if "<" in from_full:
        from_name = from_full.split("<")[0].strip().strip('"')
        from_addr = from_full.split("<")[1].rstrip(">")
    subject = _decode(msg.get("Subject", ""))
    received = msg.get("Date", "")
    try:
        received_dt = email.utils.parsedate_to_datetime(received)
    except Exception:
        received_dt = None
    body = _extract_body(msg)

    category = classifier.classify(
        from_email=from_addr, subject=subject, body=body,
        label_hint=label_hint,
    )
    if category == "ignore":
        extracted = {}
    else:
        extracted = classifier.extract_fields(
            subject=subject, body=body, category=category,
        )

    db.execute(
        """
        INSERT INTO gmail_items (
          message_id, thread_id, from_email, from_name, subject,
          received_at, category, extracted, body_excerpt, labels
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
        ON CONFLICT (message_id) DO NOTHING
        """,
        (
            message_id,
            (msg.get("Thread-Index") or msg.get("References") or "")[:255] or None,
            from_addr[:255],
            from_name[:255],
            subject[:500],
            received_dt,
            category,
            json.dumps(extracted),
            body[:2000],
            [label],
        ),
    )
    return True


def run(days: int = LOOKBACK_DAYS, dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("gmail.imap_monitor")
    LOGGER.info("Gmail IMAP monitor run %s (last %d days, %d labels)", run_id, days, len(SCAN_LABELS))
    inserted = 0
    fetched = 0
    try:
        if dry_run:
            print(f"Dry run — would scan {len(SCAN_LABELS)} labels for last {days} days")
            for label, hint in SCAN_LABELS:
                print(f"  {label} (hint={hint})")
            db.finish_scraper_run(run_id, "dry_run")
            return
        M = _connect()
        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        try:
            for label, hint in SCAN_LABELS:
                uids = _fetch_from_label(M, label, since)
                label_fetched = len(uids)
                label_inserted = 0
                for uid in uids:
                    try:
                        if _process_uid(M, uid, label=label, label_hint=hint):
                            label_inserted += 1
                    except Exception as exc:
                        LOGGER.warning("UID %r in %r failed: %s", uid, label, exc)
                fetched += label_fetched
                inserted += label_inserted
                if label_fetched:
                    LOGGER.info("  %s: %d fetched, %d new", label, label_fetched, label_inserted)
        finally:
            try:
                M.close()
            except Exception:
                pass
            M.logout()
        LOGGER.info("Gmail total: %d fetched, %d new items stored", fetched, inserted)
        db.finish_scraper_run(
            run_id, "ok", fetched=fetched, inserted=inserted, skipped=fetched - inserted
        )
    except Exception as exc:
        LOGGER.exception("Gmail monitor failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc), fetched=fetched, inserted=inserted)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(days=args.days, dry_run=args.dry_run)
