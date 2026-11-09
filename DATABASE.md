# Dữ liệu của Iris và dịch vụ định danh

| CSDL | Chủ sở hữu | Dữ liệu |
|---|---|---|
| Iris PostgreSQL | Iris API | `iris_users` lưu mã `sub` và thời điểm ghi nhận đầu tiên. `user_predictions` lưu số đo, kernel, nhãn, xác suất và mã người dùng. |
| Identity PostgreSQL | Identity Service | Tài khoản, mã băm mật khẩu và danh sách client được cấp token. |

Iris tạo hồ sơ tối thiểu khi người dùng dự đoán đơn lần đầu. Cả hồ sơ và lượt dự đoán được ghi trong giao dịch của Iris. Lịch sử được lọc theo `sub` trong JWT. Iris lấy email hiển thị từ token. Hai CSDL liên hệ qua mã người dùng và không truy vấn bảng của nhau.

`Du_an_1_Iris_SVM/database/` chứa mô hình SQLAlchemy và mã kết nối. Tiến trình PostgreSQL được cấp phát riêng. Trên Render, `DATABASE_URL` phải trỏ tới PostgreSQL. SQLite dùng cho phát triển và bộ kiểm thử cục bộ.
