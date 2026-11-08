import re
import sqlite3

from ..config import settings
from ..db import tx
from ..errors import ApiError, validation
from . import rules

_HULL_NO = re.compile(r"^[A-Za-z0-9._-]{1,20}$")
_CODE_MSG = "허용되지 않는 코드값입니다."
_NEG_MSG = "0 이상의 값을 입력하세요."
_COLUMNS = {
    "hull_no": "HullNo", "hull_nm": "HullNm", "ship_type": "ShipType", "hull_status": "HullStatus",
    "owner_nm": "OwnerNm", "class_society": "ClassSociety", "length_m": "LengthM", "breadth_m": "BreadthM",
    "depth_m": "DepthM", "dead_weight": "DeadWeight", "dock_no": "DockNo", "contract_dt": "ContractDt",
    "delivery_dt": "DeliveryDt", "remark": "Remark", "use_yn": "UseYN", "create_user_id": "CreateUserId",
    "create_dt": "CreateDt", "modify_user_id": "ModifyUserId", "modify_dt": "ModifyDt",
}
MILESTONES = ("CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER")


def not_found() -> ApiError:
    return ApiError(404, "HULL_NOT_FOUND", "호선을 찾을 수 없습니다.")


def ensure(conn: sqlite3.Connection, hull_no: str):
    row = conn.execute("SELECT * FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    if row is None:
        raise not_found()
    return row


def _plans_by_hull(conn, hull_no=None) -> dict[str, list]:
    sql = "SELECT HullNo, BlockId, PlanStartDt, PlanEndDt, ProgressRate, PlanStatus FROM TB_PRC_Plan"
    rows = conn.execute(sql + " WHERE HullNo = ?", (hull_no,)) if hull_no else conn.execute(sql)
    result: dict[str, list] = {}
    for r in rows:
        result.setdefault(r["HullNo"], []).append(r)
    return result


def _out(row, plans: list) -> dict:
    data = {api: row[col] for api, col in _COLUMNS.items()}
    data["use_yn"] = bool(data["use_yn"])
    data["plan_count"] = len(plans)
    data["progress"] = rules.weighted_progress(plans)
    data["delay_count"] = sum(p["PlanStatus"] == "DELAY" for p in plans)
    return data


def list_hulls(conn, status: str | None, ship_type: str | None, q: str | None) -> list[dict]:
    plans = _plans_by_hull(conn)
    needle = (q or "").strip().casefold()
    result = []
    for row in conn.execute("SELECT * FROM TB_MST_Hull ORDER BY HullNo"):
        if status and row["HullStatus"] != status or ship_type and row["ShipType"] != ship_type:
            continue
        if needle and not any(needle in (row[c] or "").casefold() for c in ("HullNo", "HullNm", "OwnerNm")):
            continue
        result.append(_out(row, plans.get(row["HullNo"], [])))
    return result


def get_hull(conn, hull_no: str) -> dict:
    return _out(ensure(conn, hull_no), _plans_by_hull(conn, hull_no).get(hull_no, []))


def _validate(conn, data: dict) -> dict:
    """전체 레코드(병합 후)를 검사해 DB 값으로 정리한다."""
    if data.get("ship_type") in ("", None):
        data["ship_type"] = None
    elif data["ship_type"] not in rules.code_set(conn, "SHIPTYPE"):
        raise validation("ship_type", _CODE_MSG)
    if data.get("hull_status") in ("", None):
        raise validation("hull_status", "상태를 선택하세요.")
    if data["hull_status"] not in rules.code_set(conn, "HULLSTAT"):
        raise validation("hull_status", _CODE_MSG)
    for field in ("contract_dt", "delivery_dt"):
        data[field] = rules.parse_date(data.get(field), field)
    if data["contract_dt"] and data["delivery_dt"] and data["delivery_dt"] < data["contract_dt"]:
        raise validation("delivery_dt", "인도 예정일이 계약일보다 빠릅니다.")
    for field in ("length_m", "breadth_m", "depth_m", "dead_weight"):
        if data.get(field) is not None and data[field] < 0:
            raise validation(field, _NEG_MSG)
    for field in ("hull_nm", "owner_nm", "class_society", "dock_no", "remark"):
        value = data.get(field)
        data[field] = value.strip() if isinstance(value, str) else value
    data["hull_nm"] = data.get("hull_nm") or ""
    data["use_yn"] = 1 if data.get("use_yn", True) else 0
    return data


_EDITABLE = [
    "hull_nm", "ship_type", "hull_status", "owner_nm", "class_society", "length_m", "breadth_m", "depth_m",
    "dead_weight", "dock_no", "contract_dt", "delivery_dt", "remark", "use_yn",
]


def create_hull(conn, data: dict, emp_no: str) -> dict:
    hull_no = (data.get("hull_no") or "").strip()
    if not hull_no:
        raise validation("hull_no", "호선번호를 입력하세요.")
    if not _HULL_NO.match(hull_no):
        raise validation("hull_no", "호선번호는 영문/숫자/._- 1~20자입니다.")
    data = _validate(conn, {**dict.fromkeys(_EDITABLE), "hull_status": "PLAN", "use_yn": True, **data})
    with tx(conn):
        if conn.execute("SELECT 1 FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone():
            raise ApiError(409, "DUPLICATE", "이미 존재하는 호선번호입니다.", {"field": "hull_no"})
        cols = ", ".join(_COLUMNS[f] for f in _EDITABLE)
        conn.execute(
            f"INSERT INTO TB_MST_Hull (HullNo, {cols}, CreateUserId, CreateDt) VALUES (?{', ?' * len(_EDITABLE)}, ?, ?)",
            (hull_no, *(data[f] for f in _EDITABLE), emp_no, settings.today),
        )
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone (HullNo, MilestoneCd, PlanDt) VALUES (?, ?, ?)",
            [(hull_no, cd, data["delivery_dt"] if cd == "DELIVER" else None) for cd in MILESTONES],
        )
    return get_hull(conn, hull_no)


def update_hull(conn, hull_no: str, changes: dict, emp_no: str) -> dict:
    current = ensure(conn, hull_no)
    if "hull_no" in changes and changes["hull_no"] != hull_no:
        raise validation("hull_no", "호선번호는 수정할 수 없습니다.")
    merged = {f: current[_COLUMNS[f]] for f in _EDITABLE}
    merged.update({k: v for k, v in changes.items() if k in _EDITABLE})
    data = _validate(conn, merged)
    sets = ", ".join(f"{_COLUMNS[f]} = ?" for f in _EDITABLE)
    with tx(conn):
        conn.execute(
            f"UPDATE TB_MST_Hull SET {sets}, ModifyUserId = ?, ModifyDt = ? WHERE HullNo = ?",
            (*(data[f] for f in _EDITABLE), emp_no, settings.today, hull_no),
        )
    return get_hull(conn, hull_no)


def delete_hull(conn, hull_no: str) -> None:
    """BR-08: 하위 전체는 FK CASCADE, PDF는 커밋 뒤 삭제."""
    with tx(conn):
        ensure(conn, hull_no)
        files = [
            r[0]
            for r in conn.execute(
                "SELECT r.FileId FROM TB_DWG_Revision r JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId"
                " WHERE d.HullNo = ? AND r.FileId IS NOT NULL",
                (hull_no,),
            )
        ]
        conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,))
    rules.remove_files(files)


