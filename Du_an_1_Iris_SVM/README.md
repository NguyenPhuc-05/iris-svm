# Đồ Án 1 — Iris AI Explorer: SVM Đa Nhân

> **Học phần:** Học máy Nâng cao  
> **Sinh viên:** Nguyễn Xuân Phúc — MSSV 3110524025 — Lớp 24CKDL  
> **Giảng viên:** TS. Phan Trần Đức Minh

---

## Hệ thống làm gì

Phân loại ba loài hoa Iris (*Setosa, Versicolor, Virginica*) dựa trên 4 đặc trưng kích thước đài hoa và cánh hoa, dùng SVM với 4 loại nhân. Người dùng đăng nhập qua Identity Service dùng chung (SSO), sau đó có thể:

1. Phân loại mẫu đơn (chọn kernel, nhập kích thước).
2. Khám phá Support Vectors — xem tọa độ, trọng số $w$, $b$ và số lượng vector hỗ trợ từng lớp.
3. Thử nghiệm tham số $C$, $\gamma$, degree trực tiếp — hệ thống chẩn đoán Overfitting/Underfitting ngay lập tức.
4. So sánh 4 kernel song song (độ chính xác CV, latency, decision boundary).
5. Giải thích kết quả bằng XAI — phân tích độ nhạy nhiễu từng đặc trưng.
6. Phân loại hàng loạt từ CSV, xuất báo cáo Excel.

---

## Cơ sở toán học & Đánh giá mô hình

**Bài toán tối ưu SVM (Soft Margin):**

$$\min_{w, b, \xi} \frac{1}{2}\|w\|^2 + C\sum_{i=1}^{N}\xi_i \quad \text{sao cho} \quad y_i(w \cdot \phi(x_i) + b) \ge 1 - \xi_i,\ \xi_i \ge 0$$

- **Quy ước độ rộng lề (Margin convention):** Khoảng cách từ siêu phẳng phân tách đến mỗi đường biên là $1/\|w\|$, tổng độ rộng lề là $M = 2/\|w\|$.
- **Hành vi tham số $C$:** Khi $C \to \infty$, bài toán tiệm cận lề cứng (Hard Margin); mô hình `sklearn.svm.SVC` mặc định là Soft Margin với $C=1.0$.
- **Đánh giá Cross-Validation:** Điểm số CV Accuracy (5-fold) không phải là điểm kiểm thử độc lập (held-out test score); các siêu tham số $C$ và $\gamma$ sử dụng giá trị mặc định của scikit-learn (chưa qua tinh chỉnh / tuning). Độ chính xác giữa Linear (96.67%) và RBF (96.00%) chênh lệch nhỏ hơn 1 độ lệch chuẩn nên không có kernel nào vượt trội tuyệt đối.
- **Xác suất Platt scaling:** Xác suất trả về đến từ phương pháp hiệu chuẩn Platt scaling và có thể xếp hạng khác với hàm quyết định; nhãn phân loại chính thức luôn được xác định trực tiếp từ `model.predict()`.

**Bốn hàm nhân:**

| Kernel | Biểu thức | Ghi chú |
|---|---|---|
| Linear | $K(x,x') = x^T x'$ | Cực nhanh, CV 96.67% (chênh lệch <1 std so với RBF) |
| RBF | $K(x,x') = \exp(-\gamma\|x-x'\|^2)$ | Phân tách phi tuyến mượt, CV 96.00% |
| Polynomial | $K(x,x') = (\gamma x^T x' + r)^d$ | Bắt tương tác bậc cao, CV 90.67% |
| Sigmoid | $K(x,x') = \tanh(\gamma x^T x' + r)$ | Kết nối với mạng nơ-ron Perceptron 2 lớp, CV 91.33% |

---

## Cấu trúc thư mục

```
Du_an_1_Iris_SVM/
├── backend/
│   ├── app/
│   │   └── main.py          # Toàn bộ endpoint API
│   ├── artifacts/
│   │   ├── iris_svm_linear.joblib
│   │   ├── iris_svm_rbf.joblib
│   │   ├── iris_svm_poly.joblib
│   │   ├── iris_svm_sigmoid.joblib
│   │   └── metadata.json
│   ├── scripts/
│   │   └── train.py         # Huấn luyện 4 mô hình, ghi metadata
│   ├── tests/
│   │   └── test_api.py      # 17 test cases
│   ├── .env.example
│   └── requirements.txt
├── database/
│   ├── db.py                # Kết nối PostgreSQL hoặc SQLite cục bộ
│   ├── models.py            # PredictionRecord
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── script.js
│   └── images/
└── notebooks/
    └── 01_eda_and_svm_experiments.ipynb
```

---

## Chạy cục bộ và kiểm thử

Xem [README ở gốc kho](../README.md) để chạy Iris với Identity Service độc lập. Xem [thiết kế CSDL](../DATABASE.md) để biết cấu hình PostgreSQL trên Render.

## Huấn luyện lại

```bash
cd backend
python scripts/train.py
```

Script huấn luyện 4 kernel, đánh giá 5-fold CV và lưu artifact vào `backend/artifacts/`.

---

## API Endpoints chính

| Method | Endpoint | Mô tả | Xác thực |
|---|---|---|---|
| GET | `/health` | Trạng thái dịch vụ | Không |
| GET | `/metadata` | Thông tin 4 mô hình | Không |
| POST | `/predict` | Phân loại mẫu đơn | JWT |
| POST | `/explain` | XAI — giải thích kết quả | JWT |
| POST | `/predict-batch` | Phân loại hàng loạt | JWT |
| GET | `/predictions` | Lịch sử dự đoán của user | JWT |
| GET | `/predictions/export` | Xuất Excel | JWT |
| DELETE | `/predictions` | Xóa lịch sử user | JWT |
| GET | `/decision-boundary` | Grid decision boundary 2D | Không |
| GET | `/support-vectors` | Inspector Support Vectors | Không |
| GET | `/svm-playground` | Playground tham số thời gian thực | Không |
| GET | `/kernel-arena` | So sánh 4 kernel | Không |
| GET | `/sample-csv` | Tải file CSV mẫu | Không |