"""
Iris Classification API — Multi-Kernel SVM với SQLite & các tính năng ML nâng cao.

API phân loại hoa Iris dùng 4 kernel SVM (linear, rbf, poly, sigmoid), lưu lịch sử
dự đoán theo từng user (JWT), xuất Excel, trực quan hóa decision boundary và XAI.
"""

import io
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Thêm root directory và repo root vào sys.path để import database và shared.auth
BASE_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BASE_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from backend.app.history import history_request
from shared.auth import get_current_user
from fastapi import Depends, Security
from fastapi.security import HTTPBearer

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET environment variable is missing or shorter than 32 characters.")

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from sklearn import datasets
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

# ─── Load Iris Dataset for analysis ───
iris_dataset = datasets.load_iris()
X_iris = iris_dataset.data
y_iris = iris_dataset.target
IRIS_MEDIANS = np.median(X_iris, axis=0)

# ─── Global 3D PCA Projection (~99.5% variance preserved) ───
pca_3d = PCA(n_components=3, random_state=42).fit(X_iris)
X_iris_pca_3d = pca_3d.transform(X_iris)

BASE_DIR = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = BASE_DIR / "artifacts"
METADATA_PATH = ARTIFACT_DIR / "metadata.json"

# ─── Load metadata & models ───
metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
models = {m["kernel"]: joblib.load(ARTIFACT_DIR / m["model_file"]) for m in metadata["models"]}
DEFAULT_KERNEL = metadata.get("default_kernel", "rbf")



