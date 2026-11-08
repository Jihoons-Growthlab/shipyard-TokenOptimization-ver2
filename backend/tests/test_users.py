import pytest

from conftest import login, session_headers

NEW = {"last_name": "홍", "first_name": "길동", "birth_date": "1990-01-01", "phone": "010-7777-0007",
       "email": "hong@swp.co.kr", "emp_no": "hong.gd", "password": "hong12345"}


@pytest.fixture
def admin(client):
    return session_headers(client, "admin")


def test_t01_filter_and_select(client, admin):
    data = client.get("/api/users", headers=admin).json()
    assert [u["emp_no"] for u in data["users"]] == ["admin", "choi.qa", "han.wk", "jung.new", "lee.dwg", "park.pm"]
    assert (data["total"], data["pending"]) == (6, 1)
    pend = client.get("/api/users", params={"status": "pending"}, headers=admin).json()
    assert [u["emp_no"] for u in pend["users"]] == ["jung.new"] and pend["pending"] == 1
    for q in ("도면", "LEE.DWG@", "3333-0003", "lee"):
        assert [u["emp_no"] for u in client.get("/api/users", params={"q": q}, headers=admin).json()["users"]] == ["lee.dwg"]
    one = client.get("/api/users/admin", headers=admin).json()
    assert one["groups"] == [{"code": "ADMIN", "name": "시스템관리자"}] and one["totp_enabled"] is True
    assert client.get("/api/users/nobody", headers=admin).json()["code"] == "USER_NOT_FOUND"
    assert client.get("/api/auth-groups", headers=admin).json()[0] == {"code": "ADMIN", "name": "시스템관리자"}


def test_t02_create_rejects_invalid(client, admin):
    cases = [
        ({"emp_no": "lee.dwg"}, 409, "emp_no"),
        ({"email": "LEE.DWG@swp.co.kr"}, 409, "email"),
        ({"phone": "01033330003"}, 409, "phone"),
        ({"email": "bad"}, 400, "email"),
        ({"emp_no": "ab"}, 400, "emp_no"),
        ({"password": "short"}, 400, "password"),
        ({"status": "weird"}, 400, "status"),
        ({"groups": ["NOPE"]}, 400, "groups"),
    ]
    for patch, status, field in cases:
        res = client.post("/api/users", json={**NEW, **patch}, headers=admin)
        assert (res.status_code, res.json()["details"].get("field")) == (status, field), patch
    res = client.post("/api/users", json={**NEW, "totp_enabled": True}, headers=admin)
    assert (res.status_code, res.json()["code"]) == (409, "OTP_NOT_ENROLLED")
    res = client.post("/api/users", json={**NEW, "last_name": "가" * 51}, headers=admin)
    assert res.status_code == 422
    res = client.post("/api/users", json={**NEW, "groups": ["PROC"]}, headers=admin)
    assert res.status_code == 201
    body = res.json()
    assert (body["status"], body["display_name"], body["groups"][0]["code"]) == ("approved", "홍길동", "PROC")
    assert login(client, "hong.gd", "hong12345").status_code == 200


def test_t03_blank_password_keeps_hash(client, admin, conn):
    before = conn.execute("SELECT password_hash FROM users WHERE emp_no = 'park.pm'").fetchone()[0]
    res = client.patch("/api/users/park.pm", json={"first_name": "공정2", "password": "", "phone": "010-2222-0002",
                                                   "email": "PARK.PM@swp.co.kr"}, headers=admin)
    assert res.status_code == 200 and res.json()["display_name"] == "박공정2"
    assert conn.execute("SELECT password_hash FROM users WHERE emp_no = 'park.pm'").fetchone()[0] == before
    assert client.patch("/api/users/park.pm", json={"password": "abc"}, headers=admin).json()["details"]["field"] == "password"
    assert client.patch("/api/users/park.pm", json={"email": "lee.dwg@swp.co.kr"}, headers=admin).status_code == 409
    res = client.patch("/api/users/park.pm", json={"emp_no": "park2"}, headers=admin)
    assert (res.status_code, res.json()["message"]) == (400, "아이디는 변경할 수 없습니다.")
    assert client.patch("/api/users/park.pm", json={"status": "x"}, headers=admin).json()["message"] == "허용되지 않는 상태입니다."
    client.patch("/api/users/park.pm", json={"password": "newpass99"}, headers=admin)
    assert login(client, "park.pm", "newpass99").status_code == 200


