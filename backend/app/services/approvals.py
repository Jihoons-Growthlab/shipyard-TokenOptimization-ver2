"""F08 결재함. 상태 전이는 BR-06(drawings), 재계산은 BR-03(rules)."""
from datetime import datetime

from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from . import drawings, rules, system

# 대기 조건: WAIT, Rev가 REVIEW이자 최신, 앞 단계가 모두 APPROVE.
_CURRENT = (
    "a.Result = 'WAIT' AND r.RevStatus = 'REVIEW'"
    " AND r.RevNo = (SELECT MAX(RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = a.DrawingId)"
    " AND NOT EXISTS (SELECT 1 FROM TB_DWG_Approval p WHERE p.DrawingId = a.DrawingId AND p.RevNo = a.RevNo"
    "   AND p.StepNo < a.StepNo AND p.Result <> 'APPROVE')"
)
_JOIN = (
    " FROM TB_DWG_Approval a JOIN TB_DWG_Revision r ON r.DrawingId = a.DrawingId AND r.RevNo = a.RevNo"
    " JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId"
)


def waiting(conn, emp_no: str) -> list[dict]:
    rows = conn.execute(
        f"SELECT a.ApprovalId, a.DrawingId, d.DrawingNo, d.DrawingNm, a.RevNo, a.StepNo, r.ChangeDesc{_JOIN}"
        f" WHERE a.ApproverEmpNo = ? AND {_CURRENT} ORDER BY a.ApprovalId",
        (emp_no,),
    )
    return [
        {"approval_id": r[0], "drawing_id": r[1], "drawing_no": r[2], "drawing_nm": r[3], "rev_no": r[4], "step_no": r[5],
         "change_desc": r[6]}
        for r in rows
    ]


def ready(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, r.RevNo FROM TB_DWG_Drawing d"
        " JOIN TB_DWG_Revision r ON r.DrawingId = d.DrawingId"
        " WHERE r.RevNo = (SELECT MAX(RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = d.DrawingId)"
        " AND r.RevStatus = 'APPROVED' ORDER BY d.DrawingId"
    ).fetchall()
    result = []
    for r in rows:
        effect = conn.execute(
            "SELECT b.BlockCd, pr.ProcNm FROM TB_DWG_PlanLink l JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId"
            " JOIN TB_PRC_Proc pr ON pr.ProcCd = p.ProcCd LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
            " WHERE l.DrawingId = ? AND p.PlanStatus = 'PLAN' ORDER BY p.PlanId",
            (r[0],),
        )
        result.append({"drawing_id": r[0], "drawing_no": r[1], "drawing_nm": r[2], "rev_no": r[3],
                       "effect_plans": [rules.label(e[0], e[1]) for e in effect]})
    return result


def inbox(conn, emp_no: str) -> dict:
    return {"waiting": waiting(conn, emp_no), "ready": ready(conn),
            "can_issue": system.menu_level(conn, emp_no, "M31") >= 2}


def history(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT a.*, d.DrawingNo, u.display_name AS ApproverNm FROM TB_DWG_Approval a"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo"
        " WHERE a.Result <> 'WAIT' ORDER BY a.ActDt DESC, a.ApprovalId DESC LIMIT 10"
    )
    return [
        {"approval_id": r["ApprovalId"], "act_dt": r["ActDt"], "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"],
         "rev_no": r["RevNo"], "step_no": r["StepNo"], "approver_emp_no": r["ApproverEmpNo"],
         "approver_nm": r["ApproverNm"], "result": r["Result"], "comment": r["Comment"]}
        for r in rows
    ]


def decide(conn, approval_id: int, result: str | None, comment: str | None, emp_no: str) -> dict:
    """F08 처리 순서대로 검사한 뒤 BR-06 전이와 BR-03 재계산."""
    if result not in ("APPROVE", "REJECT"):
        raise validation("result", "결재 결과는 APPROVE 또는 REJECT 이어야 합니다.")
    comment = (comment or "").strip()
    if result == "REJECT" and not comment:
        raise validation("comment", "반려 시 의견을 입력하세요.")
    with tx(conn):
        row = conn.execute(f"SELECT a.*, d.HullNo{_JOIN} WHERE a.ApprovalId = ?", (approval_id,)).fetchone()
        if row is None:
            raise ApiError(404, "APPROVAL_NOT_FOUND", "결재 건을 찾을 수 없습니다.")
        if row["ApproverEmpNo"] != emp_no:
            raise ApiError(403, "NOT_ASSIGNED_APPROVER", "본인에게 지정된 결재 건이 아닙니다.")
        if row["Result"] != "WAIT":
            raise ApiError(409, "ALREADY_DECIDED", "이미 처리된 결재 건입니다.")
        if not conn.execute(f"SELECT 1{_JOIN} WHERE a.ApprovalId = ? AND {_CURRENT}", (approval_id,)).fetchone():
            raise ApiError(409, "NOT_CURRENT_STEP", "결재 순서가 아니거나 최신 검토중 리비전이 아닙니다.")
        drawing_id, rev_no = row["DrawingId"], row["RevNo"]
        conn.execute(
            "UPDATE TB_DWG_Approval SET Result = ?, Comment = ?, ActDt = ? WHERE ApprovalId = ?",
            (result, comment or "승인", f"{settings.today} {datetime.now():%H:%M}", approval_id),
        )
        if result == "REJECT":
            conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result = 'WAIT'", (drawing_id, rev_no))
            drawings.set_status(conn, drawing_id, rev_no, "DRAFT")
        elif not conn.execute(
            "SELECT 1 FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result <> 'APPROVE'", (drawing_id, rev_no)
        ).fetchone():
            drawings.set_status(conn, drawing_id, rev_no, "APPROVED")
        rules.recalc(conn, row["HullNo"])
    return {"approval_id": approval_id, "result": result, **{k: v for k, v in inbox(conn, emp_no).items() if k != "can_issue"}}
