import pytest

from app.config import settings
from conftest import session_headers


@pytest.fixture
def dwg(client):
    return session_headers(client, "lee.dwg")


@pytest.fixture
def admin(client):
    return session_headers(client, "admin")


@pytest.fixture(autouse=True)
def files(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "file_dir", tmp_path / "files")
    return tmp_path / "files"


PDF = b"%PDF-1.4\n%test\n"


def create(client, h, **kw):
    body = {"drawing_no": "T-001", "drawing_nm": "시험 도면", "hull_no": "8001", "discipline": "HULL", **kw}
    return client.post("/api/drawings", json=body, headers=h)


def upload(client, h, drawing_id, rev, data=PDF, name="a.pdf", ctype="application/pdf"):
    return client.post(f"/api/drawings/{drawing_id}/revisions/{rev}/pdf", params={"filename": name}, content=data,
                       headers={**h, "Content-Type": ctype})


def test_t01_list_filters_and_rev(client, dwg):
    rows = client.get("/api/drawings", headers=dwg).json()
    assert len(rows) == 47 and [r["drawing_id"] for r in rows] == sorted(r["drawing_id"] for r in rows)
    r12 = next(r for r in rows if r["drawing_no"] == "8001-ELEC-401")
    assert (r12["current_rev_no"], r12["latest_rev_no"], r12["dwg_status"]) == (0, 1, "APPROVED")
    assert r12["designer_nm"] == "이도면" and r12["block_cd"] == "401" and r12["link_count"] == 1
    assert {r["hull_no"] for r in client.get("/api/drawings", params={"hull_no": "8002"}, headers=dwg).json()} == {"8002"}
    assert {r["discipline"] for r in client.get("/api/drawings", params={"discipline": "PIPE"}, headers=dwg).json()} == {"PIPE"}
    assert {r["dwg_status"] for r in client.get("/api/drawings", params={"status": "REVIEW"}, headers=dwg).json()} == {"REVIEW"}
    q = client.get("/api/drawings", params={"q": "엔진룸 블록 배관"}, headers=dwg).json()
    assert q and all("엔진룸 블록 배관" in r["drawing_nm"] for r in q)
    assert [r["drawing_no"] for r in client.get("/api/drawings", params={"q": "8001-hull-1"}, headers=dwg).json()] == ["8001-HULL-101"]


def test_t02_required_duplicate_rev0(client, dwg):
    for field, msg in (("drawing_no", "도면번호를 입력하세요."), ("hull_no", "호선을 선택하세요."), ("drawing_nm", "도면명을 입력하세요.")):
        res = create(client, dwg, **{field: ""})
        assert res.status_code == 400 and res.json()["message"] == msg
    assert create(client, dwg, discipline="XX").json()["message"] == "허용되지 않는 분야입니다."
    assert create(client, dwg, designer_emp_no="jung.new").json()["message"] == "승인된 회원만 지정할 수 있습니다."
    res = create(client, dwg, designer_emp_no="lee.dwg", block_id=1)
    assert res.status_code == 201
    d = res.json()
    assert (d["dwg_status"], d["current_rev_no"], d["latest_rev_no"]) == ("DRAFT", 0, 0)
    assert d["revisions"] == [{**d["revisions"][0], "rev_no": 0, "rev_status": "DRAFT", "change_desc": "최초 작성", "has_file": False}]
    dup = create(client, dwg)
    assert dup.status_code == 409 and dup.json()["message"] == "이미 존재하는 도면번호입니다."


def test_t03_block_hull_and_immutables(client, dwg):
    other = client.get("/api/hulls/8002/blocks", headers=dwg).json()[0]["block_id"]
    assert create(client, dwg, block_id=other).json()["message"] == "해당 호선의 블록이 아닙니다."
    assert client.patch("/api/drawings/1", json={"block_id": other}, headers=dwg).json()["message"] == "해당 호선의 블록이 아닙니다."
    assert client.patch("/api/drawings/1", json={"hull_no": "8002"}, headers=dwg).json()["message"] == "호선은 변경할 수 없습니다."
    assert client.patch("/api/drawings/1", json={"drawing_no": "X"}, headers=dwg).json()["message"] == "도면번호는 변경할 수 없습니다."
    res = client.patch("/api/drawings/1", json={"hull_no": "8001", "drawing_no": "8001-HULL-101", "drawing_nm": "새 이름", "block_id": None}, headers=dwg)
    assert res.status_code == 200 and res.json()["drawing_nm"] == "새 이름" and res.json()["block_id"] is None
    assert res.json()["modify_user_id"] == "lee.dwg"


