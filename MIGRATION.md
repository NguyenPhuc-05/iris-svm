# Chuyển sang triển khai theo mô-đun

Phiên bản gốc để đối chiếu là commit `2d3d9e9`. Chuẩn bị hai kho GitHub: `iris-svm` cho ứng dụng và `identity-service` cho định danh. Các bản chạy thử dùng tên dịch vụ `-v2` để có thể nghiệm thu song song với bản hiện tại.

1. Tạo kho IdP riêng với phạm vi truy cập đã chọn. Chạy CI ở hai kho và kiểm tra bước PostgreSQL. Giữ tài khoản, mật khẩu và URL kết nối trong biến môi trường của từng dịch vụ.
2. Cấp CSDL PostgreSQL dành cho IdP, sau đó triển khai từ kho mới. Thêm `iris-svm-api` vào `CLIENT_IDS`. Tạo CSDL Iris riêng bằng Blueprint Iris và dùng URL nội bộ cho API. Chọn gói tài nguyên sau khi xem thông tin chi phí và thời hạn trên Render.
3. Kiểm tra `health`, cấu hình CORS và đường dẫn HTTPS. Dùng tài khoản thử đăng ký, đăng nhập, dự đoán, xem lịch sử. Đăng nhập cùng tài khoản với client thứ hai để xác nhận dùng lại định danh. Khởi động lại từng backend và kiểm tra dữ liệu còn đọc được.
4. Nếu cần chuyển tài khoản hoặc lịch sử hiện có, sao lưu trước và giữ nguyên mã tài khoản `sub` khi nhập. Chuyển tài khoản và lịch sử theo cùng ánh xạ để một tài khoản mới không đọc nhầm lịch sử cũ. Bản chạy thử dùng dữ liệu mới cho tới khi xác nhận phạm vi chuyển dữ liệu.
5. Sau khi nghiệm thu, chốt URL sẽ dùng cho demo và cập nhật báo cáo, sơ đồ triển khai và gói nộp theo đúng tài nguyên đã chạy.
