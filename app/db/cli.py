from __future__ import annotations

import argparse
from pathlib import Path
from app.db.database import init_or_upgrade_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, help="Path to config YAML (dev or prod).")
    args = parser.parse_args()

    cfg = Path(args.config).resolve()
    db_path = init_or_upgrade_db(cfg)
    print(f"OK: DB ready at {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
