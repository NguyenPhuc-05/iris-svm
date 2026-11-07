"""Phát hiện các giá trị bí mật đã bị lộ công khai.

Một số mật khẩu/khóa mặc định từng nằm trong mã nguồn hoặc lịch sử git của repo
(repo này public), nên ai cũng đọc được. Chúng chỉ được lưu dưới dạng SHA-256 để
chính file này không làm lộ thêm lần nữa. Dịch vụ từ chối dùng các giá trị này
làm JWT_SECRET hoặc OWNER_PASSWORD.
"""

import hashlib

_PUBLIC_SECRET_DIGESTS = frozenset(
    {
        "57dc58ab6a5430ed24e4790c53e8e116fcee101d28b7ae6e693a6b4e4f7d1e9f",
        "9fea218fda99ce46fc1c1eeab3665cdeaa6c5682c068b6455e3116bdd05d6d86",
        "b3f0ad14631e3f3489858d72f5b0cda651050ca6a0e88af3a138f2989d5f92ec",
        "2390b64bb1fe9dff1760145c100acba92782b582cc18a9206bddcfde047d3374",
    }
)


def is_public_secret(value: str) -> bool:
    """True nếu `value` là giá trị mặc định/mẫu đã lộ công khai."""
    if not value:
        return False
    for candidate in {value, value.strip()}:
        digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
        if digest in _PUBLIC_SECRET_DIGESTS:
            return True
    return False
