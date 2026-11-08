import pytest

from conftest import session_headers

NEW = {"hull_no": "T-900", "hull_nm": "테스트선", "ship_type": "LNG", "contract_dt": "2026-01-10", "delivery_dt": "2028-03-31"}


@pytest.fixture
def pm(client):
    return session_headers(client, "park.pm")


def test_t01_filters_and_search(client, pm):
    rows = client.get("/api/hulls", headers=pm).json()
    assert [h["hull_no"] for h in rows] == ["8001", "8002", "8003", "8004", "8005"]
    assert {h["hull_no"]: h["progress"] for h in rows} == {"8001": 65, "8002": 17, "8003": 0, "8004": None, "8005": 94}
    assert rows[0]["delay_count"] == 1 and rows[3]["plan_count"] == 0
    assert [h["hull_no"] for h in client.get("/api/hulls?status=BUILD", headers=pm).json()] == ["8001", "8002"]
    assert [h["hull_no"] for h in client.get("/api/hulls?ship_type=LNG", headers=pm).json()] == ["8001", "8005"]
    owner = rows[0]["owner_nm"]
    found = client.get("/api/hulls", params={"q": owner.lower()}, headers=pm).json()
    assert "8001" in [h["hull_no"] for h in found]
    assert [h["hull_no"] for h in client.get("/api/hulls?q=8003", headers=pm).json()] == ["8003"]