# ---- 주요일정

def milestones(conn, hull_no: str) -> list[dict]:
    ensure(conn, hull_no)
    rows = conn.execute(
        "SELECT m.MilestoneCd, c.CodeName, m.PlanDt, m.ActualDt FROM TB_MST_HullMilestone m"
        " LEFT JOIN TB_SYS_Code c ON c.CodeGroup = 'MILESTONE' AND c.Code = m.MilestoneCd"
        " WHERE m.HullNo = ? ORDER BY c.Seq, m.MilestoneCd",
        (hull_no,),
    )
    return [
        {
            "milestone_cd": r["MilestoneCd"],
            "name": r["CodeName"] or r["MilestoneCd"],
            "plan_dt": r["PlanDt"],
            "actual_dt": r["ActualDt"],
            "diff_days": rules.days_between(r["PlanDt"], r["ActualDt"]) if r["PlanDt"] and r["ActualDt"] else None,
        }
        for r in rows
    ]


def save_milestones(conn, hull_no: str, items: list[dict]) -> list[dict]:
    ensure(conn, hull_no)
    allowed = rules.code_set(conn, "MILESTONE")
    codes = [i["milestone_cd"] for i in items]
    if len(set(codes)) != len(codes) or not set(codes) <= allowed:
        raise validation("milestone_cd", "허용되지 않거나 중복된 일정 코드입니다.")
    values = [
        (hull_no, i["milestone_cd"], rules.parse_date(i.get("plan_dt"), "plan_dt"),
         rules.parse_date(i.get("actual_dt"), "actual_dt"))
        for i in items
    ]
    with tx(conn):
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone (HullNo, MilestoneCd, PlanDt, ActualDt) VALUES (?, ?, ?, ?)"
            " ON CONFLICT (HullNo, MilestoneCd) DO UPDATE SET PlanDt = excluded.PlanDt, ActualDt = excluded.ActualDt",
            values,
        )
    return milestones(conn, hull_no)


