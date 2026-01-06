
import os
from pathlib import Path
from app.ui.config_loader import load_config

def test_config_res():
    # Simulate ENV
    os.environ["PROJECT_COPILOT_CONFIG_FILE"] = "config/dev.yaml"
    
    config = load_config()
    db_path = config.get("db_path")
    
    print(f"Resolved DB Path: {db_path}")
    print(f"Exists? {os.path.exists(db_path) if db_path else False}")
    
    expected = Path("dev_data/db/project_copilot.dev.db").resolve()
    print(f"Expected (Relative to Root): {expected}")
    
    if str(expected) != str(Path(db_path).resolve()):
        print("MISMATCH DETECTED!")
        print(f"Got: {Path(db_path).resolve()}")
        print(f"Exp: {expected}")
        exit(1)
    else:
        print("MATCH - Fix Verified.")
        exit(0)

if __name__ == "__main__":
    test_config_res()
