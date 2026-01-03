
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

    project_root = Path(__file__).parent.parent.parent
    config_dir = project_root / "config"
    
    # Determine config file based on ENV
    env = config_status["env"]
    config_file = config_dir / f"{env.lower()}.yaml"
    general_file = config_dir / "general.yaml"

    # Default to general if env-specific doesn't exist, but usually we load general and override
    # For now, minimal implementation to satisfy requirements
    
    loaded_config = {}
    
    try:
        if general_file.exists():
             with open(general_file, "r", encoding="utf-8") as f:
                loaded_config.update(yaml.safe_load(f) or {})

        if config_file.exists():
            config_status["config_path"] = str(config_file)
            with open(config_file, "r", encoding="utf-8") as f:
                loaded_config.update(yaml.safe_load(f) or {})
        elif general_file.exists():
             config_status["config_path"] = str(general_file)
        else:
            config_status["status"] = "ERROR"
            config_status["error"] = f"No config file found in {config_dir}"

        config_status["data"] = loaded_config
        
        # Extract DB path if available (common pattern)
        # Assuming typical structure, adjust if needed based on actual yaml content
        if "database" in loaded_config and "path" in loaded_config["database"]:
             config_status["db_path"] = loaded_config["database"]["path"]
        elif "paths" in loaded_config and "db_path" in loaded_config["paths"]:
             config_status["db_path"] = loaded_config["paths"]["db_path"]
        elif "db_path" in loaded_config:
             config_status["db_path"] = loaded_config["db_path"]

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
