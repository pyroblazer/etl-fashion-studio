"""ETL utilities for the Fashion Studio project.

The pipeline is split into three stages, each in its own module:
  - extract:   scrape raw product data from the website.
  - transform: clean and type-cast the data.
  - load:      write the data to CSV, Google Sheets, and PostgreSQL.
"""

__all__ = ["config", "extract", "transform", "load"]
