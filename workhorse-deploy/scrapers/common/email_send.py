"""SMTP send for the weekly digest email."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .config import (
    DIGEST_RECIPIENT,
    SMTP_FROM,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
)


def send_html(
    subject: str,
    html_body: str,
    *,
    to: str | None = None,
    text_fallback: str | None = None,
) -> None:
    """Send an HTML email via SMTP (Gmail by default)."""
    if not SMTP_USER or not SMTP_PASSWORD:
        raise RuntimeError("SMTP credentials not configured in .env")

    recipient = to or DIGEST_RECIPIENT or SMTP_FROM

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM or SMTP_USER
    msg["To"] = recipient

    if text_fallback:
        msg.attach(MIMEText(text_fallback, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.starttls()
        smtp.login(SMTP_USER, SMTP_PASSWORD)
        smtp.send_message(msg)
