"""F07 도면과 BR-06 리비전 상태 전이."""
import secrets
import sqlite3

from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from . import plans, rules

MAX_PDF = 30 * 1024 * 1024
_EDITABLE = ("drawing_nm", "discipline", "block_id", "designer_emp_no")
_SELECT = (
    "SELECT d.*, b.BlockCd, b.BlockNm, u.display_name AS DesignerNm,"
    " (SELECT MAX(RevNo) FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId) AS LatestRevNo,"
    " (SELECT COUNT(*) FROM TB_DWG_PlanLink l WHERE l.DrawingId = d.DrawingId) AS LinkCount"
    " FROM TB_DWG_Drawing d LEFT JOIN TB_MST_Block b ON b.BlockId = d.BlockId"
    " LEFT JOIN users u ON u.emp_no = d.DesignerEmpNo"
)


def not_found() -> ApiError:
    return ApiError(404, "DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")


def rev_state(message: str) -> ApiError:
    return ApiError(409, "INVALID_REV_STATE", message)


def _item(r) -> dict:
    return {
        "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "drawing_nm": r["DrawingNm"], "hull_no": r["HullNo"],
        "block_id": r["BlockId"], "block_cd": r["BlockCd"], "discipline": r["Discipline"], "dwg_status": r["DwgStatus"],
        "current_rev_no": r["CurrentRevNo"], "latest_rev_no": r["LatestRevNo"], "designer_emp_no": r["DesignerEmpNo"],
        "designer_nm": r["DesignerNm"], "link_count": r["LinkCount"],
    }


def list_drawings(conn, hull_no=None, discipline=None, status=None, q=None) -> list[dict]:
    where, params = [], []
    for column, value in (("d.HullNo", hull_no), ("d.Discipline", discipline), ("d.DwgStatus", status)):
        if value:
            where.append(f"{column} = ?")
            params.append(value)
    if q and q.strip():
        where.append("instr(lower(d.DrawingNo || ' ' || d.DrawingNm), ?) > 0")
        params.append(q.strip().lower())
    sql = _SELECT + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY d.DrawingId"
    return [_item(r) for r in conn.execute(sql, params)]


def _row(conn, drawing_id: int):
    row = conn.execute(f"{_SELECT} WHERE d.DrawingId = ?", (drawing_id,)).fetchone()
    if row is None:
        raise not_found()
    return row


