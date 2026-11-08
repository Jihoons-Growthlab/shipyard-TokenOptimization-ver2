import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import require
from ..services import dashboard

router = APIRouter(prefix="/api")


@router.get("/dashboard/summary", dependencies=[Depends(require("M00", 1))])
def summary(conn: sqlite3.Connection = Depends(get_db)):
    return dashboard.summary(conn)
