import pytest

from conftest import session_headers

URL = "/api/dashboard/summary"


@pytest.fixture
def pm(client):
    return session_headers(client, "park.pm")


def get(client, h):
    res = client.get(URL, headers=h)
    assert res.status_code == 200
    return res.json()


def kpis(d):
    return {k: v["value"] for k, v in d["kpi"].items()}


def statuses(d):
    return {s["status"]: s["count"] for s in d["plan_status"]}


def test_seed_values(client, pm):
    d = get(client, pm)
    assert d["today"] == "2026-10-19"
    assert kpis(d) == {"active_hulls": 4, "delay_plans": 1, "waiting_plans": 8, "pending_drawings": 6}
    assert [(h["hull_no"], h["progress"]) for h in d["hull_progress"]] == [
        ("8001", 65), ("8002", 17), ("8003", 0), ("8004", 0), ("8005", 94)]
    assert [s["status"] for s in d["plan_status"]] == ["PLAN", "READY", "WORK", "DONE", "DELAY"]
    assert statuses(d) == {"PLAN": 39, "READY": 0, "WORK": 7, "DONE": 36, "DELAY": 1}
    assert [(x["discipline"], x["name"], x["total"]) for x in d["drawing_disciplines"]] == [
        ("HULL", "선체", 17), ("ELEC", "전장", 15), ("PIPE", "배관", 15)]
    assert d["drawing_disciplines"][0]["counts"] == {"ISSUED": 11, "APPROVED": 1, "REVIEW": 2, "DRAFT": 3}
    delay = d["delay_list"]["items"][0]
    assert (delay["hull_no"], delay["label"], delay["progress_rate"], delay["plan_end_dt"]) == ("8001", "[301] 도장", 60, "2026-10-10")
    w = d["waiting_list"]["items"]
    assert [x["plan_start_dt"] for x in w] == sorted(x["plan_start_dt"] for x in w)
    assert w[0]["blockers"] == ["8002-HULL-401"] and w[0]["link"] == {"screen": "plan-gantt", "param": "8002"}
    assert [(i["drawing_no"], i["rev_no"], i["plan_label"]) for i in d["impact_list"]["items"]] == [
        ("8001-HULL-201", 2, "[201] 강재절단"), ("8001-PIPE-501", 2, "[501] 대조립"), ("8002-PIPE-101", 2, "[101] 대조립")]


def test_t01_progress_done_updates(client, pm):
    before = get(client, pm)
    res = client.put("/api/plans/10/progress/2026-10-19", json={"progress_rate": 100}, headers=pm)
    assert res.status_code == 200
    after = get(client, pm)
    assert statuses(after)["DONE"] == statuses(before)["DONE"] + 1
    assert statuses(after)["WORK"] == statuses(before)["WORK"] - 1
    assert after["hull_progress"][0]["progress"] > before["hull_progress"][0]["progress"]


def test_t02_gate_link_and_issue(client, pm):
    dwg = session_headers(client, "lee.dwg")
    base = get(client, pm)
    assert client.post("/api/drawings/29/plans", json={"plan_id": 51, "required": True}, headers=dwg).status_code == 201
    d = get(client, pm)
    assert kpis(d)["waiting_plans"] == kpis(base)["waiting_plans"] + 1 and d["waiting_list"]["count"] == kpis(d)["waiting_plans"]
    assert client.post("/api/drawings/28/revisions/0/issue", headers=dwg).status_code == 200
    d = get(client, pm)
    assert kpis(d)["waiting_plans"] == kpis(base)["waiting_plans"]
    assert 50 not in [x["plan_id"] for x in d["waiting_list"]["items"]]
    assert kpis(d)["pending_drawings"] == kpis(base)["pending_drawings"] - 1


def test_t03_impact_window_and_status(client, pm, conn):
    items = get(client, pm)["impact_list"]["items"]
    first = items[0]
    conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = 'PLAN' WHERE PlanId = ?", (first["plan_id"],))
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = '2026-09-18' WHERE DrawingId = ? AND RevNo = ?",
                 (items[1]["drawing_id"], items[1]["rev_no"]))
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt = '2026-09-19' WHERE DrawingId = ? AND RevNo = ?",
                 (items[2]["drawing_id"], items[2]["rev_no"]))
    conn.commit()
    left = get(client, pm)["impact_list"]
    assert [i["drawing_id"] for i in left["items"]] == [items[2]["drawing_id"]] and left["count"] == 1
    assert left["items"][0]["link"] == {"screen": "drawing", "param": items[2]["drawing_id"]}


def test_t04_monthly_deliveries(client, pm, conn):
    conn.execute("UPDATE TB_MST_Hull SET DeliveryDt = '2026-12-20' WHERE HullNo = '8004'")
    conn.execute("UPDATE TB_MST_Hull SET UseYN = 0 WHERE HullNo = '8003'")
    conn.commit()
    d = get(client, pm)
    assert d["deliveries"] == [
        {"month": "2026-12", "count": 2, "hull_nos": ["8004", "8005"]},
        {"month": "2027-06", "count": 1, "hull_nos": ["8001"]},
        {"month": "2027-09", "count": 1, "hull_nos": ["8002"]},
    ]
    assert "8003" not in [h["hull_no"] for h in d["hull_progress"]]
    assert all(x["hull_no"] != "8003" for x in d["waiting_list"]["items"])


def test_t05_links(client, pm):
    d = get(client, pm)
    assert {k: v["link"]["screen"] for k, v in d["kpi"].items()} == {
        "active_hulls": "hull-list", "delay_plans": "plan-gantt", "waiting_plans": "plan-gantt", "pending_drawings": "dwg-approval"}
    assert all(h["link"] == {"screen": "plan-gantt", "param": h["hull_no"]} for h in d["hull_progress"])
    assert d["delay_list"]["items"][0]["link"] == {"screen": "plan-gantt", "param": "8001"}


def test_t06_list_cap(client, pm, conn):
    conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = 'DELAY' WHERE PlanId IN (SELECT PlanId FROM TB_PRC_Plan WHERE PlanStatus = 'WORK')")
    conn.commit()
    d = get(client, pm)
    assert d["delay_list"]["count"] == 8 == d["kpi"]["delay_plans"]["value"] and len(d["delay_list"]["items"]) == 6
    assert d["waiting_list"]["count"] == 8 and len(d["waiting_list"]["items"]) == 6


def test_permission(client, conn):
    for name in ("admin", "choi.qa", "lee.dwg"):
        assert client.get(URL, headers=session_headers(client, name)).status_code == 200
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo = 'han.wk'")
    conn.commit()
    assert client.get(URL, headers=session_headers(client, "han.wk")).status_code == 403
