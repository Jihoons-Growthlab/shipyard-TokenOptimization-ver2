import pytest

from app.services import rules
from conftest import session_headers


@pytest.fixture
def pm(client):
    return session_headers(client, "park.pm")


def plan(client, h, plan_id):
    return client.get(f"/api/plans/{plan_id}", headers=h).json()


def test_seed_recalc_is_stable(conn):
    before = conn.execute("SELECT PlanId, PlanStatus, ProgressRate, ActualStartDt, ActualEndDt FROM TB_PRC_Plan").fetchall()
    for (hull_no,) in conn.execute("SELECT HullNo FROM TB_MST_Hull").fetchall():
        rules.recalc(conn, hull_no)
    after = conn.execute("SELECT PlanId, PlanStatus, ProgressRate, ActualStartDt, ActualEndDt FROM TB_PRC_Plan").fetchall()
    assert [tuple(r) for r in before] == [tuple(r) for r in after]
    counts = dict(conn.execute("SELECT PlanStatus, COUNT(*) FROM TB_PRC_Plan GROUP BY PlanStatus").fetchall())
    assert counts == {"PLAN": 39, "WORK": 7, "DONE": 36, "DELAY": 1}


def test_weighted_progress_rounds_half_up():
    rows = [{"PlanStartDt": "2026-01-01", "PlanEndDt": "2026-01-01", "ProgressRate": 50},
            {"PlanStartDt": "2026-01-01", "PlanEndDt": "2026-01-01", "ProgressRate": 51}]
    assert rules.weighted_progress(rows) == 51  # 50.5 → 51
    assert rules.weighted_progress([]) is None


def test_t01_list_shape_and_filter(client, pm):
    body = client.get("/api/hulls/8002/plans", headers=pm).json()
    assert body["today"] == "2026-10-19" and body["hull_progress"] == 17
    labels = [p["label"] for p in body["plans"]]
    assert labels[0] == "[101] 강재절단" and labels[-2:] == ["[호선] 진수", "[호선] 시운전"]
    p43 = next(p for p in body["plans"] if p["plan_id"] == 43)
    assert p43["drawing_wait"] and not p43["gate_ok"] and p43["blockers"][0]["drawing_no"] == "8002-HULL-401"
    assert {"plan_id": 29, "pred_plan_id": 28} in body["deps"]
    block = client.get("/api/hulls/8002/plans?block_id=6", headers=pm).json()
    assert {p["block_id"] for p in block["plans"]} == {6} and block["hull_progress"] == 17
    assert client.get("/api/hulls/8004/plans", headers=pm).json()["hull_progress"] is None
    assert [h["plan_count"] for h in client.get("/api/plan-hulls", headers=pm).json()][3] == 0
    assert [p["proc_cd"] for p in client.get("/api/procs", headers=pm).json()][0] == "CUT"
    users = client.get("/api/users/options", headers=pm).json()
    assert "jung.new" not in [u["emp_no"] for u in users] and users == sorted(users, key=lambda u: u["display_name"])


BASE = {"block_id": 6, "proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-10"}


def test_t02_period_and_manager_validation(client, pm):
    cases = [
        ({**BASE, "plan_start_dt": None}, "계획 시작/종료일을 입력하세요."),
        ({**BASE, "plan_end_dt": "2026-10-01"}, "계획 종료일이 시작일보다 빠릅니다."),
        ({**BASE, "block_id": 1}, "해당 호선의 블록이 아닙니다."),
        ({**BASE, "proc_cd": "NOPE"}, "허용되지 않는 공정 코드입니다."),
        ({**BASE, "manager_emp_no": "jung.new"}, "승인된 회원만 담당자로 지정할 수 있습니다."),
    ]
    for body, message in cases:
        res = client.post("/api/hulls/8002/plans", json=body, headers=pm)
        assert (res.status_code, res.json()["message"]) == (400, message)
    res = client.post("/api/hulls/8002/plans", json={**BASE, "manager_emp_no": "han.wk", "remark": "메모"}, headers=pm)
    assert res.status_code == 201
    p = res.json()
    assert (p["plan_status"], p["progress_rate"], p["manager_nm"], p["create_user_id"]) == ("READY", 0, "한현장", "park.pm")
    # 수정은 진척·실제일을 보존한다.
    p30 = client.patch("/api/plans/30", json={"remark": "수정"}, headers=pm).json()
    assert (p30["progress_rate"], p30["actual_start_dt"], p30["remark"], p30["pred_plan_ids"]) == (55, "2026-10-05", "수정", [29])


def test_t03_self_and_cycle(client, pm):
    res = client.put("/api/plans/30/predecessors", json={"pred_plan_ids": [30]}, headers=pm)
    assert (res.status_code, res.json()["code"]) == (400, "PLAN_DEPENDENCY_SELF")
    res = client.put("/api/plans/28/predecessors", json={"pred_plan_ids": [30]}, headers=pm)
    assert (res.status_code, res.json()["code"], res.json()["message"]) == (400, "PLAN_DEPENDENCY_CYCLE", "선행 공정이 순환 구조를 만듭니다.")
    res = client.put("/api/plans/28/predecessors", json={"pred_plan_ids": [1]}, headers=pm)
    assert res.json()["message"] == "선행 공정은 같은 호선의 공정이어야 합니다."
    assert plan(client, pm, 28)["pred_plan_ids"] == []


