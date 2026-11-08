import hmac
import sqlite3
import threading
import time

from ..config import settings
from ..db import tx
from ..errors import ApiError, unauthorized
from ..security import create_token, totp_code, totp_step, verify_password
from .system import utc_now

MAX_OTP_FAILURES = 5
STATUS_ERRORS = {
    "pending": ("ACCOUNT_PENDING", "관리자 승인 대기 중인 계정입니다."),
    "rejected": ("ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
    "disabled": ("ACCOUNT_DISABLED", "사용이 중지된 계정입니다."),
}

# 프로세스 메모리 상태. 검증 전체를 잠가 동시 요청이 시도 횟수와 step 재사용을 우회하지 못하게 한다.
_otp_lock = threading.Lock()
_otp_failures: dict[str, tuple[int, int]] = {}  # jti -> (실패 수, 토큰 만료)
_used_steps: dict[str, set[int]] = {}  # emp_no -> 사용한 step


def reset_otp_state() -> None:
    _otp_failures.clear()
    _used_steps.clear()


def profile(conn: sqlite3.Connection, user: sqlite3.Row | dict) -> dict:
    groups = conn.execute(
        "SELECT g.AuthCd, g.AuthNm FROM TB_SYS_AuthUser u JOIN TB_SYS_AuthGroup g ON g.AuthCd = u.AuthCd"
        " WHERE u.EmpNo = ? ORDER BY g.AuthCd",
        (user["emp_no"],),
    ).fetchall()
    return {
        "emp_no": user["emp_no"],
        "display_name": user["display_name"],
        "email": user["email"],
        "status": user["status"],
        "totp_enabled": bool(user["totp_enabled"]),
        "groups": [{"code": g["AuthCd"], "name": g["AuthNm"]} for g in groups],
        "today": settings.today,
    }


def _start_session(conn: sqlite3.Connection, user: sqlite3.Row, ip: str | None) -> dict:
    with tx(conn):
        log_id = conn.execute(
            "INSERT INTO TB_SYS_LogAccess (UserId, LoginDt, IpAddress) VALUES (?, ?, ?)",
            (user["emp_no"], utc_now(), ip),
        ).lastrowid
    return {
        "otp_required": False,
        "access_token": create_token(user["emp_no"], "full", settings.token_ttl, lid=log_id),
        "token_type": "bearer",
        "expires_in": settings.token_ttl,
        "user": profile(conn, user),
    }


def login(conn: sqlite3.Connection, emp_no: str, password: str, ip: str | None) -> dict:
    user = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if not verify_password(password, user["password_hash"] if user else None):
        raise ApiError(401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.")
    if user["status"] in STATUS_ERRORS:
        raise ApiError(403, *STATUS_ERRORS[user["status"]])
    if user["totp_enabled"]:
        token = create_token(user["emp_no"], "otp", settings.otp_token_ttl)
        return {"otp_required": True, "otp_token": token, "expires_in": settings.otp_token_ttl}
    return _start_session(conn, user, ip)


def _match_step(secret: str, emp_no: str, code: str) -> int | None:
    now = totp_step()
    used = _used_steps.get(emp_no, set())
    for step in (now - 1, now, now + 1):
        if step not in used and hmac.compare_digest(totp_code(secret, step).encode(), code.encode()):
            return step
    return None


def verify_otp(conn: sqlite3.Connection, payload: dict, code: str, ip: str | None) -> dict:
    if payload.get("stage") != "otp":
        raise unauthorized()
    user = conn.execute("SELECT * FROM users WHERE emp_no = ?", (payload["sub"],)).fetchone()
    if user is None or user["status"] != "approved" or not user["totp_secret"]:
        raise unauthorized()
    jti, emp_no = payload["jti"], user["emp_no"]
    with _otp_lock:
        failures = _otp_failures.get(jti, (0, 0))[0]
        if failures >= MAX_OTP_FAILURES:
            raise ApiError(429, "OTP_LOCKED", "인증 시도 횟수를 초과했습니다. 다시 로그인하세요.")
        step = _match_step(user["totp_secret"], emp_no, code)
        if step is None:
            now = time.time()
            for key in [k for k, (_, exp) in _otp_failures.items() if exp < now]:
                del _otp_failures[key]
            _otp_failures[jti] = (failures + 1, payload["exp"])
            raise ApiError(400, "OTP_INVALID", "인증 코드가 올바르지 않습니다.")
        current = totp_step()
        _used_steps[emp_no] = {s for s in _used_steps.get(emp_no, set()) if s >= current - 2} | {step}
        _otp_failures.pop(jti, None)
    return _start_session(conn, user, ip)


def logout(conn: sqlite3.Connection, log_id: int) -> None:
    conn.execute("UPDATE TB_SYS_LogAccess SET LogoutDt = ? WHERE LogId = ?", (utc_now(), log_id))
