import pytest

from app.config import settings
from app.security import create_token, totp_code, totp_step
from conftest import TOTP_SECRET, bearer, login, session_headers

SIGNUP = {
    "last_name": "홍", "first_name": "길동", "birth_date": "1990-01-02", "phone": "01077778888",
    "email": "Hong@swp.co.kr", "emp_no": "hong.gd", "password": "password1", "password_confirm": "password1",
}


def otp_token(client, emp_no="admin", password="admin1234"):
    return login(client, emp_no, password).json()["otp_token"]


def verify(client, token, code):
    return client.post("/api/auth/otp/verify", json={"code": code}, headers=bearer(token))


def current_code():
    return totp_code(TOTP_SECRET, totp_step())


def test_totp_matches_rfc6238_vector():
    # RFC 6238 SHA1 벡터(시각 59초)의 8자리 94287082에서 뒤 6자리
    assert totp_code("GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ", totp_step(59)) == "287082"


def test_t01_approved_login(client):
    res = login(client, "park.pm")
    body = res.json()
    assert res.status_code == 200 and body["otp_required"] is False and body["token_type"] == "bearer"
    assert body["expires_in"] == settings.token_ttl
    assert body["user"]["groups"] == [{"code": "PROC", "name": "공정관리자"}]
    me = client.get("/api/auth/me", headers=bearer(body["access_token"])).json()
    assert me == body["user"]
    assert me["today"] == "2026-10-19" and me["totp_enabled"] is False


@pytest.mark.parametrize("emp_no,password", [("nouser", "whatever1"), ("park.pm", "wrong-pass")])
def test_invalid_credentials_same_error(client, emp_no, password):
    res = login(client, emp_no, password)
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"
    assert res.json()["message"] == "아이디 또는 비밀번호가 올바르지 않습니다."


