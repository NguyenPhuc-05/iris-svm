"""Run only in CI against a newly provisioned PostgreSQL integration database."""
import os
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi.testclient import TestClient

os.environ["JWT_SECRET"] = secrets.token_urlsafe(48)
os.environ["CLIENT_ID"] = "iris-svm-api"

from app.main import app
from database.db import SessionLocal, engine
from database.models import IrisUser

assert engine.dialect.name == "postgresql"
subject = "integration-user"
now = datetime.now(timezone.utc)
token = jwt.encode(
    {"sub": subject, "aud": "iris-svm-api", "email": "integration@example.test",
     "iat": now, "exp": now + timedelta(minutes=10)},
    os.environ["JWT_SECRET"], algorithm="HS256",
)
headers = {"Authorization": f"Bearer {token}"}
sample = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4,
          "petal_width": 0.2, "kernel": "rbf"}
with TestClient(app) as client:
    for _ in range(2):
        response = client.post("/predict", json=sample, headers=headers)
        assert response.status_code == 200 and response.json()["prediction"] == "setosa"
with SessionLocal() as db:
    assert db.query(IrisUser).filter_by(user_id=subject).count() == 1
engine.dispose()
with TestClient(app) as client:
    history = client.get("/predictions", headers=headers)
    assert history.status_code == 200 and len(history.json()) == 2
print("Iris PostgreSQL: profile and both predictions persisted across connections.")
