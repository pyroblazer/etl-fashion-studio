"""Unit tests for utils.load (file IO is real; Sheets/Postgres are mocked)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from utils import load


# --- load_to_csv -----------------------------------------------------------
def test_load_to_csv_writes_file(cleaned_df, tmp_path):
    target = tmp_path / "out.csv"

    ok = load.load_to_csv(cleaned_df, filename=str(target))

    assert ok is True
    assert target.is_file()
    written = pd.read_csv(target)
    assert len(written) == len(cleaned_df)
    assert list(written.columns) == list(cleaned_df.columns)


def test_load_to_csv_empty_returns_false(tmp_path):
    target = tmp_path / "empty.csv"
    assert load.load_to_csv(pd.DataFrame(), filename=str(target)) is False
    assert not target.exists()


def test_load_to_csv_failure_returns_false(cleaned_df):
    # Writing into a path whose parent directory does not exist raises -> False.
    assert load.load_to_csv(cleaned_df, filename="no/such/dir/out.csv") is False


# --- load_to_google_sheets -------------------------------------------------
def test_load_to_google_sheets_skipped_without_id(cleaned_df, dummy_credentials):
    ok = load.load_to_google_sheets(
        cleaned_df, credentials_file=dummy_credentials, spreadsheet_id=None
    )
    assert ok is False


def test_load_to_google_sheets_missing_credentials_returns_false(cleaned_df, tmp_path):
    ok = load.load_to_google_sheets(
        cleaned_df, credentials_file=str(tmp_path / "missing.json"), spreadsheet_id="sheet-123"
    )
    assert ok is False


def test_load_to_google_sheets_success(cleaned_df, dummy_credentials, monkeypatch):
    # Patch the Google libraries (imported lazily inside the function).
    import google.oauth2.service_account as service_account
    import googleapiclient.discovery as discovery

    captured = {}

    class _Request:
        def __init__(self, result):
            self._result = result

        def execute(self):
            return self._result

    class _Values:
        def update(self, **kwargs):
            captured["update"] = kwargs
            return _Request({"updatedCells": 1})

    class _Sheets:
        def values(self):
            return _Values()

        def get(self, **kwargs):
            # Report only a default tab so the code must create "Products".
            return _Request({"sheets": [{"properties": {"title": "Sheet1"}}]})

        def batchUpdate(self, **kwargs):
            captured["batchUpdate"] = kwargs
            return _Request({})

    class _Service:
        def spreadsheets(self):
            return _Sheets()

    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        lambda *a, **k: object(),
    )
    monkeypatch.setattr(discovery, "build", lambda *a, **k: _Service())

    ok = load.load_to_google_sheets(
        cleaned_df, credentials_file=dummy_credentials, spreadsheet_id="sheet-123"
    )

    assert ok is True
    # The code created the missing "Products" tab before writing.
    assert captured["batchUpdate"]["body"]["requests"][0]["addSheet"]["properties"]["title"] == "Products"
    assert captured["update"]["spreadsheetId"] == "sheet-123"
    assert captured["update"]["valueInputOption"] == "RAW"
    # First row of the body is the header row.
    assert captured["update"]["body"]["values"][0] == list(cleaned_df.columns)


def test_ensure_worksheet_exists_skips_when_present():
    created = []

    class _Req:
        def __init__(self, result):
            self._result = result

        def execute(self):
            return self._result

    class _Sheets:
        def get(self, **kwargs):
            return _Req({"sheets": [{"properties": {"title": "Products"}}]})

        def batchUpdate(self, **kwargs):
            created.append(kwargs)
            return _Req({})

    class _Service:
        def spreadsheets(self):
            return _Sheets()

    load._ensure_worksheet_exists(_Service(), "sheet-123", "Products")

    assert created == []  # tab already present -> no addSheet request


def test_load_to_google_sheets_handles_empty_credentials_json(cleaned_df, tmp_path, monkeypatch):
    """from_service_account_file raising is caught -> False."""
    import google.oauth2.service_account as service_account

    path = tmp_path / "google-sheets-api.json"
    path.write_text("not-json", encoding="utf-8")
    monkeypatch.setattr(
        service_account.Credentials,
        "from_service_account_file",
        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad key")),
    )
    ok = load.load_to_google_sheets(cleaned_df, credentials_file=str(path), spreadsheet_id="x")
    assert ok is False


# --- load_to_postgre -------------------------------------------------------
def test_load_to_postgre_skipped_without_url(cleaned_df):
    assert load.load_to_postgre(cleaned_df, db_url=None) is False


def test_load_to_postgre_empty_returns_false():
    assert load.load_to_postgre(pd.DataFrame(), db_url="postgresql://u:p@h/db") is False


def test_load_to_postgre_success(cleaned_df, monkeypatch):
    captured = {}

    class _Engine:
        def __init__(self):
            self.disposed = False

        def dispose(self):
            self.disposed = True

    engine = _Engine()

    def fake_to_sql(self, name, con, **kwargs):
        captured.update(name=name, con=con, kwargs=kwargs)

    import sqlalchemy

    monkeypatch.setattr(pd.DataFrame, "to_sql", fake_to_sql)
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda url: engine)

    ok = load.load_to_postgre(cleaned_df, db_url="postgresql://u:p@h/db", table="products")

    assert ok is True
    assert captured["name"] == "products"
    assert captured["kwargs"]["if_exists"] == "replace"
    assert captured["kwargs"]["index"] is False
    assert engine.disposed is True


def test_load_to_postgre_failure_returns_false(cleaned_df, monkeypatch):
    import sqlalchemy

    monkeypatch.setattr(
        sqlalchemy, "create_engine", lambda url: (_ for _ in ()).throw(RuntimeError("no db"))
    )
    assert load.load_to_postgre(cleaned_df, db_url="postgresql://u:p@h/db") is False


# --- load_all --------------------------------------------------------------
def test_load_all_runs_each_repository(cleaned_df, tmp_path, monkeypatch):
    csv_target = tmp_path / "products.csv"

    results = load.load_all(
        cleaned_df,
        csv_filename=str(csv_target),
        spreadsheet_id=None,          # sheets disabled
        db_url=None,                  # postgres disabled
    )

    assert results["csv"] is True
    assert results["google_sheets"] is False
    assert results["postgresql"] is False
    assert csv_target.is_file()


def test_df_as_rows_header_and_values(cleaned_df):
    rows = load._df_as_rows(cleaned_df)
    assert rows[0] == list(cleaned_df.columns)
    assert len(rows) == len(cleaned_df) + 1


# --- _coerce_cell ----------------------------------------------------------
def test_coerce_cell_nan_becomes_empty():
    assert load._coerce_cell(float("nan")) == ""
    assert load._coerce_cell(None) == ""


def test_coerce_cell_timestamp_becomes_iso():
    ts = pd.Timestamp("2025-01-01T00:00:00")
    assert load._coerce_cell(ts) == ts.isoformat()


def test_coerce_cell_passthrough():
    assert load._coerce_cell("M") == "M"
    assert load._coerce_cell(3) == 3


def test_coerce_cell_unhashable_value_falls_through():
    # pd.isna raises on a list -> the except returns the value untouched.
    assert load._coerce_cell([1, 2, 3]) == [1, 2, 3]
