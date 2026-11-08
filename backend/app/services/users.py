"""가입 검증과 계정 생성. 회원관리(F09)가 재사용한다."""
import re
import sqlite3
from datetime import date

from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from ..security import hash_password

EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE = re.compile(r"^01\d-?\d{3,4}-?\d{4}$", re.ASCII)
EMP_NO = re.compile(r"^[A-Za-z0-9._-]{4,20}$")
BIRTH = re.compile(r"^\d{4}-\d{2}-\d{2}$", re.ASCII)


def _valid_date(value: str) -> bool:
    if not BIRTH.fullmatch(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def validate_signup(data: dict, update: bool = False) -> None:
    """update=True: 아이디 검사 제외, 비밀번호는 입력했을 때만 검사(F09)."""
    if not data["last_name"].strip() or not data["first_name"].strip():
        raise validation("name", "성과 이름을 입력하세요.")
    if not _valid_date(data["birth_date"]):
        raise validation("birth_date", "생년월일을 입력하세요.")
    if not EMAIL.fullmatch(data["email"]):
        raise validation("email", "이메일 형식이 올바르지 않습니다.")
    if not PHONE.fullmatch(data["phone"]):
        raise validation("phone", "전화번호 형식(010-0000-0000)이 올바르지 않습니다.")
    if not update and not EMP_NO.fullmatch(data["emp_no"]):
        raise validation("emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다.")
    if (data["password"] or not update) and len(data["password"]) < 8:
        raise validation("password", "비밀번호는 8자 이상 입력하세요.")
    if data.get("password_confirm", data["password"]) != data["password"]:
        raise validation("password_confirm", "비밀번호 확인이 일치하지 않습니다.")


def _check_duplicates(conn: sqlite3.Connection, emp_no: str, email: str, digits: str, update: bool = False) -> None:
    checks = (
        ("emp_no = ?", emp_no, "emp_no", "이미 사용 중인 아이디입니다."),
        ("lower(email) = lower(?)", email, "email", "이미 등록된 이메일입니다."),
        ("replace(phone, '-', '') = ?", digits, "phone", "이미 등록된 전화번호입니다."),
    )[update:]  # 수정은 아이디 검사 없이 본인을 제외한다
    for where, value, field, message in checks:
        if conn.execute(f"SELECT 1 FROM users WHERE {where} AND emp_no <> ?", (value, emp_no if update else "")).fetchone():
            raise ApiError(409, "DUPLICATE", message, {"field": field})


def _phone(value: str) -> tuple[str, str]:
    digits = value.replace("-", "")
    return digits, f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


def create_user(conn: sqlite3.Connection, data: dict, status: str = "pending", groups: list[str] = ()) -> str:
    validate_signup(data)
    digits, phone = _phone(data["phone"])
    last, first = data["last_name"].strip(), data["first_name"].strip()
    password_hash = hash_password(data["password"])  # 쓰기 잠금 밖에서 계산한다
    with tx(conn):
        _check_duplicates(conn, data["emp_no"], data["email"], digits)
        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, emp_no, status,"
            " last_name, first_name, birth_date, phone, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                f"u-{data['emp_no']}", data["email"], password_hash, last + first, data["emp_no"], status,
                last, first, data["birth_date"], phone, settings.today,
            ),
        )
        _set_groups(conn, data["emp_no"], groups)
    return data["emp_no"]


# ---- 회원관리(F09) ----
STATUSES = ("pending", "approved", "rejected", "disabled")
FIELDS = ("emp_no", "last_name", "first_name", "display_name", "email", "phone", "birth_date", "status", "created_at")


def _not_found() -> ApiError:
    return ApiError(404, "USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")


