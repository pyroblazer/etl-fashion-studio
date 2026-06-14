"""Extract stage: scrape product listings from the Fashion Studio website.

The site has 50 pages of about 20 products each. Page 1 is the site root,
every other page lives at /page{N}. Each public function catches its own
errors so a failed page or a single bad card cannot abort the whole run.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

from utils import config

# Labels of the labelled <p> lines inside a card.
_LABEL_KEYS = ("Rating", "Colors", "Size", "Gender")


def fetching_content(url: str, session: Optional[requests.Session] = None) -> str:
    """Download and return the HTML at url, or an empty string on failure."""
    try:
        sess = session if session is not None else requests.Session()
        response = sess.get(
            url,
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        return response.text
    except requests.RequestException as exc:
        print(f"[extract] request failed for {url}: {exc}")
        return ""


def build_page_url(page: int, base_url: str = config.BASE_URL) -> str:
    """Build the listing URL for a 1-based page number."""
    if page <= 1:
        return base_url + "/"
    return f"{base_url}/page{page}"


def _extract_price(card) -> str:
    """Read the raw price text from a card.

    Available prices sit in div.price-container span.price, while unavailable
    ones use a bare p.price. We try the container first and fall back.
    """
    price_node = card.select_one(".price-container .price")
    if price_node is None:
        price_node = card.select_one("p.price")
    if price_node is None:
        return ""
    return price_node.get_text(strip=True)


def _parse_lines(card) -> dict:
    """Parse the labelled <p> lines of a card into a dict."""
    values: dict = {"Rating": "", "Colors": "", "Size": "", "Gender": ""}
    for paragraph in card.find_all("p"):
        text = paragraph.get_text(strip=True)
        for label in _LABEL_KEYS:
            prefix = f"{label}:"
            if text.startswith(prefix):
                values[label] = text[len(prefix):].strip()
                break
            # "Colors" has no colon, e.g. "5 Colors".
            if label == "Colors" and text.endswith("Colors"):
                values[label] = text
                break
    return values


def scrape_page(html: str) -> list[dict]:
    """Parse one listing page into a list of raw product dicts."""
    products: list[dict] = []
    if not html:
        return products

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001
        print(f"[extract] could not parse HTML: {exc}")
        return products

    for card in soup.select(".collection-card"):
        try:
            title_node = card.select_one(".product-title")
            title = title_node.get_text(strip=True) if title_node else ""
            line_values = _parse_lines(card)
            products.append(
                {
                    "Title": title,
                    "Price": _extract_price(card),
                    "Rating": line_values["Rating"],
                    "Colors": line_values["Colors"],
                    "Size": line_values["Size"],
                    "Gender": line_values["Gender"],
                }
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[extract] could not parse a card: {exc}")
            continue
    return products


def scrape_main(max_pages: int = config.MAX_PAGES) -> pd.DataFrame:
    """Scrape every listing page and return a raw DataFrame.

    A timestamp column (UTC) is added to every row to record when the data
    was collected. Failed pages are logged and skipped; this never raises.
    """
    session = requests.Session()
    all_rows: list[dict] = []
    timestamp = datetime.now(timezone.utc).isoformat()

    for page in range(1, max_pages + 1):
        try:
            url = build_page_url(page)
            html = fetching_content(url, session=session)
            page_rows = scrape_page(html)
            if not page_rows:
                print(f"[extract] page {page}: no products parsed (empty HTML?)")
            for row in page_rows:
                row["timestamp"] = timestamp
            all_rows.extend(page_rows)
            print(f"[extract] page {page}: collected {len(page_rows)} products")
        except Exception as exc:  # noqa: BLE001
            print(f"[extract] page {page} failed: {exc}")
            continue

    try:
        return pd.DataFrame(
            all_rows,
            columns=["Title", "Price", "Rating", "Colors", "Size", "Gender", "timestamp"],
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[extract] could not build DataFrame: {exc}")
        return pd.DataFrame(
            columns=["Title", "Price", "Rating", "Colors", "Size", "Gender", "timestamp"]
        )
