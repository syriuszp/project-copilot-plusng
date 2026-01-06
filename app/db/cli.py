from __future__ import annotations

import argparse
import os
import yaml
from pathlib import Path
from app.db.database import init_or_upgrade_db


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", help="Path to config YAML (dev or prod).")
    args = parser.parse_args()

    # Priority: Arg > Env > Default
    cfg_path_str = args.config or os.environ.get("PROJECT_COPILOT_CONFIG_FILE")
    
    if cfg_path_str:
         cfg_path = Path(cfg_path_str).resolve()
    else:
         cfg_path = Path(__file__).resolve().parents[2] / "config" / "general.yaml"

    if not cfg_path.exists():
        print(f"Error: Config file not found at {cfg_path}")
        return 1

    with open(cfg_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}

    res = init_or_upgrade_db(cfg)
    
    if res.status == "OK":
        print(f"OK: DB ready at {res.db_path}")
        return 0
    else:
        print(f"ERROR: DB Init failed: {res.error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
