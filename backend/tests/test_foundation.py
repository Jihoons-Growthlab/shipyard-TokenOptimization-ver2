from app.config import settings
from app.db import connect, load_seed, migrate


def count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_seed_counts_match_foundation(conn):
    expected = {
        "users": 6, "TB_MST_Hull": 5, "TB_MST_Block": 17, "TB_PRC_Plan": 83, "TB_PRC_PlanDep": 79,
        "TB_PRC_Progress": 60, "TB_DWG_Drawing": 47, "TB_DWG_Revision": 79, "TB_DWG_Approval": 72,
        "TB_DWG_PlanLink": 45,
    }
    assert {t: count(conn, t) for t in expected} == expected
    status = dict(conn.execute("SELECT PlanStatus, COUNT(*) FROM TB_PRC_Plan GROUP BY 1").fetchall())
    assert status == {"PLAN": 39, "WORK": 7, "DONE": 36, "DELAY": 1}


def test_seed_password_is_argon2id(conn):
    assert conn.execute("SELECT password_hash FROM users WHERE emp_no='admin'").fetchone()[0].startswith("$argon2id$")


def test_init_is_idempotent_and_keeps_changes(conn):
    conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo='8005'")
    migrate(conn)
    assert load_seed(conn) is False
    assert count(conn, "TB_MST_Hull") == 4
    versions = [r[0] for r in conn.execute("SELECT version FROM schema_migrations ORDER BY 1")]
    assert versions == ["0001_schema", "seed"]


def test_connection_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_fk_cascade_and_phone_index(conn):
    conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo='8001'")
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE HullNo='8001'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_DWG_Approval a LEFT JOIN TB_DWG_Revision r"
                        " USING (DrawingId, RevNo) WHERE r.RevNo IS NULL").fetchone()[0] == 0


def test_cli_init_db(tmp_path, monkeypatch, capsys):
    from app import cli

    path = tmp_path / "sub" / "cli.db"
    monkeypatch.setattr(settings, "db_path", path)
    monkeypatch.setattr("sys.argv", ["init-db", "--seed"])
    cli.main()
    cli.main()
    assert "skipped" in capsys.readouterr().out
    conn = connect(path)
    assert count(conn, "users") == 6
    conn.close()


def test_health_and_error_body(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    res = client.get("/api/nope")
    assert res.status_code == 404 and set(res.json()) == {"code", "message", "details"}


def test_invalid_format_body(client):
    res = client.post("/api/auth/login", json={"emp_no": "x"})
    assert res.status_code == 422
    assert res.json()["code"] == "INVALID_FORMAT"
    assert res.json()["message"] == "요청 형식이 올바르지 않습니다."
