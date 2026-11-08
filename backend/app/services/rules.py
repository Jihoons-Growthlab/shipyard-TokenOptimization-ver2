"""교차 업무 규칙 BR-01~05, 07, 08. 각 규칙은 여기서만 구현한다(BR-06은 services/drawings.py)."""
import math
import re
import sqlite3
from datetime import date, timedelta

from ..config import settings
from ..errors import ApiError, validation

_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MSG = "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."
PLAN_STATUSES = ("PLAN", "READY", "WORK", "DONE", "DELAY")


def parse_date(value: str | None, field: str, message: str = DATE_MSG) -> str | None:
    """빈 값은 None, 형식이 틀리면 400. 저장 형식 문자열을 돌려준다."""
    if value is None or value == "":
        return None
    try:
        if not _DATE.match(value):
            raise ValueError
        date.fromisoformat(value)
    except ValueError:
        raise validation(field, message) from None
    return value


def label(block_cd: str | None, proc_nm: str) -> str:
    """공정 표시 라벨."""
    return f"[{block_cd or '호선'}] {proc_nm}"


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def code_set(conn: sqlite3.Connection, group: str) -> set[str]:
    return {r[0] for r in conn.execute("SELECT Code FROM TB_SYS_Code WHERE CodeGroup = ? AND UseYN = 1", (group,))}


def is_approved_user(conn: sqlite3.Connection, emp_no: str) -> bool:
    return conn.execute("SELECT 1 FROM users WHERE emp_no = ? AND status = 'approved'", (emp_no,)).fetchone() is not None


def weighted_progress(plans) -> int | None:
    """BR-01. plans: PlanStartDt, PlanEndDt, ProgressRate를 가진 행. 공정이 없으면 None."""
    total = weighted = 0.0
    for p in plans:
        days = days_between(p["PlanStartDt"], p["PlanEndDt"]) + 1
        total += days
        weighted += p["ProgressRate"] * days
    return math.floor(weighted / total + 0.5) if total else None


