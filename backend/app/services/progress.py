from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from . import hulls, plans, rules
from .system import utc_now

_ACTIVE = ("READY", "WORK", "DELAY")
_TARGET_FIELDS = (
    "plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt", "progress_rate",
    "plan_status", "manager_emp_no", "manager_nm", "drawing_wait",
)


def progress_hulls(conn) -> dict:
    rows = conn.execute(
        "SELECT HullNo, HullNm, HullStatus FROM TB_MST_Hull h"
        " WHERE EXISTS (SELECT 1 FROM TB_PRC_Plan p WHERE p.HullNo = h.HullNo) ORDER BY HullNo"
    ).fetchall()
    items = [{"hull_no": r[0], "hull_nm": r[1], "hull_status": r[2]} for r in rows]
    default = next((h["hull_no"] for h in items if h["hull_status"] == "BUILD"), items[0]["hull_no"] if items else None)
    return {"hulls": items, "default_hull_no": default}


def targets(conn, hull_no: str, include_done: bool) -> dict:
    hulls.ensure(conn, hull_no)
    rows = plans.query(conn, hull_no)
    if not include_done:
        rows = [p for p in rows if p["plan_status"] in _ACTIVE]
    return {"hull_no": hull_no, "today": settings.today, "plans": [{f: p[f] for f in _TARGET_FIELDS} for p in rows]}


def detail(conn, plan_id: int) -> dict:
    plan = plans.get_plan(conn, plan_id)
    history = conn.execute(
        "SELECT g.*, u.display_name FROM TB_PRC_Progress g LEFT JOIN users u ON u.emp_no = g.WorkerEmpNo"
        " WHERE g.PlanId = ? ORDER BY g.WorkDt DESC",
        (plan_id,),
    )
    return {
        "plan": plan,
        "history": [
            {"progress_id": r["ProgressId"], "plan_id": r["PlanId"], "work_dt": r["WorkDt"],
             "progress_rate": r["ProgressRate"], "man_hour": r["ManHour"], "worker_cnt": r["WorkerCnt"],
             "worker_emp_no": r["WorkerEmpNo"], "worker_nm": r["display_name"], "remark": r["Remark"],
             "create_dt": r["CreateDt"]}
            for r in history
        ],
    }


def _apply(conn, plan_id: int, hull_no: str) -> None:
    rules.apply_progress(conn, plan_id)
    rules.recalc(conn, hull_no)


def save(conn, plan_id: int, work_dt: str, data: dict) -> dict:
    """BR-05: 같은 공정·작업일은 수정한다."""
    plan = plans.get_plan(conn, plan_id)
    rules.parse_date(work_dt, "work_dt", "작업일을 입력하세요.")
    if work_dt > settings.today:
        raise validation("work_dt", "미래 일자의 실적은 입력할 수 없습니다.")
    rate = data.get("progress_rate")
    if rate is None or not 0 <= rate <= 100:
        raise validation("progress_rate", "진척률은 0~100 사이로 입력하세요.")
    worker = data.get("worker_emp_no") or None
    if worker and not rules.is_approved_user(conn, worker):
        raise validation("worker_emp_no", "승인된 회원만 작업자로 지정할 수 있습니다.")
    with tx(conn):
        conn.execute(
            "INSERT INTO TB_PRC_Progress (PlanId, WorkDt, ProgressRate, ManHour, WorkerCnt, WorkerEmpNo, Remark, CreateDt)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (PlanId, WorkDt) DO UPDATE SET"
            " ProgressRate = excluded.ProgressRate, ManHour = excluded.ManHour, WorkerCnt = excluded.WorkerCnt,"
            " WorkerEmpNo = excluded.WorkerEmpNo, Remark = excluded.Remark",
            (plan_id, work_dt, rate, data.get("man_hour"), data.get("worker_cnt"), worker,
             (data.get("remark") or "").strip() or None, utc_now()),
        )
        _apply(conn, plan_id, plan["hull_no"])
    return detail(conn, plan_id)


def delete(conn, progress_id: int) -> dict:
    with tx(conn):
        row = conn.execute(
            "SELECT g.PlanId, p.HullNo FROM TB_PRC_Progress g JOIN TB_PRC_Plan p ON p.PlanId = g.PlanId"
            " WHERE g.ProgressId = ?",
            (progress_id,),
        ).fetchone()
        if row is None:
            raise ApiError(404, "PROGRESS_NOT_FOUND", "실적을 찾을 수 없습니다.")
        conn.execute("DELETE FROM TB_PRC_Progress WHERE ProgressId = ?", (progress_id,))
        _apply(conn, row["PlanId"], row["HullNo"])
    return detail(conn, row["PlanId"])
