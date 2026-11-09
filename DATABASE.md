# Ranh giới dữ liệu

| Dịch vụ | Dữ liệu sở hữu |
| --- | --- |
| Iris Data Service | `iris_users` lưu mã `sub` và thời điểm ghi nhận đầu tiên. `user_predictions` lưu số đo, kernel, kết quả, thời gian và mã người dùng. |
| Identity Service | Tài khoản và thông tin xác thực dùng chung. |

Iris API xác minh JWT và gọi Iris Data Service với token dành riêng cho hai dịch vụ. Frontend chỉ gọi Iris API và Identity Service. Khi chạy trên Render, Iris API yêu cầu `IRIS_DATA_URL` và `IRIS_DATA_TOKEN`.

Bản thử Render dùng SQLite tạm. Để cấu hình PostgreSQL sau này, đặt `DATABASE_URL` trên Iris Data Service và `IDP_DATABASE_URL` trên Identity Service. Kiểm tra và chuyển dữ liệu trước khi thay đổi môi trường đang dùng.
