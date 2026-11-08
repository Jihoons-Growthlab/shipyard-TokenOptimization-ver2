import base64
import hashlib
import hmac
import struct
import time
import uuid

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from .config import settings

_hasher = PasswordHasher()  # 기본 type이 Argon2id
_decoy_hash = _hasher.hash("decoy")  # 없는 계정도 같은 시간이 걸리게 한다


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _decoy_hash, password) and password_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def create_token(sub: str, stage: str, ttl: int, **claims) -> str:
    now = int(time.time())
    payload = {"sub": sub, "stage": stage, "iat": now, "exp": now + ttl, "jti": uuid.uuid4().hex, **claims}
    return jwt.encode(payload, settings.app_secret, algorithm="HS256")


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.app_secret, algorithms=["HS256"], options={"require": ["exp", "sub", "jti"]})
    except jwt.InvalidTokenError:
        return None


def totp_code(secret: str, step: int) -> str:
    """RFC 6238: SHA1, 6자리."""
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{value % 1_000_000:06d}"


def totp_step(now: float | None = None) -> int:
    return int(time.time() if now is None else now) // 30
