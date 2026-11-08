import sqlite3

from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from . import hulls, rules

_RANGE_MSG = "계획 시작/종료일을 입력하세요."
_SELECT = (
    "SELECT p.*, b.BlockCd, b.BlockNm, pr.ProcNm, pr.Seq, u.display_name AS ManagerNm FROM TB_PRC_Plan p"
    " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
    " JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd"
    " LEFT JOIN users u ON u.emp_no = p.ManagerEmpNo"
)


def plan_not_found() -> ApiError:
    return ApiError(404, "PLAN_NOT_FOUND", "공정을 찾을 수 없습니다.")


def sort_key(p: dict):
    """F05 정렬: 블록코드 숫자순(비숫자 뒤), 블록 없는 공정 맨 뒤, 표준공정 Seq, PlanId."""
    cd = p["block_cd"]
    numeric = cd is not None and cd.isdigit()
    return (cd is None, not numeric, int(cd) if numeric else 0, cd or "", p["_seq"], p["plan_id"])


def _out(r, preds: list[int], blocked: list[dict]) -> dict:
    return {
        "plan_id": r["PlanId"], "hull_no": r["HullNo"], "block_id": r["BlockId"], "block_cd": r["BlockCd"],
        "block_nm": r["BlockNm"], "proc_cd": r["ProcCd"], "proc_nm": r["ProcNm"], "label": rules.label(r["BlockCd"], r["ProcNm"]),
        "plan_start_dt": r["PlanStartDt"], "plan_end_dt": r["PlanEndDt"], "actual_start_dt": r["ActualStartDt"],
        "actual_end_dt": r["ActualEndDt"], "progress_rate": r["ProgressRate"], "plan_status": r["PlanStatus"],
        "manager_emp_no": r["ManagerEmpNo"], "manager_nm": r["ManagerNm"], "remark": r["Remark"],
        "create_user_id": r["CreateUserId"], "create_dt": r["CreateDt"], "pred_plan_ids": preds,
        "gate_ok": not blocked, "blockers": blocked, "drawing_wait": r["PlanStatus"] == "PLAN" and bool(blocked),
        "_seq": r["Seq"],
    }


def _deps(conn, hull_no: str) -> list[dict]:
    return [
        {"plan_id": d[0], "pred_plan_id": d[1]}
        for d in conn.execute(
            "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId = d.PlanId"
            " WHERE p.HullNo = ? ORDER BY d.PlanId, d.PredPlanId",
            (hull_no,),
        )
    ]


def query(conn, hull_no: str, where: str = "", params: tuple = ()) -> list[dict]:
    """호선의 공정 응답 목록(F05 정렬). where는 추가 조건."""
    preds: dict[int, list[int]] = {}
    for d in _deps(conn, hull_no):
        preds.setdefault(d["plan_id"], []).append(d["pred_plan_id"])
    blocked = rules.blockers(conn, hull_no)
    rows = conn.execute(f"{_SELECT} WHERE p.HullNo = ? {where}", (hull_no, *params))
    result = sorted((_out(r, preds.get(r["PlanId"], []), blocked.get(r["PlanId"], [])) for r in rows), key=sort_key)
    for p in result:
        del p["_seq"]
    return result


