"""Entry point for the Fashion Studio ETL pipeline.

Run with:

    python main.py

It runs extract -> transform -> load. Each stage is guarded, so a failure
in one repository or stage does not stop the rest. The Postgres URL and
Google Sheet id are read from environment variables or a local .env file;
if either is missing the corresponding repository is skipped.
"""

from __future__ import annotations

from utils import config, extract, load, transform


def main() -> None:
    """Run the full ETL pipeline."""
    config.load_env()

    print("=" * 60)
    print(" Fashion Studio - ETL Pipeline")
    print("=" * 60)

    # Extract
    print("\n[1/3] Extracting data from Fashion Studio...")
    try:
        raw_df = extract.scrape_main()
        print(f"      extracted {len(raw_df)} raw records")
    except Exception as exc:  # noqa: BLE001
        print(f"[main] extraction failed: {exc}")
        return

    if len(raw_df) == 0:
        print("[main] no data extracted; aborting.")
        return

    # Transform
    print("\n[2/3] Transforming data...")
    try:
        clean_df = transform.transform_data(raw_df)
        print(f"      {len(raw_df)} -> {len(clean_df)} records after cleaning")
    except Exception as exc:  # noqa: BLE001
        print(f"[main] transformation failed: {exc}")
        return

    # Load
    print("\n[3/3] Loading data to repositories...")
    try:
        results = load.load_all(
            clean_df,
            csv_filename=config.DEFAULT_CSV,
            spreadsheet_id=config.get_google_sheet_id(),
            google_credentials_file=config.get_google_credentials_path(),
            google_worksheet=config.DEFAULT_GOOGLE_WORKSHEET,
            db_url=config.get_postgres_url(),
            postgres_table=config.DEFAULT_POSTGRES_TABLE,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[main] loading failed: {exc}")
        results = {"csv": False, "google_sheets": False, "postgresql": False}

    print("\n" + "=" * 60)
    print(" ETL Summary")
    print("=" * 60)
    print(f"  raw rows      : {len(raw_df)}")
    print(f"  clean rows    : {len(clean_df)}")
    print("  repositories  :")
    for repo, ok in results.items():
        print(f"    - {repo:<14}: {'OK' if ok else 'SKIPPED / FAILED'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
