"""Unit tests for utils.transform (pure functions, no mocks needed)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from utils import transform


# --- transform_price -------------------------------------------------------
def test_transform_price_valid_usd():
    result = transform.transform_price(pd.Series(["$102.15"]))
    assert result.iloc[0] == pytest.approx(102.15 * 16_000)


def test_transform_price_unavailable_becomes_nan():
    result = transform.transform_price(pd.Series(["Price Unavailable"]))
    assert pd.isna(result.iloc[0])


def test_transform_price_empty_becomes_nan():
    result = transform.transform_price(pd.Series([""]))
    assert pd.isna(result.iloc[0])


def test_transform_price_custom_exchange_rate():
    result = transform.transform_price(pd.Series(["$10.00"]), exchange_rate=15_000)
    assert result.iloc[0] == pytest.approx(150_000.0)


# --- transform_rating ------------------------------------------------------
def test_transform_rating_valid_with_star():
    result = transform.transform_rating(pd.Series(["⭐ 3.9 / 5"]))
    assert result.iloc[0] == pytest.approx(3.9)


def test_transform_rating_invalid_rating_becomes_nan():
    result = transform.transform_rating(pd.Series(["⭐ Invalid Rating / 5"]))
    assert pd.isna(result.iloc[0])


def test_transform_rating_not_rated_becomes_nan():
    result = transform.transform_rating(pd.Series(["Not Rated"]))
    assert pd.isna(result.iloc[0])


# --- transform_colors ------------------------------------------------------
def test_transform_colors_extracts_number():
    assert transform.transform_colors(pd.Series(["3 Colors"])).iloc[0] == 3


def test_transform_colors_no_digits_becomes_nan():
    assert pd.isna(transform.transform_colors(pd.Series(["Colors"])).iloc[0])


# --- clean_prefixed --------------------------------------------------------
def test_clean_prefixed_strips_label():
    assert transform.clean_prefixed(pd.Series(["Size: M"]), "Size:").iloc[0] == "M"
    assert transform.clean_prefixed(pd.Series(["Gender: Men"]), "Gender:").iloc[0] == "Men"


# --- transform_title -------------------------------------------------------
def test_transform_title_strips_unknown():
    result = transform.transform_title(pd.Series(["Unknown Product", "Hoodie 3"]))
    assert pd.isna(result.iloc[0])
    assert result.iloc[1] == "Hoodie 3"


def test_transform_title_strips_whitespace():
    assert transform.transform_title(pd.Series(["  T-shirt 2  "])).iloc[0] == "T-shirt 2"


# --- transform_data (end-to-end) ------------------------------------------
def test_transform_data_cleans_end_to_end(raw_df):
    clean = transform.transform_data(raw_df)

    # The duplicate + invalid cards are removed: only T-shirt 2 and Hoodie 3 remain.
    assert len(clean) == 2
    assert set(clean["Title"]) == {"T-shirt 2", "Hoodie 3"}
    assert "Unknown Product" not in clean["Title"].values

    # No nulls, no duplicates.
    assert clean.notna().all().all()
    assert clean.duplicated().sum() == 0


def test_transform_data_dtypes(raw_df):
    clean = transform.transform_data(raw_df)

    assert clean["Price"].dtype == float
    assert clean["Rating"].dtype == float
    assert clean["Colors"].dtype == np.dtype("int64")
    assert clean["Size"].dtype == object
    assert clean["Gender"].dtype == object
    assert pd.api.types.is_datetime64_any_dtype(clean["timestamp"])


def test_transform_data_price_conversion(raw_df):
    clean = transform.transform_data(raw_df).set_index("Title")

    assert clean.loc["T-shirt 2", "Price"] == pytest.approx(102.15 * 16_000)
    assert clean.loc["Hoodie 3", "Price"] == pytest.approx(496.88 * 16_000)


def test_transform_data_rating_and_colors(raw_df):
    clean = transform.transform_data(raw_df).set_index("Title")

    assert clean.loc["T-shirt 2", "Rating"] == pytest.approx(3.9)
    assert clean.loc["T-shirt 2", "Colors"] == 3
    assert clean.loc["Hoodie 3", "Colors"] == 3


def test_transform_data_size_gender_stripped(raw_df):
    clean = transform.transform_data(raw_df).set_index("Title")

    assert clean.loc["T-shirt 2", "Size"] == "M"
    assert clean.loc["T-shirt 2", "Gender"] == "Women"
    assert clean.loc["Hoodie 3", "Gender"] == "Unisex"


def test_transform_data_empty_input_returns_typed_frame():
    clean = transform.transform_data(pd.DataFrame())

    assert len(clean) == 0
    assert list(clean.columns) == [
        "Title",
        "Price",
        "Rating",
        "Colors",
        "Size",
        "Gender",
        "timestamp",
    ]
    assert clean["Colors"].dtype == np.dtype("int64")
    assert pd.api.types.is_datetime64_any_dtype(clean["timestamp"])


def test_transform_data_none_input_returns_typed_frame():
    clean = transform.transform_data(None)
    assert len(clean) == 0
    assert "timestamp" in clean.columns


def test_transform_data_no_invalid_values(raw_df):
    clean = transform.transform_data(raw_df)

    text_blob = clean.astype(str).apply(lambda col: " ".join(col)).str.cat(sep=" ")
    assert "Unknown Product" not in text_blob
    assert "Price Unavailable" not in text_blob
    assert "Invalid Rating" not in text_blob


# --- error handling --------------------------------------------------------
def test_helpers_return_nan_series_on_failure(monkeypatch):
    """Helpers return an all-NaN series when an internal pandas call raises."""
    series = pd.Series(["$1.00", "⭐ 4 / 5", "3 Colors"])

    def boom(*args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(transform.pd, "to_numeric", boom)

    for fn in (transform.transform_price, transform.transform_rating, transform.transform_colors):
        result = fn(series)
        assert len(result) == len(series)
        assert result.isna().all()


def test_clean_prefixed_and_title_survive_internal_error(monkeypatch):
    series = pd.Series(["Size: M", "Unknown Product"])

    def boom(self, *args, **kwargs):
        raise RuntimeError("forced failure")

    monkeypatch.setattr(pd.Series, "fillna", boom)

    # Both should return *something* rather than raising.
    assert len(transform.clean_prefixed(series, "Size:")) == len(series)
    assert len(transform.transform_title(series)) == len(series)


def test_transform_data_internal_error_returns_empty(monkeypatch, raw_df):
    monkeypatch.setattr(
        transform, "transform_title", lambda s: (_ for _ in ()).throw(RuntimeError("boom"))
    )
    clean = transform.transform_data(raw_df)

    assert len(clean) == 0
    assert "timestamp" in clean.columns

