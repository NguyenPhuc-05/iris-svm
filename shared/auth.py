import hashlib
import os
from typing import Optional

import jwt
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# HTTP Bearer scheme with auto_error=False to allow clean 401 exceptions
security = HTTPBearer(auto_error=False)

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET environment variable is missing or shorter than 32 characters.")

# Các JWT_SECRET mặc định/mẫu từng lộ công khai trong repo (chỉ lưu SHA-256).
# Cùng danh sách với identity_service/app/public_secrets.py; iris-svm-api không
# import được module đó nên lặp lại ở đây.
_PUBLIC_JWT_SECRET_DIGESTS = {
    "57dc58ab6a5430ed24e4790c53e8e116fcee101d28b7ae6e693a6b4e4f7d1e9f",
    "9fea218fda99ce46fc1c1eeab3665cdeaa6c5682c068b6455e3116bdd05d6d86",
}
if hashlib.sha256(JWT_SECRET.strip().encode("utf-8")).hexdigest() in _PUBLIC_JWT_SECRET_DIGESTS:
    raise RuntimeError(
        "JWT_SECRET is a publicly known default value from the repository. "
        'Generate a new one: python -c "import secrets; print(secrets.token_urlsafe(48))"'
    )


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
) -> dict:
    """
    FastAPI dependency that verifies Bearer JWT locally for the calling service.
    Validates signature via JWT_SECRET and audience matching CLIENT_ID.
    Returns: dict {"id": str, "email": str, "aud": str}
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yêu cầu đăng nhập (Missing Authorization header)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    expected_client_id = os.getenv("CLIENT_ID", "iris-svm-api")

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=["HS256"],
            audience=expected_client_id,
        )
        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token không hợp lệ (Missing subject claim)",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "id": str(user_id),
            "email": email,
            "aud": payload.get("aud"),
        }

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên làm việc đã hết hạn (Token expired)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidAudienceError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không dành cho dịch vụ này (Audience mismatch: expected '{expected_client_id}')",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token không hợp lệ ({str(e)})",
            headers={"WWW-Authenticate": "Bearer"},
        )

