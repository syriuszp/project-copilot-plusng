
import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from app.core.config_validator import ConfigValidator

logger = logging.getLogger(__name__)

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
    env = config_status["env"] 

    # --- 2. Determine Config Directory and Files ---
    if env_override_file:
        config_path = Path(env_override_file)
        config_dir = config_path.parent
        files_to_load = [config_path]
        config_status["config_path"] = str(config_path)
        config_status["source"] = "ENV_FILE (PROJECT_COPILOT_CONFIG_FILE)"
    elif env_override_dir:
        config_dir = Path(env_override_dir)
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]
        config_status["source"] = "ENV_DIR (PROJECT_COPILOT_CONFIG_DIR)"
    else:
        project_root = Path(__file__).parent.parent.parent
        config_dir = project_root / "config"
        files_to_load = [
            config_dir / "general.yaml",
            config_dir / f"{env.lower()}.yaml"
        ]
        config_status["source"] = "DEFAULT (repo/site-packages)"

    # --- 3. Load Configs ---
    loaded_config = {}
    files_found = 0
    
    try:
        for file_path in files_to_load:
            if file_path.exists():
                files_found += 1
                if not env_override_file:
                     config_status["config_path"] = str(file_path)

                with open(file_path, "r", encoding="utf-8") as f:
                    loaded_config.update(yaml.safe_load(f) or {})
        
        if files_found == 0:
            config_status["status"] = "ERROR"
            config_status["error"] = f"No config files found in {config_dir} (tried: {[str(f) for f in files_to_load]})"
        else:
            # --- 3b. Backward Compatibility (P0 Hardening) ---
            # Map top-level 'search_enabled' to 'features.search_enabled'
            # Prioritize existing features.search_enabled if present.
            
            if "search_enabled" in loaded_config:
                val = loaded_config.pop("search_enabled")
                if "features" not in loaded_config:
                    loaded_config["features"] = {}
                
                # Only map if not already defined in features
                if "search_enabled" not in loaded_config["features"]:
                     loaded_config["features"]["search_enabled"] = val
                     logger.warning("DEPRECATED: Top-level 'search_enabled' found. Mapped to 'features.search_enabled'.")
                else:
                     logger.info("Ignoring top-level 'search_enabled' because 'features.search_enabled' is set.")
        
            # Same for fts_enabled
            if "fts_enabled" in loaded_config:
                val = loaded_config.pop("fts_enabled")
                if "features" not in loaded_config:
                     loaded_config["features"] = {}
                if "fts_enabled" not in loaded_config["features"]:
                     loaded_config["features"]["fts_enabled"] = val

            # --- 3c. Validation (Hardening) ---
            validation_errors = ConfigValidator.validate(loaded_config)
            if validation_errors:
                config_status["status"] = "ERROR"
                config_status["error"] = "Invalid Configuration:\n" + "\n".join(validation_errors)
                # We still allow loading data for debugging config
                config_status["data"] = loaded_config
                return config_status

            config_status["data"] = loaded_config
            
            # --- 4. Resolve DB Path ---
            raw_db_path = None
            if "database" in loaded_config and "path" in loaded_config["database"]:
                 raw_db_path = loaded_config["database"]["path"]
            elif "paths" in loaded_config and "db_path" in loaded_config["paths"]:
                 raw_db_path = loaded_config["paths"]["db_path"]
            elif "db_path" in loaded_config: # Legacy support
                 raw_db_path = loaded_config["db_path"]
            
            if raw_db_path:
                db_path_obj = Path(raw_db_path)
                if not db_path_obj.is_absolute():
                    config_status["db_path"] = str(config_dir / raw_db_path)
                else:
                    config_status["db_path"] = str(db_path_obj)
            else:
                 config_status["db_path"] = None
            
            # Log startup config (DoD)
            features = loaded_config.get("features", {})
            logger.info(f"Config Loaded: search_enabled={features.get('search_enabled')}, fts_enabled={features.get('fts_enabled')}")

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
