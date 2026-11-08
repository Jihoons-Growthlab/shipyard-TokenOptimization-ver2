import sqlite3

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from .. import schemas
from ..db import get_db
from ..deps import require
from ..services import approvals, drawings

router = APIRouter(prefix="/api")
view = Depends(require("M31", 1))
write = require("M31", 2)
inbox_view = Depends(require("M33", 1))
REV = "/drawings/{drawing_id}/revisions/{rev_no}"


@router.get("/drawings", dependencies=[view])
def list_drawings(hull_no: str | None = None, discipline: str | None = None, status: str | None = None,
                  q: str | None = None, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.list_drawings(conn, hull_no, discipline, status, q)


@router.post("/drawings", status_code=201)
def create_drawing(body: schemas.DrawingIn, user: dict = Depends(write), conn: sqlite3.Connection = Depends(get_db)):
    return drawings.create_drawing(conn, body.model_dump(), user["emp_no"])


@router.get("/drawings/{drawing_id}", dependencies=[view])
def get_drawing(drawing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.get_drawing(conn, drawing_id)


@router.patch("/drawings/{drawing_id}")
def update_drawing(drawing_id: int, body: schemas.DrawingIn, user: dict = Depends(write),
                   conn: sqlite3.Connection = Depends(get_db)):
    return drawings.update_drawing(conn, drawing_id, body.model_dump(exclude_unset=True), user["emp_no"])


@router.delete("/drawings/{drawing_id}", status_code=204, dependencies=[Depends(write)])
def delete_drawing(drawing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    drawings.delete_drawing(conn, drawing_id)
    return Response(status_code=204)


@router.get("/drawings/{drawing_id}/revisions", dependencies=[view])
def revisions(drawing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.revisions(conn, drawing_id)


@router.post("/drawings/{drawing_id}/revisions", status_code=201)
def create_revision(drawing_id: int, body: schemas.RevisionIn, user: dict = Depends(write),
                    conn: sqlite3.Connection = Depends(get_db)):
    return drawings.create_revision(conn, drawing_id, body.change_desc, user["emp_no"])


@router.post(f"{REV}/pdf", dependencies=[Depends(write)])
async def upload_pdf(drawing_id: int, rev_no: int, request: Request, filename: str | None = None,
                     conn: sqlite3.Connection = Depends(get_db)):
    # 권한 의존성이 먼저 실행되고 본문은 여기서 스트리밍으로 읽는다.
    return await drawings.upload_pdf(
        conn, drawing_id, rev_no, filename, request.headers.get("content-type"), request.stream()
    )


@router.get(f"{REV}/pdf", dependencies=[view])
def get_pdf(drawing_id: int, rev_no: int, conn: sqlite3.Connection = Depends(get_db)):
    path, name = drawings.pdf_file(conn, drawing_id, rev_no)
    return FileResponse(path, media_type="application/pdf", filename=name, content_disposition_type="inline",
                        headers={"X-Content-Type-Options": "nosniff"})


@router.delete(f"{REV}/pdf", status_code=204, dependencies=[Depends(write)])
def delete_pdf(drawing_id: int, rev_no: int, conn: sqlite3.Connection = Depends(get_db)):
    drawings.delete_pdf(conn, drawing_id, rev_no)
    return Response(status_code=204)


@router.post(f"{REV}/request-approval", dependencies=[Depends(write)])
def request_approval(drawing_id: int, rev_no: int, body: schemas.ApprovalRequestIn,
                     conn: sqlite3.Connection = Depends(get_db)):
    return drawings.request_approval(conn, drawing_id, rev_no, body.reviewer_emp_no, body.approver_emp_no)


@router.post(f"{REV}/issue", dependencies=[Depends(write)])
def issue(drawing_id: int, rev_no: int, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.issue(conn, drawing_id, rev_no)


@router.get("/drawings/{drawing_id}/plans", dependencies=[view])
def linked_plans(drawing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.get_drawing(conn, drawing_id)["plans"]


@router.post("/drawings/{drawing_id}/plans", status_code=201, dependencies=[Depends(write)])
def add_plan(drawing_id: int, body: schemas.DrawingPlanIn, conn: sqlite3.Connection = Depends(get_db)):
    return drawings.add_plan(conn, drawing_id, body.plan_id, body.required)


@router.delete("/drawings/{drawing_id}/plans/{plan_id}", status_code=204, dependencies=[Depends(write)])
def remove_plan(drawing_id: int, plan_id: int, conn: sqlite3.Connection = Depends(get_db)):
    drawings.remove_plan(conn, drawing_id, plan_id)
    return Response(status_code=204)


@router.get("/approvals/inbox")
def inbox(user: dict = inbox_view, conn: sqlite3.Connection = Depends(get_db)):
    return approvals.inbox(conn, user["emp_no"])


@router.post("/approvals/{approval_id}/decision")
def decide(approval_id: int, body: schemas.DecisionIn, user: dict = Depends(require("M33", 2)),
           conn: sqlite3.Connection = Depends(get_db)):
    return approvals.decide(conn, approval_id, body.result, body.comment, user["emp_no"])


@router.get("/approvals/history", dependencies=[inbox_view])
def history(conn: sqlite3.Connection = Depends(get_db)):
    return approvals.history(conn)