def test_t04_late_predecessor_confirm(client, pm, conn):
    res = client.put("/api/plans/33/predecessors", json={"pred_plan_ids": [30]}, headers=pm)
    assert res.status_code == 409 and res.json()["code"] == "PRED_LATE_CONFIRM_REQUIRED"
    assert res.json()["details"]["late_pred_plan_ids"] == [30]
    assert plan(client, pm, 33)["pred_plan_ids"] == []
    res = client.put("/api/plans/33/predecessors", json={"pred_plan_ids": [30], "confirm_late_preds": True}, headers=pm)
    assert res.status_code == 200 and res.json()["pred_plan_ids"] == [30]
    assert conn.execute("SELECT LagDays FROM TB_PRC_PlanDep WHERE PlanId = 33").fetchone()[0] == 0
    late = {**BASE, "plan_start_dt": "2026-10-25", "pred_plan_ids": [30]}
    res = client.post("/api/hulls/8002/plans", json=late, headers=pm)
    assert res.status_code == 409
    count = conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan").fetchone()[0]
    assert client.post("/api/hulls/8002/plans", json={**late, "confirm_late_preds": True}, headers=pm).status_code == 201
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan").fetchone()[0] == count + 1


def test_t05_pred_done_and_issued_gives_ready(client, pm):
    assert client.post("/api/plans/39/drawings", json={"drawing_id": 16, "required": True}, headers=pm).status_code == 201
    assert plan(client, pm, 39)["plan_status"] == "PLAN"
    client.put("/api/plans/38/progress/2026-10-19", json={"progress_rate": 100}, headers=pm)
    assert plan(client, pm, 39)["plan_status"] == "READY"


def test_t06_draft_only_stays_plan_until_issue(client, pm, conn):
    p = plan(client, pm, 43)
    assert p["plan_status"] == "PLAN" and p["drawing_wait"]
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'ISSUED' WHERE DrawingId = 25 AND RevNo = (SELECT MAX(RevNo) FROM TB_DWG_Revision WHERE DrawingId = 25)")
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'ISSUED' WHERE DrawingId = 25")
    rules.recalc(conn, "8002")  # 배포 API(단계 7)가 호출할 재계산
    p = plan(client, pm, 43)
    assert p["plan_status"] == "READY" and p["gate_ok"] and not p["drawing_wait"]


def test_t07_delete_plan_no_orphans(client, pm, conn):
    assert client.delete("/api/plans/30", headers=pm).status_code == 204
    for sql in ("SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PlanId = 30 OR PredPlanId = 30",
                "SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId = 30",
                "SELECT COUNT(*) FROM TB_DWG_PlanLink WHERE PlanId = 30"):
        assert conn.execute(sql).fetchone()[0] == 0
    assert client.get("/api/plans/30", headers=pm).json()["code"] == "PLAN_NOT_FOUND"
    assert plan(client, pm, 31)["plan_status"] == "READY"  # 선행이 사라져 재계산


def test_t08_link_and_unlink_recalc(client, pm):
    body = client.get("/api/plans/39/drawings", headers=pm).json()
    assert body["links"] == [] and 25 in [d["drawing_id"] for d in body["available"]]
    res = client.post("/api/plans/39/drawings", json={"drawing_id": 25, "required": True}, headers=pm)
    link = res.json()["links"][0]
    assert (link["need_dt"], link["has_issued"], link["required"]) == ("2026-10-25", False, True)
    assert res.json()["blockers"][0]["drawing_id"] == 25
    assert client.post("/api/plans/39/drawings", json={"drawing_id": 25}, headers=pm).status_code == 409
    assert client.post("/api/plans/39/drawings", json={"drawing_id": 1}, headers=pm).json()["message"] == "같은 호선의 도면만 연계할 수 있습니다."
    assert client.post("/api/plans/39/drawings", json={"drawing_id": 99999}, headers=pm).json()["code"] == "DRAWING_NOT_FOUND"
    client.put("/api/plans/38/progress/2026-10-19", json={"progress_rate": 100}, headers=pm)
    assert plan(client, pm, 39)["drawing_wait"]
    assert client.delete("/api/plans/39/drawings/25", headers=pm).status_code == 204
    assert plan(client, pm, 39)["plan_status"] == "READY"
    assert client.delete("/api/plans/39/drawings/25", headers=pm).json()["code"] == "LINK_NOT_FOUND"


def test_t09_view_cannot_write(client):
    for emp in ("choi.qa", "lee.dwg"):
        h = session_headers(client, emp)
        assert client.get("/api/hulls/8002/plans", headers=h).status_code == 200
        for method, url, body in [
            ("post", "/api/hulls/8002/plans", BASE), ("patch", "/api/plans/30", {"remark": "x"}),
            ("delete", "/api/plans/30", None), ("put", "/api/plans/30/predecessors", {"pred_plan_ids": []}),
            ("post", "/api/plans/30/drawings", {"drawing_id": 16}), ("delete", "/api/plans/30/drawings/17", None),
        ]:
            res = client.request(method, url, json=body, headers=h)
            assert res.status_code == 403 and res.json()["details"]["menu_id"] == "M21", (emp, url)


def test_hull_auto_transition(client, pm, conn):
    conn.execute("UPDATE TB_MST_Hull SET HullStatus = 'DESIGN' WHERE HullNo = '8002'")
    client.put("/api/plans/39/progress/2026-10-19", json={"progress_rate": 10}, headers=pm)
    assert client.get("/api/hulls/8002", headers=pm).json()["hull_status"] == "BUILD"
    client.put("/api/plans/48/progress/2026-10-19", json={"progress_rate": 100}, headers=pm)
    assert client.get("/api/hulls/8002", headers=pm).json()["hull_status"] == "LAUNCH"
    conn.execute("UPDATE TB_MST_Hull SET HullStatus = 'PLAN' WHERE HullNo = '8002'")
    client.put("/api/plans/39/progress/2026-10-19", json={"progress_rate": 20}, headers=pm)
    assert client.get("/api/hulls/8002", headers=pm).json()["hull_status"] == "PLAN"