def blockers(conn: sqlite3.Connection, hull_no: str) -> dict[int, list[dict]]:
    """BR-02. 공정별 blocker 도면(도면번호순)."""
    rows = conn.execute(
        "SELECT l.PlanId, d.DrawingId, d.DrawingNo, d.DwgStatus FROM TB_DWG_PlanLink l"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId"
        " JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId"
        " WHERE p.HullNo = ? AND l.RequiredYN = 1 AND d.DwgStatus <> 'OBSOLETE'"
        " AND NOT EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED')"
        " ORDER BY d.DrawingNo",
        (hull_no,),
    )
    result: dict[int, list[dict]] = {}
    for r in rows:
        result.setdefault(r["PlanId"], []).append(
            {"drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "dwg_status": r["DwgStatus"]}
        )
    return result


def plan_status(plan, preds_done: bool, blocked: bool, today: str) -> str:
    """BR-03 단일 공정 판정."""
    if plan["ProgressRate"] >= 100:
        return "DONE"
    late = plan["PlanEndDt"] < today
    if plan["ProgressRate"] > 0 or plan["ActualStartDt"]:
        return "DELAY" if late else "WORK"
    if late:
        return "DELAY"
    return "READY" if preds_done and not blocked else "PLAN"


def recalc(conn: sqlite3.Connection, hull_no: str) -> None:
    """BR-03. 호선의 모든 공정 상태와 호선 자동 전이를 갱신한다."""
    plans = conn.execute(
        "SELECT p.PlanId, p.ProcCd, p.PlanEndDt, p.ProgressRate, p.ActualStartDt, p.PlanStatus"
        " FROM TB_PRC_Plan p WHERE p.HullNo = ?",
        (hull_no,),
    ).fetchall()
    rate = {p["PlanId"]: p["ProgressRate"] for p in plans}
    preds: dict[int, list[int]] = {}
    for d in conn.execute(
        "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId = d.PlanId WHERE p.HullNo = ?",
        (hull_no,),
    ):
        preds.setdefault(d["PlanId"], []).append(d["PredPlanId"])
    blocked = blockers(conn, hull_no)
    statuses = {}
    for p in plans:
        done = all(rate.get(x, 0) >= 100 for x in preds.get(p["PlanId"], []))
        statuses[p["PlanId"]] = status = plan_status(p, done, p["PlanId"] in blocked, settings.today)
        if status != p["PlanStatus"]:
            conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = ? WHERE PlanId = ?", (status, p["PlanId"]))

    hull = conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    current = new = hull["HullStatus"] if hull else None
    if new == "DESIGN" and "WORK" in statuses.values():
        new = "BUILD"
    if new == "BUILD" and any(p["ProcCd"] == "LAUNCH" and statuses[p["PlanId"]] == "DONE" for p in plans):
        new = "LAUNCH"
    if new != current:
        conn.execute("UPDATE TB_MST_Hull SET HullStatus = ? WHERE HullNo = ?", (new, hull_no))


def check_predecessors(conn: sqlite3.Connection, plan: dict, pred_ids: list[int], confirm: bool) -> list[int]:
    """BR-04 검사. plan: plan_id(신규는 None), hull_no, plan_start_dt. 중복 제거한 목록을 돌려준다."""
    pred_ids = list(dict.fromkeys(pred_ids))
    plan_id = plan["plan_id"]
    if plan_id is not None and plan_id in pred_ids:
        raise ApiError(400, "PLAN_DEPENDENCY_SELF", "자기 자신을 선행 공정으로 지정할 수 없습니다.", {"field": "pred_plan_ids"})
    rows = {}
    for pid in pred_ids:
        row = conn.execute("SELECT PlanId, HullNo, PlanEndDt FROM TB_PRC_Plan WHERE PlanId = ?", (pid,)).fetchone()
        if row is None or row["HullNo"] != plan["hull_no"]:
            raise validation("pred_plan_ids", "선행 공정은 같은 호선의 공정이어야 합니다.")
        rows[pid] = row
    if plan_id is not None and pred_ids:
        # 선행의 선행을 따라가 자신에 닿으면 순환이다.
        stack, seen = list(pred_ids), set()
        while stack:
            cur = stack.pop()
            if cur == plan_id:
                raise ApiError(400, "PLAN_DEPENDENCY_CYCLE", "선행 공정이 순환 구조를 만듭니다.", {"field": "pred_plan_ids"})
            if cur in seen:
                continue
            seen.add(cur)
            stack.extend(r[0] for r in conn.execute("SELECT PredPlanId FROM TB_PRC_PlanDep WHERE PlanId = ?", (cur,)))
    late = [pid for pid in pred_ids if rows[pid]["PlanEndDt"] > plan["plan_start_dt"]]
    if late and not confirm:
        raise ApiError(
            409,
            "PRED_LATE_CONFIRM_REQUIRED",
            "선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?",
            {"late_pred_plan_ids": late},
        )
    return pred_ids


def replace_predecessors(conn: sqlite3.Connection, plan_id: int, pred_ids: list[int]) -> None:
    """BR-04 저장: 전체 교체, LagDays=0."""
    conn.execute("DELETE FROM TB_PRC_PlanDep WHERE PlanId = ?", (plan_id,))
    conn.executemany(
        "INSERT INTO TB_PRC_PlanDep (PlanId, PredPlanId, LagDays) VALUES (?, ?, 0)", [(plan_id, p) for p in pred_ids]
    )


def apply_progress(conn: sqlite3.Connection, plan_id: int) -> None:
    """BR-05. 마지막 작업일의 누적률을 공정 진척으로 쓴다(합산하지 않음)."""
    rows = conn.execute(
        "SELECT WorkDt, ProgressRate FROM TB_PRC_Progress WHERE PlanId = ? ORDER BY WorkDt", (plan_id,)
    ).fetchall()
    if rows:
        last = rows[-1]
        values = (last["ProgressRate"], rows[0]["WorkDt"], last["WorkDt"] if last["ProgressRate"] >= 100 else None)
    else:
        values = (0, None, None)
    conn.execute(
        "UPDATE TB_PRC_Plan SET ProgressRate = ?, ActualStartDt = ?, ActualEndDt = ? WHERE PlanId = ?",
        (*values, plan_id),
    )


def remove_files(file_ids) -> None:
    """BR-08: DB 커밋 뒤 호출한다. 이미 없는 파일은 무시한다."""
    for file_id in file_ids:
        if file_id:
            pdf_path(file_id).unlink(missing_ok=True)


def pdf_path(file_id: str):
    return settings.file_dir / f"{file_id}.pdf"


def impacts(conn: sqlite3.Connection, drawing_id: int | None = None) -> list[dict]:
    """BR-07. 도면별 최근 30일 내 배포된 최대 Rev(≥1)의 연계 공정 중 WORK/DONE/DELAY."""
    today = date.fromisoformat(settings.today)
    rows = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.HullNo, r.RevNo, r.IssueDt, r.ChangeDesc,"
        " p.PlanId, p.PlanStatus, b.BlockCd, pr.ProcNm"
        " FROM TB_DWG_Revision r JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId"
        " JOIN TB_DWG_PlanLink l ON l.DrawingId = d.DrawingId"
        " JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd"
        " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
        " WHERE r.RevNo = (SELECT MAX(x.RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = r.DrawingId"
        "   AND x.RevNo >= 1 AND x.RevStatus = 'ISSUED' AND x.IssueDt BETWEEN ? AND ?)"
        " AND p.PlanStatus IN ('WORK', 'DONE', 'DELAY') AND (? IS NULL OR d.DrawingId = ?)"
        " ORDER BY r.IssueDt DESC, d.DrawingNo, p.PlanId",
        ((today - timedelta(days=30)).isoformat(), settings.today, drawing_id, drawing_id),
    )
    return [
        {"drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "rev_no": r["RevNo"], "issue_dt": r["IssueDt"],
         "plan_id": r["PlanId"], "plan_label": label(r["BlockCd"], r["ProcNm"]), "plan_status": r["PlanStatus"],
         "hull_no": r["HullNo"], "change_desc": r["ChangeDesc"], "link": {"screen": "drawing", "param": r["DrawingId"]}}
        for r in rows
    ]
