import shutil

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.db import connect, load_seed, migrate
from app.main import app
from app.security import totp_code, totp_step
from app.services import auth


@pytest.fixture(scope="session")
def seeded_db(tmp_path_factory):
    path = tmp_path_factory.mktemp("seed") / "template.db"
    conn = connect(path)
    migrate(conn)
    load_seed(conn)
    conn.close()
    return path


@pytest.fixture
def db_path(seeded_db, tmp_path, monkeypatch):
    path = tmp_path / "test.db"
    shutil.copy(seeded_db, path)
    monkeypatch.setattr(settings, "db_path", path)
    auth.reset_otp_state()
    return path


@pytest.fixture
def conn(db_path):
    c = connect(db_path)
    yield c
    c.close()


@pytest.fixture
def client(db_path):
    return TestClient(app)


PASSWORDS = {"park.pm": "pm1234", "han.wk": "wk1234", "choi.qa": "qa1234", "jung.new": "new12345"}
TOTP_SECRET = "JBSWY3DPEHPK3PXP"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def login(client, emp_no, password=None):
    return client.post("/api/auth/login", json={"emp_no": emp_no, "password": password or PASSWORDS[emp_no]})


def session_headers(client, emp_no):
    """OTP 계정(admin, lee.dwg)은 2차 인증까지 거친 헤더를 돌려준다."""
    if emp_no in ("admin", "lee.dwg"):
        password = {"admin": "admin1234", "lee.dwg": "dwg1234"}[emp_no]
        otp = login(client, emp_no, password).json()["otp_token"]
        res = client.post(
            "/api/auth/otp/verify", json={"code": totp_code(TOTP_SECRET, totp_step())}, headers=bearer(otp)
        )
        auth.reset_otp_state()  # 픽스처가 같은 step을 다시 쓸 수 있게 한다
        return bearer(res.json()["access_token"])
    return bearer(login(client, emp_no).json()["access_token"])
