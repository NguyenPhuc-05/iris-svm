import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Dùng MySQL làm CSDL chính thức (theo yêu cầu của Giảng viên).
# Tạo database 'iris_svm' trong MySQL trước khi chạy.
DATABASE_URL = os.getenv("DATABASE_URL") or "mysql+pymysql://root:@localhost:3306/iris_svm"
# Render/Heroku cấp URL "postgres://..." nhưng SQLAlchemy 2.x chỉ nhận "postgresql://...".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql://" + DATABASE_URL[len("postgres://"):]

# Thư mục chứa file SQLite fallback (cùng thư mục với module này)
_FALLBACK_DB = Path(__file__).resolve().parent / "iris_fallback.db"

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    # Không in mật khẩu CSDL ra log (log của Render có thể bị người khác xem).
    print(f"[DB] Kết nối CSDL thành công: {engine.url.render_as_string(hide_password=True)}")
except Exception:
    print("[DB] Không kết nối được MySQL. Chuyển sang SQLite fallback.")
    _fallback_url = f"sqlite:///{_FALLBACK_DB.as_posix()}"
    engine = create_engine(_fallback_url, connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
