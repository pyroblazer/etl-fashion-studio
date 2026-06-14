"""Unit tests for utils.extract. Network calls are mocked, no real requests."""

from __future__ import annotations

import pandas as pd
import pytest
import requests

from utils import extract


BASE_URL = "https://fashion-studio.dicoding.dev"


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.RequestException(f"HTTP {self.status_code}")


class _FakeSession:
    """Minimal stand-in for requests.Session used by fetching_content."""

    def __init__(self, response: _FakeResponse):
        self._response = response
        self.get_calls = []

    def get(self, url, **kwargs):
        self.get_calls.append(url)
        return self._response


# --- build_page_url --------------------------------------------------------
def test_build_page_url_page_one_is_root():
    assert extract.build_page_url(1) == BASE_URL + "/"


def test_build_page_url_subsequent_pages():
    assert extract.build_page_url(2) == f"{BASE_URL}/page2"
    assert extract.build_page_url(50) == f"{BASE_URL}/page50"


def test_build_page_url_non_positive_is_root():
    assert extract.build_page_url(0) == BASE_URL + "/"
    assert extract.build_page_url(-3) == BASE_URL + "/"


# --- fetching_content ------------------------------------------------------
def test_fetching_content_success(monkeypatch):
    response = _FakeResponse("<html>hello</html>")
    fake_session = _FakeSession(response)
    monkeypatch.setattr(extract.requests, "Session", lambda: fake_session)

    result = extract.fetching_content("https://example.com")

    assert result == "<html>hello</html>"
    assert fake_session.get_calls == ["https://example.com"]


def test_fetching_content_uses_provided_session():
    response = _FakeResponse("<html>via-session</html>")
    fake_session = _FakeSession(response)

    result = extract.fetching_content("https://example.com", session=fake_session)

    assert result == "<html>via-session</html>"


def test_fetching_content_returns_empty_on_http_error(monkeypatch):
    response = _FakeResponse("", status_code=500)
    monkeypatch.setattr(extract.requests, "Session", lambda: _FakeSession(response))

    assert extract.fetching_content("https://example.com") == ""


def test_fetching_content_returns_empty_on_connection_error(monkeypatch):
    class BoomSession(_FakeSession):
        def get(self, url, **kwargs):
            raise requests.ConnectionError("boom")

    monkeypatch.setattr(extract.requests, "Session", lambda: BoomSession(response=_FakeResponse("")))
    assert extract.fetching_content("https://example.com") == ""


# --- scrape_page -----------------------------------------------------------
def test_scrape_page_parses_valid_card(sample_html):
    products = extract.scrape_page(sample_html)

    valid = next(p for p in products if p["Title"] == "T-shirt 2")
    assert valid["Price"] == "$102.15"
    assert valid["Rating"] == "⭐ 3.9 / 5"
    assert valid["Colors"] == "3 Colors"
    assert valid["Size"] == "M"
    assert valid["Gender"] == "Women"


def test_scrape_page_captures_price_unavailable(sample_html):
    products = extract.scrape_page(sample_html)
    pants = next(p for p in products if p["Title"] == "Pants 16")
    assert pants["Price"] == "Price Unavailable"
    assert pants["Rating"] == "Not Rated"


def test_scrape_page_captures_unknown_product(sample_html):
    products = extract.scrape_page(sample_html)
    unknown = next(p for p in products if p["Title"] == "Unknown Product")
    assert unknown["Rating"] == "⭐ Invalid Rating / 5"


def test_scrape_page_returns_five_cards(sample_html):
    assert len(extract.scrape_page(sample_html)) == 5


def test_scrape_page_empty_html_returns_empty_list():
    assert extract.scrape_page("") == []


def test_scrape_page_bad_html_does_not_raise():
    # Malformed input should yield an empty list, never an exception.
    assert extract.scrape_page("<<<not html") == []


# --- scrape_main -----------------------------------------------------------
def test_scrape_main_collects_all_pages_with_timestamp(monkeypatch, sample_html):
    monkeypatch.setattr(extract, "fetching_content", lambda url, session=None: sample_html)

    df = extract.scrape_main(max_pages=3)

    assert isinstance(df, pd.DataFrame)
    # 5 cards per page x 3 pages.
    assert len(df) == 15
    assert "timestamp" in df.columns
    assert df["timestamp"].notna().all()


def test_scrape_main_skips_empty_pages(monkeypatch):
    monkeypatch.setattr(extract, "fetching_content", lambda url, session=None: "")

    df = extract.scrape_main(max_pages=4)

    assert len(df) == 0
    assert list(df.columns) == [
        "Title",
        "Price",
        "Rating",
        "Colors",
        "Size",
        "Gender",
        "timestamp",
    ]


def test_scrape_main_builds_correct_urls(monkeypatch, sample_html):
    seen_urls = []

    def fake_fetch(url, session=None):
        seen_urls.append(url)
        return sample_html

    monkeypatch.setattr(extract, "fetching_content", fake_fetch)
    extract.scrape_main(max_pages=2)

    assert seen_urls == [BASE_URL + "/", f"{BASE_URL}/page2"]