def _rev(conn, drawing_id: int, rev_no: int):
    _row(conn, drawing_id)
    rev = conn.execute("SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no)).fetchone()
    if rev is None:
        raise ApiError(404, "REV_NOT_FOUND", "리비전을 찾을 수 없습니다.")
    return rev


def _latest(conn, drawing_id: int):
    return conn.execute(
        "SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? ORDER BY RevNo DESC LIMIT 1", (drawing_id,)
    ).fetchone()


def revisions(conn, drawing_id: int) -> list[dict]:
    _row(conn, drawing_id)
    return [
        {"rev_no": r["RevNo"], "rev_status": r["RevStatus"], "change_desc": r["ChangeDesc"], "has_file": bool(r["FileId"]),
         "file_nm": r["FileNm"], "author_emp_no": r["AuthorEmpNo"], "author_nm": r["AuthorNm"], "issue_dt": r["IssueDt"],
         "create_dt": r["CreateDt"]}
        for r in conn.execute(
            "SELECT r.*, u.display_name AS AuthorNm FROM TB_DWG_Revision r LEFT JOIN users u ON u.emp_no = r.AuthorEmpNo"
            " WHERE r.DrawingId = ? ORDER BY r.RevNo DESC",
            (drawing_id,),
        )
    ]


def get_drawing(conn, drawing_id: int) -> dict:
    row = _row(conn, drawing_id)
    hull_plans = plans.query(conn, row["HullNo"])
    links = {
        r["PlanId"]: r
        for r in conn.execute("SELECT PlanId, RequiredYN, NeedDt FROM TB_DWG_PlanLink WHERE DrawingId = ?", (drawing_id,))
    }
    approvals = conn.execute(
        "SELECT a.*, u.display_name AS ApproverNm FROM TB_DWG_Approval a LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo"
        " WHERE a.DrawingId = ? ORDER BY a.RevNo DESC, a.StepNo",
        (drawing_id,),
    )
    return {
        **_item(row), "block_nm": row["BlockNm"], "create_user_id": row["CreateUserId"], "create_dt": row["CreateDt"],
        "modify_user_id": row["ModifyUserId"], "modify_dt": row["ModifyDt"], "today": settings.today,
        "revisions": revisions(conn, drawing_id),
        "approvals": [
            {"approval_id": a["ApprovalId"], "rev_no": a["RevNo"], "step_no": a["StepNo"],
             "approver_emp_no": a["ApproverEmpNo"], "approver_nm": a["ApproverNm"], "result": a["Result"],
             "comment": a["Comment"], "act_dt": a["ActDt"]}
            for a in approvals
        ],
        "plans": [
            {"plan_id": p["plan_id"], "label": p["label"], "plan_status": p["plan_status"],
             "required": bool(links[p["plan_id"]]["RequiredYN"]), "need_dt": links[p["plan_id"]]["NeedDt"],
             "plan_start_dt": p["plan_start_dt"], "plan_end_dt": p["plan_end_dt"]}
            for p in hull_plans if p["plan_id"] in links
        ],
        "available_plans": [
            {"plan_id": p["plan_id"], "label": p["label"], "plan_status": p["plan_status"]}
            for p in hull_plans if p["plan_id"] not in links
        ],
        "impacts": rules.impacts(conn, drawing_id),
    }


def _validate(conn, hull_no: str, data: dict) -> dict:
    if not (data.get("drawing_nm") or "").strip():
        raise validation("drawing_nm", "도면명을 입력하세요.")
    data["drawing_nm"] = data["drawing_nm"].strip()
    data["discipline"] = data.get("discipline") or None
    if data["discipline"] and data["discipline"] not in rules.code_set(conn, "DWGDISC"):
        raise validation("discipline", "허용되지 않는 분야입니다.")
    if data.get("block_id") is not None and not conn.execute(
        "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (data["block_id"], hull_no)
    ).fetchone():
        raise validation("block_id", "해당 호선의 블록이 아닙니다.")
    data["designer_emp_no"] = data.get("designer_emp_no") or None
    if data["designer_emp_no"] and not rules.is_approved_user(conn, data["designer_emp_no"]):
        raise validation("designer_emp_no", "승인된 회원만 지정할 수 있습니다.")
    return data


def create_drawing(conn, data: dict, emp_no: str) -> dict:
    """BR-06: Rev0 DRAFT, '최초 작성'."""
    drawing_no = (data.get("drawing_no") or "").strip()
    if not drawing_no:
        raise validation("drawing_no", "도면번호를 입력하세요.")
    hull_no = data.get("hull_no")
    if not hull_no or not conn.execute("SELECT 1 FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone():
        raise validation("hull_no", "호선을 선택하세요.")
    data = _validate(conn, hull_no, data)
    with tx(conn):
        if conn.execute("SELECT 1 FROM TB_DWG_Drawing WHERE DrawingNo = ?", (drawing_no,)).fetchone():
            raise ApiError(409, "DUPLICATE", "이미 존재하는 도면번호입니다.", {"field": "drawing_no"})
        drawing_id = conn.execute(
            "INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo, BlockId, Discipline, DwgStatus, CurrentRevNo,"
            " DesignerEmpNo, CreateUserId, CreateDt) VALUES (?, ?, ?, ?, ?, 'DRAFT', 0, ?, ?, ?)",
            (drawing_no, data["drawing_nm"], hull_no, data.get("block_id"), data["discipline"], data["designer_emp_no"],
             emp_no, settings.today),
        ).lastrowid
        conn.execute(
            "INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
            " VALUES (?, 0, 'DRAFT', '최초 작성', ?, ?)",
            (drawing_id, emp_no, settings.today),
        )
    return get_drawing(conn, drawing_id)


def update_drawing(conn, drawing_id: int, changes: dict, emp_no: str) -> dict:
    row = _row(conn, drawing_id)
    if changes.get("hull_no") not in (None, row["HullNo"]):
        raise validation("hull_no", "호선은 변경할 수 없습니다.")
    if changes.get("drawing_no") not in (None, row["DrawingNo"]):
        raise validation("drawing_no", "도면번호는 변경할 수 없습니다.")
    current = {"drawing_nm": row["DrawingNm"], "discipline": row["Discipline"], "block_id": row["BlockId"],
               "designer_emp_no": row["DesignerEmpNo"]}
    data = _validate(conn, row["HullNo"], {**current, **{k: v for k, v in changes.items() if k in _EDITABLE}})
    with tx(conn):
        conn.execute(
            "UPDATE TB_DWG_Drawing SET DrawingNm = ?, Discipline = ?, BlockId = ?, DesignerEmpNo = ?,"
            " ModifyUserId = ?, ModifyDt = ? WHERE DrawingId = ?",
            (*(data[f] for f in _EDITABLE), emp_no, settings.today, drawing_id),
        )
    return get_drawing(conn, drawing_id)


def delete_drawing(conn, drawing_id: int) -> None:
    """BR-08: 리비전·결재·연계는 CASCADE, PDF는 커밋 뒤 삭제."""
    with tx(conn):
        row = _row(conn, drawing_id)
        files = [r[0] for r in conn.execute("SELECT FileId FROM TB_DWG_Revision WHERE DrawingId = ? AND FileId IS NOT NULL", (drawing_id,))]
        conn.execute("DELETE FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,))
        rules.recalc(conn, row["HullNo"])
    rules.remove_files(files)


def create_revision(conn, drawing_id: int, change_desc: str | None, emp_no: str) -> dict:
    """BR-06: 최신이 ISSUED/OBSOLETE일 때만 N+1 DRAFT."""
    if not (change_desc or "").strip():
        raise validation("change_desc", "개정 사유를 입력하세요.")
    with tx(conn):
        row = _row(conn, drawing_id)
        latest = _latest(conn, drawing_id)
        if latest is None or latest["RevStatus"] not in ("ISSUED", "OBSOLETE"):
            raise rev_state("최신 리비전이 배포/폐기 상태일 때만 신규 리비전을 작성할 수 있습니다.")
        conn.execute(
            "INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
            " VALUES (?, ?, 'DRAFT', ?, ?, ?)",
            (drawing_id, latest["RevNo"] + 1, change_desc.strip(), emp_no, settings.today),
        )
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'DRAFT' WHERE DrawingId = ?", (drawing_id,))
        rules.recalc(conn, row["HullNo"])
    return get_drawing(conn, drawing_id)


def request_approval(conn, drawing_id: int, rev_no: int, reviewer: str | None, approver: str | None) -> dict:
    """BR-06: 최신 DRAFT만. 기존 결재행을 지우고 2단계 WAIT 생성."""
    if not reviewer or not approver:
        raise validation("reviewer_emp_no", "검토자와 승인자를 선택하세요.")
    if reviewer == approver:
        raise validation("approver_emp_no", "검토자와 승인자는 서로 다른 사람이어야 합니다.")
    for field, emp in (("reviewer_emp_no", reviewer), ("approver_emp_no", approver)):
        if not rules.is_approved_user(conn, emp):
            raise validation(field, "승인된 회원만 지정할 수 있습니다.")
    with tx(conn):
        rev = _rev(conn, drawing_id, rev_no)
        if rev["RevStatus"] != "DRAFT" or _latest(conn, drawing_id)["RevNo"] != rev_no:
            raise rev_state("최신 작성중(DRAFT) 리비전만 결재 요청할 수 있습니다.")
        conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no))
        conn.executemany(
            "INSERT INTO TB_DWG_Approval (DrawingId, RevNo, StepNo, ApproverEmpNo, Result) VALUES (?, ?, ?, ?, 'WAIT')",
            [(drawing_id, rev_no, 1, reviewer), (drawing_id, rev_no, 2, approver)],
        )
        set_status(conn, drawing_id, rev_no, "REVIEW")
    return get_drawing(conn, drawing_id)


def set_status(conn, drawing_id: int, rev_no: int, status: str) -> None:
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = ? WHERE DrawingId = ? AND RevNo = ?", (status, drawing_id, rev_no))
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = ? WHERE DrawingId = ?", (status, drawing_id))


def issue(conn, drawing_id: int, rev_no: int) -> dict:
    """BR-06 배포: 기존 ISSUED → OBSOLETE, 대상 ISSUED, CurrentRevNo 갱신."""
    with tx(conn):
        row = _row(conn, drawing_id)
        rev = _rev(conn, drawing_id, rev_no)
        if rev["RevStatus"] != "APPROVED":
            raise rev_state("승인(APPROVED)된 리비전만 배포할 수 있습니다.")
        results = [r[0] for r in conn.execute(
            "SELECT Result FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no))]
        if not results or any(r != "APPROVE" for r in results):
            raise ApiError(409, "APPROVAL_INCOMPLETE", "결재가 완료된 리비전만 배포할 수 있습니다.")
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'OBSOLETE' WHERE DrawingId = ? AND RevStatus = 'ISSUED'", (drawing_id,))
        conn.execute(
            "UPDATE TB_DWG_Revision SET RevStatus = 'ISSUED', IssueDt = ? WHERE DrawingId = ? AND RevNo = ?",
            (settings.today, drawing_id, rev_no),
        )
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'ISSUED', CurrentRevNo = ? WHERE DrawingId = ?", (rev_no, drawing_id))
        rules.recalc(conn, row["HullNo"])
    return get_drawing(conn, drawing_id)


# ---- PDF

def _clean_name(filename: str | None) -> str:
    return (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()[:200]


def _invalid_file() -> ApiError:
    return ApiError(400, "INVALID_FILE_TYPE", "PDF 파일만 업로드할 수 있습니다.")


def _draft_rev(conn, drawing_id: int, rev_no: int, message: str):
    rev = _rev(conn, drawing_id, rev_no)
    if rev["RevStatus"] != "DRAFT":
        raise rev_state(message)
    return rev


async def upload_pdf(conn, drawing_id: int, rev_no: int, filename: str | None, content_type: str | None, chunks) -> dict:
    """본문을 스트리밍으로 받아 {FileId}.pdf로 쓰고, 커밋 실패 시 새 파일을 지운다."""
    upload_msg = "작성중(DRAFT) 리비전만 업로드할 수 있습니다."
    _draft_rev(conn, drawing_id, rev_no, upload_msg)
    name = _clean_name(filename)
    mime = (content_type or "").split(";")[0].strip().lower()
    if not name.lower().endswith(".pdf") and mime != "application/pdf":
        raise _invalid_file()
    settings.file_dir.mkdir(parents=True, exist_ok=True)
    file_id = secrets.token_hex(16)
    path = rules.pdf_path(file_id)
    size, head = 0, b""
    try:
        with path.open("wb") as out:
            async for chunk in chunks:
                size += len(chunk)
                if size > MAX_PDF:
                    raise ApiError(413, "FILE_TOO_LARGE", "파일 크기는 30MB 이하여야 합니다.")
                if len(head) < 5:
                    head = (head + chunk)[:5]
                    if not b"%PDF-".startswith(head):
                        raise _invalid_file()
                out.write(chunk)
        if head != b"%PDF-":
            raise _invalid_file()
        with tx(conn):
            old = _draft_rev(conn, drawing_id, rev_no, upload_msg)["FileId"]
            conn.execute(
                "UPDATE TB_DWG_Revision SET FileId = ?, FileNm = ? WHERE DrawingId = ? AND RevNo = ?",
                (file_id, name or None, drawing_id, rev_no),
            )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    rules.remove_files([old])
    return next(r for r in revisions(conn, drawing_id) if r["rev_no"] == rev_no)


def pdf_file(conn, drawing_id: int, rev_no: int):
    rev = _rev(conn, drawing_id, rev_no)
    if not rev["FileId"]:
        raise ApiError(404, "NO_FILE", "업로드된 파일이 없습니다.")
    path = rules.pdf_path(rev["FileId"])
    if not path.is_file():
        raise ApiError(404, "FILE_NOT_FOUND", "파일을 찾을 수 없습니다.")
    return path, rev["FileNm"] or f"{rev['FileId']}.pdf"


def delete_pdf(conn, drawing_id: int, rev_no: int) -> None:
    with tx(conn):
        rev = _draft_rev(conn, drawing_id, rev_no, "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다.")
        if not rev["FileId"]:
            raise ApiError(404, "NO_FILE", "업로드된 파일이 없습니다.")
        conn.execute("UPDATE TB_DWG_Revision SET FileId = NULL, FileNm = NULL WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no))
    rules.remove_files([rev["FileId"]])


# ---- 공정 연계 (검증·재계산은 plans 서비스 재사용)

def add_plan(conn, drawing_id: int, plan_id: int | None, required: bool) -> dict:
    _row(conn, drawing_id)
    if plan_id is None:
        raise validation("plan_id", "공정을 선택하세요.")
    plans.add_link(conn, plan_id, drawing_id, required)
    return get_drawing(conn, drawing_id)


def remove_plan(conn, drawing_id: int, plan_id: int) -> None:
    _row(conn, drawing_id)
    plans.remove_link(conn, plan_id, drawing_id)
