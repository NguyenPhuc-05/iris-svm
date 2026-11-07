import os
import pytest
from fastapi.testclient import TestClient

# Ensure test DB and secret
os.environ["DATABASE_URL"] = "sqlite:///./test_identity.db"
os.environ["IDP_DATABASE_URL"] = "sqlite:///./test_identity.db"
os.environ["JWT_SECRET"] = "identity-test-jwt-secret-min32chars!!"
os.environ["CLIENT_IDS"] = "iris-svm-api,breast-cancer-api"

from app.main import app
from app.db import Base, engine
from app.models import init_db

@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_identity.db"):
        try:
            os.remove("./test_identity.db")
        except Exception:
            pass

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_login_limiter():
    from app.main import login_limiter
    login_limiter.clear()
    yield
    login_limiter.clear()


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "service": "identity-service"}


def test_register_and_login_success():
    # 1. Register
    reg_res = client.post(
        "/register",
        json={"email": "student@example.com", "password": "password123"},
    )
    assert reg_res.status_code == 201
    reg_data = reg_res.json()
    assert reg_data["email"] == "student@example.com"
    assert "id" in reg_data

    # 2. Login
    login_res = client.post(
        "/login",
        json={
            "email": "student@example.com",
            "password": "password123",
            "client_id": "iris-svm-api",
        },
    )
    assert login_res.status_code == 200
    login_data = login_res.json()
    assert "access_token" in login_data
    assert login_data["token_type"] == "bearer"
    assert login_data["user"]["email"] == "student@example.com"

    # 3. Test /me
    token = login_data["access_token"]
    me_res = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "student@example.com"


def test_register_duplicate_email():
    client.post(
        "/register",
        json={"email": "student@example.com", "password": "password123"},
    )
    duplicate_res = client.post(
        "/register",
        json={"email": "student@example.com", "password": "other_password"},
    )
    assert duplicate_res.status_code == 400
    assert "Email đã được đăng ký" in duplicate_res.json()["detail"]


def test_register_short_password_rejected():
    res = client.post(
        "/register",
        json={"email": "shortpass@example.com", "password": "short"},
    )
    assert res.status_code == 422


def test_login_wrong_password():
    client.post(
        "/register",
        json={"email": "student@example.com", "password": "password123"},
    )
    res = client.post(
        "/login",
        json={
            "email": "student@example.com",
            "password": "wrongpassword",
            "client_id": "iris-svm-api",
        },
    )
    assert res.status_code == 401
    assert "Sai email hoặc mật khẩu" in res.json()["detail"]


def test_login_unknown_client_id():
    client.post(
        "/register",
        json={"email": "student@example.com", "password": "password123"},
    )
    res = client.post(
        "/login",
        json={
            "email": "student@example.com",
            "password": "password123",
            "client_id": "unknown-service-api",
        },
    )
    assert res.status_code == 400
    assert "Unknown client_id" in res.json()["detail"]


def test_me_unauthorized():
    res = client.get("/me")
    assert res.status_code == 401

def test_owner_account_seeded_and_can_access_admin():
    # Login as seeded owner
    owner_email = os.getenv("OWNER_EMAIL", "admin@ml-dl-ai.local")
    owner_pwd = os.getenv("OWNER_PASSWORD", "test-owner-password-12345")

    login_res = client.post(
        "/login",
        json={
            "email": owner_email,
            "password": owner_pwd,
            "client_id": "iris-svm-api",
        },
    )
    assert login_res.status_code == 200
    data = login_res.json()
    assert data["user"]["is_owner"] is True
    token = data["access_token"]

    # Owner can access /admin/users
    admin_res = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 200
    users = admin_res.json()
    assert any(u["email"] == owner_email and u["is_owner"] is True for u in users)




