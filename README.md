# Đồ Án 1 — Phân loại Hoa Iris bằng SVM Đa Nhân

> **Học phần:** Học máy Nâng cao  
> **Sinh viên:** Nguyễn Xuân Phúc — MSSV 3110524025 — Lớp 24CKDL  
> **Đơn vị:** Khoa Toán - Tin, Trường ĐH Sư phạm — ĐH Đà Nẵng  
> **Giảng viên:** TS. Phan Trần Đức Minh

---

## Giới thiệu

Dự án xây dựng hệ thống phân loại ba loài hoa Iris (*Setosa, Versicolor, Virginica*) dùng thuật toán **Support Vector Machine (SVM)** với bốn loại nhân khác nhau. Ngoài chức năng phân loại cơ bản, hệ thống còn tích hợp các tính năng học thuật nâng cao và cá nhân hóa độc đáo:

- **Không gian 3D PCA (Xoay 360°)** — Phép chiếu giảm chiều 4D → 3D bảo toàn **99.48% phương sai**, trực quan hóa không gian đa chiều, mặt phân cách và các Support Vectors với camera xoay tự do.
- **KKT & Lagrange Multipliers ($\alpha_i$) Inspector** — Phân tích bài toán đối ngẫu và phân loại Support Vectors thành *Free SV* ($0 < \alpha_i < C$) và *Bounded SV* ($\alpha_i = C$) theo định lý Karush-Kuhn-Tucker.
- **Kiểm thử độ vững mô hình (Robustness Test)** — Mô phỏng nhiễu Gauss và điểm ngoại lai để đánh giá khả năng kháng nhiễu của 4 kernel.
- **Sơ đồ cấu tạo hoa tương tác** — Đồ họa SVG trực quan hóa vị trí đo đạc Sepal/Petal đồng bộ thời gian thực với thanh trượt.
- **Báo cáo phân loại mẫu hoa (Audit Report & PDF)** — Xuất báo cáo kết quả phân loại định dạng in ấn/PDF với mã băm toàn vẹn SHA-256 và chữ ký điện tử.
- **Chế độ Hướng dẫn tính năng** — Thuyết minh trực quan giúp người xem nhanh chóng nắm bắt các chức năng của hệ thống.
- **Live SVM Playground** — Khảo sát ảnh hưởng của siêu tham số C, γ theo thời gian thực và chẩn đoán Overfitting/Underfitting.
- **Kernel Benchmark** — Bảng đối sánh thực nghiệm 4 hàm nhân SVM về độ chính xác CV, latency và decision boundary.
- **Explainable AI (XAI)** — Phân tích độ nhạy nhiễu (Sensitivity Attribution) giải thích lý do đưa ra kết quả.
- **Batch CSV & Database** — Phân loại hàng loạt mẫu từ file CSV, xuất kết quả Excel và lưu trữ CSDL.

---

## Kiến trúc

| Thành phần | Trách nhiệm | Nơi triển khai |
|---|---|---|
| Iris Frontend | Giao diện phân loại, trực quan hóa, lịch sử | Static Site |
| Iris API | Xác minh JWT, suy luận SVM, ghi dữ liệu Iris | Web Service |
| Iris Data Service | Hồ sơ Iris theo mã người dùng và lịch sử dự đoán | SQLite demo, hỗ trợ cấu hình PostgreSQL |
| Identity Service | Đăng ký, đăng nhập, cấp JWT cho các dự án | Kho và Web Service riêng |

Frontend gọi Identity Service qua HTTPS để lấy JWT có `aud=iris-svm-api`. Iris API xác minh token và gọi Iris Data Service qua HTTPS. Identity Service tự quản lý CSDL tài khoản. Hai backend dùng cùng khóa JWT trong nhóm dịch vụ tin cậy.

## Cơ sở toán học & Đánh giá thực nghiệm

