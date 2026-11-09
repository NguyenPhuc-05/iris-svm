import os
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

# Configure test environment
os.environ["DATABASE_URL"] = "sqlite:///./test_iris.db"
os.environ["JWT_SECRET"] = "iris-test-jwt-secret-key-32bytes!!"
os.environ["CLIENT_ID"] = "iris-svm-api"

from app.main import app
from shared.auth import get_current_user


@pytest.fixture(autouse=True)
def default_auth_override():
    """Maintain backward compatibility for existing 14 tests by overriding auth dependency."""
    app.dependency_overrides[get_current_user] = lambda: {
        "id": "test-user-default",
        "email": "student@iris.ai",
        "aud": "iris-svm-api",
    }
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


# ==============================================================================
# EXISTING 14 TESTS (PRESERVED & PASSING)
# ==============================================================================

def test_health_reports_loaded_model():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["model_loaded"] is True
    assert "rbf" in data["models_loaded"]
    assert "linear" in data["models_loaded"]


def test_metadata_describes_multikernel_models():
    response = client.get("/metadata")
    assert response.status_code == 200
    body = response.json()
    assert len(body["models"]) == 4
    kernels = [m["kernel"] for m in body["models"]]
    assert set(kernels) == {"linear", "rbf", "poly", "sigmoid"}
    assert len(body["feature_names"]) == 4


def test_models_endpoint():
    response = client.get("/models")
    assert response.status_code == 200
    body = response.json()
    assert "default_kernel" in body
    assert len(body["models"]) == 4


def test_predict_setosa_sample():
    response = client.post(
        "/predict",
        json={
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
            "kernel": "rbf",
        },
    )
    assert response.status_code == 200
    assert response.json()["class_id"] == 0
    assert response.json()["prediction"] == "setosa"
    assert response.json()["kernel"] == "rbf"


def test_predict_returns_result_when_history_is_unavailable(monkeypatch):
    from app import main

    def unavailable(*args, **kwargs):
        raise HTTPException(status_code=503, detail="History unavailable")

    monkeypatch.setattr(main, "history_request", unavailable)
    response = client.post(
        "/predict",
        json={
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
            "kernel": "rbf",
        },
    )
    assert response.status_code == 200
    assert response.json()["prediction"] == "setosa"
    assert response.json()["id"] is None


