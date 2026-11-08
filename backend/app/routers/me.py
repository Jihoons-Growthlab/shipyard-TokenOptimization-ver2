import sqlite3

from fastapi import APIRouter, Depends, Response

from .. import schemas
from ..db import get_db
from ..deps import current_user, require
from ..services import system

router = APIRouter(prefix="/api/me")


@router.get("/menu")
def menu(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return system.user_menu(conn, user["emp_no"])


@router.post("/menu-access", status_code=204)
def menu_access(
    body: schemas.MenuAccessIn,
    user: dict = Depends(current_user),
    conn: sqlite3.Connection = Depends(get_db),
):
    require(body.menu_id, 1)(user, conn)
    system.log_menu_access(conn, body.menu_id, user["lid"])
    return Response(status_code=204)
