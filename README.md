# ETL Fashion Studio

Final project for the Dicoding course **Belajar Fundamental Pemrosesan Data**.
This is a small ETL pipeline that scrapes product data from a competitor
fashion store at `https://fashion-studio.dicoding.dev/`, cleans it, and writes
the result to three places: a CSV file, a Google Sheet, and a PostgreSQL table.

## What the pipeline does

1. **Extract** - download all 50 listing pages (about 20 products each, 1000 in
   total) with `requests` and parse them with BeautifulSoup. Each record keeps
   its title, price, rating, number of colors, size, gender, and the moment it
   was scraped (`timestamp`).
2. **Transform** - clean and standardise the data:
   - Price converted from USD to IDR at a fixed rate of Rp 16.000 per USD.
   - Rating and Colors turned into real numbers.
   - `Size:` and `Gender:` prefixes removed.
   - Rows with invalid values dropped: `Unknown Product`, `Price Unavailable`,
     `Invalid Rating`, `Not Rated`, and any empty field.
   - Duplicate rows removed.
3. **Load** - save the cleaned data to CSV, Google Sheets, and PostgreSQL.

The run typically takes 1000 scraped rows down to about 867 clean ones.

## Project structure

```
etl-fashion-studio/
├── utils/
│   ├── __init__.py
│   ├── config.py        # constants and .env loader
│   ├── extract.py       # Extract stage (web scraping)
│   ├── transform.py     # Transform stage (cleaning + type conversion)
│   └── load.py          # Load stage (CSV / Google Sheets / PostgreSQL)
├── tests/
│   ├── conftest.py      # shared fixtures
│   ├── test_config.py
│   ├── test_extract.py
│   ├── test_transform.py
│   ├── test_load.py
│   └── test_main.py
├── main.py              # orchestrator: Extract -> Transform -> Load
├── requirements.txt
├── submission.txt       # how to run, test, and configure
├── products.csv         # output of the last run
├── google-sheets-api.json
├── .env.example
├── .coveragerc
└── .gitignore
```

## Requirements

- Python 3.14 (developed and tested on 3.14.4).
- Dependencies are listed in `requirements.txt`. All of them ship a prebuilt
  wheel for Python 3.14, so nothing is compiled from source.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

## Configuration

The pipeline reads its settings from environment variables, which can be placed
in a `.env` file at the project root. Copy `.env.example` to `.env` and fill in
the values. Any variable left empty just skips that repository.

| Variable | Purpose |
|---|---|
| `POSTGRES_URL` | PostgreSQL connection string in SQLAlchemy format. Empty skips Postgres. |
| `GOOGLE_SHEET_ID` | ID of the target spreadsheet. Empty skips Google Sheets. |
| `GOOGLE_CREDENTIALS_PATH` | Path to the service-account JSON. Defaults to `google-sheets-api.json`. |

## Usage

```bash
python main.py
```

Example end of the run:

```
============================================================
 ETL Summary
============================================================
  raw rows      : 1000
  clean rows    : 867
  repositories  :
    - csv           : OK
    - google_sheets : OK
    - postgresql    : OK
============================================================
```

A repository shows `SKIPPED / FAILED` when it is not configured or the write
could not complete. The other repositories still run.

## Testing and coverage

Run the unit tests:

```bash
python -m pytest tests
```

Run them with a coverage report:

```bash
coverage run -m pytest tests
coverage report -m

# or in one command:
pytest --cov=utils --cov=main --cov-report=term-missing tests
```

Latest run: 69 tests passing, 94% total coverage
(main.py 100%, transform 98%, load 97%, extract 87%, config 95%).

## The three data repositories

| Repository | Type | Where the data goes | Writer function |
|---|---|---|---|
| CSV | Flat file | `products.csv` | `load_to_csv` |
| Google Sheets | Cloud spreadsheet | the `Products` tab | `load_to_google_sheets` |
| PostgreSQL | Relational database | the `products` table | `load_to_postgre` |

Each writer is its own function inside `utils/load.py`, returns `True` on
success, and catches its own errors, so one failing destination never blocks
the others.

## Output

`products.csv` has one row per clean product with these columns:

| Column | Type | Notes |
|---|---|---|
| Title | object | product name |
| Price | float64 | in IDR (USD x 16.000) |
| Rating | float64 | 3.0 to 5.0 |
| Colors | int64 | number of colors |
| Size | object | S / M / L / XL / XXL |
| Gender | object | Men / Women / Unisex |
| timestamp | datetime | when the row was scraped |

## Google Sheets and PostgreSQL setup

A short summary; the full steps are in `submission.txt`.

- **Google Sheets**: replace `google-sheets-api.json` with your own service
  account key, share the sheet with the service account email as Editor, set
  link-sharing to "Anyone with the link" = Editor, and put the spreadsheet ID
  in `GOOGLE_SHEET_ID`.
- **PostgreSQL**: put a SQLAlchemy connection string in `POSTGRES_URL`.