def _row(conn, plan_id: int):
    row = conn.execute("SELECT PlanId, HullNo FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,)).fetchone()
    if row is None:
        raise plan_not_found()
    return row


def get_plan(conn, plan_id: int) -> dict:
    row = _row(conn, plan_id)
    return query(conn, row["HullNo"], "AND p.PlanId = ?", (plan_id,))[0]


def hull_plans(conn, hull_no: str, block_id: int | None) -> dict:
    hulls.ensure(conn, hull_no)
    all_rows = conn.execute(
        "SELECT PlanStartDt, PlanEndDt, ProgressRate FROM TB_PRC_Plan WHERE HullNo = ?", (hull_no,)
    ).fetchall()
    plans = query(conn, hull_no, "AND p.BlockId = ?", (block_id,)) if block_id else query(conn, hull_no)
    return {
        "hull_no": hull_no, "hull_progress": rules.weighted_progress(all_rows), "today": settings.today,
        "plans": plans, "deps": _deps(conn, hull_no),
    }


def procs(conn) -> list[dict]:
    return [
        {"proc_cd": r[0], "proc_nm": r[1], "proc_group": r[2], "std_days": r[3], "seq": r[4]}
        for r in conn.execute("SELECT ProcCd, ProcNm, ProcGroup, StdDays, Seq FROM TB_PRC_Proc WHERE UseYN = 1 ORDER BY Seq")
    ]


def plan_hulls(conn) -> list[dict]:
    return [
        {"hull_no": r[0], "hull_nm": r[1], "plan_count": r[2]}
        for r in conn.execute(
            "SELECT h.HullNo, h.HullNm, COUNT(p.PlanId) FROM TB_MST_Hull h"
            " LEFT JOIN TB_PRC_Plan p ON p.HullNo = h.HullNo GROUP BY h.HullNo ORDER BY h.HullNo"
        )
    ]


def user_options(conn) -> list[dict]:
    return [
        {"emp_no": r[0], "display_name": r[1]}
        for r in conn.execute("SELECT emp_no, display_name FROM users WHERE status = 'approved' ORDER BY display_name, emp_no")
    ]


def _validate(conn, hull_no: str, data: dict) -> dict:
    block_id = data.get("block_id")
    if block_id is not None and not conn.execute(
        "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (block_id, hull_no)
    ).fetchone():
        raise validation("block_id", "해당 호선의 블록이 아닙니다.")
    if not conn.execute("SELECT 1 FROM TB_PRC_Proc WHERE ProcCd = ? AND UseYN = 1", (data.get("proc_cd"),)).fetchone():
        raise validation("proc_cd", "허용되지 않는 공정 코드입니다.")
    for field in ("plan_start_dt", "plan_end_dt"):
        if not data.get(field):
            raise validation(field, _RANGE_MSG)
        rules.parse_date(data[field], field)
    if data["plan_end_dt"] < data["plan_start_dt"]:
        raise validation("plan_end_dt", "계획 종료일이 시작일보다 빠릅니다.")
    manager = data.get("manager_emp_no") or None
    if manager and not rules.is_approved_user(conn, manager):
        raise validation("manager_emp_no", "승인된 회원만 담당자로 지정할 수 있습니다.")
    data["manager_emp_no"] = manager
    data["remark"] = (data.get("remark") or "").strip() or None
    return data


def create_plan(conn, hull_no: str, data: dict, emp_no: str) -> dict:
    hulls.ensure(conn, hull_no)
    data = _validate(conn, hull_no, data)
    with tx(conn):
        preds = rules.check_predecessors(
            conn, {"plan_id": None, "hull_no": hull_no, "plan_start_dt": data["plan_start_dt"]},
            data.get("pred_plan_ids") or [], data.get("confirm_late_preds", False),
        )
        plan_id = conn.execute(
            "INSERT INTO TB_PRC_Plan (HullNo, BlockId, ProcCd, PlanStartDt, PlanEndDt, ProgressRate, PlanStatus,"
            " ManagerEmpNo, Remark, CreateUserId, CreateDt) VALUES (?, ?, ?, ?, ?, 0, 'PLAN', ?, ?, ?, ?)",
            (hull_no, data.get("block_id"), data["proc_cd"], data["plan_start_dt"], data["plan_end_dt"],
             data["manager_emp_no"], data["remark"], emp_no, settings.today),
        ).lastrowid
        rules.replace_predecessors(conn, plan_id, preds)
        rules.recalc(conn, hull_no)
    return get_plan(conn, plan_id)


_FIELDS = ("block_id", "proc_cd", "plan_start_dt", "plan_end_dt", "manager_emp_no", "remark")


def update_plan(conn, plan_id: int, changes: dict) -> dict:
    """보낸 필드만 바꾼다. 진척·실제일은 보존한다."""
    current = get_plan(conn, plan_id)
    hull_no = current["hull_no"]
    data = _validate(conn, hull_no, {**{f: current[f] for f in _FIELDS}, **{k: v for k, v in changes.items() if k in _FIELDS}})
    with tx(conn):
        if "pred_plan_ids" in changes:
            preds = changes["pred_plan_ids"] or []
        else:
            preds = current["pred_plan_ids"]
        preds = rules.check_predecessors(
            conn, {"plan_id": plan_id, "hull_no": hull_no, "plan_start_dt": data["plan_start_dt"]},
            preds, changes.get("confirm_late_preds", False),
        )
        conn.execute(
            "UPDATE TB_PRC_Plan SET BlockId = ?, ProcCd = ?, PlanStartDt = ?, PlanEndDt = ?, ManagerEmpNo = ?, Remark = ?"
            " WHERE PlanId = ?",
            (*(data[f] for f in _FIELDS), plan_id),
        )
        rules.replace_predecessors(conn, plan_id, preds)
        rules.recalc(conn, hull_no)
    return get_plan(conn, plan_id)


def set_predecessors(conn, plan_id: int, pred_ids: list[int], confirm: bool) -> dict:
    current = get_plan(conn, plan_id)
    with tx(conn):
        preds = rules.check_predecessors(conn, current, pred_ids, confirm)
        rules.replace_predecessors(conn, plan_id, preds)
        rules.recalc(conn, current["hull_no"])
    return get_plan(conn, plan_id)


def delete_plan(conn, plan_id: int) -> None:
    """BR-08: 실적·선후행·연계는 CASCADE."""
    with tx(conn):
        row = _row(conn, plan_id)
        conn.execute("DELETE FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,))
        rules.recalc(conn, row["HullNo"])


# ---- 도면 연계

def links(conn, plan_id: int) -> dict:
    row = _row(conn, plan_id)
    linked = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, d.DwgStatus, l.RequiredYN, l.NeedDt,"
        " EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED') AS has_issued"
        " FROM TB_DWG_PlanLink l JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId"
        " WHERE l.PlanId = ? ORDER BY d.DrawingNo",
        (plan_id,),
    ).fetchall()
    available = conn.execute(
        "SELECT DrawingId, DrawingNo, DrawingNm, DwgStatus FROM TB_DWG_Drawing WHERE HullNo = ?"
        " AND DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_PlanLink WHERE PlanId = ?) ORDER BY DrawingNo",
        (row["HullNo"], plan_id),
    )
    return {
        "plan_id": plan_id,
        "blockers": rules.blockers(conn, row["HullNo"]).get(plan_id, []),
        "links": [
            {"drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "dwg_status": r[3],
             "has_issued": bool(r["has_issued"]), "required": bool(r["RequiredYN"]), "need_dt": r["NeedDt"]}
            for r in linked
        ],
        "available": [{"drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "dwg_status": r[3]} for r in available],
    }


def add_link(conn, plan_id: int, drawing_id: int, required: bool) -> dict:
    with tx(conn):
        plan = conn.execute("SELECT HullNo, PlanStartDt FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,)).fetchone()
        if plan is None:
            raise plan_not_found()
        drawing = conn.execute("SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,)).fetchone()
        if drawing is None:
            raise ApiError(404, "DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")
        if drawing["HullNo"] != plan["HullNo"]:
            raise validation("drawing_id", "같은 호선의 도면만 연계할 수 있습니다.")
        if conn.execute("SELECT 1 FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id)).fetchone():
            raise ApiError(409, "DUPLICATE", "이미 연계된 도면입니다.", {"field": "drawing_id"})
        conn.execute(
            "INSERT INTO TB_DWG_PlanLink (DrawingId, PlanId, RequiredYN, NeedDt) VALUES (?, ?, ?, ?)",
            (drawing_id, plan_id, 1 if required else 0, plan["PlanStartDt"]),
        )
        rules.recalc(conn, plan["HullNo"])
    return links(conn, plan_id)


def remove_link(conn, plan_id: int, drawing_id: int) -> None:
    with tx(conn):
        row = _row(conn, plan_id)
        if not conn.execute("DELETE FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id)).rowcount:
            raise ApiError(404, "LINK_NOT_FOUND", "연계 정보를 찾을 수 없습니다.")
        rules.recalc(conn, row["HullNo"])
