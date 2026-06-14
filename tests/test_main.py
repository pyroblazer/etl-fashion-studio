"""Unit tests for the main.py orchestrator."""

from __future__ import annotations

import pandas as pd

from utils import extract, transform
import main


def _make_raw():
    return pd.DataFrame(
        [
            {
                "Title": "T-shirt 2",
                "Price": "$102.15",
                "Rating": "⭐ 3.9 / 5",
                "Colors": "3 Colors",
                "Size": "Size: M",
                "Gender": "Gender: Women",
                "timestamp": "2025-01-01T00:00:00+00:00",
            }
        ]
    )


def test_main_runs_full_pipeline(monkeypatch, capsys):
    raw = _make_raw()
    monkeypatch.setattr(extract, "scrape_main", lambda: raw)
    monkeypatch.setattr(
        transform,
        "transform_data",
        lambda df: df.assign(Price=1.0, Rating=3.9, Colors=3, Size="M", Gender="Women"),
    )
    monkeypatch.setattr(
        main.load,
        "load_all",
        lambda **kwargs: {"csv": True, "google_sheets": False, "postgresql": False},
    )

    main.main()

    out = capsys.readouterr().out
    assert "ETL Summary" in out
    assert "raw rows" in out
    assert "clean rows" in out


def test_main_aborts_when_no_data(monkeypatch, capsys):
    monkeypatch.setattr(extract, "scrape_main", lambda: pd.DataFrame())

    main.main()

    out = capsys.readouterr().out
    assert "no data extracted" in out


def test_main_survives_extraction_failure(monkeypatch, capsys):
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(extract, "scrape_main", boom)

    main.main()  # must not raise

    out = capsys.readouterr().out
    assert "extraction failed" in out


def test_main_survives_transformation_failure(monkeypatch, capsys):
    monkeypatch.setattr(extract, "scrape_main", lambda: _make_raw())
    monkeypatch.setattr(
        transform, "transform_data", lambda df: (_ for _ in ()).throw(RuntimeError("bad"))
    )

    main.main()  # must not raise

    out = capsys.readouterr().out
    assert "transformation failed" in out
