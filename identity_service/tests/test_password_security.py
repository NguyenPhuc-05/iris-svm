"""Mật khẩu chỉ được lưu dưới dạng hash bcrypt và không bao giờ lộ qua API
(kể cả với tài khoản quản trị)."""

import os

import bcrypt
import pytest
from fastapi.testclient import TestClient

# Luôn dùng CSDL thử: các test dưới đây gọi drop_all, tuyệt đối không được chạy trên
# CSDL thật dù biến IDP_DATABASE_URL trên máy đang trỏ tới đó.
os.environ["DATABASE_URL"] = "sqlite:///./test_identity.db"
os.environ["IDP_DATABASE_URL"] = "sqlite:///./test_identity.db"
os.environ.setdefault("JWT_SECRET", "identity-test-jwt-secret-min32chars!!")
os.environ.setdefault("CLIENT_IDS", "iris-svm-api,breast-cancer-api")

from app.db import Base, SessionLocal, engine, normalize_db_url  # noqa: E402
from app.main import app, login_limiter  # noqa: E402
from app.models import User, init_db  # noqa: E402

CLIENT = "iris-svm-api"
OWNER_EMAIL = "admin@ml-dl-ai.local"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("OWNER_EMAIL", OWNER_EMAIL)
    monkeypatch.setenv("OWNER_PASSWORD", "test-owner-password-12345")
    Base.metadata.drop_all(bind=engine)
    init_db()
    login_limiter.clear()
    with TestClient(app) as c:
        yield c
    login_limiter.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _login(client, email, password):
    return client.post("/login", json={"email": email, "password": password, "client_id": CLIENT})


def _flatten(obj):
    """Gom mọi khóa và giá trị chuỗi trong JSON để rà soát."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower()
            yield from _flatten(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _flatten(item)
    elif obj is not None:
        yield str(obj)


def test_database_stores_bcrypt_hash_not_plaintext(client):
    password = "Mat-khau-rieng-cua-user-1"
    assert client.post("/register", json={"email": "user1@example.com", "password": password}).status_code == 201

    db = SessionLocal()
    try:
        stored = db.query(User).filter(User.email == "user1@example.com").one().password_hash
    finally:
        db.close()

    assert stored != password
    assert password not in stored
    assert stored.startswith("$2")  # định dạng bcrypt ($2a$/$2b$/$2y$)
    assert bcrypt.checkpw(password.encode(), stored.encode())


def test_same_password_gives_different_hashes(client):
    """Mỗi tài khoản có salt riêng: cùng mật khẩu vẫn cho hash khác nhau."""
    password = "Cung-mot-mat-khau-123"
    for email in ("a@example.com", "b@example.com"):
        assert client.post("/register", json={"email": email, "password": password}).status_code == 201

    db = SessionLocal()
    try:
        hashes = [u.password_hash for u in db.query(User).filter(User.email.in_(["a@example.com", "b@example.com"]))]
    finally:
        db.close()
    assert len(hashes) == 2 and hashes[0] != hashes[1]


def test_register_login_me_and_admin_never_expose_password_or_hash(client):
    password = "Khong-bao-gio-lo-ra-ngoai-99"
    reg = client.post("/register", json={"email": "victim@example.com", "password": password})
    assert reg.status_code == 201

    login = _login(client, "victim@example.com", password)
    assert login.status_code == 200
    user_token = login.json()["access_token"]

    owner = _login(client, OWNER_EMAIL, "test-owner-password-12345")
    assert owner.status_code == 200
    owner_token = owner.json()["access_token"]

    responses = {
        "register": reg.json(),
        "login": login.json(),
        "me": client.get("/me", headers={"Authorization": f"Bearer {user_token}"}).json(),
        "admin_users": client.get("/admin/users", headers={"Authorization": f"Bearer {owner_token}"}).json(),
    }
    assert any(u["email"] == "victim@example.com" for u in responses["admin_users"])

    for name, body in responses.items():
        flat = list(_flatten(body))
        assert not any("hash" in item or "password" in item for item in flat if item.islower()), name
        assert all(password not in item for item in flat), name
        assert all("$2b$" not in item and "$2a$" not in item for item in flat), name


def test_admin_endpoint_requires_owner(client):
    password = "Nguoi-dung-thuong-123"
    client.post("/register", json={"email": "normal@example.com", "password": password})
    token = _login(client, "normal@example.com", password).json()["access_token"]
    assert client.get("/admin/users", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/admin/users").status_code in (401, 403)


def test_normalize_db_url_accepts_provider_urls():
    assert normalize_db_url("postgres://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert normalize_db_url("  postgres://u:p@host/db?sslmode=require \n") == "postgresql+psycopg2://u:p@host/db?sslmode=require"
    assert normalize_db_url("postgresql://u:p@host/db") == "postgresql+psycopg2://u:p@host/db"
    assert normalize_db_url("postgresql+psycopg://u:p@host/db") == "postgresql+psycopg://u:p@host/db"  # giữ nguyên driver đã chọn
    assert normalize_db_url("sqlite:///./x.db") == "sqlite:///./x.db"
