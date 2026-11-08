# Lưu trữ dữ liệu bền vững (tài khoản và lịch sử dự đoán)

## Vấn đề

Gói **Free** của Render không giữ ổ đĩa: mỗi lần service khởi động lại hoặc deploy, file SQLite bị xóa,
kéo theo mất **tài khoản người dùng** (identity-service) và **lịch sử dự đoán** (iris-svm-api).

Postgres miễn phí của chính Render cũng **hết hạn sau 30 ngày** (có thêm 14 ngày ân hạn rồi bị xóa),
nên không phù hợp để lưu lâu dài. Cần một Postgres ngoài có gói miễn phí không hết hạn,
ví dụ Neon, Supabase hoặc Aiven (điều kiện từng gói có thể thay đổi, hãy kiểm tra trên trang của nhà cung cấp).

## Cấu hình (ví dụ với Neon)

1. Tạo tài khoản và một project Postgres trên nhà cung cấp.
2. Tạo **hai database riêng** trong project đó, ví dụ `idp` (tài khoản) và `iris` (lịch sử dự đoán).
   Tách riêng để CSDL tài khoản không dùng chung với dữ liệu ứng dụng.
3. Lấy chuỗi kết nối của từng database (dạng `postgresql://user:matkhau@host/tendb?sslmode=require`).
4. Trên Render, mở **Environment** của từng service và dán:

| Service | Biến | Giá trị |
|---|---|---|
| `identity-service` | `IDP_DATABASE_URL` | chuỗi kết nối database `idp` |
| `iris-svm-api` | `DATABASE_URL` | chuỗi kết nối database `iris` |

5. Lưu và deploy lại. Trong **Logs** sẽ thấy `[IdP] CSDL tài khoản: postgresql+psycopg2://...` và
   `[DB] Kết nối CSDL thành công: ...` (mật khẩu CSDL được che bằng `***`).

Có thể dán trực tiếp URL dạng `postgres://` hoặc `postgresql://`: code tự đổi thành
`postgresql+psycopg2://` để dùng đúng driver đã cài trong `requirements.txt`.

Để trống hai biến này thì service dùng SQLite tạm thời (chỉ nên dùng khi chạy thử trên máy cá nhân).
Nếu chạy trên Render mà dùng SQLite, log sẽ in cảnh báo `WARNING` về việc mất dữ liệu.

**Lưu ý:** nếu đã đặt `DATABASE_URL` mà không kết nối được, `iris-svm-api` sẽ báo lỗi và dừng
(không âm thầm chuyển sang SQLite), để tránh mất dữ liệu mà không ai biết.

## Mật khẩu được bảo vệ thế nào

- Mật khẩu người dùng **không bao giờ được lưu dạng gốc**. CSDL chỉ chứa hash **bcrypt** có salt riêng cho từng
  tài khoản (chuỗi `$2b$12$...`). Hai tài khoản đặt cùng mật khẩu vẫn cho hai hash khác nhau.
- bcrypt là hàm băm một chiều: không có cách "giải mã" để xem lại mật khẩu, kể cả quản trị viên.
- Các API (`/register`, `/login`, `/me`, `/admin/users`) **không trả về** mật khẩu hay hash.
  Tab quản trị chỉ thấy email, thời điểm tạo, lần đăng nhập cuối và quyền owner.
  Điều này được kiểm tra tự động trong `identity_service/tests/test_password_security.py`.
- Nếu người dùng quên mật khẩu, quản trị viên không thể xem lại, chỉ có thể xóa tài khoản để họ đăng ký lại.
- Riêng mật khẩu của tài khoản **owner** đặt qua biến môi trường `OWNER_PASSWORD` trên Render, nên chỉ những người
  có quyền truy cập Render của dự án mới thấy được. Hãy bảo vệ tài khoản Render bằng xác thực hai bước.

## Giới hạn cần biết

- Gói miễn phí của nhà cung cấp Postgres có giới hạn dung lượng và có thể tạm dừng khi không dùng
  (dữ liệu vẫn còn, lần truy cập đầu tiên có thể chậm). Cần sao lưu định kỳ nếu dữ liệu quan trọng.
- Bộ đếm giới hạn đăng nhập sai vẫn nằm trong bộ nhớ của service nên bị xóa khi khởi động lại.
