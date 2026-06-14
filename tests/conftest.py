"""Shared pytest fixtures for the ETL test suite."""

from __future__ import annotations

import json

import pandas as pd
import pytest

# A small slice of one listing page that covers the edge cases the scraper
# and transformer must handle: a valid product, an "Unknown Product" with an
# invalid rating, a product with an unavailable price and "Not Rated", an
# exact duplicate of the valid product, and a second valid product.
SAMPLE_HTML = """
<html><body>
  <div class="collection-grid">
    <div class="collection-card">
      <div class="product-details">
        <h3 class="product-title">T-shirt 2</h3>
        <div class="price-container"><span class="price">$102.15</span></div>
        <p>Rating: ⭐ 3.9 / 5</p>
        <p>3 Colors</p>
        <p>Size: M</p>
        <p>Gender: Women</p>
      </div>
    </div>
    <div class="collection-card">
      <div class="product-details">
        <h3 class="product-title">Unknown Product</h3>
        <div class="price-container"><span class="price">$100.00</span></div>
        <p>Rating: ⭐ Invalid Rating / 5</p>
        <p>5 Colors</p>
        <p>Size: M</p>
        <p>Gender: Men</p>
      </div>
    </div>
    <div class="collection-card">
      <div class="product-details">
        <h3 class="product-title">Pants 16</h3>
        <p class="price">Price Unavailable</p>
        <p>Rating: Not Rated</p>
        <p>8 Colors</p>
        <p>Size: S</p>
        <p>Gender: Men</p>
      </div>
    </div>
    <div class="collection-card">
      <div class="product-details">
        <h3 class="product-title">T-shirt 2</h3>
        <div class="price-container"><span class="price">$102.15</span></div>
        <p>Rating: ⭐ 3.9 / 5</p>
        <p>3 Colors</p>
        <p>Size: M</p>
        <p>Gender: Women</p>
      </div>
    </div>
    <div class="collection-card">
      <div class="product-details">
        <h3 class="product-title">Hoodie 3</h3>
        <div class="price-container"><span class="price">$496.88</span></div>
        <p>Rating: ⭐ 4.8 / 5</p>
        <p>3 Colors</p>
        <p>Size: L</p>
        <p>Gender: Unisex</p>
      </div>
    </div>
  </div>
</body></html>
"""


@pytest.fixture
def sample_html() -> str:
    return SAMPLE_HTML


@pytest.fixture
def raw_df(sample_html) -> pd.DataFrame:
    """Raw extracted DataFrame (as if produced by extract.scrape_page + timestamp)."""
    from utils.extract import scrape_page

    rows = scrape_page(sample_html)
    for row in rows:
        row["timestamp"] = "2025-01-01T00:00:00+00:00"
    return pd.DataFrame(
        rows,
        columns=["Title", "Price", "Rating", "Colors", "Size", "Gender", "timestamp"],
    )


@pytest.fixture
def cleaned_df(raw_df) -> pd.DataFrame:
    """Fully cleaned DataFrame."""
    from utils.transform import transform_data

    return transform_data(raw_df)


@pytest.fixture
def dummy_credentials(tmp_path):
    """A minimal file that exists so the Sheets loader's Path check passes."""
    path = tmp_path / "google-sheets-api.json"
    path.write_text(json.dumps({"type": "service_account"}), encoding="utf-8")
    return str(path)
