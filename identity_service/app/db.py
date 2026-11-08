import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker

APP_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_FILE = (APP_DIR / "identity.db").resolve()


def normalize_db_url(url: str) -> str:
    """Chuẩn hóa URL Postgres do Render/Heroku/Neon cấp ("postgres://..." hoặc
    "postgresql://...") thành "postgresql+psycopg2://...".

    - SQLAlchemy 2.x không nhận tiền tố "postgres://".
    - Với SQLAlchemy 2.1, "postgresql://" mặc định dùng driver psycopg (bản 3), còn
      requirements.txt cài psycopg2-binary, nên phải chỉ rõ driver để không lỗi
      ModuleNotFoundError khi khởi động trên Render.
    URL đã chỉ rõ driver (vd. "postgresql+psycopg://") được giữ nguyên.
    """
    url = url.strip()
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


# QUAN TRỌNG: Dùng IDP_DATABASE_URL riêng để không bao giờ bị dính biến DATABASE_URL (MySQL) của dự án chính
_explicit_url = os.getenv("IDP_DATABASE_URL") or os.getenv("IDENTITY_DATABASE_URL")
IDP_DB_URL = normalize_db_url(_explicit_url) if _explicit_url else f"sqlite:///{DEFAULT_DB_FILE.as_posix()}"

is_sqlite = IDP_DB_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# pool_pre_ping + pool_recycle giúp tự nối lại khi Postgres miễn phí đóng kết nối nhàn rỗi.
engine = create_engine(
    IDP_DB_URL,
    connect_args=connect_args,
    pool_pre_ping=not is_sqlite,
    **({} if is_sqlite else {"pool_recycle": 300}),
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

if is_sqlite:
    if os.getenv("RENDER"):
        print(
            "[IdP WARNING] Đang chạy trên Render với SQLite: tài khoản người dùng sẽ MẤT "
            "mỗi lần khởi động lại. Đặt IDP_DATABASE_URL trỏ tới Postgres bền vững."
        )
else:
    # Không in mật khẩu CSDL ra log (log của Render có thể bị người khác xem).
    print(f"[IdP] CSDL tài khoản: {make_url(IDP_DB_URL).render_as_string(hide_password=True)}")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
