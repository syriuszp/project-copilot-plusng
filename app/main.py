from __future__ import annotations

import os
from pathlib import Path
from datetime import datetime


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    now = datetime.now().isoformat(timespec="seconds")

    print("Project Copilot – Plus NG :: runtime check")
    print(f"timestamp: {now}")
    print(f"repo_root: {repo_root}")
    print(f"cwd:       {Path.cwd()}")
    print(f"python:    {os.sys.version.split()[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