def _out(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    groups = conn.execute(
        "SELECT g.AuthCd, g.AuthNm FROM TB_SYS_AuthUser u JOIN TB_SYS_AuthGroup g ON g.AuthCd = u.AuthCd"
        " WHERE u.EmpNo = ? ORDER BY g.AuthCd",
        (row["emp_no"],),
    ).fetchall()
    # password_hash, totp_secret은 절대 내보내지 않는다
    return {
        **{k: row[k] for k in FIELDS},
        "totp_enabled": bool(row["totp_enabled"]),
        "groups": [{"code": g[0], "name": g[1]} for g in groups],
    }


def _row(conn: sqlite3.Connection, emp_no: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if row is None:
        raise _not_found()
    return row


def _check_options(conn: sqlite3.Connection, status: str, groups: list[str] | None, totp: bool, secret) -> None:
    if status not in STATUSES:
        raise validation("status", "허용되지 않는 상태입니다.")
    for code in groups or ():
        if not conn.execute("SELECT 1 FROM TB_SYS_AuthGroup WHERE AuthCd = ?", (code,)).fetchone():
            raise validation("groups", "존재하지 않는 권한 그룹입니다.")
    if totp and not secret:
        raise ApiError(409, "OTP_NOT_ENROLLED", "OTP가 등록되지 않은 사용자는 2차 인증을 사용할 수 없습니다.")


def _set_groups(conn: sqlite3.Connection, emp_no: str, groups) -> None:
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo = ?", (emp_no,))
    conn.executemany("INSERT INTO TB_SYS_AuthUser (AuthCd, EmpNo) VALUES (?, ?)", [(g, emp_no) for g in dict.fromkeys(groups)])


def list_users(conn: sqlite3.Connection, status: str | None, q: str | None) -> dict:
    sql, args = "SELECT * FROM users WHERE 1 = 1", []
    if status:
        sql += " AND status = ?"
        args.append(status)
    if q and q.strip():
        sql += " AND instr(lower(emp_no || ' ' || display_name || ' ' || email || ' ' || phone), lower(?)) > 0"
        args.append(q.strip())
    rows = conn.execute(sql + " ORDER BY created_at, emp_no", args).fetchall()
    pending = conn.execute("SELECT count(*) FROM users WHERE status = 'pending'").fetchone()[0]
    return {"users": [_out(conn, r) for r in rows], "total": len(rows), "pending": pending}


def get_user(conn: sqlite3.Connection, emp_no: str) -> dict:
    return _out(conn, _row(conn, emp_no))


def admin_create(conn: sqlite3.Connection, data: dict) -> dict:
    status = data.get("status") or "approved"
    _check_options(conn, status, data.get("groups"), bool(data.get("totp_enabled")), None)
    emp_no = create_user(conn, data, status, data.get("groups") or [])
    return get_user(conn, emp_no)


def update_user(conn: sqlite3.Connection, emp_no: str, data: dict) -> dict:
    row = _row(conn, emp_no)
    if data.get("emp_no") not in (None, emp_no):
        raise validation("emp_no", "아이디는 변경할 수 없습니다.")
    merged = {**dict(row), "password": "", **{k: v for k, v in data.items() if v is not None}}
    totp = bool(merged["totp_enabled"])
    _check_options(conn, merged["status"], data.get("groups"), totp and not row["totp_enabled"], row["totp_secret"])
    validate_signup(merged, update=True)
    digits, phone = _phone(merged["phone"])
    last, first = merged["last_name"].strip(), merged["first_name"].strip()
    password_hash = hash_password(merged["password"]) if merged["password"] else row["password_hash"]
    with tx(conn):
        _check_duplicates(conn, emp_no, merged["email"], digits, update=True)
        conn.execute(
            "UPDATE users SET last_name = ?, first_name = ?, display_name = ?, email = ?, phone = ?, birth_date = ?,"
            " status = ?, totp_enabled = ?, password_hash = ? WHERE emp_no = ?",
            (last, first, last + first, merged["email"], phone, merged["birth_date"], merged["status"], int(totp),
             password_hash, emp_no),
        )
        if data.get("groups") is not None:
            _set_groups(conn, emp_no, data["groups"])
    return get_user(conn, emp_no)


def _require_pending(conn: sqlite3.Connection, emp_no: str) -> None:
    if _row(conn, emp_no)["status"] != "pending":
        raise ApiError(409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")


def _decide_pending(conn: sqlite3.Connection, emp_no: str, status: str, groups: list[str]) -> dict:
    with tx(conn):
        _require_pending(conn, emp_no)
        conn.execute("UPDATE users SET status = ? WHERE emp_no = ?", (status, emp_no))
        if groups:
            _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def approve(conn: sqlite3.Connection, emp_no: str, groups: list[str] | None) -> dict:
    _require_pending(conn, emp_no)
    if not groups:
        raise validation("groups", "승인 시 권한 그룹을 1개 이상 지정하세요.")
    _check_options(conn, "approved", groups, False, None)
    return _decide_pending(conn, emp_no, "approved", groups)


def reject(conn: sqlite3.Connection, emp_no: str) -> dict:
    return _decide_pending(conn, emp_no, "rejected", [])


def delete_user(conn: sqlite3.Connection, emp_no: str, me: str) -> None:
    _row(conn, emp_no)
    if emp_no == me:
        raise ApiError(409, "SELF_DELETE", "로그인 중인 본인 계정은 삭제할 수 없습니다.")
    with tx(conn):
        conn.execute("DELETE FROM users WHERE emp_no = ?", (emp_no,))


def auth_groups(conn: sqlite3.Connection) -> list[dict]:
    return [{"code": r[0], "name": r[1]} for r in conn.execute("SELECT AuthCd, AuthNm FROM TB_SYS_AuthGroup ORDER BY AuthCd")]
