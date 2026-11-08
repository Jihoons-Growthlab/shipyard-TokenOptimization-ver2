import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from .. import schemas
from ..db import get_db
from ..deps import bearer_payload, current_user
from ..services import auth, users

router = APIRouter(prefix="/api/auth")


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login")
def login(body: schemas.LoginIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return auth.login(conn, body.emp_no, body.password, _ip(request))


@router.post("/otp/verify")
def verify_otp(
    body: schemas.OtpIn,
    request: Request,
    payload: dict = Depends(bearer_payload),
    conn: sqlite3.Connection = Depends(get_db),
):
    return auth.verify_otp(conn, payload, body.code, _ip(request))


@router.post("/register", status_code=201)
def register(body: schemas.RegisterIn, conn: sqlite3.Connection = Depends(get_db)):
    emp_no = users.create_user(conn, body.model_dump())
    return {"emp_no": emp_no, "status": "pending", "message": "가입 신청 완료. 관리자 승인 후 로그인할 수 있습니다."}


@router.post("/logout", status_code=204)
def logout(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    auth.logout(conn, user["lid"])
    return Response(status_code=204)


@router.get("/me")
def me(user: dict = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return auth.profile(conn, user)
