import sqlite3

from fastapi import Depends, Header

from . import security
from .db import get_db
from .errors import ApiError, unauthorized
from .services import system


def bearer_payload(authorization: str | None = Header(None)) -> dict:
    scheme, _, token = (authorization or "").partition(" ")
    payload = security.decode_token(token) if scheme.lower() == "bearer" else None
    if payload is None:
        raise unauthorized()
    return payload


def current_user(payload: dict = Depends(bearer_payload), conn: sqlite3.Connection = Depends(get_db)) -> dict:
    if payload.get("stage") != "full" or "lid" not in payload:
        raise unauthorized()
    row = conn.execute(
        "SELECT u.* FROM TB_SYS_LogAccess l JOIN users u ON u.emp_no = l.UserId"
        " WHERE l.LogId = ? AND l.UserId = ? AND l.LogoutDt IS NULL AND u.status = 'approved'",
        (payload["lid"], payload["sub"]),
    ).fetchone()
    if row is None:
        raise unauthorized()
    return {**dict(row), "lid": payload["lid"]}


def require(menu_id: str, level: int = 1):
    """메뉴 최소 등급 의존성. View=1, Write=2, Admin=3."""

    def dependency(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> dict:
        if system.menu_level(conn, user["emp_no"], menu_id) < level:
            raise ApiError(403, "FORBIDDEN", "해당 화면에 대한 권한이 없습니다.", {"menu_id": menu_id})
        return user

    return dependency