def test_t02_create_validation(client, pm):
    cases = [
        ({"hull_no": ""}, "호선번호를 입력하세요."),
        ({"hull_no": "가나"}, "호선번호는 영문/숫자/._- 1~20자입니다."),
        ({"hull_no": "8001"}, "이미 존재하는 호선번호입니다."),
        ({**NEW, "delivery_dt": "2025-01-01"}, "인도 예정일이 계약일보다 빠릅니다."),
        ({**NEW, "contract_dt": "2026/01/10"}, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."),
        ({**NEW, "ship_type": "XX"}, "허용되지 않는 코드값입니다."),
        ({**NEW, "length_m": -1}, "0 이상의 값을 입력하세요."),
        ({**NEW, "hull_status": ""}, "상태를 선택하세요."),
    ]
    for body, message in cases:
        res = client.post("/api/hulls", json=body, headers=pm)
        assert res.json()["message"] == message, body
        assert res.status_code == (409 if message.startswith("이미") else 400)
    assert client.get("/api/hulls/NOPE", headers=pm).json()["code"] == "HULL_NOT_FOUND"


def test_t03_create_defaults_and_milestones(client, pm):
    res = client.post("/api/hulls", json=NEW, headers=pm)
    assert res.status_code == 201
    hull = res.json()
    assert (hull["hull_status"], hull["use_yn"], hull["create_user_id"], hull["create_dt"]) == ("PLAN", True, "park.pm", "2026-10-19")
    assert hull["progress"] is None
    ms = client.get("/api/hulls/T-900/milestones", headers=pm).json()
    assert [m["milestone_cd"] for m in ms] == ["CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER"]
    assert [m["plan_dt"] for m in ms] == [None, None, None, None, "2028-03-31"]
    saved = client.put("/api/hulls/T-900/milestones", headers=pm, json={"items": [
        {"milestone_cd": "CUT", "plan_dt": "2026-05-01", "actual_dt": "2026-05-04"},
        {"milestone_cd": "KEEL", "plan_dt": "2026-04-01", "actual_dt": None},
    ]}).json()
    assert saved[0]["diff_days"] == 3 and saved[1]["plan_dt"] == "2026-04-01" and saved[1]["diff_days"] is None
    for items in ([{"milestone_cd": "CUT"}, {"milestone_cd": "CUT"}], [{"milestone_cd": "XX"}]):
        res = client.put("/api/hulls/T-900/milestones", headers=pm, json={"items": items})
        assert res.status_code == 400 and res.json()["message"] == "허용되지 않거나 중복된 일정 코드입니다."


def test_t04_patch_sent_fields_only(client, pm):
    res = client.patch("/api/hulls/8001", json={"hull_nm": "변경선", "dock_no": "D9"}, headers=pm)
    assert res.status_code == 200
    body = res.json()
    assert body["hull_nm"] == "변경선" and body["ship_type"] == "LNG" and body["modify_user_id"] == "park.pm"
    assert next(h for h in client.get("/api/hulls", headers=pm).json() if h["hull_no"] == "8001")["dock_no"] == "D9"
    res = client.patch("/api/hulls/8001", json={"hull_no": "9999"}, headers=pm)
    assert res.json()["message"] == "호선번호는 수정할 수 없습니다."
    res = client.patch("/api/hulls/8001", json={"delivery_dt": "2000-01-01"}, headers=pm)
    assert res.json()["message"] == "인도 예정일이 계약일보다 빠릅니다."


def test_t05_block_code_unique_in_hull(client, pm):
    assert client.post("/api/hulls/8001/blocks", json={"block_nm": "x"}, headers=pm).json()["message"] == "블록코드를 입력하세요."
    res = client.post("/api/hulls/8001/blocks", json={"block_cd": "101"}, headers=pm)
    assert res.status_code == 409 and res.json()["message"] == "이미 존재하는 블록코드입니다."
    res = client.post("/api/hulls/8004/blocks", json={"block_cd": "901", "block_type": "FLAT", "weight_ton": 10}, headers=pm)
    assert res.status_code == 201 and res.json()["progress"] is None and res.json()["plan_count"] == 0
    assert client.post("/api/hulls/8004/blocks", json={"block_cd": "902", "block_type": "X"}, headers=pm).status_code == 400
    assert client.post("/api/hulls/8004/blocks", json={"block_cd": "902", "weight_ton": -1}, headers=pm).status_code == 400
    blocks = client.get("/api/hulls/8001/blocks", headers=pm).json()
    assert [b["block_cd"] for b in blocks] == ["101", "201", "301", "401", "501"]
    assert blocks[0]["drawing_count"] > 0 and blocks[0]["progress"] is not None


def test_t06_block_delete_keeps_drawings(client, pm, conn):
    block = client.get("/api/hulls/8002/blocks", headers=pm).json()[0]
    drawings = [r[0] for r in conn.execute("SELECT DrawingId FROM TB_DWG_Drawing WHERE BlockId = ?", (block["block_id"],))]
    assert drawings and block["plan_count"] == 5
    assert client.delete(f"/api/blocks/{block['block_id']}", headers=pm).status_code == 204
    left = conn.execute(f"SELECT BlockId FROM TB_DWG_Drawing WHERE DrawingId IN ({','.join('?' * len(drawings))})", drawings).fetchall()
    assert len(left) == len(drawings) and all(r[0] is None for r in left)
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE BlockId = ?", (block["block_id"],)).fetchone()[0] == 0
    assert client.delete(f"/api/blocks/{block['block_id']}", headers=pm).json()["code"] == "BLOCK_NOT_FOUND"


def test_t07_hull_delete_leaves_no_orphans(client, pm, conn, tmp_path, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "file_dir", tmp_path)
    conn.execute("UPDATE TB_DWG_Revision SET FileId = 'f1' WHERE DrawingId = 16 AND RevNo = 0")
    (tmp_path / "f1.pdf").write_bytes(b"%PDF")
    assert client.delete("/api/hulls/8002", headers=pm).status_code == 204
    assert not (tmp_path / "f1.pdf").exists()
    orphans = {
        "block": "SELECT COUNT(*) FROM TB_MST_Block WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "milestone": "SELECT COUNT(*) FROM TB_MST_HullMilestone WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "plan": "SELECT COUNT(*) FROM TB_PRC_Plan WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "dep": "SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
        "progress": "SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
        "drawing": "SELECT COUNT(*) FROM TB_DWG_Drawing WHERE HullNo NOT IN (SELECT HullNo FROM TB_MST_Hull)",
        "revision": "SELECT COUNT(*) FROM TB_DWG_Revision WHERE DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_Drawing)",
        "approval": "SELECT COUNT(*) FROM TB_DWG_Approval WHERE DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_Drawing)",
        "link": "SELECT COUNT(*) FROM TB_DWG_PlanLink WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)",
    }
    assert {k: conn.execute(sql).fetchone()[0] for k, sql in orphans.items()} == dict.fromkeys(orphans, 0)
    assert client.get("/api/hulls/8002", headers=pm).status_code == 404


def test_t08_view_cannot_write(client):
    qa = session_headers(client, "choi.qa")
    assert client.get("/api/hulls", headers=qa).status_code == 200
    for method, url, body in [
        ("post", "/api/hulls", NEW), ("patch", "/api/hulls/8001", {"hull_nm": "x"}), ("delete", "/api/hulls/8001", None),
        ("put", "/api/hulls/8001/milestones", {"items": []}), ("post", "/api/hulls/8001/blocks", {"block_cd": "9"}),
        ("delete", "/api/blocks/1", None),
    ]:
        res = client.request(method, url, json=body, headers=qa)
        assert res.status_code == 403 and res.json()["details"]["menu_id"] == "M11", url


def test_summary(client, pm):
    s = client.get("/api/hulls/8002/summary", headers=pm).json()
    assert s["plan_count"] == 22 and s["progress"] == 17
    assert sum(s["plan_status"].values()) == 22 and set(s["plan_status"]) == {"PLAN", "READY", "WORK", "DONE", "DELAY"}
    assert s["drawing_count"] == 12 and s["drawing_status"] == {"ISSUED": 8, "APPROVED": 0, "REVIEW": 2, "DRAFT": 2}
