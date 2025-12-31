from __future__ import annotations

import sqlite3
from pathlib import Path


def _parse_simple_yaml_paths(config_path: Path) -> dict:
    """
    Minimal YAML reader for our simple structure:
      paths:
        db_path: ...
    (No external dependencies.)
    """
    data: dict = {}
    current = None
    for raw in config_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not ":" in line[:-1]:
            current = line[:-1]
            data[current] = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip().strip("'").strip('"')
            if current and isinstance(data.get(current), dict):
                data[current][k] = v
            else:
                data[k] = v
    return data


def resolve_db_path(config_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    cfg = _parse_simple_yaml_paths(config_path)
    db_rel = cfg.get("paths", {}).get("db_path")
    if not db_rel:
        raise ValueError(f"Missing paths.db_path in config: {config_path}")
    return (repo_root / db_rel).resolve()


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


def _ensure_migrations_table(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )


def apply_migrations(con: sqlite3.Connection, migrations_dir: Path) -> None:
    _ensure_migrations_table(con)
    applied = {row["version"] for row in con.execute("SELECT version FROM schema_migrations").fetchall()}

    for sql_file in sorted(migrations_dir.glob("*.sql")):
        version = sql_file.stem  # e.g. "001_initial"
        if version in applied:
            continue
        con.executescript(sql_file.read_text(encoding="utf-8"))
        con.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        con.commit()


def init_or_upgrade_db(config_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    migrations_dir = repo_root / "db" / "migrations"
    db_path = resolve_db_path(config_path)

    con = connect(db_path)
    try:
        apply_migrations(con, migrations_dir)
    finally:
        con.close()

    return db_path


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parents[2]
    config_path = repo_root / "config" / "dev.yaml"
    dbp = init_or_upgrade_db(config_path)
    print(f"OK: DB ready at {dbp}")