def test_t04_pdf_rules(client, dwg, files):
    d = create(client, dwg).json()
    did = d["drawing_id"]
    bad = upload(client, dwg, did, 0, data=b"hello world")
    assert bad.status_code == 400 and bad.json()["code"] == "INVALID_FILE_TYPE"
    assert upload(client, dwg, did, 0, name="a.txt", ctype="text/plain").json()["code"] == "INVALID_FILE_TYPE"
    big = upload(client, dwg, did, 0, data=PDF + b"0" * (30 * 1024 * 1024))
    assert big.status_code == 413 and big.json()["message"] == "파일 크기는 30MB 이하여야 합니다."
    assert not any(files.iterdir())  # 실패한 업로드는 파일을 남기지 않는다
    ok = upload(client, dwg, did, 0, name="C:\\dir\\..\\도면.pdf", ctype="application/octet-stream")
    assert ok.status_code == 200 and ok.json()["has_file"] and ok.json()["file_nm"] == "도면.pdf"
    stored = list(files.iterdir())
    assert len(stored) == 1 and len(stored[0].stem) == 32 and stored[0].suffix == ".pdf"
    pdf = client.get(f"/api/drawings/{did}/revisions/0/pdf", headers=dwg)
    assert pdf.content == PDF and pdf.headers["x-content-type-options"] == "nosniff"
    assert pdf.headers["content-disposition"].startswith("inline") and pdf.headers["content-type"] == "application/pdf"
    assert upload(client, dwg, did, 0).status_code == 200  # 교체 시 이전 파일 제거
    assert len(list(files.iterdir())) == 1
    # 비 DRAFT
    issued = upload(client, dwg, 1, 0)
    assert issued.status_code == 409 and issued.json()["message"] == "작성중(DRAFT) 리비전만 업로드할 수 있습니다."
    assert client.delete("/api/drawings/1/revisions/0/pdf", headers=dwg).json()["message"] == "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다."
    assert client.delete(f"/api/drawings/{did}/revisions/0/pdf", headers=dwg).status_code == 204
    assert not any(files.iterdir())
    assert client.get(f"/api/drawings/{did}/revisions/0/pdf", headers=dwg).json()["code"] == "NO_FILE"


def test_t05_seed_has_no_file(client, dwg, conn, files):
    rev = client.get("/api/drawings/1/revisions", headers=dwg).json()[0]
    assert rev["has_file"] is False and rev["file_nm"] == "8001-HULL-101_R0.dwg"
    assert client.get("/api/drawings/1/revisions/0/pdf", headers=dwg).json()["code"] == "NO_FILE"
    conn.execute("UPDATE TB_DWG_Revision SET FileId = 'gone' WHERE DrawingId = 1 AND RevNo = 0")
    assert client.get("/api/drawings/1/revisions/0/pdf", headers=dwg).json()["code"] == "FILE_NOT_FOUND"


def test_t06_revision_approval_issue(client, dwg, admin):
    url = "/api/drawings/1/revisions"
    assert client.post(url, json={"change_desc": " "}, headers=dwg).json()["message"] == "개정 사유를 입력하세요."
    d = client.post(url, json={"change_desc": "치수 수정"}, headers=dwg)
    assert d.status_code == 201 and d.json()["dwg_status"] == "DRAFT" and d.json()["revisions"][0]["rev_no"] == 1
    assert d.json()["revisions"][1]["rev_status"] == "ISSUED"  # 기존 ISSUED 유지
    again = client.post(url, json={"change_desc": "x"}, headers=dwg)
    assert again.status_code == 409 and again.json()["code"] == "INVALID_REV_STATE"
    assert client.post(f"{url}/1/issue", headers=dwg).json()["message"] == "승인(APPROVED)된 리비전만 배포할 수 있습니다."
    req = f"{url}/1/request-approval"
    assert client.post(req, json={"reviewer_emp_no": "lee.dwg"}, headers=dwg).json()["message"] == "검토자와 승인자를 선택하세요."
    assert client.post(req, json={"reviewer_emp_no": "admin", "approver_emp_no": "admin"}, headers=dwg).json()["message"] == "검토자와 승인자는 서로 다른 사람이어야 합니다."
    assert client.post(f"{url}/0/request-approval", json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=dwg).json()["code"] == "INVALID_REV_STATE"
    d = client.post(req, json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=dwg).json()
    assert d["dwg_status"] == "REVIEW" and [(a["step_no"], a["result"]) for a in d["approvals"][:2]] == [(1, "WAIT"), (2, "WAIT")]
    ids = [a["approval_id"] for a in d["approvals"][:2]]
    assert client.post(f"/api/approvals/{ids[0]}/decision", json={"result": "APPROVE"}, headers=dwg).status_code == 200
    assert client.post(f"/api/approvals/{ids[1]}/decision", json={"result": "APPROVE", "comment": ""}, headers=admin).status_code == 200
    d = client.get("/api/drawings/1", headers=dwg).json()
    assert d["dwg_status"] == "APPROVED" and d["approvals"][1]["comment"] == "승인"
    d = client.post(f"{url}/1/issue", headers=dwg).json()
    assert (d["dwg_status"], d["current_rev_no"]) == ("ISSUED", 1)
    assert [(r["rev_no"], r["rev_status"]) for r in d["revisions"]] == [(1, "ISSUED"), (0, "OBSOLETE")]
    assert d["revisions"][0]["issue_dt"] == settings.today


