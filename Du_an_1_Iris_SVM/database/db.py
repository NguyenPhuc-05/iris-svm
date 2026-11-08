import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Dùng MySQL làm CSDL chính thức (theo yêu cầu của Giảng viên) khi chạy trên máy cá nhân.
# Tạo database 'iris_svm' trong MySQL trước khi chạy.
_DEFAULT_URL = "mysql+pymysql://root:@localhost:3306/iris_svm"

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
    """Tạo engine cho lịch sử dự đoán.

    - Nếu người triển khai ĐẶT RÕ DATABASE_URL mà không nối được: báo lỗi và dừng.
      Tuyệt đối không lặng lẽ chuyển sang SQLite, vì SQLite trên Render bị xóa mỗi
      lần khởi động lại, dữ liệu sẽ mất mà không ai hay biết.
    - Nếu không đặt DATABASE_URL (chạy trên máy cá nhân): thử MySQL mặc định,
      không được thì dùng SQLite fallback như trước.
    """
    if explicit_url:
        url = normalize_db_url(explicit_url)
        try:
            engine = _make_engine(url)
        except Exception as exc:
            # Không in URL/mật khẩu ra log (log của Render có thể bị người khác xem).
            raise RuntimeError(
                "DATABASE_URL được đặt nhưng không kết nối được tới CSDL "
                f"({type(exc).__name__}). Kiểm tra lại URL; service sẽ không "
                "chuyển sang SQLite để tránh mất dữ liệu."
            ) from None
        print(f"[DB] Kết nối CSDL thành công: {engine.url.render_as_string(hide_password=True)}")
        return engine

    try:
        engine = _make_engine(_DEFAULT_URL)
        print(f"[DB] Kết nối CSDL thành công: {engine.url.render_as_string(hide_password=True)}")
        return engine
    except Exception:
        print("[DB] Không kết nối được MySQL. Chuyển sang SQLite fallback.")
        if os.getenv("RENDER"):
            print(
                "[DB WARNING] Đang chạy trên Render với SQLite: lịch sử dự đoán sẽ MẤT "
                "mỗi lần khởi động lại. Đặt DATABASE_URL trỏ tới Postgres bền vững."
            )
        return create_engine(
            f"sqlite:///{_FALLBACK_DB.as_posix()}",
            connect_args={"check_same_thread": False},
        )


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