# ---- 블록

def _block_out(row, plans: list, drawing_count: int) -> dict:
    return {
        "block_id": row["BlockId"], "hull_no": row["HullNo"], "block_cd": row["BlockCd"], "block_nm": row["BlockNm"],
        "block_type": row["BlockType"], "parent_block_id": row["ParentBlockId"], "weight_ton": row["WeightTon"],
        "use_yn": bool(row["UseYN"]), "plan_count": len(plans), "progress": rules.weighted_progress(plans),
        "drawing_count": drawing_count,
    }


def blocks(conn, hull_no: str) -> list[dict]:
    ensure(conn, hull_no)
    plans: dict[int, list] = {}
    for p in _plans_by_hull(conn, hull_no).get(hull_no, []):
        plans.setdefault(p["BlockId"], []).append(p)
    drawings = dict(
        conn.execute("SELECT BlockId, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo = ? GROUP BY BlockId", (hull_no,)).fetchall()
    )
    return [
        _block_out(r, plans.get(r["BlockId"], []), drawings.get(r["BlockId"], 0))
        for r in conn.execute("SELECT * FROM TB_MST_Block WHERE HullNo = ? ORDER BY BlockCd, BlockId", (hull_no,))
    ]


def create_block(conn, hull_no: str, data: dict) -> dict:
    ensure(conn, hull_no)
    block_cd = (data.get("block_cd") or "").strip()
    if not block_cd:
        raise validation("block_cd", "블록코드를 입력하세요.")
    block_type = data.get("block_type") or None
    if block_type and block_type not in rules.code_set(conn, "BLOCKTYPE"):
        raise validation("block_type", _CODE_MSG)
    if data.get("weight_ton") is not None and data["weight_ton"] < 0:
        raise validation("weight_ton", _NEG_MSG)
    with tx(conn):
        if conn.execute("SELECT 1 FROM TB_MST_Block WHERE HullNo = ? AND BlockCd = ?", (hull_no, block_cd)).fetchone():
            raise ApiError(409, "DUPLICATE", "이미 존재하는 블록코드입니다.", {"field": "block_cd"})
        block_id = conn.execute(
            "INSERT INTO TB_MST_Block (HullNo, BlockCd, BlockNm, BlockType, WeightTon) VALUES (?, ?, ?, ?, ?)",
            (hull_no, block_cd, (data.get("block_nm") or "").strip() or None, block_type, data.get("weight_ton")),
        ).lastrowid
    return next(b for b in blocks(conn, hull_no) if b["block_id"] == block_id)


def delete_block(conn, block_id: int) -> None:
    """BR-08: 공정·연계는 CASCADE, 도면은 BlockId=NULL. 이후 BR-03."""
    with tx(conn):
        row = conn.execute("SELECT HullNo FROM TB_MST_Block WHERE BlockId = ?", (block_id,)).fetchone()
        if row is None:
            raise ApiError(404, "BLOCK_NOT_FOUND", "블록을 찾을 수 없습니다.")
        conn.execute("DELETE FROM TB_MST_Block WHERE BlockId = ?", (block_id,))
        rules.recalc(conn, row["HullNo"])


def summary(conn, hull_no: str) -> dict:
    ensure(conn, hull_no)
    plans = _plans_by_hull(conn, hull_no).get(hull_no, [])
    drawing_status = dict.fromkeys(("ISSUED", "APPROVED", "REVIEW", "DRAFT"), 0)
    drawing_count = 0
    for r in conn.execute("SELECT DwgStatus, COUNT(*) FROM TB_DWG_Drawing WHERE HullNo = ? GROUP BY DwgStatus", (hull_no,)):
        drawing_count += r[1]
        if r[0] in drawing_status:
            drawing_status[r[0]] = r[1]
    plan_status = dict.fromkeys(rules.PLAN_STATUSES, 0)
    for p in plans:
        plan_status[p["PlanStatus"]] = plan_status.get(p["PlanStatus"], 0) + 1
    return {
        "hull_no": hull_no, "plan_count": len(plans), "progress": rules.weighted_progress(plans),
        "plan_status": plan_status, "drawing_count": drawing_count, "drawing_status": drawing_status,
    }
