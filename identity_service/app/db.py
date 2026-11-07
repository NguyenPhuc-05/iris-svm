import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_FILE = (APP_DIR / "identity.db").resolve()

# QUAN TRỌNG: Dùng IDP_DATABASE_URL riêng để không bao giờ bị dính biến DATABASE_URL (MySQL) của dự án chính
IDP_DB_URL = (
    os.getenv("IDP_DATABASE_URL") 
    or os.getenv("IDENTITY_DATABASE_URL") 
    or f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"
)

# Render/Heroku cấp URL dạng "postgres://..." nhưng SQLAlchemy 2.x chỉ nhận
# "postgresql://...". Chuẩn hóa để có thể dán thẳng Internal Database URL của Render.
if IDP_DB_URL.startswith("postgres://"):
    IDP_DB_URL = "postgresql://" + IDP_DB_URL[len("postgres://"):]

is_sqlite = IDP_DB_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# pool_pre_ping giúp tự nối lại khi Postgres miễn phí đóng kết nối nhàn rỗi.
engine = create_engine(IDP_DB_URL, connect_args=connect_args, pool_pre_ping=not is_sqlite)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
