"""Centralised config loaded from .env at /srv/scrapers/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(os.environ.get("WORKHORSE_ENV", "/srv/scrapers/.env"))
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", "5433"))
DB_NAME = os.environ.get("DB_NAME", "workhorse")
DB_USER = os.environ.get("DB_USER", "workhorse_user")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "")

PERPLEXITY_API_KEY = os.environ.get("PERPLEXITY_API_KEY", "")

GMAIL_ADDRESS = os.environ.get("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "")
DIGEST_RECIPIENT = os.environ.get("DIGEST_RECIPIENT", "")

USB_ROOT = Path(os.environ.get("USB_ROOT", "/mnt/usb-archive"))

COMPANIES_HOUSE_API_KEY = os.environ.get("COMPANIES_HOUSE_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


def database_url() -> str:
    from urllib.parse import quote_plus
    return (
        f"postgresql://{quote_plus(DB_USER)}:{quote_plus(DB_PASSWORD)}"
        f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    )
