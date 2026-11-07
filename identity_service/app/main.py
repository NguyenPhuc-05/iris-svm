import os
import re
import hmac
import threading
import time
import bcrypt
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

try:
    from app.db import get_db
    from app.models import Client, User, init_db
    from app.public_secrets import is_public_secret
except (ImportError, ModuleNotFoundError):
    from identity_service.app.db import get_db
    from identity_service.app.models import Client, User, init_db
    from identity_service.app.public_secrets import is_public_secret

# JWT configuration
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET environment variable is missing or shorter than 32 characters.")
if is_public_secret(JWT_SECRET):
    raise RuntimeError(
        "JWT_SECRET is a publicly known default value from the repository. "
        'Generate a new one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60

security = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Centralized Identity Provider (IdP)",
    description="Unified SSO Identity Provider for All Projects",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS setup
raw_origins = os.getenv("FRONTEND_ORIGINS", "")
if raw_origins.strip():
    origins = [o.strip() for o in raw_origins.split(",") if o.strip()]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True if origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Pydantic Schemas ───

# Định dạng email đơn giản nhưng đủ chặt: không khoảng trắng, không ký tự HTML
# (< > " ' &) để email không thể mang mã độc khi được hiển thị trên giao diện.
EMAIL_PATTERN = re.compile(r"^[^@\s<>\"'&]+@[^@\s<>\"'&]+\.[^@\s<>\"'&]+$")


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, value: str) -> str:
        value = value.strip()
        if not EMAIL_PATTERN.match(value):
            raise ValueError("Email không hợp lệ")
        return value


class LoginRequest(BaseModel):
    email: str
    password: str
    client_id: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    is_owner: bool = False


# ─── Login rate limiting ───

class LoginRateLimiter:
    """Giới hạn số lần đăng nhập sai (trong bộ nhớ, đủ cho một instance Render).

    - Mỗi cặp (IP, email): tối đa `max_per_ip_email` lần sai trong `window_seconds`.
    - Mỗi email (mọi IP): tối đa `max_per_email` lần sai, chặn việc đổi IP/giả
      header X-Forwarded-For để vượt giới hạn trên.
    Trạng thái mất khi service khởi động lại, vì vậy đây là lớp phòng thủ bổ sung,
    không thay thế mật khẩu mạnh.
    """

    def __init__(
        self,
        max_per_ip_email: int = 5,
        max_per_email: int = 30,
        window_seconds: int = 15 * 60,
        max_keys: int = 10_000,
    ):
        self.max_per_ip_email = max_per_ip_email
        self.max_per_email = max_per_email
        self.window = window_seconds
        self.max_keys = max_keys
        self._failures: dict[tuple, deque] = {}
        self._lock = threading.Lock()

    def _keys(self, ip: str, email: str) -> tuple[tuple, tuple]:
        email = email[:255]
        return ("ie", ip, email), ("e", email)

    def _live(self, key: tuple, now: float) -> deque:
        dq = self._failures.get(key)
        if dq is None:
            return deque()
        while dq and now - dq[0] > self.window:
            dq.popleft()
        if not dq:
            self._failures.pop(key, None)
        return dq

    def retry_after(self, ip: str, email: str) -> int:
        """Số giây phải chờ nếu đang bị chặn, 0 nếu được phép thử."""
        now = time.monotonic()
        ie_key, e_key = self._keys(ip, email)
        wait = 0
        with self._lock:
            for key, limit in ((ie_key, self.max_per_ip_email), (e_key, self.max_per_email)):
                dq = self._live(key, now)
                if len(dq) >= limit:
                    wait = max(wait, int(self.window - (now - dq[0])) + 1)
        return wait

    def record_failure(self, ip: str, email: str) -> None:
        now = time.monotonic()
        with self._lock:
            for key in self._keys(ip, email):
                self._failures.setdefault(key, deque()).append(now)
            if len(self._failures) > self.max_keys:
                self._evict(now)

    def reset(self, ip: str, email: str) -> None:
        """Xóa bộ đếm của cặp (IP, email) sau khi đăng nhập thành công."""
        with self._lock:
            self._failures.pop(self._keys(ip, email)[0], None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()

    def _evict(self, now: float) -> None:
        for key in list(self._failures):
            self._live(key, now)
        while len(self._failures) > self.max_keys:
            oldest = min(self._failures, key=lambda k: self._failures[k][-1])
            self._failures.pop(oldest, None)


login_limiter = LoginRateLimiter()


def client_ip(request: Request) -> str:
    # Sau proxy của Render, IP thật nằm ở phần tử đầu của X-Forwarded-For.
    forwarded = request.headers.get("x-forwarded-for", "")
    first = forwarded.split(",")[0].strip()
    if first:
        return first[:64]
    return request.client.host if request.client else "unknown"


# ─── Auth Helper Functions ───

def hash_password(password: str) -> str:
    pwd_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, email: str, client_id: str, is_owner: bool = False) -> tuple[str, int]:
    now = datetime.now(timezone.utc)
    expires_delta = timedelta(minutes=JWT_EXPIRATION_MINUTES)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "email": email,
        "aud": client_id,
        "iat": now,
        "exp": expire,
        "is_owner": is_owner,  # claim bổ sung để frontend nhận biết owner
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())


