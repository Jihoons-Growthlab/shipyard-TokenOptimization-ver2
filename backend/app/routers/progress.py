import sqlite3

from fastapi import APIRouter, Depends

from .. import schemas
from ..db import get_db
from ..deps import require
from ..services import progress

router = APIRouter(prefix="/api")
view = Depends(require("M22", 1))
write = Depends(require("M22", 2))


@router.get("/progress-hulls", dependencies=[view])
def progress_hulls(conn: sqlite3.Connection = Depends(get_db)):
    return progress.progress_hulls(conn)


@router.get("/hulls/{hull_no}/progress-targets", dependencies=[view])
def targets(hull_no: str, include_done: bool = False, conn: sqlite3.Connection = Depends(get_db)):
    return progress.targets(conn, hull_no, include_done)


@router.get("/plans/{plan_id}/progress", dependencies=[view])
def detail(plan_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return progress.detail(conn, plan_id)


@router.put("/plans/{plan_id}/progress/{work_dt}", dependencies=[write])
def save(plan_id: int, work_dt: str, body: schemas.ProgressIn, conn: sqlite3.Connection = Depends(get_db)):
    return progress.save(conn, plan_id, work_dt, body.model_dump())


@router.delete("/progress/{progress_id}", dependencies=[write])
def delete(progress_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return progress.delete(conn, progress_id)