def test_issue_requires_all_approvals(client, dwg, conn):
    conn.execute("UPDATE TB_DWG_Approval SET Result = 'WAIT' WHERE DrawingId = 12 AND RevNo = 1 AND StepNo = 2")
    res = client.post("/api/drawings/12/revisions/1/issue", headers=dwg)
    assert res.status_code == 409 and res.json()["code"] == "APPROVAL_INCOMPLETE"


def test_t07_issue_opens_gate(client, dwg):
    d = client.get("/api/drawings/28", headers=dwg).json()
    pid = d["plans"][0]["plan_id"]
    before = client.get(f"/api/plans/{pid}", headers=dwg).json()
    assert not before["gate_ok"] and before["plan_status"] == "PLAN"
    d = client.post("/api/drawings/28/revisions/0/issue", headers=dwg).json()
    assert d["current_rev_no"] == 0 and d["dwg_status"] == "ISSUED"
    after = client.get(f"/api/plans/{pid}", headers=dwg).json()
    assert after["gate_ok"] and after["plan_status"] == ("READY" if all(
        client.get(f"/api/plans/{p}", headers=dwg).json()["progress_rate"] >= 100 for p in after["pred_plan_ids"]) else "PLAN")


def test_t08_link_and_impacts(client, dwg, conn):
    d = create(client, dwg).json()
    did = d["drawing_id"]
    assert client.post(f"/api/drawings/{did}/plans", json={}, headers=dwg).json()["message"] == "공정을 선택하세요."
    target = next(p for p in d["available_plans"] if p["plan_status"] in ("PLAN", "READY"))
    d = client.post(f"/api/drawings/{did}/plans", json={"plan_id": target["plan_id"], "required": True}, headers=dwg)
    assert d.status_code == 201 and d.json()["plans"][0]["plan_id"] == target["plan_id"] and d.json()["plans"][0]["required"]
    assert all(p["plan_id"] != target["plan_id"] for p in d.json()["available_plans"])
    assert client.get(f"/api/plans/{target['plan_id']}", headers=dwg).json()["plan_status"] == "PLAN"  # 게이트 막힘
    assert client.post(f"/api/drawings/{did}/plans", json={"plan_id": target["plan_id"]}, headers=dwg).status_code == 409
    assert client.delete(f"/api/drawings/{did}/plans/{target['plan_id']}", headers=dwg).status_code == 204
    assert client.get(f"/api/drawings/{did}/plans", headers=dwg).json() == []
    # 영향: Rev≥1, 30일 내 배포, 연계 공정 WORK/DONE/DELAY
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = ? WHERE DrawingId = 2 AND RevNo = 1", (settings.today,))
    status = conn.execute("SELECT p.PlanStatus FROM TB_DWG_PlanLink l JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId WHERE l.DrawingId = 2").fetchone()[0]
    impacts = client.get("/api/drawings/2", headers=dwg).json()["impacts"]
    assert bool(impacts) == (status in ("WORK", "DONE", "DELAY"))
    conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = 'DONE' WHERE PlanId IN (SELECT PlanId FROM TB_DWG_PlanLink WHERE DrawingId = 2)")
    impacts = client.get("/api/drawings/2", headers=dwg).json()["impacts"]
    assert impacts and impacts[0]["rev_no"] == 1 and impacts[0]["plan_label"].startswith("[")
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = '2026-09-18' WHERE DrawingId = 2 AND RevNo = 1")  # 31일 전
    assert client.get("/api/drawings/2", headers=dwg).json()["impacts"] == []
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = '2026-09-19' WHERE DrawingId = 2 AND RevNo = 1")  # 30일 전
    assert client.get("/api/drawings/2", headers=dwg).json()["impacts"]


def test_t09_delete_no_orphans(client, dwg, conn, files):
    did = create(client, dwg).json()["drawing_id"]
    upload(client, dwg, did, 0)
    client.post(f"/api/drawings/{did}/revisions/0/request-approval", json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=dwg)
    pid = client.get(f"/api/drawings/{did}", headers=dwg).json()["available_plans"][0]["plan_id"]
    client.post(f"/api/drawings/{did}/plans", json={"plan_id": pid}, headers=dwg)
    assert client.delete(f"/api/drawings/{did}", headers=dwg).status_code == 204
    assert not any(files.iterdir())
    for table in ("TB_DWG_Revision", "TB_DWG_Approval", "TB_DWG_PlanLink"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE DrawingId = ?", (did,)).fetchone()[0] == 0
    assert client.get(f"/api/drawings/{did}", headers=dwg).json()["code"] == "DRAWING_NOT_FOUND"


def test_t10_view_only_forbidden(client, dwg):
    did = create(client, dwg).json()["drawing_id"]
    for emp in ("choi.qa", "park.pm"):
        h = session_headers(client, emp)
        assert client.get("/api/drawings/1", headers=h).status_code == 200
        assert upload(client, h, did, 0).status_code == 403
        assert client.post("/api/drawings/12/revisions/1/issue", headers=h).status_code == 403
        assert client.delete(f"/api/drawings/{did}", headers=h).status_code == 403
        assert create(client, h, drawing_no="Z").status_code == 403