def decode_owner_token(credentials: Optional[HTTPAuthorizationCredentials]) -> dict:
    """Dependency: chỉ cho phép owner truy cập. Trả về payload nếu hợp lệ."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        if not payload.get("is_owner"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Chỉ tài khoản chủ sở hữu mới có quyền truy cập",
            )
        return payload
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ─── Endpoints ───

@app.get("/health")
def health():
    return {"status": "ok", "service": "identity-service"}


@app.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()

    # Không cho phép đăng ký đè lên tài khoản owner
    existing_user = db.query(User).filter(User.email == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email đã được đăng ký",
        )

    user = User(
        email=normalized_email,
        password_hash=hash_password(payload.password),
        is_owner=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "id": user.id,
        "email": user.email,
        "msg": "Đăng ký thành công",
    }


@app.post("/login", response_model=TokenResponse)
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    # 1. Validate client_id
    client = db.query(Client).filter(Client.client_id == payload.client_id).first()
    if not client:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown client_id '{payload.client_id}'",
        )

    # 2. Validate user credentials.
    # Self-heal the configured Owner account if the database contains an old
    # password hash (or the row was lost during an ephemeral SQLite restart).
    normalized_email = payload.email.strip().lower()
    ip = client_ip(request)

    # Chặn dò mật khẩu: quá nhiều lần sai thì từ chối trước khi kiểm tra.
    wait_seconds = login_limiter.retry_after(ip, normalized_email)
    if wait_seconds:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Đăng nhập sai quá nhiều lần. Vui lòng thử lại sau {wait_seconds // 60 + 1} phút.",
            headers={"Retry-After": str(wait_seconds)},
        )
    owner_email = os.getenv("OWNER_EMAIL", "admin@ml-dl-ai.local").strip().lower()
    raw_owner_password = os.getenv("OWNER_PASSWORD") or ""
    user = db.query(User).filter(User.email == normalized_email).first()

    # Compare as bytes: hmac.compare_digest raises TypeError for str arguments
    # containing non-ASCII characters, which turned a valid owner login into a
    # 500 error. Also accept the secret with stray leading/trailing whitespace
    # removed, since copy-pasting a secret into Render often adds a newline.
    submitted_bytes = payload.password.encode("utf-8")
    # A publicly known default password (it appeared in the public git history)
    # is never accepted as the owner secret.
    owner_candidates = {
        candidate
        for candidate in (raw_owner_password, raw_owner_password.strip())
        if candidate and not is_public_secret(candidate)
    }
    is_configured_owner = normalized_email == owner_email and any(
        hmac.compare_digest(submitted_bytes, candidate.encode("utf-8"))
        for candidate in owner_candidates
    )
    configured_owner_password = payload.password if is_configured_owner else None

    if is_configured_owner:
        if user is None:
            user = User(
                email=owner_email,
                password_hash=hash_password(configured_owner_password),
                is_owner=True,
                created_at=datetime.now(timezone.utc),
            )
            db.add(user)
        else:
            # Re-sync stale hashes and restore the owner flag only when the
            # submitted password exactly matches the Render secret.
            if not verify_password(configured_owner_password, user.password_hash):
                user.password_hash = hash_password(configured_owner_password)
            user.is_owner = True
        db.commit()
        db.refresh(user)

    # Owner authentication is anchored to the configured Render secret.
    # Do not re-check the synchronized bcrypt hash after the constant-time
    # comparison above: this avoids rejecting a valid owner due to stale or
    # malformed legacy hashes.
    if not user or (
        not is_configured_owner
        and not verify_password(payload.password, user.password_hash)
    ):
        login_limiter.record_failure(ip, normalized_email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sai email hoặc mật khẩu",
        )

    login_limiter.reset(ip, normalized_email)

    # 3. Cập nhật last_login_at
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    # 4. Generate token (kèm is_owner claim)
    token, expires_in = create_access_token(user.id, user.email, payload.client_id, user.is_owner)

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=expires_in,
        user={"id": user.id, "email": user.email, "is_owner": user.is_owner},
    )


@app.get("/me", response_model=UserResponse)
def get_me(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM],
            options={"verify_aud": False},
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token claims",
            )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User không tồn tại",
        )

    return UserResponse(id=user.id, email=user.email, is_owner=user.is_owner)


# ─── Admin Endpoints (Owner only) ───

@app.get("/admin/users")
def admin_list_users(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    db: Session = Depends(get_db),
):
    """
    [OWNER ONLY] Danh sách tất cả tài khoản:
    email, thời điểm tạo, lần đăng nhập cuối, có phải owner không.
    """
    decode_owner_token(credentials)

    users = db.query(User).order_by(User.created_at.desc()).all()

    def fmt(dt):
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()

    return [
        {
            "id": u.id,
            "email": u.email,
            "is_owner": u.is_owner,
            "created_at": fmt(u.created_at),
            "last_login_at": fmt(u.last_login_at),
        }
        for u in users
    ]
    