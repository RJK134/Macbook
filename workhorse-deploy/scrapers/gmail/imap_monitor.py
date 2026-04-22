"""IMAP monitor for the Gmail inbox.

Connects via IMAPS to imap.gmail.com using a Google App Password (NOT
the account password). Pulls messages from the last 7 days, classifies
them via classifier.py, and upserts to the gmail_items table.

Idempotent — uses the Message-ID header as the unique key.
"""

from __future__ import annotations

import argparse
import email
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


def _fetch_recent(M: imaplib.IMAP4_SSL, days: int) -> list[bytes]:
    M.select("INBOX")
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
    status, data = M.search(None, f'(SINCE "{since}")')
    if status != "OK":
        LOGGER.warning("IMAP search failed: %s", status)
        return []
    return data[0].split() if data and data[0] else []


def _process_uid(M: imaplib.IMAP4_SSL, uid: bytes) -> bool:
    """Process a single message UID. Returns True if newly inserted."""
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
    except Exception:  # noqa: BLE001
        received_dt = None
    body = _extract_body(msg)

    category = classifier.classify(
        from_email=from_addr, subject=subject, body=body,
    )
    if category == "ignore":
        # Still store to avoid re-classifying next run (cheaper than re-fetch).
        extracted = {}
    else:
        extracted = classifier.extract_fields(
            subject=subject, body=body, category=category,
        )

    db.execute(
        """
        INSERT INTO gmail_items (
          message_id, thread_id, from_email, from_name, subject,
          received_at, category, extracted, body_excerpt
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
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
        ),
    )
    return True


def run(days: int = LOOKBACK_DAYS, dry_run: bool = False) -> None:
    run_id = db.start_scraper_run("gmail.imap_monitor")
    LOGGER.info("Gmail IMAP monitor run %s (last %d days)", run_id, days)
    inserted = 0
    fetched = 0
    try:
        if dry_run:
            print(f"Dry run — would scan inbox for last {days} days")
            db.finish_scraper_run(run_id, "dry_run")
            return
        M = _connect()
        try:
            uids = _fetch_recent(M, days)
            fetched = len(uids)
            LOGGER.info("IMAP returned %d messages", fetched)
            for uid in uids:
                try:
                    if _process_uid(M, uid):
                        inserted += 1
                except Exception as exc:  # noqa: BLE001
                    LOGGER.warning("UID %r failed: %s", uid, exc)
        finally:
            try:
                M.close()
            except Exception:  # noqa: BLE001
                pass
            M.logout()
        LOGGER.info("Gmail: %d new items stored", inserted)
        db.finish_scraper_run(
            run_id, "ok", fetched=fetched, inserted=inserted, skipped=fetched - inserted
        )
    except Exception as exc:  # noqa: BLE001
        LOGGER.exception("Gmail monitor failed: %s", exc)
        db.finish_scraper_run(run_id, "error", error=str(exc), fetched=fetched, inserted=inserted)
        sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=LOOKBACK_DAYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(days=args.days, dry_run=args.dry_run)