def test_t04_group_change_applies_now(client, admin):
    choi = session_headers(client, "choi.qa")
    assert client.post("/api/hulls", json={}, headers=choi).status_code == 403
    assert client.patch("/api/users/choi.qa", json={"groups": ["PROC"]}, headers=admin).json()["groups"][0]["code"] == "PROC"
    assert client.post("/api/hulls", json={}, headers=choi).status_code != 403
    assert client.patch("/api/users/choi.qa", json={"groups": []}, headers=admin).json()["groups"] == []
    assert client.get("/api/hulls", headers=choi).status_code == 403


def test_t05_approve_then_login(client, admin):
    assert login(client, "jung.new", "new12345").json()["code"] == "ACCOUNT_PENDING"
    res = client.post("/api/users/jung.new/approve", json={"groups": []}, headers=admin)
    assert (res.status_code, res.json()["message"]) == (400, "승인 시 권한 그룹을 1개 이상 지정하세요.")
    res = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=admin)
    assert res.json()["status"] == "approved" and res.json()["groups"][0]["code"] == "VIEW"
    assert login(client, "jung.new", "new12345").status_code == 200
    res = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=admin)
    assert (res.status_code, res.json()["code"], res.json()["message"]) == (409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")
    assert client.post("/api/users/jung.new/reject", headers=admin).status_code == 409


def test_reject_and_status_blocks_session(client, admin):
    assert client.post("/api/users/jung.new/reject", headers=admin).json()["status"] == "rejected"
    assert login(client, "jung.new", "new12345").json()["code"] == "ACCOUNT_REJECTED"
    park = session_headers(client, "park.pm")
    client.patch("/api/users/park.pm", json={"status": "disabled"}, headers=admin)
    assert client.get("/api/auth/me", headers=park).status_code == 401


def test_t06_delete(client, admin, conn):
    res = client.delete("/api/users/admin", headers=admin)
    assert (res.status_code, res.json()["code"]) == (409, "SELF_DELETE")
    assert conn.execute("SELECT count(*) FROM TB_PRC_Plan WHERE ManagerEmpNo = 'park.pm'").fetchone()[0] > 0
    session_headers(client, "park.pm")
    assert client.delete("/api/users/park.pm", headers=admin).status_code == 204
    assert conn.execute("SELECT count(*) FROM TB_PRC_Plan WHERE ManagerEmpNo = 'park.pm'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM TB_SYS_AuthUser WHERE EmpNo = 'park.pm'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM TB_SYS_LogAccess WHERE UserId IS NULL").fetchone()[0] > 0
    assert client.delete("/api/users/park.pm", headers=admin).status_code == 404


def test_t07_non_admin_forbidden(client):
    for name in ("park.pm", "choi.qa"):
        h = session_headers(client, name)
        assert client.get("/api/users", headers=h).status_code == 403
        assert client.patch("/api/users/jung.new", json={}, headers=h).status_code == 403
        assert client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h).status_code == 403
        assert client.get("/api/users/options", headers=h).status_code == 200


def test_t08_secret_hidden_and_otp_toggle(client, admin, conn):
    text = client.get("/api/users", headers=admin).text + client.get("/api/users/admin", headers=admin).text
    assert "password_hash" not in text and "totp_secret" not in text and "JBSWY3DPEHPK3PXP" not in text
    res = client.patch("/api/users/park.pm", json={"totp_enabled": True}, headers=admin)
    assert (res.status_code, res.json()["code"]) == (409, "OTP_NOT_ENROLLED")
    assert client.patch("/api/users/lee.dwg", json={"totp_enabled": False}, headers=admin).json()["totp_enabled"] is False
    assert conn.execute("SELECT totp_secret FROM users WHERE emp_no = 'lee.dwg'").fetchone()[0] == "JBSWY3DPEHPK3PXP"
    assert client.patch("/api/users/lee.dwg", json={"totp_enabled": True}, headers=admin).json()["totp_enabled"] is True
