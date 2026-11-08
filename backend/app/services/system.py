import sqlite3
from datetime import datetime, timezone

LEVELS = {"View": 1, "Write": 2, "Admin": 3}
_LEVEL_SQL = "MAX(CASE m.AuthGbn WHEN 'View' THEN 1 WHEN 'Write' THEN 2 WHEN 'Admin' THEN 3 END)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def menu_level(conn: sqlite3.Connection, emp_no: str, menu_id: str) -> int:
    row = conn.execute(
        f"SELECT {_LEVEL_SQL} FROM TB_SYS_AuthMenu m"
        " JOIN TB_SYS_AuthUser u ON u.AuthCd = m.AuthCd WHERE u.EmpNo = ? AND m.MenuId = ?",
        (emp_no, menu_id),
    ).fetchone()
    return row[0] or 0


def user_menu(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    rows = conn.execute(
        f"SELECT i.MenuId, i.ParentId, i.Title, i.TokenUrl, i.Seq, {_LEVEL_SQL} AS level"
        " FROM TB_SYS_MenuInfo i"
        " JOIN TB_SYS_AuthMenu m ON m.MenuId = i.MenuId"
        " JOIN TB_SYS_AuthUser u ON u.AuthCd = m.AuthCd"
        " WHERE u.EmpNo = ? AND i.UseYN = 1 GROUP BY i.MenuId ORDER BY i.Seq",
        (emp_no,),
    ).fetchall()
    by_id = {r["MenuId"]: r for r in rows}

    def visible(row) -> bool:
        parent = row["ParentId"]
        return parent is None or (parent in by_id and visible(by_id[parent]))

    names = {v: k for k, v in LEVELS.items()}
    return [
        {
            "menu_id": r["MenuId"],
            "parent_id": r["ParentId"],
            "title": r["Title"],
            "token": r["TokenUrl"],
            "seq": r["Seq"],
            "level": r["level"],
            "auth_gbn": names[r["level"]],
            "can_write": r["level"] >= 2,
        }
        for r in rows
        if visible(r)
    ]


def log_menu_access(conn: sqlite3.Connection, menu_id: str, log_id: int) -> None:
    conn.execute(
        "INSERT INTO TB_SYS_LogMenuAccess (MenuId, LogId, InDt) VALUES (?, ?, ?)",
        (menu_id, log_id, utc_now()),
    )


def codes(conn: sqlite3.Connection) -> dict[str, list[dict]]:
    result: dict[str, list[dict]] = {}
    for r in conn.execute(
        "SELECT c.CodeGroup, c.Code, c.CodeName FROM TB_SYS_Code c"
        " JOIN TB_SYS_CodeGroup g ON g.CodeGroup = c.CodeGroup"
        " WHERE c.UseYN = 1 AND g.UseYN = 1 ORDER BY g.Seq, c.Seq"
    ):
        result.setdefault(r["CodeGroup"], []).append({"code": r["Code"], "name": r["CodeName"]})
    return result
