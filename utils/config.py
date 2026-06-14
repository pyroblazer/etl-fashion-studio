"""Configuration constants and a minimal .env loader for the ETL pipeline."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

# Source website.
BASE_URL = "https://fashion-studio.dicoding.dev"

# Number of listing pages on the website.
MAX_PAGES = 50

# USD to IDR exchange rate.
EXCHANGE_RATE = 16_000

# HTTP settings for the scraper.
REQUEST_TIMEOUT = 15  # seconds
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Defaults for each loader.
DEFAULT_CSV = "products.csv"
DEFAULT_GOOGLE_CREDENTIALS = "google-sheets-api.json"
DEFAULT_GOOGLE_WORKSHEET = "Products"
DEFAULT_POSTGRES_TABLE = "products"

# Scope needed to read and write a spreadsheet.
GOOGLE_SHEETS_SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]


def load_env(env_path: str | Path = ".env") -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ, if present."""
    try:
        path = Path(env_path)
        if not path.is_file():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
    except Exception as exc:  # noqa: BLE001
        print(f"[config] could not load .env: {exc}")


def get_postgres_url() -> Optional[str]:
    """Return the Postgres URL from env, or None if not set."""
    return os.environ.get("POSTGRES_URL") or None


def get_google_sheet_id() -> Optional[str]:
    """Return the Google Sheet id from env, or None if not set."""
    return os.environ.get("GOOGLE_SHEET_ID") or None


def get_google_credentials_path() -> str:
    """Return the path to the service-account JSON (with env override)."""
    return os.environ.get("GOOGLE_CREDENTIALS_PATH", DEFAULT_GOOGLE_CREDENTIALS)
