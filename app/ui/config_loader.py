
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

def load_config() -> Dict[str, Any]:
    """
    Loads configuration from YAML files and environment variables.
    Returns a dictionary with configuration and status metadata.
    """
    config_status = {
        "status": "OK",
        "error": None,
        "env": get_env(),
        "config_path": None,
        "db_path": None,
        "data": {}
    }

    # --- 1. Read Overrides from ENV ---
    env_override_file = os.environ.get("PROJECT_COPILOT_CONFIG_FILE")
    env_override_dir = os.environ.get("PROJECT_COPILOT_CONFIG_DIR")
    
    # Priority for ENV: ENV var > default detection
    # get_env() already respects PROJECT_COPILOT_ENV, so we just use it.
    env = config_status["env"] # This calls get_env() which checks PROJECT_COPILOT_ENV

    # --- 2. Determine Config Directory and Files ---
    if env_override_file:
        # CASE A: Explicit Config File
        config_path = Path(env_override_file)
        config_dir = config_path.parent
        files_to_load = [config_path]
        config_status["config_path"] = str(config_path)
    elif env_override_dir:
        # CASE B: Explicit Config Directory
        config_dir = Path(env_override_dir)
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]
    else:
        # CASE C: Default Repo Structure (site-packages or dev repo)
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config"
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]

    # --- 3. Load Configs ---
    loaded_config = {}
    files_found = 0
    
    try:
        for file_path in files_to_load:
            if file_path.exists():
                files_found += 1
                # Track the last successfully loaded specific file as the main "config_path"
                # (unless we are in single-file override mode, where it's already set)
                if not env_override_file:
                     # For dir mode, we might note specific env config as priority, or general if only general exists
                     config_status["config_path"] = str(file_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    loaded_config.update(yaml.safe_load(f) or {})
        
        if files_found == 0:
            config_status["status"] = "ERROR"
            config_status["error"] = f"No config files found in {config_dir} (tried: {[str(f) for f in files_to_load]})"
        else:
            config_status["data"] = loaded_config
            
            # --- 4. Resolve DB Path ---
            raw_db_path = None
            if "database" in loaded_config and "path" in loaded_config["database"]:
                 raw_db_path = loaded_config["database"]["path"]
            elif "paths" in loaded_config and "db_path" in loaded_config["paths"]:
                 raw_db_path = loaded_config["paths"]["db_path"]
            elif "db_path" in loaded_config:
                 raw_db_path = loaded_config["db_path"]
            
            if raw_db_path:
                # If relative, resolve against config_dir
                db_path_obj = Path(raw_db_path)
                if not db_path_obj.is_absolute():
                    config_status["db_path"] = str(config_dir / raw_db_path)
                else:
                    config_status["db_path"] = str(db_path_obj)
            else:
                 config_status["db_path"] = None

    except Exception as e:
        config_status["status"] = "ERROR"
        config_status["error"] = str(e)

    return config_status

def get_env() -> str:
    """
    Detects the current environment.
    Checks PROJECT_COPILOT_ENV, defaults to DEV.
    """
    return os.environ.get("PROJECT_COPILOT_ENV", "DEV").upper()