def configured_origins() -> list[str]:
    default_origins = [
        "https://iris-svm-frontend-6s3t.onrender.com",
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    raw_origins = os.getenv("FRONTEND_ORIGINS", "")
    origins = [origin.strip().rstrip("/") for origin in raw_origins.split(",")]
    return [origin for origin in origins if origin] or default_origins


# ─── App ───
app = FastAPI(
    title="Iris Classification API",
    description="Multi-kernel SVM classifier for the Iris dataset with prediction history & Advanced ML tools",
    version=metadata["model_version"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configured_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication handled via shared.auth.get_current_user (Centralized IdP)


# ─── Schemas ───
class IrisInput(BaseModel):
    sepal_length: float = Field(ge=4.0, le=8.0)
    sepal_width: float = Field(ge=2.0, le=5.0)
    petal_length: float = Field(ge=1.0, le=7.0)
    petal_width: float = Field(ge=0.1, le=3.0)
    kernel: str = Field(default="rbf", pattern="^(linear|rbf|poly|sigmoid)$")


class IrisPrediction(BaseModel):
    id: int | None
    class_id: int
    prediction: str
    probability: float
    kernel: str
    model_version: str


class PredictionRecord(BaseModel):
    id: int
    username: str
    sepal_length: float
    sepal_width: float
    petal_length: float
    petal_width: float
    kernel: str
    prediction: str
    class_id: int
    probability: float
    model_version: str
    created_at: str


class BatchPredictRequest(BaseModel):
    samples: list[IrisInput]





# ─── Endpoints ───

@app.get("/")
def home():
    return {
        "service": "Iris SVM API (Multi-Kernel + Advanced ML)",
        "docs": "/docs",
        "version": metadata["model_version"],
        "available_kernels": [m["kernel"] for m in metadata["models"]],
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "model_loaded": len(models) > 0,
        "models_loaded": list(models.keys()),
        "model_version": metadata["model_version"],
    }


@app.get("/metadata")
def get_metadata():
    return metadata


@app.get("/models")
def list_models():
    """List all available SVM model versions."""
    return {
        "default_kernel": DEFAULT_KERNEL,
        "models": metadata["models"],
    }


@app.post("/predict", response_model=IrisPrediction)
def predict(data: IrisInput, current_user: dict = Depends(get_current_user)):
    """Predict iris species using selected kernel version."""
    if data.kernel not in models:
        raise HTTPException(status_code=400, detail=f"Kernel '{data.kernel}' not available")

    features = np.array([[data.sepal_length, data.sepal_width, data.petal_length, data.petal_width]], dtype=float)
    if not np.isfinite(features).all():
        raise HTTPException(status_code=422, detail="Features must be finite numbers")

    # Model decision and probability inference
    model = models[data.kernel]
    probs = model.predict_proba(features)[0]
    prediction_idx = int(model.predict(features)[0])
    label = metadata["class_mapping"].get(str(prediction_idx))
    if label is None:
        raise HTTPException(status_code=500, detail="Model returned an unknown class")

    probability = float(probs[prediction_idx])
    now = datetime.now(timezone.utc)
    user_id = str(current_user["id"])

    try:
        result = history_request(
            "POST", "/records",
            payload={
                **data.model_dump(),
                "user_id": user_id,
                "prediction": label,
                "class_id": prediction_idx,
                "probability": probability,
                "model_version": metadata["model_version"],
                "created_at": now.isoformat(),
            },
            readiness_timeout=12,
        )
        record_id = result["id"]
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        # The prediction succeeded even if the data service could not confirm the write.
        record_id = None

    return IrisPrediction(
        id=record_id,
        class_id=prediction_idx,
        prediction=label,
        probability=probability,
        kernel=data.kernel,
        model_version=metadata["model_version"],
    )


@app.get("/predictions", response_model=list[PredictionRecord])
def get_predictions(limit: int = Query(default=50, le=500), current_user: dict = Depends(get_current_user)):
    """Get prediction history from database for the last 5 hours for current user."""
    user_id = str(current_user["id"])
    records = history_request("GET", "/records", params=history_filters(user_id, limit))
    return [dict(record, username=current_user.get("email") or user_id) for record in records]


def history_filters(user_id: str, limit: int | None = None) -> dict:
    since = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()
    filters = {"user_id": user_id, "since": since}
    if limit is not None:
        filters["limit"] = limit
    return filters


@app.delete("/predictions")
def clear_predictions(current_user: dict = Depends(get_current_user)):
    """Clear prediction history for current user."""
    return history_request("DELETE", "/records", params={"user_id": str(current_user["id"])})


@app.get("/predictions/export")
def export_predictions(current_user: dict = Depends(get_current_user)):
    """Export current user predictions as Excel file (.xlsx)."""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed")

    rows = history_request("GET", "/records", params=history_filters(str(current_user["id"])))

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Iris Predictions"

    headers = ["ID", "Sepal Length", "Sepal Width", "Petal Length", "Petal Width",
               "Kernel", "Prediction", "Class ID", "Probability (%)", "Model Version", "Created At"]
    ws.append(headers)

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="593E67", end_color="593E67", fill_type="solid")
    for cell in ws[1]:
        cell.font, cell.fill = header_font, header_fill

    for record in rows:
        ws.append([
            record["id"], record["sepal_length"], record["sepal_width"],
            record["petal_length"], record["petal_width"], record["kernel"],
            record["prediction"], record["class_id"], round(record["probability"] * 100, 1),
            record["model_version"], record["created_at"],
        ])

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        ws.column_dimensions[col[0].column_letter].width = max_len + 3

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=iris_predictions.xlsx"},
    )


FEATURE_NAME_MAP = {
    "sepal_length": 0, "sepal_width": 1, "petal_length": 2, "petal_width": 3,
    "sepal length (cm)": 0, "sepal width (cm)": 1, "petal length (cm)": 2, "petal width (cm)": 3,
}


@app.get("/decision-boundary")
def decision_boundary(
    kernel: str = Query(default="rbf", pattern="^(linear|rbf|poly|sigmoid)$"),
    feature_x: str = Query(default="petal_length"),
    feature_y: str = Query(default="petal_width"),
    resolution: int = Query(default=60, ge=20, le=100),
):
    """Generate 2D decision boundary grid for visualization."""
    if kernel not in models:
        raise HTTPException(status_code=400, detail=f"Kernel '{kernel}' not available")

    idx_x, idx_y = FEATURE_NAME_MAP.get(feature_x), FEATURE_NAME_MAP.get(feature_y)
    if idx_x is None or idx_y is None:
        raise HTTPException(status_code=400, detail="Invalid feature name")

    x_min, x_max = float(X_iris[:, idx_x].min() - 0.5), float(X_iris[:, idx_x].max() + 0.5)
    y_min, y_max = float(X_iris[:, idx_y].min() - 0.5), float(X_iris[:, idx_y].max() + 0.5)

    xx_grid, yy_grid = np.meshgrid(np.linspace(x_min, x_max, resolution), np.linspace(y_min, y_max, resolution))

    # Vectorized grid initialization using precomputed medians
    grid_points = np.tile(IRIS_MEDIANS, (xx_grid.size, 1))
    grid_points[:, idx_x] = xx_grid.ravel()
    grid_points[:, idx_y] = yy_grid.ravel()

    preds = models[kernel].predict(grid_points).astype(int).tolist()

    return {
        "kernel": kernel,
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
        "resolution": resolution,
        "grid": [preds[i * resolution:(i + 1) * resolution] for i in range(resolution)],
    }


# ====================================================================
# PHẦN 1: SUPPORT VECTORS & KKT MULTIPLIERS INSPECTOR
# ====================================================================
@app.get("/support-vectors")
def get_support_vectors(kernel: str = Query(default="rbf", pattern="^(linear|rbf|poly|sigmoid)$")):
    """Detailed inspection of Support Vectors, KKT Multipliers (alpha), and boundary geometry."""
    if kernel not in models:
        raise HTTPException(status_code=400, detail=f"Kernel '{kernel}' not available")

    svc = models[kernel].named_steps["svc"]
    indices = [int(idx) for idx in svc.support_]
    n_support = [int(n) for n in svc.n_support_]

    # Calculate Dual coefficients (Lagrange multipliers alpha_i)
    dual_coef = svc.dual_coef_.toarray() if hasattr(svc.dual_coef_, "toarray") else svc.dual_coef_
    max_alphas = np.max(np.abs(dual_coef), axis=0) if dual_coef.size > 0 else np.zeros(len(indices))
    C_val = float(svc.C)

    sv_points = []
    for i, idx in enumerate(indices):
        alpha_val = float(max_alphas[i])
        is_bounded = bool(alpha_val >= 0.95 * C_val)
        sv_points.append({
            "index": idx,
            "sepal_length": float(X_iris[idx, 0]),
            "sepal_width": float(X_iris[idx, 1]),
            "petal_length": float(X_iris[idx, 2]),
            "petal_width": float(X_iris[idx, 3]),
            "class_id": int(y_iris[idx]),
            "species": metadata["class_mapping"][str(int(y_iris[idx]))],
            "alpha": round(alpha_val, 4),
            "is_bounded": is_bounded,
            "kkt_type": "Bounded SV (Trong lề / Vi phạm)" if is_bounded else "Free SV (Chuẩn trên Margin)",
        })

    free_count = sum(1 for p in sv_points if not p["is_bounded"])
    bounded_count = sum(1 for p in sv_points if p["is_bounded"])

    response = {
        "kernel": kernel,
        "total_support_vectors": len(indices),
        "n_support_per_class": {"setosa": n_support[0], "versicolor": n_support[1], "virginica": n_support[2]},
        "support_vector_indices": indices,
        "support_vectors": sv_points,
        "kkt_analysis": {
            "C": C_val,
            "free_sv_count": free_count,
            "bounded_sv_count": bounded_count,
            "free_sv_pct": round(free_count / (len(indices) or 1) * 100, 1),
            "bounded_sv_pct": round(bounded_count / (len(indices) or 1) * 100, 1),
            "theorem": (
                "Định lý Karush-Kuhn-Tucker (KKT) trong bài toán quy hoạch toàn phương SVM: "
                "1. Điểm an toàn ngoài lề có α_i = 0 (không là SV). "
                "2. Free SV (0 < α_i < C): Điểm tiếp xúc đúng mặt lề tối ưu, quyết định vị trí siêu phẳng. "
                "3. Bounded SV (α_i = C): Điểm rơi vào khoảng đệm vi phạm lề (Soft Margin slack ξ_i > 0)."
            ),
        },
    }

    if kernel == "linear":
        response["coef"] = svc.coef_.tolist()
        response["intercept"] = svc.intercept_.tolist()
        response["hyperplane_math"] = (
            "Phương trình siêu phẳng: w · x + b = 0. "
            "Các điểm dữ liệu là Support Vector khi: y_i(w · x_i + b) = 1."
        )

    return response


# ====================================================================
# PHẦN 2: 3D PCA DECISION SPACE (XOAY 360 ĐỘ)
# ====================================================================
@app.get("/pca-3d")
def get_pca_3d(
    kernel: str = Query(default="rbf", pattern="^(linear|rbf|poly|sigmoid)$"),
    user_sl: Optional[float] = Query(default=None),
    user_sw: Optional[float] = Query(default=None),
    user_pl: Optional[float] = Query(default=None),
    user_pw: Optional[float] = Query(default=None),
):
    """3D PCA Projection preserving ~99.5% variance with 360-degree interactive rotation data."""
    if kernel not in models:
        raise HTTPException(status_code=400, detail=f"Kernel '{kernel}' not available")

    svc = models[kernel].named_steps["svc"]
    sv_indices = set(int(idx) for idx in svc.support_)

    points = []
    for i in range(len(X_iris)):
        cid = int(y_iris[i])
        species = metadata["class_mapping"][str(cid)]
        points.append({
            "id": i,
            "x": round(float(X_iris_pca_3d[i, 0]), 3),
            "y": round(float(X_iris_pca_3d[i, 1]), 3),
            "z": round(float(X_iris_pca_3d[i, 2]), 3),
            "class_id": cid,
            "species": species,
            "is_support_vector": i in sv_indices,
            "features": [
                round(float(X_iris[i, 0]), 2),
                round(float(X_iris[i, 1]), 2),
                round(float(X_iris[i, 2]), 2),
                round(float(X_iris[i, 3]), 2),
            ],
        })

    user_projection = None
    if all(v is not None for v in [user_sl, user_sw, user_pl, user_pw]):
        raw_pt = np.array([[user_sl, user_sw, user_pl, user_pw]], dtype=float)
        proj = pca_3d.transform(raw_pt)[0]
        user_projection = {
            "x": round(float(proj[0]), 3),
            "y": round(float(proj[1]), 3),
            "z": round(float(proj[2]), 3),
            "features": [user_sl, user_sw, user_pl, user_pw],
        }

    variance_pct = [round(float(v * 100), 2) for v in pca_3d.explained_variance_ratio_]

    return {
        "kernel": kernel,
        "explained_variance_ratio": variance_pct,
        "total_explained_variance": round(sum(variance_pct), 2),
        "components_description": {
            "pc1": "Trục PC1 (chủ yếu là Chiều dài & Chiều rộng cánh hoa — mang thông tin phân loài cao nhất)",
            "pc2": "Trục PC2 (chủ yếu là Chiều rộng đài hoa — phân biệt Setosa với 2 loài còn lại)",
            "pc3": "Trục PC3 (vi sai chiều dài đài hoa — phân tách tinh vi giữa Versicolor & Virginica)",
        },
        "points": points,
        "user_projection": user_projection,
    }


# ====================================================================
# PHẦN 3: STRESS-TEST & OUTLIER / NOISE SIMULATOR
# ====================================================================
@app.get("/stress-test")
def stress_test_kernels(
    noise_level: float = Query(default=0.15, ge=0.0, le=1.0),
    outliers: int = Query(default=2, ge=0, le=10),
    seed: int = Query(default=42),
):
    """Simulate Gaussian noise and boundary-crossing outliers to stress-test SVM Kernel robustness."""
    safe_seed = int(getattr(seed, "default", seed))
    safe_noise = float(getattr(noise_level, "default", noise_level))
    safe_outliers = int(getattr(outliers, "default", outliers))

    rng = np.random.RandomState(safe_seed)
    X_noisy = X_iris.copy()
    y_noisy = y_iris.copy()

    # 1. Add Gaussian noise to continuous features
    if safe_noise > 0:
        std_devs = np.std(X_iris, axis=0)
        noise = rng.normal(0, safe_noise * std_devs, size=X_noisy.shape)
        X_noisy += noise

    # 2. Inject adversarial/outlier samples
    if safe_outliers > 0:
        outlier_points = []
        outlier_labels = []
        for o_idx in range(safe_outliers):
            if o_idx % 2 == 0:
                # Versicolor with Setosa size
                outlier_points.append([5.0, 3.4, 1.6, 0.3])
                outlier_labels.append(1)
            else:
                # Setosa with Virginica size
                outlier_points.append([6.5, 3.0, 5.5, 2.0])
                outlier_labels.append(0)
        X_noisy = np.vstack([X_noisy, outlier_points])
        y_noisy = np.concatenate([y_noisy, outlier_labels])

    results = []
    for k in ["linear", "rbf", "poly", "sigmoid"]:
        pipe = Pipeline([
            ("scaler", StandardScaler()),
            ("svc", SVC(kernel=k, C=1.0, random_state=42))
        ])
        pipe.fit(X_noisy, y_noisy)
        score_noisy = float(pipe.score(X_noisy, y_noisy)) * 100
        score_orig = float(pipe.score(X_iris, y_iris)) * 100
        n_sv = len(pipe.named_steps["svc"].support_)

        # Diagnosis
        if k == "linear":
            diag = "Mặt phẳng tuyến tính bị kéo lệch đáng kể bởi outlier do tính chất cứng nhắc của siêu phẳng đơn."
        elif k == "rbf":
            diag = "RBF duy trì vùng lõi cực tốt, tự động cô lập các outlier vào các 'ốc đảo' bán kính nhỏ quanh chúng."
        elif k == "poly":
            diag = "Đa thức bậc cao bị uốn cong đuôi ở vùng xa tâm dữ liệu khi gặp nhiễu ngoại lai."
        else:
            diag = "Sigmoid có độ bền kém nhất, ma trận Gram biến thiên mạnh làm suy giảm độ chính xác."

        results.append({
            "kernel": k,
            "accuracy_on_noisy": round(score_noisy, 2),
            "accuracy_on_clean": round(score_orig, 2),
            "support_vectors": n_sv,
            "robustness_score": round(max(0, 100 - abs(score_orig - score_noisy) * 2 - (safe_outliers * 3)), 1),
            "diagnosis": diag,
        })

    return {
        "noise_level": safe_noise,
        "outliers": safe_outliers,
        "total_samples": len(X_noisy),
        "results": results,
    }


# ====================================================================
# PHẦN 4: LIVE SVM PLAYGROUND
# ====================================================================
@app.get("/svm-playground")
def svm_playground(
    kernel: str = Query(default="rbf", pattern="^(linear|rbf|poly|sigmoid)$"),
    C: float = Query(default=1.0, ge=0.001, le=1000.0),
    gamma: float = Query(default=1.0, ge=0.001, le=100.0),
    degree: int = Query(default=3, ge=1, le=5),
    resolution: int = Query(default=50, ge=20, le=80),
):
    """Live SVM Training Playground on 2D Petal features with real-time Overfit/Underfit diagnosis."""
    X_2d = X_iris[:, [2, 3]]
    kwargs = {"kernel": kernel, "C": C, "random_state": 42}
    if kernel in ("rbf", "poly", "sigmoid"):
        kwargs["gamma"] = gamma
    if kernel == "poly":
        kwargs["degree"] = degree

    pipe = Pipeline([("scaler", StandardScaler()), ("svc", SVC(**kwargs))]).fit(X_2d, y_iris)
    svc = pipe.named_steps["svc"]
    train_acc = float(pipe.score(X_2d, y_iris))

    x_min, x_max = float(X_2d[:, 0].min() - 0.5), float(X_2d[:, 0].max() + 0.5)
    y_min, y_max = float(X_2d[:, 1].min() - 0.5), float(X_2d[:, 1].max() + 0.5)

    xx_grid, yy_grid = np.meshgrid(np.linspace(x_min, x_max, resolution), np.linspace(y_min, y_max, resolution))
    grid_points = np.c_[xx_grid.ravel(), yy_grid.ravel()]
    preds = pipe.predict(grid_points).astype(int).tolist()

    # Diagnosis rule logic
    diagnoses = []
    if C >= 50.0:
        diagnoses.append("⚠️ C rất lớn (Hard Margin): Mô hình phạt nặng sai số, margin hẹp → Nguy cơ Quá khớp (Overfitting).")
    elif C <= 0.05:
        diagnoses.append("⚠️ C rất nhỏ (Soft Margin): Lề mở rộng tối đa, chấp nhận nhiều điểm vi phạm → Nguy cơ Dưới khớp (Underfitting).")
    else:
        diagnoses.append("✅ C cân bằng tốt giữa tối đa hóa khoảng cách lề và hạn chế lỗi phân loại.")

    if kernel == "rbf":
        if gamma >= 10.0:
            diagnoses.append("⚠️ Gamma rất cao: Bán kính Gaussian nhỏ, tạo các 'ốc đảo' quanh từng điểm → Hiện tượng Overfitting!")
        elif gamma <= 0.05:
            diagnoses.append("⚠️ Gamma quá nhỏ: Bán kính tương tác quá lớn làm phẳng biên → Mất tính phi tuyến của RBF.")
        else:
            diagnoses.append("✅ Gamma hài hòa: Đường biên uốn lượn tự nhiên theo mật độ dữ liệu hoa.")
    elif kernel == "poly":
        diagnoses.append(f"Đa thức bậc {degree}: Bậc càng cao đường biên càng uốn khúc mạnh, cần kiểm soát C hợp lý.")

    return {
        "kernel": kernel,
        "C": C,
        "gamma": gamma,
        "degree": degree,
        "train_accuracy": round(train_acc * 100, 1),
        "total_support_vectors": len(svc.support_),
        "n_support_per_class": [int(n) for n in svc.n_support_],
        "support_vector_indices": [int(idx) for idx in svc.support_],
        "x_range": [x_min, x_max],
        "y_range": [y_min, y_max],
        "resolution": resolution,
        "grid": [preds[i * resolution:(i + 1) * resolution] for i in range(resolution)],
        "diagnosis": " ".join(diagnoses),
    }


# ====================================================================
# PHẦN 5: KERNEL BENCHMARK (4-WAY COMPARISON)
# ====================================================================
@app.get("/kernel-arena")
def kernel_arena():
    """Comparison matrix and benchmark of all 4 SVM kernels (Linear, RBF, Poly, Sigmoid)."""
    descriptions = {
        "linear": {
            "surface": "Siêu phẳng tuyến tính (Flat Hyperplane)",
            "best_for": "Dữ liệu phân tách phẳng, ưu tiên tốc độ suy luận nhanh nhất",
            "math_form": "K(x, x') = x^T x'",
            "pros": "Cực nhanh, CV 96.67% (chênh lệch với RBF <1 std, không kernel nào vượt trội tuyệt đối), dễ giải thích trọng số w",
            "cons": "Không bắt được đường biên cong phức tạp giữa Versicolor và Virginica",
        },
        "rbf": {
            "surface": "Phi tuyến mượt mà (Gaussian Radial Basis Function)",
            "best_for": "Mọi bài toán phân loại tổng quát (Khuyên dùng chuẩn mực)",
            "math_form": "K(x, x') = exp(-γ ||x - x'||^2)",
            "pros": "Độ chính xác cao (96.0% CV), phân tách mượt; chênh lệch với Linear <1 độ lệch chuẩn nên không kernel nào vượt trội",
            "cons": "Cần tinh chỉnh siêu tham số C và gamma cẩn thận để tránh Overfitting",
        },
        "poly": {
            "surface": "Đa thức bậc 3 (Polynomial Curved Surface)",
            "best_for": "Dữ liệu có mối tương tác phi tuyến bậc cao giữa các đặc trưng",
            "math_form": "K(x, x') = (γ x^T x' + coef0)^d",
            "pros": "Mô hình hóa được tương tác tích giữa chiều dài và chiều rộng cánh hoa",
            "cons": "Tính toán chậm hơn, nhạy cảm với việc chuẩn hóa thang đo (StandardScaler)",
        },
        "sigmoid": {
            "surface": "Phi tuyến Hyperbolic (S-curve)",
            "best_for": "Nghiên cứu học thuật so sánh hành vi giữa SVM và Mạng Neural",
            "math_form": "K(x, x') = tanh(γ x^T x' + coef0)",
            "pros": "Có cơ sở lý thuyết kết nối SVM với mạng nơ-ron Perceptron 2 lớp",
            "cons": "Dễ vi phạm điều kiện Mercer (ma trận Gram bán xác định dương), độ chính xác thấp hơn",
        },
    }

    X_2d = X_iris[:, [2, 3]]
    x_min, x_max = float(X_2d[:, 0].min() - 0.5), float(X_2d[:, 0].max() + 0.5)
    y_min, y_max = float(X_2d[:, 1].min() - 0.5), float(X_2d[:, 1].max() + 0.5)
    res = 40
    xx_grid, yy_grid = np.meshgrid(np.linspace(x_min, x_max, res), np.linspace(y_min, y_max, res))

    grid_points = np.tile(IRIS_MEDIANS, (xx_grid.size, 1))
    grid_points[:, 2] = xx_grid.ravel()
    grid_points[:, 3] = yy_grid.ravel()

    test_sample = np.array([[5.8, 3.0, 4.2, 1.3]])
    arena_results = []

    for m in metadata["models"]:
        k = m["kernel"]
        model = models[k]
        svc = model.named_steps["svc"]

        # Latency benchmark (25 iterations)
        t0 = time.perf_counter()
        for _ in range(25):
            model.predict(test_sample)
        latency = (time.perf_counter() - t0) / 25 * 1000  # ms

        preds = model.predict(grid_points).astype(int).tolist()

        arena_results.append({
            "version": m["version"],
            "kernel": k,
            "display_name": m["display_name"],
            "cv_accuracy": round(m["cv_accuracy_mean"] * 100, 2),
            "cv_accuracy_std": round(m["cv_accuracy_std"] * 100, 2),
            "total_support_vectors": len(svc.support_),
            "n_support_per_class": [int(n) for n in svc.n_support_],
            "latency_ms": round(latency, 3),
            "details": descriptions.get(k, {}),
            "mini_grid": [preds[i * res:(i + 1) * res] for i in range(res)],
            "x_range": [x_min, x_max],
            "y_range": [y_min, y_max],
            "resolution": res,
        })

    return {"arena": arena_results}


# ====================================================================
# PHẦN 6: EXPLAINABLE AI (XAI)
# ====================================================================
@app.post("/explain")
def explain_prediction(data: IrisInput, current_user: dict = Depends(get_current_user)):
    """Explainable AI (XAI) feature attribution via finite difference sensitivity analysis."""
    if data.kernel not in models:
        raise HTTPException(status_code=400, detail=f"Kernel '{data.kernel}' not available")

    model = models[data.kernel]
    sample = np.array([[data.sepal_length, data.sepal_width, data.petal_length, data.petal_width]], dtype=float)
    probs = model.predict_proba(sample)[0]
    pred_idx = int(model.predict(sample)[0])
    pred_label = metadata["class_mapping"][str(pred_idx)]

    feature_names = ["sepal_length", "sepal_width", "petal_length", "petal_width"]
    display_names = ["Chiều dài đài (Sepal Length)", "Chiều rộng đài (Sepal Width)", "Chiều dài cánh (Petal Length)", "Chiều rộng cánh (Petal Width)"]

    step = 0.3
    diffs = []
    for i in range(4):
        s_plus, s_minus = sample.copy(), sample.copy()
        s_plus[0, i] += step
        s_minus[0, i] -= step
        diffs.append(abs(float(model.predict_proba(s_plus)[0][pred_idx] - model.predict_proba(s_minus)[0][pred_idx])))

    total = sum(diffs) or 1.0
    importances = [round(float(d / total * 100), 1) for d in diffs]

    ranges = {
        "setosa": {"petal_length": "1.0 – 1.9 cm", "petal_width": "0.1 – 0.6 cm", "sepal_length": "4.3 – 5.8 cm", "sepal_width": "2.3 – 4.4 cm"},
        "versicolor": {"petal_length": "3.0 – 5.1 cm", "petal_width": "1.0 – 1.8 cm", "sepal_length": "4.9 – 7.0 cm", "sepal_width": "2.0 – 3.4 cm"},
        "virginica": {"petal_length": "4.5 – 6.9 cm", "petal_width": "1.4 – 2.5 cm", "sepal_length": "4.9 – 7.9 cm", "sepal_width": "2.2 – 3.8 cm"},
    }

    attributions = [
        {
            "feature": feature_names[i],
            "display_name": display_names[i],
            "value": float(sample[0, i]),
            "importance_pct": importances[i],
            "typical_range": ranges[pred_label].get(feature_names[i], ""),
        }
        for i in range(4)
    ]
    attributions.sort(key=lambda x: x["importance_pct"], reverse=True)
    top_feature = attributions[0]["display_name"]

    explanation_text = (
        f"Mô hình dự đoán hoa này là **{pred_label.capitalize()}** với độ tin cậy {round(float(probs[pred_idx]*100), 1)}%. "
        f"Yếu tố có trọng số quyết định cao nhất là **{top_feature}** ({attributions[0]['importance_pct']}%), "
        f"bởi vì giá trị {attributions[0]['value']} cm hoàn toàn trùng khớp với dải kích thước đặc trưng của loài {pred_label}."
    )

    return {
        "prediction": pred_label,
        "class_id": pred_idx,
        "probability": float(probs[pred_idx]),
        "attributions": attributions,
        "explanation": explanation_text,
    }


# ====================================================================
# PHẦN 7: BATCH PREDICTION & SAMPLE CSV
# ====================================================================
@app.post("/predict-batch")
def predict_batch(payload: BatchPredictRequest, current_user: dict = Depends(get_current_user)):
    """Batch prediction endpoint for up to 500 samples."""
    if len(payload.samples) > 500:
        raise HTTPException(status_code=400, detail="Tối đa 500 mẫu trong một lần xử lý")

    results = []
    for idx, item in enumerate(payload.samples):
        kernel = item.kernel if item.kernel in models else "rbf"
        model = models[kernel]
        feats = np.array([[item.sepal_length, item.sepal_width, item.petal_length, item.petal_width]], dtype=float)
        probs = model.predict_proba(feats)[0]
        pred_idx = int(model.predict(feats)[0])
        prob = float(probs[pred_idx])
        label = metadata["class_mapping"][str(pred_idx)]
        status = "Tin cậy cao" if prob >= 0.85 else ("Tin cậy khá" if prob >= 0.65 else "Vùng bất định")

        results.append({
            "id": idx + 1,
            "sepal_length": item.sepal_length,
            "sepal_width": item.sepal_width,
            "petal_length": item.petal_length,
            "petal_width": item.petal_width,
            "kernel": kernel,
            "prediction": label,
            "class_id": pred_idx,
            "probability": round(prob * 100, 1),
            "status": status,
        })
    return {"count": len(results), "predictions": results}


@app.get("/sample-csv")
def get_sample_csv():
    """Download a template CSV with 10 sample flowers for batch testing."""
    sample_data = (
        "sepal_length,sepal_width,petal_length,petal_width,kernel\n"
        "5.1,3.5,1.4,0.2,rbf\n"
        "4.9,3.0,1.4,0.2,linear\n"
        "4.7,3.2,1.3,0.2,rbf\n"
        "6.4,3.2,4.5,1.5,rbf\n"
        "6.9,3.1,4.9,1.5,poly\n"
        "5.5,2.3,4.0,1.3,linear\n"
        "6.3,3.3,6.0,2.5,rbf\n"
        "5.8,2.7,5.1,1.9,sigmoid\n"
        "7.1,3.0,5.9,2.1,rbf\n"
        "5.9,3.0,5.1,1.8,poly\n"
    )
    return StreamingResponse(
        io.BytesIO(sample_data.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=iris_test_samples.csv"},
    )

# ====================================================================
# ADMIN: Danh sach du doan toan he thong (owner only, khong co username)
# ====================================================================
@app.get("/admin/predictions")
def admin_all_predictions(
    limit: int = Query(default=200, ge=1, le=500),
    credentials=Security(HTTPBearer(auto_error=False)),
):
    import jwt as _jwt

    if credentials is None:
        raise HTTPException(status_code=401, detail="Yêu cầu đăng nhập")
    try:
        payload = _jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=os.getenv("CLIENT_ID", "iris-svm-api"),
        )
        if not payload.get("is_owner"):
            raise HTTPException(status_code=403, detail="Chỉ chủ sở hữu mới có quyền truy cập")
    except _jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Token không hợp lệ")

    records = history_request("GET", "/admin/records", params={"limit": limit})
    return [
        {
            "id": record["id"],
            "created_at": record["created_at"],
            "kernel": record["kernel"],
            "prediction": record["prediction"],
            "probability": round(record["probability"] * 100, 1),
            "model_version": record["model_version"],
        }
        for record in records
    ]
