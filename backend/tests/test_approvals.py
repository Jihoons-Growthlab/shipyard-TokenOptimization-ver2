import pytest

from conftest import session_headers


@pytest.fixture
def dwg(client):
    return session_headers(client, "lee.dwg")


@pytest.fixture
def admin(client):
    return session_headers(client, "admin")


def decide(client, h, approval_id, result="APPROVE", comment=None):
    return client.post(f"/api/approvals/{approval_id}/decision", json={"result": result, "comment": comment}, headers=h)


def test_t01_second_step_waits_for_first(client, dwg, admin):
    mine = client.get("/api/approvals/inbox", headers=dwg).json()
    assert [w["approval_id"] for w in mine["waiting"]] == [29, 47, 53] and mine["can_issue"]
    assert all(w["step_no"] == 1 for w in mine["waiting"])
    adm = client.get("/api/approvals/inbox", headers=admin).json()["waiting"]
    assert [w["approval_id"] for w in adm] == [50] and adm[0]["drawing_no"] == "8002-HULL-401"
    res = decide(client, admin, 30)
    assert res.status_code == 409 and res.json()["code"] == "NOT_CURRENT_STEP"
    assert decide(client, dwg, 29).json()["waiting"][0]["approval_id"] == 47
    assert 30 in [w["approval_id"] for w in client.get("/api/approvals/inbox", headers=admin).json()["waiting"]]


def test_t02_only_assigned(client, dwg):
    res = decide(client, dwg, 50)
    assert res.status_code == 403 and res.json()["code"] == "NOT_ASSIGNED_APPROVER"
    qa = session_headers(client, "choi.qa")
    assert client.get("/api/approvals/inbox", headers=qa).json()["can_issue"] is False
    assert decide(client, qa, 50).status_code == 403
    assert client.get("/api/approvals/inbox", headers=session_headers(client, "park.pm")).status_code == 403


def test_order_of_checks(client, dwg):
    assert decide(client, dwg, 999, result="OK").json()["message"] == "결재 결과는 APPROVE 또는 REJECT 이어야 합니다."
    assert decide(client, dwg, 999, result="REJECT", comment=" ").json()["message"] == "반려 시 의견을 입력하세요."
    assert decide(client, dwg, 999).json()["code"] == "APPROVAL_NOT_FOUND"
    res = decide(client, dwg, 1)
    assert res.status_code == 409 and res.json()["code"] == "ALREADY_DECIDED"


def test_t03_reject(client, dwg, conn):
    res = decide(client, dwg, 29, "REJECT", "치수 오류")
    assert res.status_code == 200 and res.json()["result"] == "REJECT"
    d = client.get("/api/drawings/15", headers=dwg).json()
    assert d["dwg_status"] == "DRAFT" and d["revisions"][0]["rev_status"] == "DRAFT"
    assert conn.execute("SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId = 15 AND RevNo = 1 AND Result = 'WAIT'").fetchone()[0] == 0
    hist = client.get("/api/approvals/history", headers=dwg).json()
    assert any(h["approval_id"] == 29 and h["result"] == "REJECT" and h["comment"] == "치수 오류" for h in hist)
    # 재요청은 결재행을 새로 만든다
    d = client.post("/api/drawings/15/revisions/1/request-approval", json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=dwg).json()
    assert [a["result"] for a in d["approvals"] if a["rev_no"] == 1] == ["WAIT", "WAIT"]


def test_t04_t05_approve_then_issue(client, dwg, admin):
    decide(client, dwg, 29)
    res = decide(client, admin, 30, comment="좋음")
    assert res.status_code == 200
    assert 15 in [r["drawing_id"] for r in res.json()["ready"]]
    assert client.get("/api/drawings/15", headers=dwg).json()["dwg_status"] == "APPROVED"
    hist = client.get("/api/approvals/history", headers=dwg).json()
    mine = next(h for h in hist if h["approval_id"] == 30)  # 시드에 기준일 이후 ActDt가 있어 맨 앞이 아닐 수 있다
    assert mine["act_dt"].startswith("2026-10-19 ") and mine["comment"] == "좋음"
    client.post("/api/drawings/15/revisions/1/issue", headers=dwg)
    inbox = client.get("/api/approvals/inbox", headers=dwg).json()
    assert 15 not in [r["drawing_id"] for r in inbox["ready"]]
    assert client.get("/api/drawings/15", headers=dwg).json()["dwg_status"] == "ISSUED"


def test_ready_effect_plans(client, dwg):
    ready = client.get("/api/approvals/inbox", headers=dwg).json()["ready"]
    assert [(r["drawing_no"], r["rev_no"]) for r in ready] == [("8001-ELEC-401", 1), ("8003-HULL-101", 0)]
    assert all(isinstance(r["effect_plans"], list) for r in ready)


def test_t06_history(client, dwg, conn):
    hist = client.get("/api/approvals/history", headers=dwg).json()
    assert len(hist) == 10 and all(h["result"] != "WAIT" for h in hist)
    keys = [(h["act_dt"], h["approval_id"]) for h in hist]
    assert keys == sorted(keys, reverse=True)
    conn.execute("DELETE FROM TB_DWG_Approval WHERE Result <> 'WAIT'")
    assert client.get("/api/approvals/history", headers=dwg).json() == []
