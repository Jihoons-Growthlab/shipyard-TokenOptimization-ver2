import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import current_user
from ..services import system, weather

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/codes", dependencies=[Depends(current_user)])
def codes(conn: sqlite3.Connection = Depends(get_db)):
    return system.codes(conn)


@router.get("/weather", dependencies=[Depends(current_user)])
def get_weather(region: str = "울산"):
    return weather.get_weather(region)
