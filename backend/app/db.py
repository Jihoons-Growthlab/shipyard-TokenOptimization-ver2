import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import ROOT, settings
from .security import hash_password

MIGRATIONS = ROOT / "database" / "migrations"
SEED = ROOT / "reference" / "seed" / "seed.json"


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    # 요청 의존성이 스레드풀의 다른 스레드에서 닫을 수 있다.
    conn = sqlite3.connect(path or settings.db_path, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


@contextmanager
def tx(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    for file in sorted(MIGRATIONS.glob("*.sql")):
        if file.stem in done:
            continue
        try:
            # executescript는 열린 트랜잭션을 먼저 커밋하므로 스크립트 안에서 묶는다.
            conn.executescript(
                f"BEGIN IMMEDIATE;\n{file.read_text('utf-8')}\n"
                f"INSERT INTO schema_migrations(version) VALUES ('{file.stem}');\nCOMMIT;"
            )
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise


def load_seed(conn: sqlite3.Connection) -> bool:
    """시드를 한 번만 적재한다. 이후 실행이 사용자 변경·삭제를 되돌리지 않도록 표식을 남긴다."""
    if conn.execute("SELECT 1 FROM schema_migrations WHERE version = 'seed'").fetchone():
        return False
    data = json.loads(SEED.read_text("utf-8"))
    with tx(conn):
        conn.execute("PRAGMA defer_foreign_keys=ON")
        for table, content in data.items():
            columns, rows = content["columns"], content["rows"]
            if table == "users":
                at = columns.index("demo_password")
                columns = [*columns[:at], "password_hash", *columns[at + 1:]]
                rows = [[*r[:at], hash_password(r[at]), *r[at + 1:]] for r in rows]
            names = ", ".join(columns)
            marks = ", ".join("?" * len(columns))
            conn.executemany(f"INSERT OR IGNORE INTO {table} ({names}) VALUES ({marks})", rows)
        conn.execute("INSERT INTO schema_migrations(version) VALUES ('seed')")
    return True
