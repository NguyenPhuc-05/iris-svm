"""Cấu hình CSDL: không được lặng lẽ chuyển sang SQLite khi đã đặt DATABASE_URL."""

import pytest

from database.db import connect_database, normalize_db_url


def test_normalize_db_url_accepts_provider_urls():
    assert normalize_db_url("postgres://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert normalize_db_url(" postgres://u:p@host/db?sslmode=require\n") == "postgresql+psycopg2://u:p@host/db?sslmode=require"
    assert normalize_db_url("postgresql://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert normalize_db_url("sqlite:///./x.db") == "sqlite:///./x.db"


def test_explicit_database_url_that_cannot_connect_raises_instead_of_falling_back():
    # Cổng 1 từ chối kết nối ngay: mô phỏng URL sai/Postgres chưa sẵn sàng.
    with pytest.raises(RuntimeError) as err:
        connect_database("postgresql://user:SECRET-PASSWORD@127.0.0.1:1/nodb")
    assert "SECRET-PASSWORD" not in str(err.value)  # không làm lộ mật khẩu CSDL trong log


def test_explicit_sqlite_url_connects():
    engine = connect_database("sqlite:///./test_iris.db")
    assert engine.dialect.name == "sqlite"


def test_render_requires_explicit_postgres(monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    with pytest.raises(RuntimeError, match="DATABASE_URL is required"):
        connect_database(None)
    with pytest.raises(RuntimeError, match="must point to PostgreSQL"):
        connect_database("sqlite:///./test_iris.db")
