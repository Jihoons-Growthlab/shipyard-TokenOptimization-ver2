import argparse

from .config import settings
from .db import connect, load_seed, migrate


def main() -> None:
    parser = argparse.ArgumentParser(prog="init-db", description="마이그레이션을 적용하고 시드를 적재한다.")
    parser.add_argument("--seed", action="store_true")
    args = parser.parse_args()
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        migrate(conn)
        seeded = args.seed and load_seed(conn)
    finally:
        conn.close()
    print(f"{settings.db_path}: migrated, seed {'loaded' if seeded else 'skipped'}")


if __name__ == "__main__":
    main()