def test_predict_all_kernels():
    for kernel in ["linear", "rbf", "poly", "sigmoid"]:
        response = client.post(
            "/predict",
            json={
                "sepal_length": 6.0,
                "sepal_width": 3.0,
                "petal_length": 4.5,
                "petal_width": 1.5,
                "kernel": kernel,
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["kernel"] == kernel
        assert data["prediction"] in ["setosa", "versicolor", "virginica"]
        assert 0.0 <= data["probability"] <= 1.0


def test_predict_rejects_missing_field():
    response = client.post(
        "/predict",
        json={
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
        },
    )
    assert response.status_code == 422


def test_predict_rejects_out_of_range_value():
    response = client.post(
        "/predict",
        json={
            "sepal_length": 99,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
        },
    )
    assert response.status_code == 422


def test_decision_boundary():
    response = client.get("/decision-boundary?kernel=linear&resolution=30")
    assert response.status_code == 200
    data = response.json()
    assert data["kernel"] == "linear"
    assert len(data["grid"]) == 30


def test_support_vectors_endpoint():
    for kernel in ["linear", "rbf"]:
        res = client.get(f"/support-vectors?kernel={kernel}")
        assert res.status_code == 200
        data = res.json()
        assert data["total_support_vectors"] > 0
        assert "setosa" in data["n_support_per_class"]
        assert len(data["support_vectors"]) == data["total_support_vectors"]
        if kernel == "linear":
            assert "coef" in data
            assert "intercept" in data


def test_svm_playground_endpoint():
    res = client.get("/svm-playground?kernel=rbf&C=10.0&gamma=0.5&resolution=25")
    assert res.status_code == 200
    data = res.json()
    assert data["train_accuracy"] > 80.0
    assert data["total_support_vectors"] > 0
    assert len(data["grid"]) == 25
    assert "diagnosis" in data


def test_kernel_arena_endpoint():
    res = client.get("/kernel-arena")
    assert res.status_code == 200
    arena = res.json()["arena"]
    assert len(arena) == 4
    kernels = [x["kernel"] for x in arena]
    assert set(kernels) == {"linear", "rbf", "poly", "sigmoid"}
    for item in arena:
        assert item["latency_ms"] >= 0
        assert len(item["mini_grid"]) == item["resolution"]


def test_explain_endpoint():
    res = client.post(
        "/explain",
        json={
            "sepal_length": 5.1,
            "sepal_width": 3.5,
            "petal_length": 1.4,
            "petal_width": 0.2,
            "kernel": "rbf",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["prediction"] == "setosa"
    assert len(data["attributions"]) == 4
    assert "explanation" in data


def test_batch_prediction_and_sample_csv():
    # Test batch prediction
    res = client.post(
        "/predict-batch",
        json={
            "samples": [
                {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "linear"},
                {"sepal_length": 6.7, "sepal_width": 3.1, "petal_length": 4.7, "petal_width": 1.5, "kernel": "rbf"},
            ]
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    assert len(data["predictions"]) == 2

    # Test sample CSV download
    csv_res = client.get("/sample-csv")
    assert csv_res.status_code == 200
    assert "text/csv" in csv_res.headers.get("content-type", "")
    assert "sepal_length" in csv_res.text


def test_predictions_history_and_export():
    client.post(
        "/predict",
        json={
            "sepal_length": 5.0,
            "sepal_width": 3.4,
            "petal_length": 1.5,
            "petal_width": 0.2,
            "kernel": "linear",
        },
    )
    res = client.get("/predictions?limit=10")
    assert res.status_code == 200
    assert len(res.json()) > 0

    export_res = client.get("/predictions/export")
    assert export_res.status_code == 200
    assert "spreadsheetml" in export_res.headers.get("content-type", "")


# ==============================================================================
# NEW AUTHENTICATION & CENTRALIZED IDP INTEGRATION TESTS
# ==============================================================================

def test_unauthenticated_endpoints_return_401():
    """Verify protected endpoints reject requests when no Authorization header is provided."""
    app.dependency_overrides.clear()  # Remove mock override

    endpoints = [
        ("POST", "/predict", {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"}),
        ("POST", "/predict-batch", {"samples": [{"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"}]}),
        ("POST", "/explain", {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"}),
        ("GET", "/predictions", None),
        ("GET", "/predictions/export", None),
        ("DELETE", "/predictions", None),
    ]

    for method, path, body in endpoints:
        if method == "POST":
            res = client.post(path, json=body)
        elif method == "GET":
            res = client.get(path)
        elif method == "DELETE":
            res = client.delete(path)
        assert res.status_code == 401, f"{method} {path} should return 401 when unauthenticated, got {res.status_code}"


def test_wrong_audience_token_rejected_with_401():
    """Verify that a valid JWT token intended for another client (wrong aud) is rejected."""
    app.dependency_overrides.clear()

    wrong_aud_token = jwt.encode(
        {
            "sub": "user-999",
            "email": "user@breast-cancer.ai",
            "aud": "breast-cancer-api",  # Wrong audience for iris-svm-api
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

    res = client.post(
        "/predict",
        headers={"Authorization": f"Bearer {wrong_aud_token}"},
        json={"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"},
    )
    assert res.status_code == 401
    assert "Audience mismatch" in res.json()["detail"]


def test_valid_token_authenticates_successfully():
    """Verify that a correctly signed JWT with aud=iris-svm-api succeeds without overrides."""
    app.dependency_overrides.clear()

    valid_token = jwt.encode(
        {
            "sub": "user-888",
            "email": "valid-student@iris.ai",
            "aud": "iris-svm-api",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
        },
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

    res = client.post(
        "/predict",
        headers={"Authorization": f"Bearer {valid_token}"},
        json={"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"},
    )
    assert res.status_code == 200
    assert res.json()["prediction"] == "setosa"


def test_per_user_history_isolation():
    """Verify user prediction history is completely isolated between users."""
    app.dependency_overrides.clear()

    user_a_token = jwt.encode(
        {"sub": "user-A", "email": "a@iris.ai", "aud": "iris-svm-api", "exp": datetime.now(timezone.utc) + timedelta(minutes=60)},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )
    user_b_token = jwt.encode(
        {"sub": "user-B", "email": "b@iris.ai", "aud": "iris-svm-api", "exp": datetime.now(timezone.utc) + timedelta(minutes=60)},
        os.environ["JWT_SECRET"],
        algorithm="HS256",
    )

    # 1. Clear both histories first
    client.delete("/predictions", headers={"Authorization": f"Bearer {user_a_token}"})
    client.delete("/predictions", headers={"Authorization": f"Bearer {user_b_token}"})

    # 2. User A makes 1 prediction
    client.post(
        "/predict",
        headers={"Authorization": f"Bearer {user_a_token}"},
        json={"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"},
    )

    # 3. User B makes 2 predictions
    for _ in range(2):
        client.post(
            "/predict",
            headers={"Authorization": f"Bearer {user_b_token}"},
            json={"sepal_length": 6.0, "sepal_width": 3.0, "petal_length": 4.5, "petal_width": 1.5, "kernel": "linear"},
        )

    # 4. Check User A only sees 1 prediction belonging to user A
    res_a = client.get("/predictions", headers={"Authorization": f"Bearer {user_a_token}"})
    assert res_a.status_code == 200
    records_a = res_a.json()
    assert len(records_a) == 1
    assert records_a[0]["username"] == "a@iris.ai"

    # 5. Check User B only sees 2 predictions belonging to user B
    res_b = client.get("/predictions", headers={"Authorization": f"Bearer {user_b_token}"})
    assert res_b.status_code == 200
    records_b = res_b.json()
    assert len(records_b) == 2
    for r in records_b:
        assert r["username"] == "b@iris.ai"

    # 6. User A deletes their history: User B history must remain intact!
    client.delete("/predictions", headers={"Authorization": f"Bearer {user_a_token}"})
    assert len(client.get("/predictions", headers={"Authorization": f"Bearer {user_a_token}"}).json()) == 0
    assert len(client.get("/predictions", headers={"Authorization": f"Bearer {user_b_token}"}).json()) == 2

def test_admin_predictions_accessible_by_owner_without_usernames():
    # Generate an owner token
    secret = os.environ.get("JWT_SECRET", "iris-test-jwt-secret-key-32bytes!!")
    now = datetime.now(timezone.utc)
    owner_token = jwt.encode(
        {"sub": "owner-1", "email": "admin@ml-dl-ai.local", "aud": "iris-svm-api", "is_owner": True, "iat": now, "exp": now + timedelta(hours=1)},
        secret,
        algorithm="HS256"
    )

    # Make a prediction to ensure data exists
    client.post(
        "/predict",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2, "kernel": "rbf"},
    )

    # Call admin predictions
    res = client.get("/admin/predictions", headers={"Authorization": f"Bearer {owner_token}"})
    assert res.status_code == 200
    items = res.json()
    assert len(items) >= 1

    # SECURITY CHECK: Tuyệt đối KHÔNG hiển thị username hay email người dùng trong lịch sử
    for item in items:
        assert "username" not in item
        assert "user_id" not in item
        assert "email" not in item
        assert "created_at" in item
        assert "kernel" in item
        assert "prediction" in item
        assert "probability" in item


def test_admin_predictions_forbidden_for_regular_user():
    secret = os.environ.get("JWT_SECRET", "iris-test-jwt-secret-key-32bytes!!")
    now = datetime.now(timezone.utc)
    # Regular user token without is_owner
    regular_token = jwt.encode(
        {"sub": "regular-99", "email": "user@iris.ai", "aud": "iris-svm-api", "is_owner": False, "iat": now, "exp": now + timedelta(hours=1)},
        secret,
        algorithm="HS256"
    )

    res = client.get("/admin/predictions", headers={"Authorization": f"Bearer {regular_token}"})
    assert res.status_code == 403
    assert "chủ sở hữu" in res.json()["detail"].lower()


def _owner_token(secret=None, exp_delta=timedelta(hours=1)):
    secret = secret or os.environ.get("JWT_SECRET", "iris-test-jwt-secret-key-32bytes!!")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": "owner-1", "email": "admin@ml-dl-ai.local", "aud": "iris-svm-api",
         "is_owner": True, "iat": now, "exp": now + exp_delta},
        secret,
        algorithm="HS256",
    )


def test_admin_predictions_limit_is_capped():
    headers = {"Authorization": f"Bearer {_owner_token()}"}
    assert client.get("/admin/predictions?limit=500", headers=headers).status_code == 200
    assert client.get("/admin/predictions?limit=501", headers=headers).status_code == 422
    assert client.get("/admin/predictions?limit=0", headers=headers).status_code == 422


def test_admin_predictions_requires_valid_token():
    assert client.get("/admin/predictions").status_code == 401

    forged = _owner_token(secret="a-different-secret-that-is-32-chars-long!!")
    res = client.get("/admin/predictions", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401

    expired = _owner_token(exp_delta=timedelta(hours=-1))
    res = client.get("/admin/predictions", headers={"Authorization": f"Bearer {expired}"})
    assert res.status_code == 401


def test_cors_only_allows_configured_origins():
    allowed = client.get("/health", headers={"Origin": "http://localhost:5500"})
    assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5500"

    blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


# ==============================================================================
# TESTS CHO TÍNH NĂNG ĐỘT PHÁ SÁNG TẠO MỚI (KKT, 3D PCA, STRESS TEST)
# ==============================================================================

def test_support_vectors_kkt_analysis():
    res = client.get("/support-vectors?kernel=rbf")
    assert res.status_code == 200
    data = res.json()
    assert "kkt_analysis" in data
    kkt = data["kkt_analysis"]
    assert kkt["free_sv_count"] + kkt["bounded_sv_count"] == data["total_support_vectors"]
    assert len(data["support_vectors"]) > 0
    first_sv = data["support_vectors"][0]
    assert "alpha" in first_sv
    assert "is_bounded" in first_sv
    assert "kkt_type" in first_sv


def test_pca_3d_endpoint():
    res = client.get("/pca-3d?kernel=rbf&user_sl=5.1&user_sw=3.5&user_pl=1.4&user_pw=0.2")
    assert res.status_code == 200
    data = res.json()
    assert len(data["points"]) == 150
    assert data["total_explained_variance"] > 95.0
    assert data["user_projection"] is not None
    assert "x" in data["user_projection"]
    assert "y" in data["user_projection"]
    assert "z" in data["user_projection"]


def test_stress_test_endpoint():
    res = client.get("/stress-test?noise_level=0.2&outliers=2&seed=42")
    assert res.status_code == 200
    data = res.json()
    assert data["noise_level"] == 0.2
    assert data["outliers"] == 2
    assert len(data["results"]) == 4
    for r in data["results"]:
        assert "robustness_score" in r
        assert "accuracy_on_noisy" in r
        assert "diagnosis" in r


def test_label_matches_svm_decision_not_platt_argmax():
    """Verify that class label strictly equals model.predict() even when Platt scaling probabilities disagree."""
    from sklearn.datasets import load_iris
    from app.main import models, metadata

    iris = load_iris()
    sample = iris.data[72]
    model = models["poly"]
    expected_pred_idx = int(model.predict([sample])[0])
    expected_label = metadata["class_mapping"][str(expected_pred_idx)]

    res = client.post(
        "/predict",
        json={
            "sepal_length": float(sample[0]),
            "sepal_width": float(sample[1]),
            "petal_length": float(sample[2]),
            "petal_width": float(sample[3]),
            "kernel": "poly",
        },
    )
    assert res.status_code == 200
    assert res.json()["prediction"] == expected_label

    batch_res = client.post(
        "/predict-batch",
        json={
            "samples": [
                {
                    "sepal_length": float(sample[0]),
                    "sepal_width": float(sample[1]),
                    "petal_length": float(sample[2]),
                    "petal_width": float(sample[3]),
                    "kernel": "poly",
                }
            ]
        },
    )
    assert batch_res.status_code == 200
    assert batch_res.json()["predictions"][0]["class_id"] == expected_pred_idx
    assert batch_res.json()["predictions"][0]["prediction"] == expected_label


def test_owner_token_for_another_service_cannot_list_iris_predictions():
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {"sub": "owner-1", "aud": "another-api", "is_owner": True,
         "exp": now + timedelta(minutes=5)},
        os.environ["JWT_SECRET"], algorithm="HS256",
    )
    res = client.get("/admin/predictions", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