@pytest.mark.parametrize("status,code,message", [
    ("pending", "ACCOUNT_PENDING", "관리자 승인 대기 중인 계정입니다."),
    ("rejected", "ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
    ("disabled", "ACCOUNT_DISABLED", "사용이 중지된 계정입니다."),
])
def test_t02_status_guidance(client, conn, status, code, message):
    conn.execute("UPDATE users SET status=? WHERE emp_no='jung.new'", (status,))
    res = login(client, "jung.new")
    assert res.status_code == 403 and res.json()["code"] == code and res.json()["message"] == message


def test_t02_wrong_password_hides_status(client):
    assert login(client, "jung.new", "wrong-pass").status_code == 401


def test_t03_otp_token_cannot_access_protected_api(client):
    body = login(client, "admin", "admin1234").json()
    assert body["otp_required"] is True and body["expires_in"] == settings.otp_token_ttl
    assert "access_token" not in body
    assert client.get("/api/auth/me", headers=bearer(body["otp_token"])).status_code == 401
    assert client.get("/api/me/menu", headers=bearer(body["otp_token"])).status_code == 401


def test_otp_success_returns_session(client, conn):
    res = verify(client, otp_token(client), current_code())
    assert res.status_code == 200 and res.json()["user"]["emp_no"] == "admin"
    assert res.json()["user"]["totp_enabled"] is True
    assert client.get("/api/auth/me", headers=bearer(res.json()["access_token"])).status_code == 200
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_LogAccess WHERE UserId='admin'").fetchone()[0] == 1


def test_otp_accepts_adjacent_step_only(client):
    token = otp_token(client)
    assert verify(client, token, totp_code(TOTP_SECRET, totp_step() - 3)).status_code == 400
    assert verify(client, token, totp_code(TOTP_SECRET, totp_step() + 1)).status_code == 200


def test_otp_step_reuse_rejected_for_same_user(client):
    code = current_code()
    assert verify(client, otp_token(client), code).status_code == 200
    res = verify(client, otp_token(client), code)
    assert res.status_code == 400 and res.json()["code"] == "OTP_INVALID"
    assert res.json()["message"] == "인증 코드가 올바르지 않습니다."


def test_otp_step_tracked_per_user(client):
    code = current_code()
    assert verify(client, otp_token(client), code).status_code == 200
    assert verify(client, otp_token(client, "lee.dwg", "dwg1234"), code).status_code == 200


def test_otp_locks_after_five_failures_per_token(client):
    token = otp_token(client)
    wrong = "000000" if current_code() != "000000" else "111111"
    for _ in range(5):
        assert verify(client, token, wrong).status_code == 400
    res = verify(client, token, current_code())
    assert res.status_code == 429 and res.json()["code"] == "OTP_LOCKED"
    assert res.json()["message"] == "인증 시도 횟수를 초과했습니다. 다시 로그인하세요."
    assert verify(client, otp_token(client), current_code()).status_code == 200


def test_otp_verify_requires_otp_stage(client):
    headers = session_headers(client, "park.pm")
    res = client.post("/api/auth/otp/verify", json={"code": "123456"}, headers=headers)
    assert res.status_code == 401


def test_non_ascii_otp_code_is_rejected_not_crash(client):
    assert verify(client, otp_token(client), "한글코드").status_code == 400


@pytest.mark.parametrize("change,field,message", [
    ({"last_name": " "}, "name", "성과 이름을 입력하세요."),
    ({"birth_date": "1990-13-01"}, "birth_date", "생년월일을 입력하세요."),
    ({"email": "bad@mail"}, "email", "이메일 형식이 올바르지 않습니다."),
    ({"phone": "02-123-4567"}, "phone", "전화번호 형식(010-0000-0000)이 올바르지 않습니다."),
    ({"emp_no": "ab"}, "emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다."),
    ({"emp_no": "a" * 21}, "emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다."),
    ({"password": "short", "password_confirm": "short"}, "password", "비밀번호는 8자 이상 입력하세요."),
    ({"password_confirm": "different1"}, "password_confirm", "비밀번호 확인이 일치하지 않습니다."),
])
def test_t04_validation(client, change, field, message):
    res = client.post("/api/auth/register", json={**SIGNUP, **change})
    assert res.status_code == 400
    assert res.json() == {"code": "VALIDATION_ERROR", "message": message, "details": {"field": field}}


def test_validation_order(client):
    res = client.post("/api/auth/register", json={"email": "bad", "phone": "x"})
    assert res.json()["details"]["field"] == "name"


@pytest.mark.parametrize("change,message", [
    ({"emp_no": "park.pm"}, "이미 사용 중인 아이디입니다."),
    ({"email": "PARK.PM@swp.co.kr"}, "이미 등록된 이메일입니다."),
    ({"phone": "01022220002"}, "이미 등록된 전화번호입니다."),
])
def test_t04_duplicates(client, change, message):
    res = client.post("/api/auth/register", json={**SIGNUP, **change})
    assert res.status_code == 409 and res.json()["code"] == "DUPLICATE" and res.json()["message"] == message


def test_t05_register_pending_cannot_login(client, conn):
    res = client.post("/api/auth/register", json=SIGNUP)
    assert res.status_code == 201
    assert res.json()["emp_no"] == "hong.gd" and res.json()["status"] == "pending" and res.json()["message"]
    row = conn.execute("SELECT * FROM users WHERE emp_no='hong.gd'").fetchone()
    assert (row["id"], row["display_name"], row["phone"], row["status"], row["created_at"]) == (
        "u-hong.gd", "홍길동", "010-7777-8888", "pending", "2026-10-19")
    assert row["password_hash"].startswith("$argon2id$")
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_AuthUser WHERE EmpNo='hong.gd'").fetchone()[0] == 0
    assert login(client, "hong.gd", "password1").json()["code"] == "ACCOUNT_PENDING"


def test_t06_logout_then_401(client, conn):
    headers = session_headers(client, "park.pm")
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401 and res.json()["message"] == "세션이 만료되었거나 유효하지 않습니다."
    assert conn.execute("SELECT LogoutDt FROM TB_SYS_LogAccess WHERE UserId='park.pm'").fetchone()[0]


def test_t06_expired_token_401(client, monkeypatch):
    monkeypatch.setattr(settings, "token_ttl", -1)
    token = login(client, "park.pm").json()["access_token"]
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_protected_api_requires_token_and_approved_user(client, conn):
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("garbage")).status_code == 401
    headers = session_headers(client, "park.pm")
    conn.execute("UPDATE users SET status='disabled' WHERE emp_no='park.pm'")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_token_with_mismatched_log_is_rejected(client, conn):
    log_id = conn.execute("INSERT INTO TB_SYS_LogAccess (UserId, LoginDt) VALUES ('admin','x')").lastrowid
    token = create_token("park.pm", "full", 60, lid=log_id)
    assert client.get("/api/auth/me", headers=bearer(token)).status_code == 401


def test_t07_access_log_matches_account(client, conn):
    session_headers(client, "park.pm")
    session_headers(client, "lee.dwg")
    login(client, "choi.qa", "wrong-pass")
    login(client, "admin", "admin1234")  # 1차 인증만으로는 세션이 아니다
    rows = conn.execute("SELECT UserId, LoginDt, LogoutDt, IpAddress FROM TB_SYS_LogAccess ORDER BY LogId").fetchall()
    assert [r["UserId"] for r in rows] == ["park.pm", "lee.dwg"]
    assert all(r["LoginDt"].endswith("+00:00") and r["LogoutDt"] is None and r["IpAddress"] for r in rows)
