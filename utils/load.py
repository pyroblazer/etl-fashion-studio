"""Load stage: write the cleaned data to the supported repositories.

Three writers live here, one per destination:

  - load_to_csv           -> a local CSV file.
  - load_to_google_sheets -> a Google Sheet, via a service account.
  - load_to_postgre       -> a PostgreSQL table, via SQLAlchemy.

Each writer returns True on success and catches its own errors, so a failure
in one repository never affects the others. load_all runs all three together.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from utils import config


def _df_as_rows(df: pd.DataFrame) -> list[list]:
    """Return the dataframe as [columns, *rows] for APIs that take a 2D list."""
    values = [list(df.columns)]
    for _, row in df.iterrows():
        values.append([_coerce_cell(value) for value in row])
    return values


def _coerce_cell(value) -> object:
    """Make NaN values and timestamps safe for the Sheets API."""
    try:
        if pd.isna(value):
            return ""
        if isinstance(value, pd.Timestamp):
            return value.isoformat()
    except (TypeError, ValueError):
        pass
    return value


def load_to_csv(df: pd.DataFrame, filename: str = config.DEFAULT_CSV) -> bool:
    """Write the dataframe to a UTF-8 CSV without the index. Returns success."""
    try:
        if df is None or len(df) == 0:
            print("[load] csv: nothing to write")
            return False
        df.to_csv(filename, index=False, encoding="utf-8")
        print(f"[load] csv: wrote {len(df)} rows to {filename}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[load] csv failed: {exc}")
        return False


def _ensure_worksheet_exists(service, spreadsheet_id: str, worksheet: str) -> None:
    """Create the worksheet tab if it is not already in the spreadsheet.

    A new spreadsheet only has a default "Sheet1" tab, so writing to
    "Products!A1" would fail unless the tab is created first.
    """
    metadata = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = {
        sheet.get("properties", {}).get("title")
        for sheet in metadata.get("sheets", [])
    }
    if worksheet not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [
                    {"addSheet": {"properties": {"title": worksheet}}}
                ]
            },
        ).execute()


def load_to_google_sheets(
    df: pd.DataFrame,
    credentials_file: str = config.DEFAULT_GOOGLE_CREDENTIALS,
    spreadsheet_id: Optional[str] = None,
    worksheet: str = config.DEFAULT_GOOGLE_WORKSHEET,
) -> bool:
    """Write the dataframe into a worksheet of the given Google Sheet.

    The service account must be shared on the sheet as an Editor. If
    spreadsheet_id is None, the step is skipped and returns False.
    """
    try:
        if spreadsheet_id is None:
            print("[load] sheets: skipped (no GOOGLE_SHEET_ID configured)")
            return False
        if df is None or len(df) == 0:
            print("[load] sheets: nothing to write")
            return False
        if not Path(credentials_file).is_file():
            print(f"[load] sheets: credentials file not found at {credentials_file}")
            return False

        # Imported lazily so the module loads even without these packages.
        from google.oauth2 import service_account
        from googleapiclient.discovery import build

        creds = service_account.Credentials.from_service_account_file(
            credentials_file, scopes=config.GOOGLE_SHEETS_SCOPE
        )
        service = build("sheets", "v4", credentials=creds, cache_discovery=False)

        _ensure_worksheet_exists(service, spreadsheet_id, worksheet)

        body = {"values": _df_as_rows(df)}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{worksheet}!A1",
            valueInputOption="RAW",
            body=body,
        ).execute()
        print(f"[load] sheets: wrote {len(df)} rows to sheet {spreadsheet_id}")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[load] sheets failed: {exc}")
        return False


def load_to_postgre(
    df: pd.DataFrame,
    db_url: Optional[str] = None,
    table: str = config.DEFAULT_POSTGRES_TABLE,
) -> bool:
    """Replace a Postgres table with the dataframe.

    Uses SQLAlchemy with the psycopg2 driver. If db_url is None, the step is
    skipped and returns False.
    """
    try:
        if db_url is None:
            print("[load] postgre: skipped (no POSTGRES_URL configured)")
            return False
        if df is None or len(df) == 0:
            print("[load] postgre: nothing to write")
            return False

        from sqlalchemy import create_engine

        engine = create_engine(db_url)
        try:
            df.to_sql(table, con=engine, if_exists="replace", index=False)
        finally:
            engine.dispose()
        print(f"[load] postgre: wrote {len(df)} rows to table '{table}'")
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[load] postgre failed: {exc}")
        return False


def load_all(
    df: pd.DataFrame,
    csv_filename: str = config.DEFAULT_CSV,
    spreadsheet_id: Optional[str] = None,
    google_credentials_file: str = config.DEFAULT_GOOGLE_CREDENTIALS,
    google_worksheet: str = config.DEFAULT_GOOGLE_WORKSHEET,
    db_url: Optional[str] = None,
    postgres_table: str = config.DEFAULT_POSTGRES_TABLE,
) -> dict:
    """Run all three writers and return a {repository: success} dict."""
    return {
        "csv": load_to_csv(df, filename=csv_filename),
        "google_sheets": load_to_google_sheets(
            df,
            credentials_file=google_credentials_file,
            spreadsheet_id=spreadsheet_id,
            worksheet=google_worksheet,
        ),
        "postgresql": load_to_postgre(df, db_url=db_url, table=postgres_table),
    }
