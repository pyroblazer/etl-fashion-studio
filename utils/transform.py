"""Transform stage: clean, normalise and type-cast the scraped data.

Conversions applied here:
  - Price from USD to IDR at Rp 16.000 per USD.
  - Rating and Colors turned into numbers.
  - Size and Gender stripped of their "Size: " / "Gender: " prefix.
  - Rows with invalid or missing values removed, duplicates dropped.

Each helper is a small pure function wrapped in error handling.
transform_data works on a copy of the frame and reassigns whole columns,
which keeps it compatible with pandas' Copy-on-Write behaviour.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils import config

_INVALID_TITLE = "Unknown Product"

_OUTPUT_COLUMNS = [
    "Title",
    "Price",
    "Rating",
    "Colors",
    "Size",
    "Gender",
    "timestamp",
]


def transform_price(series: pd.Series, exchange_rate: float = config.EXCHANGE_RATE) -> pd.Series:
    """Turn a raw price ("$102.15" / "Price Unavailable") into an IDR float."""
    try:
        as_text = series.fillna("").astype(str)
        usd = as_text.str.extract(r"\$([0-9]+(?:\.[0-9]+)?)", expand=False)
        idr = pd.to_numeric(usd, errors="coerce") * exchange_rate
        return idr.round(2)
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] transform_price failed: {exc}")
        return pd.Series([np.nan] * len(series), index=series.index, dtype=float)


def transform_rating(series: pd.Series) -> pd.Series:
    """Extract the numeric rating from "3.9 / 5" / "Invalid Rating" / "Not Rated".

    Valid ratings always end in "/ 5"; invalid ones replace the number with
    text. Matching the "<number> / 5" pattern avoids reading the 5 denominator
    as a rating for invalid rows.
    """
    try:
        cleaned = series.fillna("").astype(str).str.replace("⭐", "", regex=False)
        matched = cleaned.str.extract(r"(\d+(?:\.\d+)?)\s*/\s*5", expand=False)
        return pd.to_numeric(matched, errors="coerce")
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] transform_rating failed: {exc}")
        return pd.Series([np.nan] * len(series), index=series.index, dtype=float)


def transform_colors(series: pd.Series) -> pd.Series:
    """Extract the colour count from "5 Colors" (NaN if there is no number)."""
    try:
        digits = series.fillna("").astype(str).str.extract(r"(\d+)", expand=False)
        return pd.to_numeric(digits, errors="coerce")
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] transform_colors failed: {exc}")
        return pd.Series([np.nan] * len(series), index=series.index, dtype=float)


def clean_prefixed(series: pd.Series, prefix: str) -> pd.Series:
    """Strip a leading label such as "Size: " or "Gender: " and trim spaces."""
    try:
        text = series.fillna("").astype(str)
        return text.str.replace(prefix, "", regex=False).str.strip()
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] clean_prefixed failed: {exc}")
        return series.astype(str)


def transform_title(series: pd.Series) -> pd.Series:
    """Trim titles and mark "Unknown Product" as missing."""
    try:
        text = series.fillna("").astype(str).str.strip()
        return text.where(text != _INVALID_TITLE, other=np.nan)
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] transform_title failed: {exc}")
        return series


def _empty_typed_frame() -> pd.DataFrame:
    """Return an empty DataFrame with the expected column types."""
    return pd.DataFrame({col: pd.Series(dtype=dtype) for col, dtype in {
        "Title": object,
        "Price": float,
        "Rating": float,
        "Colors": "int64",
        "Size": object,
        "Gender": object,
        "timestamp": "datetime64[ns]",
    }.items()})


def transform_data(df: pd.DataFrame, exchange_rate: float = config.EXCHANGE_RATE) -> pd.DataFrame:
    """Clean a raw DataFrame end to end and return it with the right types.

    An empty or None input returns an empty typed frame. This never raises.
    """
    try:
        if df is None or len(df) == 0:
            print("[transform] no data to transform")
            return _empty_typed_frame()

        data = df.copy()

        # Make sure every expected column exists.
        for col in _OUTPUT_COLUMNS:
            if col not in data.columns:
                data[col] = np.nan

        # Clean each column with its helper.
        data["Title"] = transform_title(data["Title"])
        data["Price"] = transform_price(data["Price"], exchange_rate=exchange_rate)
        data["Rating"] = transform_rating(data["Rating"])
        data["Colors"] = transform_colors(data["Colors"])
        data["Size"] = clean_prefixed(data["Size"], "Size:")
        data["Gender"] = clean_prefixed(data["Gender"], "Gender:")

        # Drop rows that still have a missing or invalid critical value.
        data = data.dropna(
            subset=["Title", "Price", "Rating", "Colors", "Size", "Gender"]
        )
        data = data[data["Title"] != _INVALID_TITLE]

        # Cast to the final types. Pandas 3.0 defaults string columns to a
        # dedicated string dtype, so cast to object explicitly.
        data["Title"] = data["Title"].astype(object)
        data["Price"] = data["Price"].astype(float)
        data["Rating"] = data["Rating"].astype(float)
        data["Colors"] = data["Colors"].astype("int64")
        data["Size"] = data["Size"].astype(object)
        data["Gender"] = data["Gender"].astype(object)
        data["timestamp"] = pd.to_datetime(data["timestamp"], errors="coerce")

        data = data.drop_duplicates().reset_index(drop=True)
        return data[_OUTPUT_COLUMNS]
    except Exception as exc:  # noqa: BLE001
        print(f"[transform] transform_data failed: {exc}")
        return _empty_typed_frame()
