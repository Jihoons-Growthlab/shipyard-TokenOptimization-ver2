import sqlite3

from fastapi import APIRouter, Depends, Response

from .. import schemas
from ..db import get_db
from ..deps import current_user, require
from ..services import plans

router = APIRouter(prefix="/api")
view = Depends(require("M21", 1))
write = require("M21", 2)


@router.get("/procs", dependencies=[Depends(current_user)])
def procs(conn: sqlite3.Connection = Depends(get_db)):
    return plans.procs(conn)


@router.get("/plan-hulls", dependencies=[view])
def plan_hulls(conn: sqlite3.Connection = Depends(get_db)):
    return plans.plan_hulls(conn)


@router.get("/users/options", dependencies=[Depends(current_user)])
def user_options(conn: sqlite3.Connection = Depends(get_db)):
    return plans.user_options(conn)


@router.get("/hulls/{hull_no}/plans", dependencies=[view])
def hull_plans(hull_no: str, block_id: int | None = None, conn: sqlite3.Connection = Depends(get_db)):
    return plans.hull_plans(conn, hull_no, block_id)


@router.post("/hulls/{hull_no}/plans", status_code=201)
def create_plan(hull_no: str, body: schemas.PlanIn, user: dict = Depends(write),
                conn: sqlite3.Connection = Depends(get_db)):
    return plans.create_plan(conn, hull_no, body.model_dump(), user["emp_no"])


@router.get("/plans/{plan_id}", dependencies=[view])
def get_plan(plan_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return plans.get_plan(conn, plan_id)


@router.patch("/plans/{plan_id}", dependencies=[Depends(write)])
def update_plan(plan_id: int, body: schemas.PlanIn, conn: sqlite3.Connection = Depends(get_db)):
    return plans.update_plan(conn, plan_id, body.model_dump(exclude_unset=True))


@router.delete("/plans/{plan_id}", status_code=204, dependencies=[Depends(write)])
def delete_plan(plan_id: int, conn: sqlite3.Connection = Depends(get_db)):
    plans.delete_plan(conn, plan_id)
    return Response(status_code=204)


@router.put("/plans/{plan_id}/predecessors", dependencies=[Depends(write)])
def set_predecessors(plan_id: int, body: schemas.PredecessorsIn, conn: sqlite3.Connection = Depends(get_db)):
    return plans.set_predecessors(conn, plan_id, body.pred_plan_ids, body.confirm_late_preds)


@router.get("/plans/{plan_id}/drawings", dependencies=[view])
def links(plan_id: int, conn: sqlite3.Connection = Depends(get_db)):
    return plans.links(conn, plan_id)


@router.post("/plans/{plan_id}/drawings", status_code=201, dependencies=[Depends(write)])
def add_link(plan_id: int, body: schemas.PlanLinkIn, conn: sqlite3.Connection = Depends(get_db)):
    return plans.add_link(conn, plan_id, body.drawing_id, body.required)


@router.delete("/plans/{plan_id}/drawings/{drawing_id}", status_code=204, dependencies=[Depends(write)])
def remove_link(plan_id: int, drawing_id: int, conn: sqlite3.Connection = Depends(get_db)):
    plans.remove_link(conn, plan_id, drawing_id)
    return Response(status_code=204)
