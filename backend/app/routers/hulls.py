import sqlite3

from fastapi import APIRouter, Depends, Response

from .. import schemas
from ..db import get_db
from ..deps import require
from ..services import hulls

router = APIRouter(prefix="/api")
view = Depends(require("M11", 1))
write = require("M11", 2)


@router.get("/hulls", dependencies=[view])
def list_hulls(status: str | None = None, ship_type: str | None = None, q: str | None = None,
               conn: sqlite3.Connection = Depends(get_db)):
    return hulls.list_hulls(conn, status, ship_type, q)


@router.post("/hulls", status_code=201)
def create_hull(body: schemas.HullIn, user: dict = Depends(write), conn: sqlite3.Connection = Depends(get_db)):
    return hulls.create_hull(conn, body.model_dump(exclude_unset=True), user["emp_no"])


@router.get("/hulls/{hull_no}", dependencies=[view])
def get_hull(hull_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.get_hull(conn, hull_no)


@router.patch("/hulls/{hull_no}")
def update_hull(hull_no: str, body: schemas.HullIn, user: dict = Depends(write),
                conn: sqlite3.Connection = Depends(get_db)):
    return hulls.update_hull(conn, hull_no, body.model_dump(exclude_unset=True), user["emp_no"])


@router.delete("/hulls/{hull_no}", status_code=204, dependencies=[Depends(write)])
def delete_hull(hull_no: str, conn: sqlite3.Connection = Depends(get_db)):
    hulls.delete_hull(conn, hull_no)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/milestones", dependencies=[view])
def milestones(hull_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.milestones(conn, hull_no)


@router.put("/hulls/{hull_no}/milestones", dependencies=[Depends(write)])
def save_milestones(hull_no: str, body: schemas.MilestonesIn, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.save_milestones(conn, hull_no, [i.model_dump() for i in body.items])


@router.get("/hulls/{hull_no}/blocks", dependencies=[view])
def blocks(hull_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.blocks(conn, hull_no)


@router.post("/hulls/{hull_no}/blocks", status_code=201, dependencies=[Depends(write)])
def create_block(hull_no: str, body: schemas.BlockIn, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.create_block(conn, hull_no, body.model_dump())


@router.delete("/blocks/{block_id}", status_code=204, dependencies=[Depends(write)])
def delete_block(block_id: int, conn: sqlite3.Connection = Depends(get_db)):
    hulls.delete_block(conn, block_id)
    return Response(status_code=204)


@router.get("/hulls/{hull_no}/summary", dependencies=[view])
def summary(hull_no: str, conn: sqlite3.Connection = Depends(get_db)):
    return hulls.summary(conn, hull_no)
