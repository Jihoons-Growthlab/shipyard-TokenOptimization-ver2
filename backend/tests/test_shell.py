import pytest
from fastapi import Depends

from app.deps import require
from app.main import app
from app.services import weather
from app.config import settings
from conftest import session_headers


def menu(client, emp_no):
    return client.get("/api/me/menu", headers=session_headers(client, emp_no)).json()


def test_menu_shape_for_viewer(client):
    items = {m["menu_id"]: m for m in menu(client, "choi.qa")}
    assert "M91" not in items and "M90" not in items
    assert items["M11"] == {
        "menu_id": "M11", "parent_id": "M10", "title": "호선 목록", "token": "hull-list", "seq": 3,
        "level": 1, "auth_gbn": "View", "can_write": False,
    }


@pytest.mark.parametrize("emp_no,expected", [
    ("admin", {"M00", "M10", "M11", "M20", "M21", "M22", "M30", "M31", "M33", "M90", "M91"}),
    ("park.pm", {"M00", "M10", "M11", "M20", "M21", "M22", "M30", "M31"}),
    ("lee.dwg", {"M00", "M10", "M11", "M20", "M21", "M30", "M31", "M33"}),
])
def test_t01_menu_follows_br09(client, emp_no, expected):
    assert {m["menu_id"] for m in menu(client, emp_no)} == expected


def test_br09_can_write(client):
    writes = {m["menu_id"] for m in menu(client, "park.pm") if m["can_write"]}
    assert writes == {"M10", "M11", "M20", "M21", "M22"}
    assert all(m["can_write"] and m["level"] == 3 for m in menu(client, "admin"))


def test_child_hidden_when_parent_not_visible_or_disabled(client, conn):
    conn.execute("DELETE FROM TB_SYS_AuthMenu WHERE MenuId='M20' AND AuthCd='VIEW'")
    assert not {"M21", "M22"} & {m["menu_id"] for m in menu(client, "choi.qa")}
    conn.execute("UPDATE TB_SYS_MenuInfo SET UseYN=0 WHERE MenuId='M31'")
    assert "M31" not in {m["menu_id"] for m in menu(client, "choi.qa")}


def test_t01_menu_access_logged_and_forbidden(client, conn):
    headers = session_headers(client, "choi.qa")
    assert client.post("/api/me/menu-access", json={"menu_id": "M11"}, headers=headers).status_code == 204
    row = conn.execute("SELECT MenuId, LogId FROM TB_SYS_LogMenuAccess").fetchone()
    assert row["MenuId"] == "M11" and row["LogId"]
    res = client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=headers)
    assert res.status_code == 403
    assert res.json()["code"] == "FORBIDDEN" and res.json()["details"] == {"menu_id": "M91"}


def test_require_dependency_levels_and_live_permissions(client, conn):
    if not any(getattr(r, "path", "") == "/api/test-write" for r in app.routes):
        app.get("/api/test-write", dependencies=[Depends(require("M11", 2))])(lambda: {"ok": True})
    headers = session_headers(client, "park.pm")
    assert client.get("/api/test-write", headers=headers).status_code == 200
    conn.execute("UPDATE TB_SYS_AuthMenu SET AuthGbn='View' WHERE MenuId='M11' AND AuthCd='PROC'")
    res = client.get("/api/test-write", headers=headers)
    assert res.status_code == 403 and res.json()["details"]["menu_id"] == "M11"
    assert client.get("/api/test-write", headers=session_headers(client, "admin")).status_code == 200


def test_highest_level_of_multiple_groups(client, conn):
    conn.execute("INSERT INTO TB_SYS_AuthUser VALUES ('VIEW', 'park.pm')")
    assert next(m for m in menu(client, "park.pm") if m["menu_id"] == "M11")["can_write"] is True


def test_codes_require_login_and_group(client):
    assert client.get("/api/codes").status_code == 401
    codes = client.get("/api/codes", headers=session_headers(client, "choi.qa")).json()
    assert codes["SHIPTYPE"][0] == {"code": "LNG", "name": "LNG운반선"}
    assert len(codes) == 7


@pytest.mark.parametrize("region,temp,condition,humidity,wind", [
    ("울산", 17.6, "맑음", 52, 3.2), ("거제", 18.9, "구름조금", 61, 4.1), ("목포", 16.2, "흐림", 70, 5.0),
])
def test_weather_t01_samples(client, region, temp, condition, humidity, wind):
    res = client.get("/api/weather", params={"region": region}, headers=session_headers(client, "choi.qa")).json()
    assert (res["region"], res["source"], res["tempC"], res["condition"], res["humidity"], res["windMs"]) == (
        region, "SAMPLE", temp, condition, humidity, wind)
    assert res["error"]


def test_weather_requires_login_and_known_region(client):
    assert client.get("/api/weather").status_code == 401
    res = client.get("/api/weather", params={"region": "부산"}, headers=session_headers(client, "choi.qa"))
    assert res.status_code == 400 and res.json()["details"]["field"] == "region"


@pytest.mark.parametrize("provider", [
    lambda region: 1 / 0,
    lambda region: {"tempC": "not-a-number"},
    lambda region: {"obsDt": "x", "tempC": None, "condition": "맑음", "humidity": 1, "windMs": 1},
])
def test_weather_t02_failure_falls_back_to_sample(client, monkeypatch, provider):
    monkeypatch.setattr(settings, "weather_provider", "fake")
    monkeypatch.setitem(weather.PROVIDERS, "fake", provider)
    res = client.get("/api/weather", headers=session_headers(client, "choi.qa")).json()
    assert res["source"] == "SAMPLE" and res["error"]


def test_weather_unknown_provider_is_sample(client, monkeypatch):
    monkeypatch.setattr(settings, "weather_provider", "ghost")
    res = client.get("/api/weather", headers=session_headers(client, "choi.qa")).json()
    assert res["source"] == "SAMPLE" and "ghost" in res["error"]


def test_weather_live_only_on_provider_success(client, monkeypatch):
    monkeypatch.setattr(settings, "weather_provider", "fake")
    monkeypatch.setitem(weather.PROVIDERS, "fake", lambda region: {
        "obsDt": "2026-10-19 09:00", "tempC": 10, "condition": "비", "humidity": 90, "windMs": 2})
    res = client.get("/api/weather", headers=session_headers(client, "choi.qa")).json()
    assert res["source"] == "LIVE" and res["tempC"] == 10 and res["error"] is None
