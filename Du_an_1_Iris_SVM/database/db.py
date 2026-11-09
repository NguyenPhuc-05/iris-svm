import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker, declarative_base

# Thư mục chứa file SQLite fallback (cùng thư mục với module này)
_FALLBACK_DB = Path(__file__).resolve().parent / "iris_fallback.db"


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


def _make_engine(url: str):
    # pool_pre_ping + pool_recycle: tự nối lại khi CSDL miễn phí đóng kết nối nhàn rỗi.
    engine = create_engine(url, pool_pre_ping=True, pool_recycle=300)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return engine


def connect_database(explicit_url: str | None):
    """Use SQLite by default and honor an explicitly configured database."""
    if not explicit_url:
        return create_engine(
            f"sqlite:///{_FALLBACK_DB.as_posix()}",
            connect_args={"check_same_thread": False},
        )

    url = normalize_db_url(explicit_url)
    try:
        make_url(url)
    except Exception:
        raise RuntimeError("DATABASE_URL has an invalid format.") from None
    try:
        return _make_engine(url)
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL được đặt nhưng không kết nối được tới CSDL "
            f"({type(exc).__name__}). Kiểm tra lại URL; service sẽ không chuyển sang SQLite."
        ) from None


DATABASE_URL = os.getenv("DATABASE_URL") or None
engine = connect_database(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
