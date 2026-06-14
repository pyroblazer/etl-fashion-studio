"""Unit tests for utils.config (env loading + secret getters)."""

from __future__ import annotations

import os

from utils import config


def test_load_env_reads_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        '# a comment\nPOSTGRES_URL=postgresql://u:p@h:5432/db\nGOOGLE_SHEET_ID="abc123"\n\n',
        encoding="utf-8",
    )
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)

    config.load_env(env_file)

    assert os.environ["POSTGRES_URL"] == "postgresql://u:p@h:5432/db"
    assert os.environ["GOOGLE_SHEET_ID"] == "abc123"


def test_load_env_does_not_overwrite_existing(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("POSTGRES_URL=from-file", encoding="utf-8")
    monkeypatch.setenv("POSTGRES_URL", "from-env")

    config.load_env(env_file)

    assert os.environ["POSTGRES_URL"] == "from-env"


def test_load_env_missing_file_is_silent(tmp_path):
    # No exception even though the file does not exist.
    config.load_env(tmp_path / "does-not-exist.env")


def test_load_env_skips_malformed_lines(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("no_equals_sign_here\nVALID=ok\n", encoding="utf-8")
    monkeypatch.delenv("VALID", raising=False)

    config.load_env(env_file)
    assert os.environ["VALID"] == "ok"


def test_get_postgres_url(monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    assert config.get_postgres_url() is None
    monkeypatch.setenv("POSTGRES_URL", "postgresql://x")
    assert config.get_postgres_url() == "postgresql://x"


def test_get_google_sheet_id(monkeypatch):
    monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
    assert config.get_google_sheet_id() is None
    monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet-1")
    assert config.get_google_sheet_id() == "sheet-1"


def test_get_google_credentials_path_default(monkeypatch):
    monkeypatch.delenv("GOOGLE_CREDENTIALS_PATH", raising=False)
    assert config.get_google_credentials_path() == config.DEFAULT_GOOGLE_CREDENTIALS


def test_get_google_credentials_path_override(monkeypatch):
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", "/tmp/key.json")
    assert config.get_google_credentials_path() == "/tmp/key.json"
