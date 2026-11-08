import pytest

from conftest import session_headers


@pytest.fixture
def pm(client):
    return session_headers(client, "park.pm")


def save(client, h, plan_id, work_dt, **body):
    return client.put(f"/api/plans/{plan_id}/progress/{work_dt}", json=body, headers=h)


def test_t01_default_targets_and_include_done(client, pm):
    hulls = client.get("/api/progress-hulls", headers=pm).json()
    assert hulls["default_hull_no"] == "8001" and "8004" not in [h["hull_no"] for h in hulls["hulls"]]
    body = client.get("/api/hulls/8002/progress-targets", headers=pm).json()
    assert body["today"] == "2026-10-19"
    assert {p["plan_status"] for p in body["plans"]} <= {"READY", "WORK", "DELAY"}
    assert [p["plan_id"] for p in body["plans"]] == [30, 34, 38]
    full = client.get("/api/hulls/8002/progress-targets?include_done=true", headers=pm).json()["plans"]
    assert len(full) == 22 and set(full[0]) == {
        "plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt", "progress_rate",
        "plan_status", "manager_emp_no", "manager_nm", "drawing_wait"}


def test_t02_same_day_updates_single_row(client, pm):
    save(client, pm, 39, "2026-10-18", progress_rate=10, man_hour=8, worker_cnt=2, worker_emp_no="han.wk")
    body = save(client, pm, 39, "2026-10-18", progress_rate=20, man_hour=4).json()
    assert len(body["history"]) == 1 and body["history"][0]["progress_rate"] == 20
    assert body["history"][0]["worker_emp_no"] is None and body["plan"]["progress_rate"] == 20


def test_t03_last_day_rate_is_used(client, pm):
    save(client, pm, 39, "2026-10-17", progress_rate=40)
    body = save(client, pm, 39, "2026-10-15", progress_rate=60).json()
    assert [h["work_dt"] for h in body["history"]] == ["2026-10-17", "2026-10-15"]
    p = body["plan"]
    assert (p["progress_rate"], p["actual_start_dt"], p["actual_end_dt"], p["plan_status"]) == (40, "2026-10-15", None, "WORK")


def test_t04_rejects_bad_input(client, pm):
    cases = [
        ("2026-10-20", {"progress_rate": 10}, "미래 일자의 실적은 입력할 수 없습니다."),
        ("bad-date", {"progress_rate": 10}, "작업일을 입력하세요."),
        ("2026-10-18", {"progress_rate": 101}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-18", {"progress_rate": -1}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-18", {}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-18", {"progress_rate": 5, "worker_emp_no": "jung.new"}, "승인된 회원만 작업자로 지정할 수 있습니다."),
    ]
    for work_dt, body, message in cases:
        res = save(client, pm, 39, work_dt, **body)
        assert (res.status_code, res.json()["message"]) == (400, message), body
    # 음수 공수와 역행 누적률은 허용한다.
    assert save(client, pm, 30, "2026-10-19", progress_rate=10, man_hour=-3).status_code == 200
    assert client.get("/api/plans/99999/progress", headers=pm).json()["code"] == "PLAN_NOT_FOUND"


def test_t05_done_and_revert_on_delete(client, pm):
    body = save(client, pm, 38, "2026-10-19", progress_rate=100).json()
    p = body["plan"]
    assert (p["plan_status"], p["actual_end_dt"], p["progress_rate"]) == ("DONE", "2026-10-19", 100)
    new_row = next(h for h in body["history"] if h["work_dt"] == "2026-10-19")
    body = client.delete(f"/api/progress/{new_row['progress_id']}", headers=pm).json()
    assert body["plan"]["plan_status"] == "WORK" and body["plan"]["actual_end_dt"] is None and body["plan"]["progress_rate"] == 62  # 같은 날 65 행을 덮어썼다
    for h in body["history"]:
        body = client.delete(f"/api/progress/{h['progress_id']}", headers=pm).json()
    p = body["plan"]
    assert (p["progress_rate"], p["actual_start_dt"], p["actual_end_dt"], p["plan_status"]) == (0, None, None, "READY")
    assert client.delete(f"/api/progress/{new_row['progress_id']}", headers=pm).json()["code"] == "PROGRESS_NOT_FOUND"


def test_t06_view_cannot_write(client):
    qa = session_headers(client, "choi.qa")
    assert client.get("/api/plans/30/progress", headers=qa).status_code == 200
    res = save(client, qa, 30, "2026-10-19", progress_rate=10)
    assert res.status_code == 403 and res.json()["details"]["menu_id"] == "M22"
    assert client.delete("/api/progress/1", headers=qa).status_code == 403
    dwg = session_headers(client, "lee.dwg")
    assert client.get("/api/progress-hulls", headers=dwg).status_code == 403