- **Quy ước độ rộng lề (Margin convention):** Khoảng cách từ siêu phẳng phân tách đến mỗi siêu phẳng biên là $1/\|w\|$, tổng độ rộng toàn phần của lề phân tách là $M = 2/\|w\|$.
- **Hành vi tham số phạt C:** Khi $C \to \infty$, bài toán tiến tới tiệm cận lề cứng (Hard Margin); mô hình `sklearn.svm.SVC` sử dụng cơ chế lề mềm (Soft Margin) với mặc định $C=1.0$.
- **Đánh giá Cross-Validation:** Độ chính xác 5-fold CV (Linear 96.67%, RBF 96.00%, Sigmoid 91.33%, Poly 90.67%) phản ánh hiệu năng xác thực chéo nội bộ, không phải điểm số kiểm thử độc lập (held-out test score); các tham số $C$ và $\gamma$ giữ nguyên giá trị mặc định của scikit-learn (chưa qua tuning). Chênh lệch giữa Linear và RBF nhỏ hơn một độ lệch chuẩn (std ≈ 0.04–0.05), do đó không có kernel nào được tuyên bố là vượt trội tuyệt đối.
- **Xác suất Platt scaling:** Xác suất dự đoán được tính từ phương pháp hiệu chuẩn Platt scaling và có thể xếp hạng khác với giá trị hàm quyết định; nhãn loài hoa chính thức luôn được xác định trực tiếp từ `model.predict()`.

---

## Cấu trúc thư mục

| Vị trí | Nội dung |
|---|---|
| `Du_an_1_Iris_SVM/backend/` | FastAPI, bốn mô hình đã lưu, huấn luyện và kiểm thử |
| `Du_an_1_Iris_SVM/frontend/` | HTML, CSS, JavaScript và cấu hình URL dịch vụ |
| `Du_an_1_Iris_SVM/database/` | Kết nối SQLAlchemy và schema của Iris |
| `shared/auth.py` | Kiểm tra JWT trong Iris API |
| `render.yaml` | Các dịch vụ của bản thử và kho định danh độc lập |

## Chạy cục bộ trên Windows

1. Khởi động kho Identity Service theo README của kho đó trên cổng `8001`. Cấp client `iris-svm-api` cho Iris.
2. Từ gốc kho Iris, tạo môi trường và sao chép tệp cấu hình mẫu.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r Du_an_1_Iris_SVM/backend/requirements.txt
Copy-Item Du_an_1_Iris_SVM/backend/.env.example Du_an_1_Iris_SVM/backend/.env
```

Điền khóa JWT thử giống Identity Service vào tệp vừa sao chép. `DATABASE_URL` dùng SQLite cho máy cá nhân. Mở hai terminal tại gốc kho và chạy hai lệnh sau, mỗi lệnh ở một terminal.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --app-dir Du_an_1_Iris_SVM --env-file Du_an_1_Iris_SVM/backend/.env --host 127.0.0.1 --port 8000
.\.venv\Scripts\python.exe -m http.server 5500 --directory Du_an_1_Iris_SVM/frontend --bind 127.0.0.1
```

Mở `http://127.0.0.1:5500`. Khi chạy cục bộ, frontend gọi API ở cổng `8000` và IdP ở cổng `8001`.

## Kiểm thử

GitHub Actions chạy bộ kiểm thử API trên SQLite, kiểm tra cú pháp frontend và chạy thử hồ sơ, dự đoán, lịch sử với PostgreSQL riêng trong CI.

## Huấn luyện lại mô hình

```bash
cd Du_an_1_Iris_SVM/backend
python scripts/train.py
```

Sau khi huấn luyện xong, tăng `model_version` trong `metadata.json` nếu hành vi mô hình thay đổi đáng kể.

---

## Triển khai thử trên Render

Tạo Blueprint riêng từ nhánh `deploy/modular-iris`. Blueprint triển khai frontend, Iris API, Iris Data Service và Identity Service. Identity Service lấy mã từ kho riêng. Các tên có đuôi `-v2` và các nhóm biến môi trường dành cho bản thử.

Kiểm tra URL các dịch vụ trên Dashboard sau khi tạo. Nếu Render thêm hậu tố vào tên miền, cập nhật URL và CORS trong `render.yaml` rồi đồng bộ Blueprint. Hai nhóm biến môi trường tạo riêng khóa JWT và token gọi Data Service. Frontend chỉ nhận URL công khai.

Iris Data Service và Identity Service dùng hai tệp SQLite riêng trên bản thử. Dữ liệu thử có thể mất khi Render ngủ hoặc triển khai lại. Xem [thiết kế CSDL](DATABASE.md) và [kế hoạch chuyển đổi](MIGRATION.md).
