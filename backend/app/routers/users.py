import sqlite3

from fastapi import APIRouter, Depends, Response

from .. import schemas
from ..db import get_db
from ..deps import require
from ..services import users

router = APIRouter(prefix="/api")
admin = require("M91", 3)
guard = Depends(admin)


@router.get("/users", dependencies=[guard])
def list_users(status: str | None = None, q: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    return users.list_users(conn, status, q)


@router.post("/users", status_code=201, dependencies=[guard])
def create_user(body: schemas.UserIn, conn: sqlite3.Connection = Depends(get_db)):
    data = {k: v or "" for k, v in body.model_dump(exclude={"groups", "status", "totp_enabled"}).items()}
    return users.admin_create(conn, {**data, "status": body.status, "groups": body.groups, "totp_enabled": body.totp_enabled})


@router.get("/users/{emp_no}", dependencies=[guard])
def get_user(emp_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return users.get_user(conn, emp_no)


@router.patch("/users/{emp_no}", dependencies=[guard])
def update_user(emp_no: str, body: schemas.UserIn, conn: sqlite3.Connection = Depends(get_db)):
    return users.update_user(conn, emp_no, body.model_dump())


@router.delete("/users/{emp_no}", status_code=204)
def delete_user(emp_no: str, user: dict = Depends(admin), conn: sqlite3.Connection = Depends(get_db)):
    users.delete_user(conn, emp_no, user["emp_no"])
    return Response(status_code=204)


@router.post("/users/{emp_no}/approve", dependencies=[guard])
def approve(emp_no: str, body: schemas.ApproveIn, conn: sqlite3.Connection = Depends(get_db)):
    return users.approve(conn, emp_no, body.groups)


@router.post("/users/{emp_no}/reject", dependencies=[guard])
def reject(emp_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return users.reject(conn, emp_no)


@router.get("/auth-groups", dependencies=[guard])
def auth_groups(conn: sqlite3.Connection = Depends(get_db)):
    return users.auth_groups(conn)