def test_configured_owner_login_repairs_stale_password_hash(monkeypatch):
    from app.models import User
    from app.main import hash_password

    owner_email = "configured-owner@example.com"
    owner_password = "render-owner-secret-123"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", owner_password)

    # Simulate a stale password hash left behind by an earlier deployment.
    from app.db import SessionLocal
    db = SessionLocal()
    try:
        stale_owner = User(
            email=owner_email,
            password_hash=hash_password("old-owner-password"),
            is_owner=True,
        )
        db.add(stale_owner)
        db.commit()
    finally:
        db.close()

    login_res = client.post(
        "/login",
        json={
            "email": owner_email,
            "password": owner_password,
            "client_id": "iris-svm-api",
        },
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["is_owner"] is True

def test_configured_owner_login_with_non_ascii_password(monkeypatch):
    owner_email = "unicode-owner@example.com"
    owner_password = "mậtkhẩu-quản-trị-123"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", owner_password)

    login_res = client.post(
        "/login",
        json={"email": owner_email, "password": owner_password, "client_id": "iris-svm-api"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["is_owner"] is True


def test_configured_owner_login_tolerates_whitespace_in_env_secret(monkeypatch):
    owner_email = "spaced-owner@example.com"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", "render-owner-secret-123\n")

    login_res = client.post(
        "/login",
        json={"email": owner_email, "password": "render-owner-secret-123", "client_id": "iris-svm-api"},
    )
    assert login_res.status_code == 200
    assert login_res.json()["user"]["is_owner"] is True


def test_configured_owner_wrong_password_rejected(monkeypatch):
    owner_email = "strict-owner@example.com"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", "render-owner-secret-123")

    login_res = client.post(
        "/login",
        json={"email": owner_email, "password": "wrong-password-xyz", "client_id": "iris-svm-api"},
    )
    assert login_res.status_code == 401


@pytest.mark.parametrize(
    "bad_email",
    [
        "<img src=x onerror=alert(1)>@evil.com",
        "no-at-sign.example.com",
        "has space@example.com",
        "quote\"@example.com",
        "a@b",
        "a@@example.com",
    ],
)
def test_register_rejects_invalid_or_html_emails(bad_email):
    res = client.post("/register", json={"email": bad_email, "password": "password123"})
    assert res.status_code == 422


def test_register_accepts_normal_email_and_normalizes_case():
    res = client.post("/register", json={"email": "  Student.Name+1@Example.com ", "password": "password123"})
    assert res.status_code == 201
    assert res.json()["email"] == "student.name+1@example.com"


def _login(email, password):
    return client.post(
        "/login",
        json={"email": email, "password": password, "client_id": "iris-svm-api"},
    )


def test_login_is_rate_limited_after_repeated_failures():
    client.post("/register", json={"email": "victim@example.com", "password": "password123"})

    for _ in range(5):
        assert _login("victim@example.com", "wrong-password").status_code == 401

    blocked = _login("victim@example.com", "wrong-password")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers

    # Even the correct password is refused while the block is active.
    assert _login("victim@example.com", "password123").status_code == 429

    # Another account is not affected.
    client.post("/register", json={"email": "other@example.com", "password": "password123"})
    assert _login("other@example.com", "password123").status_code == 200


def test_successful_login_resets_failure_counter():
    client.post("/register", json={"email": "forgetful@example.com", "password": "password123"})

    for _ in range(4):
        assert _login("forgetful@example.com", "wrong-password").status_code == 401
    assert _login("forgetful@example.com", "password123").status_code == 200

    # Counter was reset, so four more wrong tries are still allowed.
    for _ in range(4):
        assert _login("forgetful@example.com", "wrong-password").status_code == 401


def test_email_wide_limit_blocks_rotating_forwarded_ips():
    client.post("/register", json={"email": "target@example.com", "password": "password123"})

    status_codes = []
    for i in range(35):
        res = client.post(
            "/login",
            json={"email": "target@example.com", "password": "wrong-password", "client_id": "iris-svm-api"},
            headers={"X-Forwarded-For": f"203.0.113.{i}"},
        )
        status_codes.append(res.status_code)

    assert status_codes[:30] == [401] * 30
    assert 429 in status_codes[30:]


LEAKED_OWNER_PASSWORD = "Admin@" + "ML2024!!"  # từng nằm trong lịch sử git công khai


def test_is_public_secret_detects_leaked_defaults():
    from app.public_secrets import is_public_secret

    assert is_public_secret(LEAKED_OWNER_PASSWORD)
    assert is_public_secret(LEAKED_OWNER_PASSWORD + "\n")
    assert not is_public_secret("a-brand-new-owner-secret-0f3c9d")
    assert not is_public_secret("")


def test_leaked_default_owner_password_is_rejected(monkeypatch):
    owner_email = "leaky-owner@example.com"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", LEAKED_OWNER_PASSWORD)

    res = client.post(
        "/login",
        json={"email": owner_email, "password": LEAKED_OWNER_PASSWORD, "client_id": "iris-svm-api"},
    )
    assert res.status_code == 401


def test_seed_owner_disables_old_hash_of_leaked_password(monkeypatch):
    from app.db import SessionLocal
    from app.main import hash_password
    from app.models import User, seed_owner

    owner_email = "stale-leaky-owner@example.com"
    monkeypatch.setenv("OWNER_EMAIL", owner_email)
    monkeypatch.setenv("OWNER_PASSWORD", LEAKED_OWNER_PASSWORD)

    db = SessionLocal()
    try:
        db.add(User(email=owner_email, password_hash=hash_password(LEAKED_OWNER_PASSWORD), is_owner=True))
        db.commit()
    finally:
        db.close()

    seed_owner()

    res = client.post(
        "/login",
        json={"email": owner_email, "password": LEAKED_OWNER_PASSWORD, "client_id": "iris-svm-api"},
    )
    assert res.status_code == 401


def test_regular_user_forbidden_from_admin():
    # Register and login as regular user
    client.post("/register", json={"email": "regular@example.com", "password": "regularpassword123"})
    login_res = client.post(
        "/login",
        json={"email": "regular@example.com", "password": "regularpassword123", "client_id": "iris-svm-api"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]

    # Regular user is forbidden (403) from /admin/users
    admin_res = client.get("/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 403
    assert "chủ sở hữu" in admin_res.json()["detail"].lower()
